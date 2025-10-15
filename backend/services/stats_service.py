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


def ingest_once_for_server(server_id: int, stats_dir: Path, metrics: List[str], *, namespace: str = DEFAULT_NAMESPACE) -> None:
    """对单个服务器执行一次入库（使用主库 models 定义）。"""
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

    def _ensure_player_id(session: Session, player_uuid: str) -> Optional[int]:
        pid = session.scalar(select(models.Player.id).where(models.Player.uuid == player_uuid))
        if pid is not None:
            return int(pid)
        # 若玩家不存在，这里按需创建（保持最小字段）
        obj = models.Player(uuid=player_uuid, player_name=None, play_time="{}", is_offline=True)
        session.add(obj)
        session.flush()
        return int(obj.id)

    def _ensure_metric_id(session: Session, metric: str) -> int:
        cat, item = metric.split(".", 1)
        cat_key = f"{namespace}:{cat}"
        item_key = f"{namespace}:{item}"
        m_id = session.scalar(
            select(models.MetricsDim.metric_id)
            .where(models.MetricsDim.category == cat_key, models.MetricsDim.item == item_key)
        )
        if m_id is not None:
            return int(m_id)
        obj = models.MetricsDim(category=cat_key, item=item_key)
        session.add(obj)
        session.flush()
        return int(obj.metric_id)

    def _read_metric_from_json(js: dict, metric: str) -> int:
        category, item = metric.split(".", 1)
        cat_key = f"{namespace}:{category}"
        item_key = f"{namespace}:{item}"
        stats = js.get("stats", {}) or {}
        return int((stats.get(cat_key, {}) or {}).get(item_key, 0) or 0)

    def _get_prev_total(session: Session, *, player_id: int, metric_id: int, ts_: int) -> Optional[int]:
        row = session.execute(
            select(models.PlayerMetrics.total)
            .where(
                models.PlayerMetrics.server_id == server_id,
                models.PlayerMetrics.player_id == player_id,
                models.PlayerMetrics.metric_id == metric_id,
                models.PlayerMetrics.ts <= ts_,
            )
            .order_by(models.PlayerMetrics.ts.desc())
            .limit(1)
        ).scalar_one_or_none()
        return int(row) if row is not None else None

    def _compute_delta(prev_total: Optional[int], curr_total: int) -> Tuple[int, int]:
        if prev_total is None:
            return int(curr_total), 0
        if curr_total < prev_total:
            return int(curr_total), 1
        return int(curr_total - prev_total), 0

    db = SessionLocal()
    try:
        with db.begin():
            for fp in files:
                player_uuid = fp.stem
                pid = _ensure_player_id(db, player_uuid)
                try:
                    js = json.loads(fp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                for metric in metrics:
                    metric_id = _ensure_metric_id(db, metric)
                    curr_total = _read_metric_from_json(js, metric)
                    prev_total = _get_prev_total(db, player_id=pid, metric_id=metric_id, ts_=ts - 1)
                    delta, reset = _compute_delta(prev_total, curr_total)
                    if delta == 0 and reset == 0:
                        continue
                    # upsert（按 PK 查找后更新/插入）
                    existing = db.execute(
                        select(models.PlayerMetrics)
                        .where(
                            models.PlayerMetrics.server_id == server_id,
                            models.PlayerMetrics.player_id == pid,
                            models.PlayerMetrics.metric_id == metric_id,
                            models.PlayerMetrics.ts == ts,
                        )
                    ).scalar_one_or_none()
                    if existing is None:
                        obj = models.PlayerMetrics(
                            ts=ts,
                            server_id=server_id,
                            player_id=pid,
                            metric_id=metric_id,
                            total=int(curr_total),
                            delta=int(delta),
                        )
                        db.add(obj)
                    else:
                        existing.total = int(curr_total)
                        existing.delta = int(delta)
                        db.add(existing)
        logger.debug(f"ingested {stats_dir}")
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
    finally:
        db.close()

    count = 0
    for srv in servers:
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
    """后台循环：每逢 10 分钟整点触发一次入库。"""
    # 启动先对齐一次
    await _sleep_until_next_10min_boundary()
    while True:
        try:
            n, metrics = await asyncio.to_thread(ingest_all_servers_now)
            logger.info(f"统计入库完成 | 服务器数={n} | 指标数={len(metrics)}")
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
                     namespace: str = DEFAULT_NAMESPACE) -> List[Tuple[int, int]]:
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
        rows = db.execute(
            select(models.PlayerMetrics.ts, func.sum(models.PlayerMetrics.delta))
            .where(
                models.PlayerMetrics.player_id == player_id,
                models.PlayerMetrics.metric_id == metric_id,
                models.PlayerMetrics.ts >= start_ts,
                models.PlayerMetrics.ts <= end_ts,
            )
            .group_by(models.PlayerMetrics.ts)
            .order_by(models.PlayerMetrics.ts.asc())
        ).all()

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
                     namespace: str = DEFAULT_NAMESPACE) -> List[Tuple[int, int]]:
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

        t_min = db.scalar(
            select(func.min(models.PlayerMetrics.ts))
            .where(models.PlayerMetrics.player_id == player_id, models.PlayerMetrics.metric_id == metric_id)
        )
        t_max = db.scalar(
            select(func.max(models.PlayerMetrics.ts))
            .where(models.PlayerMetrics.player_id == player_id, models.PlayerMetrics.metric_id == metric_id)
        )
        pool_min = t_min
        pool_max = t_max
        if pool_min is None or pool_max is None:
            return []

        req_start = _parse_iso(start) or int(pool_min)
        req_end = _parse_iso(end) or int(pool_max)
        start_ts = _align_floor(req_start, step)
        end_ts = _align_floor(req_end, step)

        # 基准：各 server 在 start_ts 时刻（或之前）最新一条 total 的和
        base_rows = db.execute(
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
        ).all()
        last_total_by_server: dict[int, Tuple[int, int]] = {}
        for sid, t, tot in base_rows:
            # 仅保留每个 server 最新（<= start_ts）的记录
            prev = last_total_by_server.get(int(sid))
            if prev is None or int(t) >= prev[0]:
                last_total_by_server[int(sid)] = (int(t), int(tot or 0))
        base_total = sum(v[1] for v in last_total_by_server.values())

        # 取 start_ts 之后的增量（汇总不同 server）
        delta_rows = db.execute(
            select(models.PlayerMetrics.ts, func.sum(models.PlayerMetrics.delta))
            .where(
                models.PlayerMetrics.player_id == player_id,
                models.PlayerMetrics.metric_id == metric_id,
                models.PlayerMetrics.ts > start_ts,
                models.PlayerMetrics.ts <= end_ts,
            )
            .group_by(models.PlayerMetrics.ts)
            .order_by(models.PlayerMetrics.ts.asc())
        ).all()

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
