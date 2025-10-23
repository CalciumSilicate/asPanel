# services/stats_service.py
# 统计入库与查询封装（不依赖 storages 包直接调用）：
# - 读取各服务器 <server_path>/server/world/stats 目录
# - 内置稀疏入库（10min 对齐 + 12h 快照）与查询逻辑
# - 支持通过 config 中的 STATS_WHITELIST_ON / STATS_WHITELIST / STATS_IGNORE 过滤指标
# - 查询支持 delta/total 两种时间序列

from __future__ import annotations

import asyncio
import fnmatch
import json
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

from backend.core.constants import STATS_WHITELIST_ON, STATS_WHITELIST, STATS_IGNORE, get_tzinfo
from backend.database import SessionLocal
from backend import crud, models
from backend.logger import logger
from backend.dependencies import mcdr_manager

# 统计专用 SQLite（独立于 asPanel.db）
from sqlalchemy import select, func
from sqlalchemy.orm import Session

# 默认命名空间（Minecraft 官方 stats）
DEFAULT_NAMESPACE = "minecraft"


# 使用主库 asPanel.db 的 ORM（models.py 定义）进行统计存取


# ---------- 指标发现与过滤 ----------

def _stat_json_to_metric_names(js: dict, *, namespace: str = DEFAULT_NAMESPACE) -> Set[str]:
    """从单个玩家 JSON stats 构建可用指标名集合（形如 'custom.play_one_minute'）。"""
    metrics: Set[str] = set()
    stats = js.get("stats", {}) or {}
    for cat_ns, items in stats.items():
        # cat_ns 形如 'minecraft:custom'
        try:
            ns, cat = cat_ns.split(":", 1)
        except ValueError:
            # 非预期键，跳过
            continue
        if ns != namespace:
            # 仅提取目标命名空间
            continue
        if not isinstance(items, dict):
            continue
        for item_ns, _val in items.items():
            try:
                ns2, item = item_ns.split(":", 1)
            except ValueError:
                continue
            if ns2 != namespace:
                continue
            metrics.add(f"{cat}.{item}")
    return metrics


def _list_metrics_in_stats_dir(stats_dir: Path, *, sample_files: int = 16) -> Set[str]:
    """扫描 stats 目录（最多 sample_files 个样本）聚合所有出现过的指标名。"""
    out: Set[str] = set()
    if not stats_dir.is_dir():
        return out
    files = [p for p in stats_dir.glob("*.json")][:sample_files]
    for fp in files:
        try:
            js = json.loads(fp.read_text(encoding="utf-8"))
            out |= _stat_json_to_metric_names(js)
        except Exception:
            continue
    return out


def _fmt_full_key(metric: str, *, namespace: str = DEFAULT_NAMESPACE) -> str:
    """将 'custom.play_one_minute' 转为 'minecraft:custom.minecraft:play_one_minute' 便于与配置匹配。"""
    cat, item = metric.split(".", 1)
    return f"{namespace}:{cat}.{namespace}:{item}"


def _filter_metrics(all_metrics: Iterable[str], *, namespace: str = DEFAULT_NAMESPACE) -> List[str]:
    """按配置过滤指标集合。支持通配符：如 '*.minecraft:stone' 或 'minecraft:used.minecraft:*_pickaxe'。

    - STATS_WHITELIST_ON 为真：先按白名单匹配，再应用忽略列表剔除
    - 否则：在全部集合上应用忽略列表剔除

    参数 all_metrics 为 'cat.item' 形式的集合；namespace 用于拼接完整键参与匹配。
    """
    metrics = set(all_metrics)
    if STATS_WHITELIST_ON:
        allowed = set()
        for m in metrics:
            full = _fmt_full_key(m, namespace=namespace)
            if any(fnmatch.fnmatch(full, pat) for pat in STATS_WHITELIST):
                allowed.add(m)
        metrics = allowed

    # 忽略项
    filtered = set()
    for m in metrics:
        full = _fmt_full_key(m, namespace=namespace)
        if any(fnmatch.fnmatch(full, pat) for pat in STATS_IGNORE):
            continue
        filtered.add(m)

    return sorted(filtered)


# ---------- 服务器枚举与入库 ----------

def _server_stats_dir(server_path: str | Path) -> Path:
    """根据约定 <server_path>/server/world/stats 返回目录路径。"""
    base = Path(server_path)
    return base / "server" / "world" / "stats"


def discover_metrics_from_all_servers() -> List[str]:
    """从所有服务器的 stats 目录中发现可用指标并应用过滤。"""
    db = SessionLocal()
    try:
        servers = crud.get_all_servers(db)
    finally:
        db.close()

    all_metrics: Set[str] = set()
    for srv in servers:
        stats_dir = _server_stats_dir(srv.path)
        all_metrics |= _list_metrics_in_stats_dir(stats_dir)

    metrics = _filter_metrics(all_metrics, namespace=DEFAULT_NAMESPACE)
    if not metrics:
        # 回退至少包含游玩时长（历史兼容）
        metrics = ["custom.play_one_minute"]
    return metrics


