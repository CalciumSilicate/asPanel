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

from backend.core.config import STATS_WHITELIST_ON, STATS_WHITELIST, STATS_IGNORE
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


def _filter_metrics(all_metrics: Iterable[str]) -> List[str]:
    """按配置过滤指标集合。支持通配符：如 '*.minecraft:stone' 或 'minecraft:used.minecraft:*_pickaxe'。

    - STATS_WHITELIST_ON 为真：先按白名单匹配，再应用忽略列表剔除
    - 否则：在全部集合上应用忽略列表剔除
    """
    metrics = set(all_metrics)
    if STATS_WHITELIST_ON:
        allowed = set()
        for m in metrics:
            full = _fmt_full_key(m)
            if any(fnmatch.fnmatch(full, pat) for pat in STATS_WHITELIST):
                allowed.add(m)
        metrics = allowed

    # 忽略项
    filtered = set()
    for m in metrics:
        full = _fmt_full_key(m)
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

    metrics = _filter_metrics(all_metrics)
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
                return int(curr_total), 0
            if curr_total < prev_total:
                return int(curr_total), 1
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
                .join(sub, (models.PlayerMetrics.metric_id == sub.c.metric_id) & (models.PlayerMetrics.ts == sub.c.mts))
            ).all()
            prev_map = {int(mid): int(t or 0) for (mid, t) in prev_rows}

            # 计算并写入变更（合并 upsert 行为）
            to_add: list[models.PlayerMetrics] = []
            updated_count = 0
            for metric in metrics:
                mid = metric_id_map[metric]
                curr_total = _read_metric_from_json(js, metric)
                prev_total = prev_map.get(mid)
                delta, reset = _compute_delta(prev_total, curr_total)
                if delta == 0 and reset == 0:
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
        logger.debug(f"ingested {stats_dir}")
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
    # await _sleep_until_next_10min_boundary()
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
                if srv.id in ignore_ids:
                    ignored += 1
                    continue
                stats_dir = _server_stats_dir(srv.path)
                # 若服务器在运行，先 save-all
                try:
                    proc = mcdr_manager.processes.get(srv.id)
                    if proc and proc.returncode is None:
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


def get_delta_series(*, player_uuid: str, metric: str, granularity: str = "10min",
                     start: Optional[str] = None, end: Optional[str] = None,
                     namespace: str = DEFAULT_NAMESPACE,
                     server_ids: Optional[List[int]] = None) -> List[Tuple[int, int]]:
    metric = _normalize_metric(metric)
    step = _GRANULARITY_SECONDS.get(granularity)
    if step is None:
        raise ValueError(f"不支持的粒度: {granularity}")

    db = SessionLocal()
    try:
        # metric_id
        cat, item = metric.split(".", 1)
        cat_key = f"{namespace}:{cat}"
        item_key = f"{namespace}:{item}"
        metric_id = db.scalar(
            select(models.MetricsDim.metric_id)
            .where(models.MetricsDim.category == cat_key, models.MetricsDim.item == item_key)
        )
        if metric_id is None:
            return []

        # 找到该玩家 id
        player_id = db.scalar(select(models.Player.id).where(models.Player.uuid == player_uuid))
        if player_id is None:
            return []

        t_min = db.scalar(
            select(func.min(models.PlayerMetrics.ts))
            .where(models.PlayerMetrics.player_id == player_id, models.PlayerMetrics.metric_id == metric_id)
        )
        t_max = db.scalar(
            select(func.max(models.PlayerMetrics.ts))
            .where(models.PlayerMetrics.player_id == player_id, models.PlayerMetrics.metric_id == metric_id)
        )
        if t_min is None or t_max is None:
            return []

        start_ts = _parse_iso(start) or int(t_min)
        end_ts = _parse_iso(end) or int(t_max)
        start_ts = _align_floor(start_ts, step)
        end_ts = _align_floor(end_ts, step)

        # 汇总不同 server_id 在同一 ts 的 delta
        stmt = (
            select(models.PlayerMetrics.ts, func.sum(models.PlayerMetrics.delta))
            .where(
                models.PlayerMetrics.player_id == player_id,
                models.PlayerMetrics.metric_id == metric_id,
                models.PlayerMetrics.ts >= start_ts,
                models.PlayerMetrics.ts <= end_ts,
            )
            .group_by(models.PlayerMetrics.ts)
            .order_by(models.PlayerMetrics.ts.asc())
        )
        if server_ids:
            stmt = stmt.where(models.PlayerMetrics.server_id.in_(server_ids))
        rows = db.execute(stmt).all()

        out: List[Tuple[int, int]] = []
        bucket = start_ts
        idx = 0
        acc = 0
        while bucket <= end_ts:
            upper = bucket + step
            while idx < len(rows) and rows[idx][0] < upper:
                acc += int(rows[idx][1] or 0)
                idx += 1
            out.append((bucket, acc))
            acc = 0
            bucket = upper
        return out
    finally:
        db.close()


