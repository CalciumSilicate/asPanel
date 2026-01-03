import base64
import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import functools
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core import crud, models
from backend.core.database import get_db_context
from backend.core.logger import logger
from backend.core.utils import get_tz_info
from backend.services import stats_service
from backend.services.qq_rank_image import RankRow, render_rank_image


_BAD_FOOD_METRICS = [
    "used.poisonous_potato",
    "used.rotten_flesh",
    "used.spider_eye",
    "used.pufferfish",
    "used.suspicious_stew"
]

_EAT_METRICS = [
    "used.apple",
    "used.golden_apple",
    "used.enchanted_golden_apple",
    "used.baked_potato",
    "used.beetroot",
    "used.beetroot_soup",
    "used.bread",
    "custom.eat_cake_slice",
    "used.carrot",
    "used.chorus_fruit",
    "used.cooked_chicken",
    "used.cooked_cod",
    "used.cooked_mutton",
    "used.cooked_porkchop",
    "used.cooked_rabbit",
    "used.cooked_salmon",
    "used.cookie",
    "used.dried_kelp",
    "used.glow_berries",
    "used.golden_carrot",
    "used.honey_bottle",
    "used.melon_slice",
    "used.mushroom_stew",
    "used.potato",
    "used.poisonous_potato",
    "used.pufferfish",
    "used.pumpkin_pie",
    "used.rabbit_stew",
    "used.raw_beef",
    "used.raw_chicken",
    "used.raw_cod",
    "used.raw_mutton",
    "used.raw_porkchop",
    "used.raw_rabbit",
    "used.raw_salmon",
    "used.rotten_flesh",
    "used.spider_eye",
    "used.steak",
    "used.suspicious_stew",
    "used.sweet_berries",
    "used.tropical_fish",
]

def _to_local_dt(dt: datetime) -> datetime:
    tz = get_tz_info()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def _time_formatter(hours: float) -> str:
    try:
        total_minutes = int(round(float(hours) * 60))
    except Exception:
        return "0"
    h = total_minutes // 60
    m = total_minutes % 60
    parts: List[str] = []
    if h > 0:
        parts.append(f"{h:,}h")
    if m > 0:
        parts.append(f"{m}m")
    if h == 0 and m == 0:
        parts.append("<1m")
    return "".join(parts) if parts else "0"


def _distance_formatter(km: float) -> str:
    try:
        km_f = float(km)
        abs_km = abs(km_f)
    except Exception:
        return "0"
    if abs_km >= 1_000:
        s = f"{km_f:,.1f}".rstrip("0").rstrip(".")
        return f"{s}km"
    if abs_km >= 1:
        s = f"{km_f:,.2f}".rstrip("0").rstrip(".")
        return f"{s}km"
    meters = km_f * 1000
    return f"{meters:,.2f}".rstrip("0").rstrip(".") + "m"


def _fmt_int(val: object) -> str:
    try:
        return f"{int(val):,}"
    except Exception:
        return str(val)