def ingest_once_for_server(server_id: int, stats_dir: Path, metrics: List[str], *, namespace: str = DEFAULT_NAMESPACE) -> int:
    """对单个服务器执行一次入库（使用主库 models 定义），包含：
    - 跳过未修改的 JSON（基于 JsonDim.last_read_time 与文件 mtime）
    - 缓存 JSON 解析结果，避免重复读取
    - 批量查询上次 total，减少 N×M 次查询
    """
    if not stats_dir.is_dir():
        return

    # 计算对齐 ts
    import time
    now = int(time.time())
    step = 600
    ts = now - (now % step)

    files = sorted(stats_dir.glob("*.json"))
    if not files:
        return

    db = SessionLocal()
    rows_written_total = 0
    try:
        # 预取 json_dim map
        json_dim_map = crud.get_json_dim_map_for_server(db, server_id)

        # 预构建 metric_id 映射（减少循环内查询）
        metric_id_map: dict[str, int] = {}
        for metric in metrics:
            cat, item = metric.split(".", 1)
            cat_key = f"{namespace}:{cat}"
            item_key = f"{namespace}:{item}"
            m_id = db.scalar(
                select(models.MetricsDim.metric_id)
                .where(models.MetricsDim.category == cat_key, models.MetricsDim.item == item_key)
            )
            if m_id is None:
                obj = models.MetricsDim(category=cat_key, item=item_key)
                db.add(obj)
                db.flush()
                m_id = obj.metric_id
            metric_id_map[metric] = int(m_id)

        def _ensure_player_id(player_uuid: str) -> int:
            pid = db.scalar(select(models.Player.id).where(models.Player.uuid == player_uuid))
            if pid is not None:
                return int(pid)
            obj = models.Player(uuid=player_uuid, player_name=None, play_time="{}", is_offline=True)
            db.add(obj)
            db.flush()
            return int(obj.id)

        def _read_metric_from_json(js: dict, metric: str) -> int:
            category, item = metric.split(".", 1)
            cat_key = f"{namespace}:{category}"
            item_key = f"{namespace}:{item}"
            stats = js.get("stats", {}) or {}
            return int((stats.get(cat_key, {}) or {}).get(item_key, 0) or 0)

        def _compute_delta(prev_total: Optional[int], curr_total: int) -> Tuple[int, int]:
            if prev_total is None:
                return 0, 1
            return int(curr_total - prev_total), 0

        for fp in files:
            fn = fp.name
            mtime = int(fp.stat().st_mtime)
            last_read = json_dim_map.get(fn)
            # 若文件未变化（mtime <= last_read_time），跳过
            if last_read is not None and mtime <= int(last_read or 0):
                continue

            # 读取并解析 JSON（一次）
            try:
                js = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                # 无法解析：仍然记录 last_read_time，避免频繁重试
                crud.upsert_json_dim_last_read(db, server_id, fn, now)
                continue

            player_uuid = fp.stem
            pid = _ensure_player_id(player_uuid)

            metric_ids = [metric_id_map[m] for m in metrics]
            if not metric_ids:
                crud.upsert_json_dim_last_read(db, server_id, fn, now)
                continue

            # 批量获取上一时刻 total（ts<=ts-1），每个 metric_id 只取最新一条
            sub = (
                select(
                    models.PlayerMetrics.metric_id,
                    func.max(models.PlayerMetrics.ts).label("mts")
                )
                .where(
                    models.PlayerMetrics.server_id == server_id,
                    models.PlayerMetrics.player_id == pid,
                    models.PlayerMetrics.metric_id.in_(metric_ids),
                    models.PlayerMetrics.ts <= ts - 1,
                )
                .group_by(models.PlayerMetrics.metric_id)
                .subquery()
            )
            prev_rows = db.execute(
                select(models.PlayerMetrics.metric_id, models.PlayerMetrics.total)
                .join(
                    sub,
                    (models.PlayerMetrics.metric_id == sub.c.metric_id)
                    & (models.PlayerMetrics.ts == sub.c.mts)
                )
                .where(
                    models.PlayerMetrics.server_id == server_id,
                    models.PlayerMetrics.player_id == pid,
                )
            ).all()
            prev_map = {int(mid): int(t or 0) for (mid, t) in prev_rows}

            # 计算并写入变更（合并 upsert 行为）
            to_add: list[models.PlayerMetrics] = []
            updated_count = 0
            for metric in metrics:
                mid = metric_id_map[metric]
                curr_total = _read_metric_from_json(js, metric)
                prev_total = prev_map.get(mid)
                delta, new = _compute_delta(prev_total, curr_total)
                if delta == 0 and not new:
                    continue
                if curr_total == 0 and new:
                    continue
                # 查找是否已存在同(ts, server, player, metric)记录
                existing = db.execute(
                    select(models.PlayerMetrics)
                    .where(
                        models.PlayerMetrics.server_id == server_id,
                        models.PlayerMetrics.player_id == pid,
                        models.PlayerMetrics.metric_id == mid,
                        models.PlayerMetrics.ts == ts,
                    )
                ).scalar_one_or_none()
                if existing is None:
                    to_add.append(models.PlayerMetrics(
                        ts=ts, server_id=server_id, player_id=pid, metric_id=mid,
                        total=int(curr_total), delta=int(delta)
                    ))
                else:
                    existing.total = int(curr_total)
                    existing.delta = int(delta)
                    db.add(existing)
                    updated_count += 1

            if to_add:
                db.add_all(to_add)
            # 更新 json_dim 的 last_read_time（读取时间点）
            crud.upsert_json_dim_last_read(db, server_id, fn, now)

            rows_written_total += updated_count + len(to_add)

        db.commit()
        logger.debug(f"服务器 {server_id} 入库完成 stats_dir={stats_dir} | rows_written={rows_written_total}")
        return rows_written_total
    finally:
        db.close()