def get_total_series(*, player_uuid: str, metric: str, granularity: str = "10min",
                     start: Optional[str] = None, end: Optional[str] = None,
                     namespace: str = DEFAULT_NAMESPACE,
                     server_ids: Optional[List[int]] = None) -> List[Tuple[int, int]]:
    metric = _normalize_metric(metric)
    step = _GRANULARITY_SECONDS.get(granularity)
    if step is None:
        raise ValueError(f"不支持的粒度: {granularity}")

    db = SessionLocal()
    try:
        cat, item = metric.split(".", 1)
        cat_key = f"{namespace}:{cat}"
        item_key = f"{namespace}:{item}"
        metric_id = db.scalar(
            select(models.MetricsDim.metric_id)
            .where(models.MetricsDim.category == cat_key, models.MetricsDim.item == item_key)
        )
        if metric_id is None:
            return []

        player_id = db.scalar(select(models.Player.id).where(models.Player.uuid == player_uuid))
        if player_id is None:
            return []

        tmin_stmt = select(func.min(models.PlayerMetrics.ts)).where(
            models.PlayerMetrics.player_id == player_id,
            models.PlayerMetrics.metric_id == metric_id,
        )
        tmax_stmt = select(func.max(models.PlayerMetrics.ts)).where(
            models.PlayerMetrics.player_id == player_id,
            models.PlayerMetrics.metric_id == metric_id,
        )
        if server_ids:
            tmin_stmt = tmin_stmt.where(models.PlayerMetrics.server_id.in_(server_ids))
            tmax_stmt = tmax_stmt.where(models.PlayerMetrics.server_id.in_(server_ids))
        t_min = db.scalar(tmin_stmt)
        t_max = db.scalar(tmax_stmt)
        pool_min = t_min
        pool_max = t_max
        if pool_min is None or pool_max is None:
            return []

        req_start = _parse_iso(start) or int(pool_min)
        req_end = _parse_iso(end) or int(pool_max)
        start_ts = _align_floor(req_start, step)
        end_ts = _align_floor(req_end, step)

        # 基准：各 server 在 start_ts 时刻（或之前）最新一条 total 的和
        base_stmt = (
            select(
                models.PlayerMetrics.server_id,
                models.PlayerMetrics.ts,
                models.PlayerMetrics.total,
            )
            .where(
                models.PlayerMetrics.player_id == player_id,
                models.PlayerMetrics.metric_id == metric_id,
                models.PlayerMetrics.ts <= start_ts,
            )
            .order_by(models.PlayerMetrics.server_id.asc(), models.PlayerMetrics.ts.asc())
        )
        if server_ids:
            base_stmt = base_stmt.where(models.PlayerMetrics.server_id.in_(server_ids))
        base_rows = db.execute(base_stmt).all()
        last_total_by_server: dict[int, Tuple[int, int]] = {}
        for sid, t, tot in base_rows:
            # 仅保留每个 server 最新（<= start_ts）的记录
            prev = last_total_by_server.get(int(sid))
            if prev is None or int(t) >= prev[0]:
                last_total_by_server[int(sid)] = (int(t), int(tot or 0))
        base_total = sum(v[1] for v in last_total_by_server.values())

        # 取 start_ts 之后的增量（汇总不同 server）
        delta_stmt = (
            select(models.PlayerMetrics.ts, func.sum(models.PlayerMetrics.delta))
            .where(
                models.PlayerMetrics.player_id == player_id,
                models.PlayerMetrics.metric_id == metric_id,
                models.PlayerMetrics.ts > start_ts,
                models.PlayerMetrics.ts <= end_ts,
            )
            .group_by(models.PlayerMetrics.ts)
            .order_by(models.PlayerMetrics.ts.asc())
        )
        if server_ids:
            delta_stmt = delta_stmt.where(models.PlayerMetrics.server_id.in_(server_ids))
        delta_rows = db.execute(delta_stmt).all()

        out: List[Tuple[int, int]] = []
        cumulative = int(base_total)
        idx = 0
        bucket_ts = start_ts
        while bucket_ts <= end_ts:
            while idx < len(delta_rows) and delta_rows[idx][0] <= bucket_ts:
                cumulative += int(delta_rows[idx][1] or 0)
                idx += 1
            out.append((bucket_ts, cumulative))
            bucket_ts += step
        return out
    finally:
        db.close()