def _image_to_base64(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _mc_avatar_url(uuid_str: str, size: int = 128) -> str:
    uuid_str = (uuid_str or "").strip()
    return f"https://cravatar.eu/helmavatar/{uuid_str}/{int(size)}.png"


def _qq_avatar_url(qq: str, size: int = 100) -> str:
    qq = (qq or "").strip()
    return f"http://q1.qlogo.cn/g?b=qq&nk={qq}&s={int(size)}"


@dataclass(frozen=True)
class BuiltinBoard:
    name: str
    description: str
    metrics: List[str]
    scale: float
    formatter: Callable[[float], str]


@functools.lru_cache(maxsize=1)
def _builtin_boards() -> Dict[str, BuiltinBoard]:
    # 复用 qq_stats_command 中的内置 metric 列表，保证含义一致
    from backend.services.qq_stats_command import _BREAK_METRICS, _WALK_METRICS, _VEHICLE_METRICS

    move_metrics = ["custom.aviate_one_cm", "custom.ender_pearl_one_cm", *_WALK_METRICS, *_VEHICLE_METRICS]

    boards = [
        BuiltinBoard("上线榜", "统计上线次数", ["custom.leave_game"], 1.0, lambda x: _fmt_int(x)),
        BuiltinBoard("在线榜", "统计在线时长", ["custom.play_one_minute", "custom.play_time"], 1 / 20 / 3600, _time_formatter),
        BuiltinBoard("挖掘榜", "统计挖掘方块（按工具使用次数汇总）", list(_BREAK_METRICS), 1.0, lambda x: _fmt_int(x)),
        BuiltinBoard("真挖掘榜", "统计挖掘方块（按方块挖掘次数汇总）", ["mined.*"], 1.0, lambda x: _fmt_int(x)),
        BuiltinBoard("击杀榜", "统计击杀玩家数", ["custom.player_kills"], 1.0, lambda x: _fmt_int(x)),
        BuiltinBoard("被击杀榜", "统计被玩家击杀数", ["killed_by.player"], 1.0, lambda x: _fmt_int(x)),
        BuiltinBoard("死亡榜", "统计死亡次数", ["custom.deaths"], 1.0, lambda x: _fmt_int(x)),
        BuiltinBoard("鞘翅榜", "统计鞘翅飞行距离", ["custom.aviate_one_cm"], 0.00001, _distance_formatter),
        BuiltinBoard("珍珠榜", "统计末影珍珠传送距离", ["custom.ender_pearl_one_cm"], 0.00001, _distance_formatter),
        BuiltinBoard("步行榜", "统计步行/游泳等距离", list(_WALK_METRICS), 0.00001, _distance_formatter),
        BuiltinBoard("移动榜", "统计移动距离（含鞘翅/珍珠/步行/交通工具）", move_metrics, 0.00001, _distance_formatter),
        BuiltinBoard("烟花榜", "统计使用烟花次数", ["custom.firework_boost", "used.firework_rocket"], 1.0, lambda x: _fmt_int(x)),
        BuiltinBoard("不死图腾榜", "统计消耗不死图腾次数", ["used.totem_of_undying"], 1.0, lambda x: _fmt_int(x)),
        BuiltinBoard("基岩榜", "统计破基岩次数", ["custom.break_bedrock"], 1.0, lambda x: _fmt_int(x)),
        BuiltinBoard("吃货榜", "统计吃各类食物次数", list(_EAT_METRICS), 1.0, lambda x: _fmt_int(x)),
        BuiltinBoard("小馋猫榜", "统计吃各类会提供负面效果食物的次数", list(_BAD_FOOD_METRICS), 1.0, lambda x: _fmt_int(x)),
    ]
    out: Dict[str, BuiltinBoard] = {}
    for b in boards:
        out[b.name] = b
        if b.name.endswith("榜"):
            out[b.name[:-1]] = b
    # 自定义榜单名称也允许省略“榜”
    out["航天"] = BuiltinBoard("航天榜", "玩家最高 Y 值（米）", [], 1.0, lambda x: f"{float(x):.1f}m")
    out["航天榜"] = out["航天"]
    out["最后在线"] = BuiltinBoard("最后在线榜", "最近一次在线时间（越晚越靠前）", [], 1.0, lambda x: str(x))
    out["最后在线榜"] = out["最后在线"]
    out["放置"] = BuiltinBoard("放置榜", "统计放置方块次数（只统计可挖掘的方块）", [], 1.0, lambda x: _fmt_int(x))
    out["放置榜"] = out["放置"]
    return out


def list_board_names() -> List[str]:
    names = [
        "上线榜", "在线榜", "挖掘榜", "真挖掘榜", "放置榜", "击杀榜", "被击杀榜", "死亡榜", "鞘翅榜", "珍珠榜", "步行榜", "移动榜", "烟花榜", "不死图腾榜", "基岩榜",
        "航天榜", "最后在线榜", "吃货榜", "小馋猫榜"
    ]
    return names


def resolve_board(query: str) -> Optional[BuiltinBoard]:
    q = (query or "").strip()
    if not q:
        return None
    return _builtin_boards().get(q)


def _resolve_player_qq_map(db: Session, *, player_uuids: Sequence[str]) -> Dict[str, Optional[str]]:
    uuids = [u for u in player_uuids if u]
    if not uuids:
        return {}
    players = db.query(models.Player.id, models.Player.uuid).filter(models.Player.uuid.in_(uuids)).all()
    pid_by_uuid = {uuid: int(pid) for pid, uuid in players}
    pids = list(pid_by_uuid.values())
    if not pids:
        return {}
    users = (
        db.query(models.User.bound_player_id, models.User.qq)
        .filter(models.User.bound_player_id.in_(pids))
        .all()
    )
    qq_by_pid: Dict[int, Optional[str]] = {}
    for pid, qq in users:
        if pid is None or not qq:
            continue
        qq_by_pid.setdefault(int(pid), str(qq))
    return {uuid: qq_by_pid.get(pid_by_uuid.get(uuid, 0)) for uuid in uuids}


def _daily_boundaries_ts(*, days: int = 7) -> Tuple[datetime, List[int], datetime]:
    tz = get_tz_info()
    now = datetime.now(tz)
    start_day = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    boundaries: List[int] = []
    cur = start_day
    for _ in range(days):
        cur = cur + timedelta(days=1)
        boundaries.append(int(cur.timestamp()))
    return (start_day, boundaries, now)


def _trend_series_7d(
    *,
    player_uuids: List[str],
    metrics: List[str],
    server_ids: List[int],
    scale: float,
) -> Dict[str, List[float]]:
    if not player_uuids:
        return {}
    start_dt, boundaries, now_dt = _daily_boundaries_ts(days=7)
    # 说明：stats_service.get_delta_series 会触发入库（save-all + ingest），会导致后端阻塞/SQLite 写锁；
    # 这里直接查 player_metrics 进行聚合，避免写入。
    zeros = [0.0 for _ in boundaries]

    start_anchor_ts = int(start_dt.timestamp())
    end_boundary_ts = int(boundaries[-1]) if boundaries else int(now_dt.timestamp())

    out: Dict[str, List[float]] = {uid: list(zeros) for uid in player_uuids}
    with get_db_context() as db:
        allowed = stats_service.resolve_metrics(
            db,
            metrics,
            namespace=stats_service.DEFAULT_NAMESPACE,
            include_discovered=False,
        )
        if not allowed:
            return out
        pairs = stats_service._normalize_metrics(allowed, stats_service.DEFAULT_NAMESPACE)  # type: ignore[attr-defined]
        metric_ids = stats_service._resolve_metric_ids(db, pairs)  # type: ignore[attr-defined]
        if not metric_ids:
            return out

        # uuid -> player_id
        rows_p = db.query(models.Player.id, models.Player.uuid).filter(models.Player.uuid.in_(player_uuids)).all()
        pid_by_uuid = {str(uuid): int(pid) for pid, uuid in rows_p if pid is not None and uuid}
        player_ids = [pid_by_uuid.get(uid) for uid in player_uuids]
        player_ids = [int(pid) for pid in player_ids if pid]
        if not player_ids:
            return out

        q = (
            select(
                models.PlayerMetrics.player_id,
                models.PlayerMetrics.ts,
                func.sum(models.PlayerMetrics.delta).label("v"),
            )
            .where(
                models.PlayerMetrics.player_id.in_(player_ids),
                models.PlayerMetrics.metric_id.in_(metric_ids),
                models.PlayerMetrics.ts > start_anchor_ts,
                models.PlayerMetrics.ts <= end_boundary_ts,
            )
            .group_by(models.PlayerMetrics.player_id, models.PlayerMetrics.ts)
            .order_by(models.PlayerMetrics.player_id.asc(), models.PlayerMetrics.ts.asc())
        )
        if server_ids:
            q = q.where(models.PlayerMetrics.server_id.in_(server_ids))

        rows = db.execute(q).all()

    # 聚合到每个玩家的 ts->delta
    delta_by_pid: Dict[int, Dict[int, int]] = {}
    for pid, ts, v in rows:
        try:
            pid_i = int(pid)
            ts_i = int(ts)
            v_i = int(v or 0)
        except Exception:
            continue
        delta_by_pid.setdefault(pid_i, {})[ts_i] = v_i

    # 分桶求和：按本地日历边界
    for uid in player_uuids:
        pid = pid_by_uuid.get(uid)
        if not pid:
            continue
        by_ts = delta_by_pid.get(int(pid), {})
        if not by_ts:
            continue
        sorted_ts = sorted(by_ts.keys())
        vals: List[float] = []
        idx = 0
        prev = start_anchor_ts
        for b in boundaries:
            bucket = 0
            b_i = int(b)
            while idx < len(sorted_ts) and sorted_ts[idx] <= b_i:
                t = sorted_ts[idx]
                if t > prev:
                    bucket += int(by_ts.get(t, 0) or 0)
                idx += 1
            if bucket < 0:
                bucket = 0
            vals.append(float(bucket) * float(scale))
            prev = b_i
        out[uid] = vals

    return out


def _metric_total_rank_for_player(
    db: Session,
    *,
    player_uuid: str,
    metrics: List[str],
    server_ids: List[int],
    at_iso: str,
    namespace: str = stats_service.DEFAULT_NAMESPACE,
) -> Optional[Tuple[int, int]]:
    player_uuid = (player_uuid or "").strip()
    if not player_uuid:
        return None

    # 归一 + 通配符展开 + 白名单/忽略过滤（保持与 stats_service.leaderboard_total 一致）
    allowed = stats_service.resolve_metrics(
        db,
        metrics,
        namespace=namespace,
        include_discovered=False,
    )
    if not allowed:
        return None

    metric_pairs = stats_service._normalize_metrics(allowed, namespace)  # type: ignore[attr-defined]
    metric_ids = stats_service._resolve_metric_ids(db, metric_pairs)  # type: ignore[attr-defined]
    if not metric_ids:
        return None

    player_id = db.scalar(select(models.Player.id).where(models.Player.uuid == player_uuid))
    if player_id is None:
        return None
    player_id = int(player_id)

    at_ts = stats_service._parse_iso(at_iso)  # type: ignore[attr-defined]
    if at_ts is None:
        return None

    latest = (
        select(
            models.PlayerMetrics.server_id.label("server_id"),
            models.PlayerMetrics.player_id.label("player_id"),
            models.PlayerMetrics.metric_id.label("metric_id"),
            func.max(models.PlayerMetrics.ts).label("ts"),
        )
        .where(
            models.PlayerMetrics.metric_id.in_(metric_ids),
            models.PlayerMetrics.ts <= int(at_ts),
        )
        .group_by(models.PlayerMetrics.server_id, models.PlayerMetrics.player_id, models.PlayerMetrics.metric_id)
    )
    if server_ids:
        latest = latest.where(models.PlayerMetrics.server_id.in_(server_ids))
    latest = latest.subquery("latest")

    agg_values = (
        select(
            latest.c.player_id.label("player_id"),
            func.sum(models.PlayerMetrics.total).label("value"),
        )
        .select_from(latest)
        .join(
            models.PlayerMetrics,
            (models.PlayerMetrics.server_id == latest.c.server_id)
            & (models.PlayerMetrics.player_id == latest.c.player_id)
            & (models.PlayerMetrics.metric_id == latest.c.metric_id)
            & (models.PlayerMetrics.ts == latest.c.ts),
        )
        .group_by(latest.c.player_id)
    ).subquery("agg_values")

    user_val = db.scalar(select(agg_values.c.value).where(agg_values.c.player_id == player_id))
    if user_val is None:
        return None
    try:
        user_val_i = int(user_val or 0)
    except Exception:
        user_val_i = 0

    higher = db.scalar(select(func.count()).select_from(agg_values).where(agg_values.c.value > user_val_i))
    try:
        higher_i = int(higher or 0)
    except Exception:
        higher_i = 0
    return (higher_i + 1, user_val_i)


def build_metric_rank_image_b64(
    *,
    title: str,
    description: str,
    metrics: List[str],
    server_ids: List[int],
    limit: int,
    scale: float,
    formatter: Callable[[float], str],
    subtitle: Optional[str] = None,
    pinned_uuid: Optional[str] = None,
    pinned_name: Optional[str] = None,
) -> Tuple[bool, str]:
    at_iso = datetime.now(timezone.utc).isoformat()
    rows = stats_service.leaderboard_total(metrics=metrics, at=at_iso, server_ids=server_ids, limit=max(1, int(limit)))
    if not rows:
        return False, "没有查到数据（可能是指标无效，或该服务器暂无统计数据）"
    player_uuids: List[str] = [str(r.get("player_uuid") or "") for r in rows if r.get("player_uuid")]
    pinned_uuid_norm = (pinned_uuid or "").strip()
    include_pinned = bool(pinned_uuid_norm) and pinned_uuid_norm not in set(player_uuids)
    all_uuids = list(player_uuids)
    if include_pinned:
        all_uuids.append(pinned_uuid_norm)
    with get_db_context() as db:
        qq_map = _resolve_player_qq_map(db, player_uuids=all_uuids)

    trend_map = _trend_series_7d(player_uuids=all_uuids, metrics=metrics, server_ids=server_ids, scale=scale)

    rank_rows: List[RankRow] = []
    for idx, r in enumerate(rows, start=1):
        puid = str(r.get("player_uuid") or "")
        pname = str(r.get("player_name"))
        raw_val = int(r.get("value") or 0)
        display_val = float(raw_val) * float(scale)
        score_text = formatter(display_val)
        qq = qq_map.get(puid)
        big_avatar = _qq_avatar_url(qq) if qq else _mc_avatar_url(puid)
        rank_rows.append(
            RankRow(
                rank=idx,
                player_name=pname,
                player_uuid=puid,
                score_text=score_text,
                avatar_big=big_avatar,
                avatar_small=_mc_avatar_url(puid),
                trend_values=trend_map.get(puid),
            )
        )

    pinned_row: Optional[RankRow] = None
    if include_pinned:
        with get_db_context() as db:
            rank_val = _metric_total_rank_for_player(
                db,
                player_uuid=pinned_uuid_norm,
                metrics=metrics,
                server_ids=server_ids,
                at_iso=at_iso,
            )
            if rank_val is None:
                pinned_rank = 0
                raw_val = None
            else:
                pinned_rank, raw_val = rank_val

            pname = (pinned_name or "").strip()
            if not pname:
                try:
                    rec = db.query(models.Player).filter(models.Player.uuid == pinned_uuid_norm).first()
                    pname = str(rec.player_name or "Unknown") if rec else "Unknown"
                except Exception:
                    pname = "Unknown"

        qq = qq_map.get(pinned_uuid_norm)
        big_avatar = _qq_avatar_url(qq) if qq else _mc_avatar_url(pinned_uuid_norm)
        if raw_val is None:
            score_text = "暂无数据"
        else:
            score_text = formatter(float(int(raw_val)) * float(scale))
        pinned_row = RankRow(
            rank=int(pinned_rank or 0),
            player_name=pname,
            player_uuid=pinned_uuid_norm,
            score_text=score_text,
            avatar_big=big_avatar,
            avatar_small=_mc_avatar_url(pinned_uuid_norm),
            trend_values=trend_map.get(pinned_uuid_norm),
            is_pinned=True,
        )

    img = render_rank_image(
        title=title,
        subtitle=subtitle or description,
        rows=rank_rows,
        show_trend=True,
        pinned_row=pinned_row,
    )
    return True, _image_to_base64(img)


def build_space_rank_image_b64(
    *,
    server_ids: List[int],
    limit: int,
    pinned_uuid: Optional[str] = None,
    pinned_name: Optional[str] = None,
) -> Tuple[bool, str]:
    pinned_uuid_norm = (pinned_uuid or "").strip()
    with get_db_context() as db:
        maxy = (
            select(
                models.PlayerPosition.player_id.label("player_id"),
                func.max(models.PlayerPosition.y).label("max_y"),
            )
            .where(models.PlayerPosition.y.isnot(None))
        )
        if server_ids:
            maxy = maxy.where(models.PlayerPosition.server_id.in_(server_ids))
        maxy = maxy.group_by(models.PlayerPosition.player_id).subquery("maxy")

        q_top = select(maxy.c.player_id, maxy.c.max_y).order_by(maxy.c.max_y.desc()).limit(max(1, int(limit)))
        rows = db.execute(q_top).all()
        if not rows:
            return False, "没有查到坐标数据（player_positions）"

        player_ids = [int(pid) for pid, _ in rows if pid is not None]
        pinned_player_id = None
        if pinned_uuid_norm:
            pinned_player_id = db.scalar(select(models.Player.id).where(models.Player.uuid == pinned_uuid_norm))
            if pinned_player_id is not None:
                pinned_player_id = int(pinned_player_id)
                if pinned_player_id not in player_ids:
                    player_ids.append(pinned_player_id)

        players = (
            db.query(models.Player.id, models.Player.uuid, models.Player.player_name)
            .filter(models.Player.id.in_(player_ids))
            .all()
        )
        pmap = {int(pid): (str(uuid), str(name or "Unknown")) for pid, uuid, name in players}
        uuids = [pmap.get(int(pid), ("", ""))[0] for pid, _ in rows]
        qq_map = _resolve_player_qq_map(db, player_uuids=uuids + ([pinned_uuid_norm] if pinned_uuid_norm else []))

        pinned_row: Optional[RankRow] = None
        if pinned_uuid_norm and pinned_player_id is not None and pinned_uuid_norm not in set(uuids):
            pinned_y = db.scalar(select(maxy.c.max_y).where(maxy.c.player_id == pinned_player_id))
            if pinned_y is None:
                pinned_rank = 0
                score_text = "暂无数据"
            else:
                try:
                    pinned_y_f = float(pinned_y or 0.0)
                except Exception:
                    pinned_y_f = 0.0
                higher = db.scalar(select(func.count()).select_from(maxy).where(maxy.c.max_y > pinned_y_f))
                try:
                    higher_i = int(higher or 0)
                except Exception:
                    higher_i = 0
                pinned_rank = higher_i + 1
                score_text = f"{pinned_y_f:.1f}m"

            name = (pinned_name or "").strip() or pmap.get(pinned_player_id, (pinned_uuid_norm, "Unknown"))[1]
            qq = qq_map.get(pinned_uuid_norm)
            big_avatar = _qq_avatar_url(qq) if qq else _mc_avatar_url(pinned_uuid_norm)
            pinned_row = RankRow(
                rank=int(pinned_rank or 0),
                player_name=name,
                player_uuid=pinned_uuid_norm,
                score_text=score_text,
                avatar_big=big_avatar,
                avatar_small=_mc_avatar_url(pinned_uuid_norm),
                trend_values=None,
                is_pinned=True,
            )

    rank_rows: List[RankRow] = []
    for idx, (pid, max_y) in enumerate(rows, start=1):
        uuid, name = pmap.get(int(pid), ("", "Unknown"))
        try:
            y_val = float(max_y or 0.0)
        except Exception:
            y_val = 0.0
        qq = qq_map.get(uuid)
        big_avatar = _qq_avatar_url(qq) if qq else _mc_avatar_url(uuid)
        rank_rows.append(
            RankRow(
                rank=idx,
                player_name=name,
                player_uuid=uuid,
                score_text=f"{y_val:.1f}m",
                avatar_big=big_avatar,
                avatar_small=_mc_avatar_url(uuid),
                trend_values=None,
            )
        )

    img = render_rank_image(
        title="航天榜",
        subtitle="玩家最高 Y 值（米）",
        rows=rank_rows,
        show_trend=False,
        pinned_row=pinned_row,
    )
    return True, _image_to_base64(img)


def build_last_seen_rank_image_b64(
    *,
    server_ids: List[int],
    limit: int,
    pinned_uuid: Optional[str] = None,
    pinned_name: Optional[str] = None,
) -> Tuple[bool, str]:
    tz = get_tz_info()
    now = datetime.now(tz)
    now_ts = int(datetime.now(timezone.utc).timestamp())

    with get_db_context() as db:
        # ----------------------------
        # 1) PlayerSession: 最近离线时间
        # ----------------------------
        q_logout = (
            select(models.PlayerSession.player_uuid, func.max(models.PlayerSession.logout_time).label("t"))
            .where(models.PlayerSession.logout_time.isnot(None))
        )
        if server_ids:
            q_logout = q_logout.where(models.PlayerSession.server_id.in_(server_ids))
        q_logout = q_logout.group_by(models.PlayerSession.player_uuid)
        logout_rows = db.execute(q_logout).all()

        # ----------------------------
        # 2) PlayerSession: 当前在线（logout_time 为空）
        # ----------------------------
        q_online = (
            select(models.PlayerSession.player_uuid, func.max(models.PlayerSession.login_time).label("t"))
            .where(models.PlayerSession.logout_time.is_(None))
        )
        if server_ids:
            q_online = q_online.where(models.PlayerSession.server_id.in_(server_ids))
        q_online = q_online.group_by(models.PlayerSession.player_uuid)
        online_rows = db.execute(q_online).all()

        # last_seen: uuid -> (dt_local, is_online)
        last_seen: Dict[str, Tuple[datetime, bool]] = {}
        # source_map: uuid -> "session" | "online" | "metric"
        source_map: Dict[str, str] = {}

        for uuid, t in logout_rows:
            if not uuid or not t:
                continue
            u = str(uuid)
            last_seen[u] = (_to_local_dt(t), False)
            source_map[u] = "session"

        for uuid, _t in online_rows:
            if not uuid:
                continue
            u = str(uuid)
            # 在线玩家：排序值使用 now，展示标注在线
            last_seen[u] = (now, True)
            source_map[u] = "online"

        # ----------------------------
        # 3) Metrics 兜底：minecraft:custom / minecraft:leave_game
        #    只补“没有 session 记录”的玩家（不覆盖 session/online）
        # ----------------------------
        cat_key = "minecraft:custom"
        item_key = "minecraft:leave_game"
        metric_id = db.scalar(
            select(models.MetricsDim.metric_id).where(
                models.MetricsDim.category == cat_key,
                models.MetricsDim.item == item_key,
            )
        )

        if metric_id:
            q_metric = (
                select(models.Player.uuid, func.max(models.PlayerMetrics.ts).label("ts"))
                .select_from(models.PlayerMetrics)
                .join(models.Player, models.Player.id == models.PlayerMetrics.player_id)
                .where(
                    models.PlayerMetrics.metric_id == metric_id,
                    models.PlayerMetrics.ts.isnot(None),
                    models.PlayerMetrics.ts <= now_ts,
                )
            )
            if server_ids:
                q_metric = q_metric.where(models.PlayerMetrics.server_id.in_(server_ids))

            q_metric = q_metric.group_by(models.Player.uuid)
            metric_rows = db.execute(q_metric).all()

            for uuid, ts in metric_rows:
                if not uuid or not ts:
                    continue
                u = str(uuid)
                if u in last_seen:
                    continue  # session/online 已经更可信，不覆盖
                dt_local = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(tz)
                last_seen[u] = (dt_local, False)
                source_map[u] = "metric"

        if not last_seen:
            return False, "没有查到会话数据（player_sessions），且也没有查到离线指标（metrics leave_game）"
        last_seen_copy = dict(last_seen)  # type: ignore[var-annotated]
        for u, (dt, is_online) in last_seen_copy.items():
            rec = db.query(models.Player).filter(models.Player.uuid == u).first()
            if rec is None or rec.is_bot or rec.player_name in ["Steve", "Alex", "Bot"] or str(rec.player_name).lower().startswith("bot_") or rec.player_name is None:
                # 过滤掉默认名和疑似机器人玩家
                last_seen.pop(u, None)

        # ----------------------------
        # 4) 排序 & 名字/QQ映射
        # ----------------------------
        sorted_items = sorted(last_seen.items(), key=lambda kv: kv[1][0], reverse=True)[: max(1, int(limit))]
        uuids = [u for u, _ in sorted_items]

        players = (
            db.query(models.Player.uuid, models.Player.player_name)
            .filter(models.Player.uuid.in_(uuids))
            .all()
        )
        name_map = {str(u): str(n or "Unknown") for u, n in players}
        qq_map = _resolve_player_qq_map(db, player_uuids=uuids)

        # ----------------------------
        # 5) pinned 逻辑（保持原样，但 score_text 增强：识别 metric）
        # ----------------------------
        pinned_row: Optional[RankRow] = None
        pinned_uuid_norm = (pinned_uuid or "").strip()
        if pinned_uuid_norm and pinned_uuid_norm not in set(uuids):
            info = last_seen.get(pinned_uuid_norm)
            if info is None:
                pinned_rank = 0
                score_text = "暂无数据"
                is_online = False
            else:
                dt_local, is_online = info
                higher = 0
                for _u, (dt2, _on2) in last_seen.items():
                    if dt2 > dt_local:
                        higher += 1
                pinned_rank = higher + 1
                dt_disp = dt_local.strftime("%Y-%m-%d %H:%M")
                src = source_map.get(pinned_uuid_norm, "session")
                if is_online:
                    score_text = f"{dt_disp}（在线）"
                elif src == "metric":
                    score_text = f"至少于 {dt_disp} 前"
                else:
                    score_text = dt_disp

            name = (pinned_name or "").strip()
            if not name:
                try:
                    rec = db.query(models.Player).filter(models.Player.uuid == pinned_uuid_norm).first()
                    name = str(rec.player_name or "Unknown") if rec else "Unknown"
                except Exception:
                    name = "Unknown"

            qq = None
            try:
                qq = _resolve_player_qq_map(db, player_uuids=[pinned_uuid_norm]).get(pinned_uuid_norm)
            except Exception:
                qq = None
            big_avatar = _qq_avatar_url(qq) if qq else _mc_avatar_url(pinned_uuid_norm)
            pinned_row = RankRow(
                rank=int(pinned_rank or 0),
                player_name=name,
                player_uuid=pinned_uuid_norm,
                score_text=score_text,
                avatar_big=big_avatar,
                avatar_small=_mc_avatar_url(pinned_uuid_norm),
                trend_values=None,
                is_pinned=True,
            )

    # ----------------------------
    # 6) 渲染 rows：同样识别 metric 的 score_text
    # ----------------------------
    rank_rows: List[RankRow] = []
    for idx, (uuid, (dt_local, is_online)) in enumerate(sorted_items, start=1):
        src = source_map.get(uuid, "session")
        if src == "metric":
            dt_disp = dt_local.strftime("%Y-%m-%d %H:%M")
        else:
            dt_disp = dt_local.strftime("%Y-%m-%d %H:%M:%S")

        if is_online:
            score_text = f"当前在线"
        elif src == "metric":
            score_text = f"至少于 {dt_disp} 前"
        else:
            score_text = dt_disp

        qq = qq_map.get(uuid)
        big_avatar = _qq_avatar_url(qq) if qq else _mc_avatar_url(uuid)
        rank_rows.append(
            RankRow(
                rank=idx,
                player_name=name_map.get(uuid, "Unknown"),
                player_uuid=uuid,
                score_text=score_text,
                avatar_big=big_avatar,
                avatar_small=_mc_avatar_url(uuid),
                trend_values=None,
            )
        )

    img = render_rank_image(
        title="最后在线榜",
        subtitle="最近一次在线时间（越晚越靠前）",
        rows=rank_rows,
        show_trend=False,
        pinned_row=pinned_row,
    )
    return True, _image_to_base64(img)


def build_placement_rank_image_b64(
    *,
    server_ids: List[int],
    limit: int,
    pinned_uuid: Optional[str] = None,
    pinned_name: Optional[str] = None,
) -> Tuple[bool, str]:
    """放置榜：统计 used.X 的次数，其中 X 是可挖掘的方块（存在于 mined.X 的项目）。
    
    这样可以过滤掉食物消耗、工具使用等非方块放置的统计。
    """
    with get_db_context() as db:
        # 1. 获取所有 mined.* 指标，提取方块名称
        mined_metrics = stats_service.resolve_metrics(
            db,
            ["mined.*"],
            namespace=stats_service.DEFAULT_NAMESPACE,
            include_discovered=True,
        )
        # mined_metrics 格式: ["mined.stone", "mined.dirt", ...]
        block_names = set()
        for m in mined_metrics:
            if m.startswith("mined."):
                block_name = m[6:]  # 去掉 "mined." 前缀
                block_names.add(block_name)
        
        if not block_names:
            return False, "没有查到可挖掘方块数据，无法生成放置榜"
        
        # 2. 构建 used.X 指标列表
        placement_metrics = [f"used.{block}" for block in block_names]
        
        # 3. 验证这些指标在数据库中存在
        valid_metrics = stats_service.resolve_metrics(
            db,
            placement_metrics,
            namespace=stats_service.DEFAULT_NAMESPACE,
            include_discovered=True,
        )
        
        if not valid_metrics:
            return False, "没有查到方块放置数据"
    
    # 4. 使用通用的 metric rank 构建函数
    return build_metric_rank_image_b64(
        title="放置榜",
        description="统计放置方块次数（只统计可挖掘的方块）",
        metrics=valid_metrics,
        server_ids=server_ids,
        limit=limit,
        scale=1.0,
        formatter=lambda x: _fmt_int(x),
        pinned_uuid=pinned_uuid,
        pinned_name=pinned_name,
    )


def build_rank_image_from_args_b64(
    args: List[str],
    server_ids: List[int],
    limit: int,
    pinned_uuid: Optional[str] = None,
    pinned_name: Optional[str] = None,
) -> Tuple[bool, str]:
    # 统一入口，便于在后台/进程池里调用
    args = list(args or [])
    if not args:
        args = ["挖掘榜"]

    query = (args[0] or "").strip()
    board = resolve_board(query) or resolve_board(query + "榜")

    if board and board.name == "航天榜":
        return build_space_rank_image_b64(
            server_ids=server_ids,
            limit=limit,
            pinned_uuid=pinned_uuid,
            pinned_name=pinned_name,
        )

    if board and board.name == "最后在线榜":
        return build_last_seen_rank_image_b64(
            server_ids=server_ids,
            limit=limit,
            pinned_uuid=pinned_uuid,
            pinned_name=pinned_name,
        )

    if board and board.name == "放置榜":
        return build_placement_rank_image_b64(
            server_ids=server_ids,
            limit=limit,
            pinned_uuid=pinned_uuid,
            pinned_name=pinned_name,
        )

    if board and board.metrics:
        return build_metric_rank_image_b64(
            title=board.name,
            description=board.description,
            metrics=board.metrics,
            server_ids=server_ids,
            limit=limit,
            scale=board.scale,
            formatter=board.formatter,
            pinned_uuid=pinned_uuid,
            pinned_name=pinned_name,
        )

    # 自定义指标榜
    metrics = [t for t in args if t and str(t).strip()]
    if not metrics:
        return False, "用法：##rank <榜单名> 或 ##rank <metric1> [metric2] ..."
    subtitle = " + ".join(metrics)
    return build_metric_rank_image_b64(
        title="自定义指标榜",
        description="自定义指标总量榜",
        subtitle=subtitle,
        metrics=metrics,
        server_ids=server_ids,
        limit=limit,
        scale=1.0,
        formatter=lambda x: f"{int(x):,}",
        pinned_uuid=pinned_uuid,
        pinned_name=pinned_name,
    )