def ingest_all_servers_now() -> Tuple[int, List[str]]:
    """立即对所有服务器执行一次入库。
    返回 (服务器数量, 使用的指标列表)
    """
    metrics = discover_metrics_from_all_servers()

    db = SessionLocal()
    try:
        servers = crud.get_all_servers(db)
        cfg = crud.get_system_settings_data(db)
        ignore_ids = list(map(int, (cfg or {}).get('stats_ignore_server', []) or []))
    finally:
        db.close()

    count = 0
    for srv in servers:
        if srv.id in ignore_ids:
            continue
        stats_dir = _server_stats_dir(srv.path)
        ingest_once_for_server(srv.id, stats_dir, metrics)
        count += 1
    return count, metrics


# ---------- 定时任务 ----------

async def _sleep_until_next_10min_boundary():
    """计算距离下一个 10 分钟整点的秒数并睡眠。"""
    import time
    now = int(time.time())
    step = 600
    remain = step - (now % step)
    await asyncio.sleep(remain)


async def ingest_scheduler_loop():
    """后台循环：每逢 10 分钟整点触发一次入库，并在运行中服务器执行 save-all。"""
    # 启动先对齐一次
    await _sleep_until_next_10min_boundary()
    while True:
        try:
            # 发现指标集合（全局）
            metrics = discover_metrics_from_all_servers()
            # 忽略服务器列表
            ignore_ids: list[int] = []
            try:
                with SessionLocal() as db:
                    cfg = crud.get_system_settings_data(db)
                    ignore_ids = list(map(int, (cfg or {}).get('stats_ignore_server', []) or []))
            except Exception:
                ignore_ids = []

            # 遍历服务器
            with SessionLocal() as db:
                servers = crud.get_all_servers(db)
            processed = 0
            inserted_rows_total = 0
            ignored = 0
            for srv in servers:
                stats_dir = _server_stats_dir(srv.path)
                if srv.id in ignore_ids or not stats_dir.exists():
                    ignored += 1
                    logger.debug(f"ignored {stats_dir}")
                    continue
                # 若服务器在运行，先 save-all
                try:
                    proc = mcdr_manager.processes.get(srv.id)
                    if proc and proc.returncode is None:
                        logger.debug(f"服务器运行中，试发送命令save-all server_id={srv.id}")
                        await mcdr_manager.send_command(srv, 'save-all')
                        await asyncio.sleep(1.0)
                except Exception:
                    pass
                # 入库放到线程池中，避免阻塞事件循环
                inserted = await asyncio.to_thread(ingest_once_for_server, srv.id, stats_dir, metrics)
                inserted_rows_total += int(inserted or 0)
                processed += 1
            logger.info(f"统计入库完成 | 服务器数={processed} | 指标数={len(metrics)} | ignored={ignored} | rows_written={inserted_rows_total}")
        except Exception as e:
            logger.opt(exception=e).error("统计入库循环发生异常")
        finally:
            # 下一轮继续对齐 10min
            await _sleep_until_next_10min_boundary()


# ---------- 查询封装（供路由调用） ----------

def _normalize_metric(metric: str) -> str:
    """允许用户传入 'minecraft:custom.minecraft:deaths' 或 'custom.deaths'，统一为后者。"""
    if ":" in metric:
        # 形如 'minecraft:custom.minecraft:deaths'
        try:
            left, right = metric.split(".", 1)
            _ns1, cat = left.split(":", 1)
            _ns2, item = right.split(":", 1)
            return f"{cat}.{item}"
        except Exception:
            return metric
    return metric


_GRANULARITY_SECONDS = {
    "10min": 600,
    "20min": 1200,
    "30min": 1800,
    "1h": 3600,
    "6h": 21600,
    "12h": 43200,
    "24h": 86400,
    "1week": 604800,
    "1month": 2629800,   # 约 30.44 天
    "3month": 7889400,   # 约 91.31 天
    "6month": 15778800,  # 约 182.62 天
    "1year": 31557600,   # 约 365.25 天
}


def _parse_iso(ts_str: Optional[str]) -> Optional[int]:
    if ts_str is None:
        return None
    import datetime as dt
    return int(dt.datetime.fromisoformat(ts_str).timestamp())


def _align_floor(ts: int, step: int) -> int:
    return ts - (ts % step)


from typing import Dict
from datetime import datetime, timedelta

# 支持的粒度（统一由日历对齐器处理）
SUPPORTED_GRANULARITIES = {
    "10min", "20min", "30min",
    "1h", "6h", "12h", "24h",
    "1week", "1month", "3month", "6month", "1year"
}


def _normalize_metrics(metrics: List[str], namespace: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for m in metrics:
        nm = _normalize_metric(m)
        cat, item = nm.split(".", 1)
        out.append((f"{namespace}:{cat}", f"{namespace}:{item}"))
    return out


def _resolve_metric_ids(db: Session, pairs: List[Tuple[str, str]]) -> List[int]:
    ids: List[int] = []
    for cat_key, item_key in pairs:
        m_id = db.scalar(
            select(models.MetricsDim.metric_id)
            .where(models.MetricsDim.category == cat_key, models.MetricsDim.item == item_key)
        )
        if m_id is not None:
            ids.append(int(m_id))
    return ids


def list_metrics(db: Session, q: Optional[str] = None, limit: int = 50,
                 namespace: str = DEFAULT_NAMESPACE) -> List[str]:
    """列出已存在的指标（归一为 'cat.item' 形式），支持按关键字模糊过滤；
    并依据 STATS_WHITELIST_ON/WHITELIST/IGNORE 约束输出。
    """
    # 简单 LIKE 过滤，尽量利用索引；否则回退到 Python 过滤
    like = None
    if q:
        like = f"%{q}%"
    stmt = select(models.MetricsDim.category, models.MetricsDim.item)
    if like:
        stmt = stmt.where(
            (models.MetricsDim.category.ilike(like)) | (models.MetricsDim.item.ilike(like))
        )
    stmt = stmt.limit(max(1, int(limit)))
    rows = db.execute(stmt).all()
    out: List[str] = []
    for cat_key, item_key in rows:
        try:
            ns1, cat = str(cat_key).split(":", 1)
            ns2, item = str(item_key).split(":", 1)
            if ns1 == namespace and ns2 == namespace:
                out.append(f"{cat}.{item}")
        except Exception:
            continue
    # 去重保持顺序
    seen = set()
    uniq = []
    for m in out:
        if m not in seen:
            seen.add(m)
            uniq.append(m)
    # 应用白名单/忽略过滤输出
    return _filter_metrics(uniq, namespace=namespace)


def _align_down_calendar(ts: int, granularity: str, tz) -> int:
    dt = datetime.fromtimestamp(ts, tz)
    if granularity == "10min":
        minute = (dt.minute // 10) * 10
        aligned = dt.replace(minute=minute, second=0, microsecond=0)
        return int(aligned.timestamp())
    if granularity == "20min":
        minute = (dt.minute // 20) * 20
        aligned = dt.replace(minute=minute, second=0, microsecond=0)
        return int(aligned.timestamp())
    if granularity == "30min":
        minute = 0 if dt.minute < 30 else 30
        aligned = dt.replace(minute=minute, second=0, microsecond=0)
        return int(aligned.timestamp())
    if granularity == "1h":
        aligned = dt.replace(minute=0, second=0, microsecond=0)
        return int(aligned.timestamp())
    if granularity == "6h":
        hour = (dt.hour // 6) * 6
        aligned = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
        return int(aligned.timestamp())
    if granularity == "12h":
        hour = 0 if dt.hour < 12 else 12
        aligned = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
        return int(aligned.timestamp())
    if granularity == "24h":
        aligned = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(aligned.timestamp())
    if granularity == "1week":
        weekday = dt.weekday()  # 0..6 (Mon..Sun)
        days_to_sunday = (weekday + 1) % 7
        start = (dt - timedelta(days=days_to_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp())
    if granularity == "1month":
        start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp())
    if granularity == "3month":
        # 以季度为边界：1/4/7/10 月
        q_start_month = 1
        if dt.month >= 10:
            q_start_month = 10
        elif dt.month >= 7:
            q_start_month = 7
        elif dt.month >= 4:
            q_start_month = 4
        start = dt.replace(month=q_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp())
    if granularity == "6month":
        month = 1 if dt.month <= 6 else 7
        start = dt.replace(month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp())
    if granularity == "1year":
        start = dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp())
    raise ValueError(f"不支持的粒度: {granularity}")


def _next_boundary(ts: int, granularity: str, tz) -> int:
    dt = datetime.fromtimestamp(ts, tz)
    if granularity == "10min":
        minute = (dt.minute // 10) * 10
        base = dt.replace(minute=minute, second=0, microsecond=0)
        nxt = base + timedelta(minutes=10)
        return int(nxt.timestamp())
    if granularity == "20min":
        minute = (dt.minute // 20) * 20
        base = dt.replace(minute=minute, second=0, microsecond=0)
        nxt = base + timedelta(minutes=20)
        return int(nxt.timestamp())
    if granularity == "30min":
        minute = 0 if dt.minute < 30 else 30
        base = dt.replace(minute=minute, second=0, microsecond=0)
        nxt = base + timedelta(minutes=30)
        return int(nxt.timestamp())
    if granularity == "1h":
        nxt = dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return int(nxt.timestamp())
    if granularity == "6h":
        hour = (dt.hour // 6) * 6
        base = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
        nxt = base + timedelta(hours=6)
        return int(nxt.timestamp())
    if granularity == "12h":
        hour = 0 if dt.hour < 12 else 12
        base = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
        nxt = base + timedelta(hours=12)
        return int(nxt.timestamp())
    if granularity == "24h":
        base = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        nxt = base + timedelta(days=1)
        return int(nxt.timestamp())
    if granularity == "1week":
        weekday = dt.weekday()
        days_to_sunday = (weekday + 1) % 7
        start = (dt - timedelta(days=days_to_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)
        nxt = start + timedelta(days=7)
        return int(nxt.timestamp())
    if granularity == "1month":
        year = dt.year + (1 if dt.month == 12 else 0)
        month = 1 if dt.month == 12 else dt.month + 1
        nxt = dt.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
        return int(nxt.timestamp())
    if granularity == "3month":
        # 1->4->7->10->(next year 1)
        if dt.month <= 3:
            nxt = dt.replace(month=4, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif dt.month <= 6:
            nxt = dt.replace(month=7, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif dt.month <= 9:
            nxt = dt.replace(month=10, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            nxt = dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return int(nxt.timestamp())
    if granularity == "6month":
        if dt.month <= 6:
            nxt = dt.replace(month=7, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            nxt = dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return int(nxt.timestamp())
    if granularity == "1year":
        nxt = dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return int(nxt.timestamp())
    raise ValueError(f"不支持的粒度: {granularity}")


def _align_up_calendar(ts: int, granularity: str, tz) -> int:
    """将时间向后对齐到下一个粒度边界（若已在边界上则返回自身）。

    规则：
    - 30min → 小时内的 :00 或 :30；非边界则取下一个边界
    - 1h    → 整点
    - 12h   → 0 点或 12 点
    - 24h   → 当日 00:00:00
    - 1week → 周起始（按 _align_down_calendar 的周起始定义）
    - 1month→ 月初 00:00:00
    - 6month→ 半年起始（1 月或 7 月 1 日）
    - 1year → 当年 1 月 1 日 00:00:00
    """
    down = _align_down_calendar(ts, granularity, tz)
    if down == ts:
        return ts
    return _next_boundary(down, granularity, tz)


def _build_boundaries_for_player(db: Session, *, player_id: int, metric_ids: List[int], granularity: str,
                                 start_ts: Optional[int], end_ts: Optional[int], server_ids: Optional[List[int]] = None) -> Tuple[List[int], Dict[int, int], int, int]:
    """构建边界并拉取该玩家在所选指标/服务器上的 delta 聚合。

    返回 (boundaries, delta_by_ts, start_anchor, end_boundary)
    语义：边界序列表示连续的右端点，窗口均为 (prev, cur]，用于统一 (start, end]。
    """
    tz = get_tzinfo()

    # 统一对齐结束边界；若 end 缺省，取当前时间并向后对齐
    import time as _t
    base_end = int(end_ts if end_ts is not None else _t.time())
    effective_end_ts = _align_up_calendar(base_end, granularity, tz)

    # 计算数据集中最早记录时间（不依赖 delta 是否存在，避免因无 delta 导致边界过晚）
    min_q = select(func.min(models.PlayerMetrics.ts)).where(
        models.PlayerMetrics.player_id == player_id,
        models.PlayerMetrics.metric_id.in_(metric_ids),
    )
    if server_ids:
        min_q = min_q.where(models.PlayerMetrics.server_id.in_(server_ids))
    if effective_end_ts is not None:
        min_q = min_q.where(models.PlayerMetrics.ts <= effective_end_ts)
    min_ts_all = db.scalar(min_q)

    # 聚合各 ts 的 delta（跨 server 与 metric 求和）
    q = select(models.PlayerMetrics.ts, func.sum(models.PlayerMetrics.delta)).where(
        models.PlayerMetrics.player_id == player_id,
        models.PlayerMetrics.metric_id.in_(metric_ids),
    )
    if server_ids:
        q = q.where(models.PlayerMetrics.server_id.in_(server_ids))
    # 统一 (start, end]：大于 start，小于等于 end
    if start_ts is not None:
        q = q.where(models.PlayerMetrics.ts > start_ts)
    if effective_end_ts is not None:
        q = q.where(models.PlayerMetrics.ts <= effective_end_ts)
    rows = db.execute(q.group_by(models.PlayerMetrics.ts).order_by(models.PlayerMetrics.ts.asc())).all()
    # 构建 delta_by_ts 映射
    delta_by_ts: Dict[int, int] = {int(ts): int(total or 0) for ts, total in rows}

    # 选择序列起点：若提供 start，则以 start 为基准；否则以数据集中或全局最早记录为基准
    if min_ts_all is None and not rows:
        # 完全无数据
        return [], {}, 0, 0
    first_ts = int(min_ts_all) if min_ts_all is not None else int(min(delta_by_ts.keys()))
    # 若未提供 start，则将起点微调到 first_ts 之前，确保 first_ts 归入首个桶 (prev, first_boundary]
    base_start = int(start_ts if start_ts is not None else (first_ts - 1))
    start_anchor = _align_down_calendar(base_start, granularity, tz)
    end_boundary = int(effective_end_ts)
    # 生成边界：从 start_anchor 之后的第一个边界开始，到 end_boundary（含）
    boundaries: List[int] = []
    cur = start_anchor
    while cur < end_boundary:
        cur = _next_boundary(cur, granularity, tz)
        boundaries.append(cur)
    if not boundaries or boundaries[-1] != end_boundary:
        boundaries.append(end_boundary)
    return boundaries, delta_by_ts, start_anchor, end_boundary


def get_delta_series(*, player_uuids: List[str], metrics: List[str], granularity: str = "10min",
                     start: Optional[str] = None, end: Optional[str] = None,
                     namespace: str = DEFAULT_NAMESPACE,
                     server_ids: Optional[List[int]] = None) -> Dict[str, List[Tuple[int, int]]]:
    if not player_uuids:
        raise ValueError("必须提供至少一个 player_uuid")
    if not metrics:
        raise ValueError("必须提供至少一个 metric")
    if granularity not in SUPPORTED_GRANULARITIES:
        raise ValueError(f"不支持的粒度: {granularity}")

    start_ts = _parse_iso(start) if start else None
    end_ts = _parse_iso(end) if end else None

    # 输入指标按白名单/忽略进行过滤（支持通配符），并归一为 cat.item
    normed: List[str] = []
    for m in metrics:
        nm = _normalize_metric(m)
        try:
            cat, item = nm.split('.', 1)
            normed.append(f"{cat}.{item}")
        except Exception:
            continue
    allowed = _filter_metrics(normed, namespace=namespace)
    if not allowed:
        return {uid: [] for uid in player_uuids}

    pairs = _normalize_metrics(allowed, namespace)
    db = SessionLocal()
    try:
        metric_ids = _resolve_metric_ids(db, pairs)
        if not metric_ids:
            return {uid: [] for uid in player_uuids}

        result: Dict[str, List[Tuple[int, int]]] = {}
        # 查询阶段参数：允许负 delta，不进行 clamp；不补零桶，由前端完成
        clamp_negative = False
        fill_missing = False
        for uid in player_uuids:
            player_id = db.scalar(select(models.Player.id).where(models.Player.uuid == uid))
            if player_id is None:
                result[uid] = []
                continue

            boundaries, delta_by_ts, start_anchor, end_boundary = _build_boundaries_for_player(
                db, player_id=player_id, metric_ids=metric_ids, granularity=granularity,
                start_ts=start_ts, end_ts=end_ts, server_ids=server_ids,
            )
            if not boundaries:
                result[uid] = []
                continue

            out: List[Tuple[int, int]] = []
            prev_boundary = start_anchor
            sorted_ts = sorted(delta_by_ts.keys())
            idx = 0
            for b in boundaries:
                bucket_delta = 0
                # 汇总 (prev_boundary, b] 内的所有 delta
                while idx < len(sorted_ts) and sorted_ts[idx] <= b:
                    t = sorted_ts[idx]
                    if t > prev_boundary:
                        bucket_delta += delta_by_ts[t]
                    idx += 1
                # 允许负 delta；如需 clamp 可在此启用
                if clamp_negative:
                    bucket_delta = max(bucket_delta, 0)
                # 不补零空桶：仅在非零时返回该桶
                if fill_missing:
                    out.append((b, int(bucket_delta)))
                else:
                    if bucket_delta != 0:
                        out.append((b, int(bucket_delta)))
                prev_boundary = b
            result[uid] = out
        return result
    finally:
        db.close()

def leaderboard_total(*, metrics: List[str], at: Optional[str] = None,
                      server_ids: Optional[List[int]] = None,
                      namespace: str = DEFAULT_NAMESPACE,
                      limit: int = 50) -> List[Dict[str, object]]:
    """排行榜：某时刻各玩家（跨所选服务器与指标）total 之和，按降序返回。
    输入 metrics 将按配置进行白名单/忽略过滤。
    """
    from time import time as _time
    at_ts = _parse_iso(at) if at else int(_time())

    # 过滤输入指标
    normed: List[str] = []
    for m in metrics:
        nm = _normalize_metric(m)
        try:
            cat, item = nm.split('.', 1)
            normed.append(f"{cat}.{item}")
        except Exception:
            continue
    allowed = _filter_metrics(normed, namespace=namespace)
    if not allowed:
        return []

    pairs = _normalize_metrics(allowed, namespace)
    db = SessionLocal()
    try:
        metric_ids = _resolve_metric_ids(db, pairs)
        if not metric_ids:
            return []
        # 子查询：每个 (server, player, metric) 在 at_ts 时刻之前的最新 ts
        latest = (
            select(
                models.PlayerMetrics.server_id.label('server_id'),
                models.PlayerMetrics.player_id.label('player_id'),
                models.PlayerMetrics.metric_id.label('metric_id'),
                func.max(models.PlayerMetrics.ts).label('ts'),
            )
            .where(
                models.PlayerMetrics.metric_id.in_(metric_ids),
                models.PlayerMetrics.ts <= at_ts,
            )
            .group_by(models.PlayerMetrics.server_id, models.PlayerMetrics.player_id, models.PlayerMetrics.metric_id)
        )
        if server_ids:
            latest = latest.where(models.PlayerMetrics.server_id.in_(server_ids))
        latest = latest.subquery('latest')

        # 连接到主表取出 total，再按 player 汇总
        agg = (
            select(
                latest.c.player_id.label('player_id'),
                func.sum(models.PlayerMetrics.total).label('value')
            )
            .select_from(latest)
            .join(models.PlayerMetrics, (models.PlayerMetrics.server_id == latest.c.server_id) &
                                     (models.PlayerMetrics.player_id == latest.c.player_id) &
                                     (models.PlayerMetrics.metric_id == latest.c.metric_id) &
                                     (models.PlayerMetrics.ts == latest.c.ts))
            .group_by(latest.c.player_id)
            .order_by(func.sum(models.PlayerMetrics.total).desc())
            .limit(max(1, int(limit)))
        )
        rows = db.execute(agg).all()
        out: List[Dict[str, object]] = []
        for pid, val in rows:
            rec = db.query(models.Player).filter(models.Player.id == pid).first()
            out.append({
                'player_uuid': rec.uuid if rec else None,
                'player_name': rec.player_name if rec else None,
                'value': int(val or 0),
            })
        return out
    finally:
        db.close()

def leaderboard_delta(*, metrics: List[str], start: Optional[str] = None, end: Optional[str] = None,
                      server_ids: Optional[List[int]] = None,
                      namespace: str = DEFAULT_NAMESPACE,
                      limit: int = 50) -> List[Dict[str, object]]:
    """排行榜：区间内各玩家（跨所选服务器与指标）delta 之和，按降序返回。
    输入 metrics 将按配置进行白名单/忽略过滤。
    """
    start_ts = _parse_iso(start) if start else None
    end_ts = _parse_iso(end) if end else None

    # 过滤输入指标
    normed: List[str] = []
    for m in metrics:
        nm = _normalize_metric(m)
        try:
            cat, item = nm.split('.', 1)
            normed.append(f"{cat}.{item}")
        except Exception:
            continue
    allowed = _filter_metrics(normed, namespace=namespace)
    if not allowed:
        return []

    pairs = _normalize_metrics(allowed, namespace)
    db = SessionLocal()
    try:
        metric_ids = _resolve_metric_ids(db, pairs)
        if not metric_ids:
            return []
        q = (
            select(models.PlayerMetrics.player_id, func.sum(models.PlayerMetrics.delta).label('value'))
            .where(models.PlayerMetrics.metric_id.in_(metric_ids))
        )
        if start_ts is not None:
            q = q.where(models.PlayerMetrics.ts > start_ts)
        if end_ts is not None:
            q = q.where(models.PlayerMetrics.ts <= end_ts)
        if server_ids:
            q = q.where(models.PlayerMetrics.server_id.in_(server_ids))
        q = q.group_by(models.PlayerMetrics.player_id).order_by(func.sum(models.PlayerMetrics.delta).desc()).limit(max(1,int(limit)))
        rows = db.execute(q).all()
        out: List[Dict[str, object]] = []
        for pid, val in rows:
            rec = db.query(models.Player).filter(models.Player.id == pid).first()
            out.append({
                'player_uuid': rec.uuid if rec else None,
                'player_name': rec.player_name if rec else None,
                'value': int(val or 0),
            })
        return out
    finally:
        db.close()


def get_total_series(*, player_uuids: List[str], metrics: List[str], granularity: str = "10min",
                     start: Optional[str] = None, end: Optional[str] = None,
                     namespace: str = DEFAULT_NAMESPACE,
                     server_ids: Optional[List[int]] = None) -> Dict[str, List[Tuple[int, int]]]:
    if not player_uuids:
        raise ValueError("必须提供至少一个 player_uuid")
    if not metrics:
        raise ValueError("必须提供至少一个 metric")
    if granularity not in SUPPORTED_GRANULARITIES:
        raise ValueError(f"不支持的粒度: {granularity}")

    start_ts = _parse_iso(start) if start else None
    end_ts = _parse_iso(end) if end else None

    # 输入指标按白名单/忽略进行过滤（支持通配符），并归一为 cat.item
    normed: List[str] = []
    for m in metrics:
      nm = _normalize_metric(m)
      try:
          cat, item = nm.split('.', 1)
          normed.append(f"{cat}.{item}")
      except Exception:
          continue
    allowed = _filter_metrics(normed, namespace=namespace)
    if not allowed:
        return {uid: [] for uid in player_uuids}

    pairs = _normalize_metrics(allowed, namespace)

    db = SessionLocal()
    try:
        metric_ids = _resolve_metric_ids(db, pairs)
        if not metric_ids:
            return {uid: [] for uid in player_uuids}

        result: Dict[str, List[Tuple[int, int]]] = {}
        # 查询阶段参数：不补零桶；仅在值变化或首点时输出
        fill_missing = False
        for uid in player_uuids:
            player_id = db.scalar(select(models.Player.id).where(models.Player.uuid == uid))
            if player_id is None:
                result[uid] = []
                continue

            # 使用统一边界构建（仅用于锚点），total 使用 "<= boundary" 最新值
            boundaries, _delta_by_ts, start_anchor, end_boundary = _build_boundaries_for_player(
                db, player_id=player_id, metric_ids=metric_ids, granularity=granularity,
                start_ts=start_ts, end_ts=end_ts, server_ids=server_ids,
            )
            if not boundaries:
                result[uid] = []
                continue

            first_b = boundaries[0]

            # 1) 计算基线：在 first_b 时刻（含）之前，每个 (server, metric) 的最新 total 之和
            # 修复：需要按 player_id 参与聚合与连接，否则会将不同玩家在同一时刻的记录混合
            latest_baseline = (
                select(
                    models.PlayerMetrics.server_id.label('server_id'),
                    models.PlayerMetrics.player_id.label('player_id'),
                    models.PlayerMetrics.metric_id.label('metric_id'),
                    func.max(models.PlayerMetrics.ts).label('ts'),
                )
                .where(
                    models.PlayerMetrics.player_id == player_id,
                    models.PlayerMetrics.metric_id.in_(metric_ids),
                    models.PlayerMetrics.ts <= first_b,
                )
                .group_by(
                    models.PlayerMetrics.server_id,
                    models.PlayerMetrics.player_id,
                    models.PlayerMetrics.metric_id,
                )
            )
            if server_ids:
                latest_baseline = latest_baseline.where(models.PlayerMetrics.server_id.in_(server_ids))
            latest_baseline = latest_baseline.subquery('latest_baseline')

            baseline_rows = db.execute(
                select(
                    latest_baseline.c.server_id,
                    latest_baseline.c.metric_id,
                    models.PlayerMetrics.total,
                )
                .select_from(latest_baseline)
                .join(
                    models.PlayerMetrics,
                    (models.PlayerMetrics.server_id == latest_baseline.c.server_id)
                    & (models.PlayerMetrics.player_id == latest_baseline.c.player_id)
                    & (models.PlayerMetrics.metric_id == latest_baseline.c.metric_id)
                    & (models.PlayerMetrics.ts == latest_baseline.c.ts)
                )
            ).all()

            totals_by_key: Dict[Tuple[int, int], int] = {}
            current_sum = 0
            for sid, mid, tot in baseline_rows:
                key = (int(sid), int(mid))
                val = int(tot or 0)
                totals_by_key[key] = val
                current_sum += val

            # 2) 拉取 first_b..last_ts 期间的所有变更事件（按时间升序），逐边界推进最新值
            events_q = (
                select(
                    models.PlayerMetrics.ts,
                    models.PlayerMetrics.server_id,
                    models.PlayerMetrics.metric_id,
                    models.PlayerMetrics.total,
                )
                .where(
                    models.PlayerMetrics.player_id == player_id,
                    models.PlayerMetrics.metric_id.in_(metric_ids),
                    models.PlayerMetrics.ts > first_b,
                    models.PlayerMetrics.ts <= end_boundary,
                )
                .order_by(models.PlayerMetrics.ts.asc())
            )
            if server_ids:
                events_q = events_q.where(models.PlayerMetrics.server_id.in_(server_ids))
            events = db.execute(events_q).all()

            # 3) 沿边界推进，应用事件更新 current_sum，并记录 total 值
            out: List[Tuple[int, int]] = []
            idx = 0
            # 首点：输出基线；若不补零桶，则保留首点作为锚点
            last_output_val = None
            def _maybe_append(point_ts: int, val: int):
                nonlocal last_output_val
                if fill_missing:
                    out.append((point_ts, int(val)))
                else:
                    if last_output_val is None or int(val) != int(last_output_val):
                        out.append((point_ts, int(val)))
                        last_output_val = int(val)

            _maybe_append(first_b, int(current_sum))
            for b in boundaries[1:]:
                while idx < len(events) and int(events[idx][0]) <= b:
                    _ts, sid, mid, tot = events[idx]
                    key = (int(sid), int(mid))
                    new_val = int(tot or 0)
                    prev_val = totals_by_key.get(key, 0)
                    if new_val != prev_val:
                        current_sum += (new_val - prev_val)
                        totals_by_key[key] = new_val
                    idx += 1
                _maybe_append(b, int(current_sum))

            result[uid] = out
        return result
    finally:
        db.close()
