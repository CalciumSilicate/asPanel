import json
import base64
import io
import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Callable

from PIL import Image
from sqlalchemy import select, desc, func, and_
from sqlalchemy.orm import Session


from backend.core import crud, models
from backend.core.constants import BASE_DIR
from backend.core.database import get_db_context
from backend.core.logger import logger
from backend.core.utils import get_tz_info
from backend.services import stats_service
from backend.services.qq_stats_image import render_combined_view

DEFAULT_MAP_CONFIG = {
    "nether_json": str(BASE_DIR / "the_nether.json"),
    "end_json": str(BASE_DIR / "the_end.json"),
}

def _uuid_to_hyphenated(uuid_str: str) -> str:
    s = str(uuid_str or "").strip()
    if "-" in s:
        return s
    if len(s) == 32:
        # 8-4-4-4-12
        return f"{s[0:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}"
    return s


def _dim_to_int(d: Optional[str]) -> int:
    if d is None:
        return 0
    s = str(d).lower()
    if "nether" in s:
        return -1
    if "end" in s:
        return 1
    try:
        return int(s)
    except Exception:
        return 0


def _read_location_from_playerdata(server_path: str, player_uuid: str) -> Optional[Dict[str, Any]]:
    """从 <server_path>/server/world/playerdata/<UUIDhyphen>.dat 读取玩家位置（NBT）。"""
    try:
        import nbtlib  # local import: optional dependency
    except Exception:
        return None

    try:
        uuid_hyphen = _uuid_to_hyphenated(player_uuid)
        fp = Path(str(server_path)) / "server" / "world" / "playerdata" / f"{uuid_hyphen}.dat"
        if not fp.exists():
            return None

        nbt_obj = nbtlib.load(str(fp))  # type: ignore[attr-defined]
        root = getattr(nbt_obj, "root", nbt_obj)

        pos = root.get("Pos") if hasattr(root, "get") else None
        if not pos or len(pos) < 3:
            return None

        x = float(pos[0])
        z = float(pos[2])

        dim = None
        try:
            dim_tag = root.get("Dimension")
            if dim_tag is not None:
                dim = str(dim_tag)
        except Exception:
            dim = None

        yaw = None
        try:
            rot = root.get("Rotation")
            if rot and len(rot) >= 1:
                yaw = float(rot[0])
        except Exception:
            yaw = None

        out: Dict[str, Any] = {"x": x, "z": z, "dim": dim}
        if yaw is not None:
            out["yaw"] = yaw
        return out
    except Exception:
        logger.opt(exception=True).debug(f"读取 playerdata 位置失败 | server_path={server_path} uuid={player_uuid}")
        return None


def _resolve_map_json_path(path: Optional[str]) -> Optional[str]:
    """尽量把路径解析为可用的本地路径（兼容旧的相对路径写法）。"""
    if not path:
        return None
    s = str(path)
    if os.path.exists(s):
        return s
    try:
        candidate = str((BASE_DIR / s).resolve())
        if os.path.exists(candidate):
            return candidate
    except Exception:
        pass
    return s

def _ceil_to_10min(dt: datetime) -> datetime:
    minute = dt.minute % 10
    return dt + timedelta(minutes=(10 - minute), seconds=-dt.second, microseconds=-dt.microsecond)

def _floor_to_10min(dt: datetime) -> datetime:
    minute = dt.minute % 10
    return dt + timedelta(minutes=-minute, seconds=-dt.second, microseconds=-dt.microsecond)


def _parse_server_map_config(raw: Optional[str]) -> Dict[str, Optional[str]]:
    try:
        obj = json.loads(raw or "{}")
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        obj = {}
    # 兼容字段：旧/新 key 都尝试读一下
    nether_json = obj.get("nether_json") or obj.get("the_nether") or obj.get("the_overworld")
    end_json = obj.get("end_json") or obj.get("the_end")
    return {
        "nether_json": _resolve_map_json_path(nether_json),
        "end_json": _resolve_map_json_path(end_json),
    }


def _pick_map_config(
    db: Session,
    server_ids: List[int],
    server_dir_name: Optional[str],
    positions: Optional[List[models.PlayerPosition]],
) -> Dict[str, Optional[str]]:
    """根据在线服务器/最近坐标所属服务器，从 DB 里挑选最合适的 map json 配置。"""
    candidates: List[int] = []

    # 1) 最近一次坐标所属服务器（最贴近本次展示的 path/location）
    if positions:
        try:
            sid = int(getattr(positions[-1], "server_id", 0) or 0)
            if sid:
                candidates.append(sid)
        except Exception:
            pass

    # 2) 在线所在服务器（按目录名匹配）
    if server_dir_name and server_ids:
        for sid in server_ids:
            srv = crud.get_server_by_id(db, sid)
            if not srv:
                continue
            try:
                if os.path.basename(str(srv.path)) == str(server_dir_name):
                    candidates.append(int(sid))
                    break
            except Exception:
                continue

    # 3) 组内/数据源服务器兜底
    if server_ids:
        candidates.extend([int(s) for s in server_ids if s is not None])

    # 去重保序
    uniq: List[int] = []
    seen = set()
    for sid in candidates:
        if sid in seen:
            continue
        seen.add(sid)
        uniq.append(sid)

    # 优先找“配置了且文件存在”的
    for sid in uniq:
        srv = crud.get_server_by_id(db, sid)
        if not srv:
            continue
        cfg = _parse_server_map_config(getattr(srv, "map", None))
        if (cfg.get("nether_json") and os.path.exists(cfg["nether_json"])) or (cfg.get("end_json") and os.path.exists(cfg["end_json"])):
            return cfg

    # 次选：有配置但文件可能是相对路径/尚未落盘（交给渲染层再处理）
    for sid in uniq:
        srv = crud.get_server_by_id(db, sid)
        if not srv:
            continue
        cfg = _parse_server_map_config(getattr(srv, "map", None))
        if cfg.get("nether_json") or cfg.get("end_json"):
            return cfg

    # 最后兜底：使用仓库根目录的示例文件（如果存在）
    return {
        "nether_json": _resolve_map_json_path(DEFAULT_MAP_CONFIG.get("nether_json")),
        "end_json": _resolve_map_json_path(DEFAULT_MAP_CONFIG.get("end_json")),
    }


_TOOLS = [
    "axe",
    "sword",
    "pickaxe",
    "shovel",
    "hoe",
]
_MATS = ["wooden", "stone", "iron", "golden", "diamond", "netherite", "copper"]
_BREAK_METRICS = ["used.shears", *[f"used.{m}_{t}" for m in _MATS for t in _TOOLS]]
_WALK_METRICS = ['custom.sprint_one_cm','custom.walk_one_cm','custom.walk_under_water_one_cm','custom.walk_on_water_one_cm', 'custom.crouch_one_cm', 'custom.swim_one_cm']
_VEHICLE = ['boat','horse','minecart','pig','crouch']
_VEHICLE_METRICS = [f'custom.{v}_one_cm' for v in _VEHICLE]

def _TIME_FORMATTER(x: float) -> str:
    try:
        total_minutes = int(round(float(x) * 60))
    except Exception:
        return "0"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours:,}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if hours == 0 and minutes == 0:
        parts.append("<1m")
    return "".join(parts) if parts else "0"

def _DISTANCE_FORMATTER(x: float) -> str:
    try:
        km = float(x)
        abs_km = abs(km)
    except Exception:
        return "0"
    if abs_km >= 1_000:
        s = f"{km:,.1f}".rstrip("0").rstrip(".")
        return f"{s}km"
    if abs_km >= 1:
        s = f"{km:,.2f}".rstrip("0").rstrip(".")
        return f"{s}km"
    meters = km * 1000
    return f"{meters:,.2f}".rstrip("0").rstrip(".") + "m"

TOTAL_ITEMS = [
    ("上线次数", ["custom.leave_game"], 1, lambda x: x),
    ("在线时长(hr)", ["custom.play_one_minute", "custom.play_time"], 1 / 20 / 3600, _TIME_FORMATTER),
    # ("击杀玩家", ["custom.player_kills"], 1, "count"),
    # ("被玩家击杀", ["killed_by.player"], 1, "count"),
    ("挖掘方块", _BREAK_METRICS, 1, lambda x: int(x)),
    ("死亡次数", ["custom.deaths"], 1, lambda x: int(x)),
    ("鞘翅飞行", ["custom.aviate_one_cm"], 0.00001, _DISTANCE_FORMATTER),
    ("珍珠传送", ["custom.ender_pearl_one_cm"], 0.00001, _DISTANCE_FORMATTER),
    ("步行前进", _WALK_METRICS, 0.00001, _DISTANCE_FORMATTER),
    ("交通工具", _VEHICLE_METRICS, 0.00001, _DISTANCE_FORMATTER),
    ("使用烟花", ["custom.firework_boost", "used.firework_rocket"], 1, lambda x: int(x)),
    ("消耗不死图腾", ["used.totem_of_undying"], 1, lambda x: int(x)),
    ("破基岩", ["custom.break_bedrock"], 1, lambda x: int(x)),
]

CHART_ITEMS = [
    ("上线时长 (min)", ["custom.play_one_minute", "custom.play_time"], 1 / 20 / 60, True),
    # ("上线次数", ["custom.leave_game"], 1, True),
    ("移动 (m)", ['custom.aviate_one_cm', 'custom.ender_pearl_one_cm', 'custom.fly_one_cm', *_WALK_METRICS, *_VEHICLE_METRICS], 0.01, True),
    ("挖掘方块", _BREAK_METRICS, 1, True),
    ("破基岩", ["custom.break_bedrock"], 1, True),
    ("死亡次数", ["custom.deaths"], 1, True),
]


def convert_to_tz(dt: datetime) -> datetime:
    tz = get_tz_info()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)

def get_now_tz() -> datetime:
    tz = get_tz_info()
    return datetime.now(tz)

@dataclass
class TimeRange:
    start: datetime
    end: datetime
    real_start: datetime
    real_end: datetime
    granularity: str
    label: str
    x_labels: List[str]


def _format_number(val: float, formatter: Callable) -> Any:
    return formatter(val)


def _build_boundaries(tr: TimeRange) -> List[datetime]:
    step = tr.granularity
    if step == "10min":
        delta = timedelta(minutes=10)
    elif step == "1h":
        delta = timedelta(hours=1)
    elif step == "24h":
        delta = timedelta(days=1)
    elif step == "1month":
        delta = None
    else:
        delta = timedelta(hours=1)
    if delta:
        pts = []
        cur = tr.start
        while cur < tr.end:
            cur = cur + delta
            pts.append(cur)
        if not pts:
            logger.warning(f"No points generated in _build_boundaries | tr.start={tr.start} tr.end={tr.end} granularity={tr.granularity}")
            pts.append(tr.start)
        if pts[-1] != tr.end:
            pts.append(tr.end)
        return pts
    # month
    pts = []
    cur = tr.start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while cur <= tr.end:
        pts.append(cur)
        month = cur.month + 1
        year = cur.year + (1 if month > 12 else 0)
        month = month if month <= 12 else 1
        cur = cur.replace(year=year, month=month)
    if not pts:
        logger.warning(f"No points generated in _build_boundaries | tr.start={tr.start} tr.end={tr.end} granularity={tr.granularity}")
        pts.append(tr.start)
    if pts[-1] != tr.end:
        pts.append(tr.end)
    return pts


def _calc_preset(label: str, offset: int = 0) -> TimeRange:
    now = get_now_tz()
    if label == "1d":
        start = (now - timedelta(days=offset)).replace(hour=1, minute=0, second=0, microsecond=0)
        if offset:
            end = (start + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            end = start + timedelta(hours=now.hour)
        display = "今天" if offset == 0 else "昨天" if offset == 1 else f"{offset}天前"
        return TimeRange(start, end, start, end, "1h", f"{display}", [])
    if label == "1w":
        weekday = now.weekday()
        start = (now - timedelta(days=weekday + offset * 7 - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if offset:
            end = (start + timedelta(days=6))
        else:
            end = start + timedelta(days=now.weekday())
        week_num = int(start.strftime("%W")) + 1
        prefix = "本周" if offset == 0 else "上周" if offset == 1 else f"{offset}周前"
        return TimeRange(start, end, start, end, "24h", f"{prefix}（{start.year}年第{week_num}周）", [])
    if label == "1m":
        current_total_months = now.year * 12 + (now.month - 1)
        target_total_months = current_total_months - offset
        
        target_year = target_total_months // 12
        target_month = (target_total_months % 12) + 1
        start = now.replace(year=target_year, month=target_month, day=2, 
                            hour=0, minute=0, second=0, microsecond=0)
        if offset == 0:
            end = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            prefix = "本月"
        else:
            next_total_months = target_total_months + 1
            next_year = next_total_months // 12
            next_month = (next_total_months % 12) + 1
            
            end = now.replace(year=next_year, month=next_month, day=1, 
                            hour=0, minute=0, second=0, microsecond=0)
            
            prefix = "上月" if offset == 1 else f"{offset}个月前"

        return TimeRange(start, end, start, end, "24h", f"{prefix}（{start.year}年{start.month}月）", [])
    if label == "1y":
        target_year = now.year - offset
        start = now.replace(year=target_year, month=2, day=1, 
                            hour=0, minute=0, second=0, microsecond=0)

        end = now.replace(year=target_year + 1, month=1, day=1, 
                            hour=0, minute=0, second=0, microsecond=0)
        if offset == 0:
            prefix = "今年"
        else:
            prefix = "去年" if offset == 1 else f"{offset}年前"

        return TimeRange(start, end, start, end, "1month", f"{prefix}（{target_year}年）", [])
    if label == "all":
        start = now - timedelta(days=365 * 5)
        end = now

        return TimeRange(start, end, start, end, "1month", "全部记录", [])
    if label == "last":
        min = (now.minute // 10 + 1) * 10
        end = now.replace(microsecond=0, second=0, minute=min if min != 60 else 0)
        if min == 60:
            end = end + timedelta(hours=1)
        start = end - timedelta(days=1)
        start = convert_to_tz(start)
        end = convert_to_tz(end)
        label = f"上次在线({start.strftime('%Y-%m-%d %H:%M')} ~ {end.strftime('%Y-%m-%d %H:%M')})"
        return TimeRange(start, end, start, end, "10min", label, [])
    return TimeRange(now - timedelta(days=1), now, now - timedelta(days=1), now, "1h", "最近", [])


def _parse_custom_range(start_text: str, end_text: str) -> TimeRange:
    fmt = "%Y-%m-%d %H:%M"
    tz = get_tz_info()
    start = datetime.strptime(start_text, fmt).replace(tzinfo=tz)
    end = datetime.strptime(end_text, fmt).replace(tzinfo=tz)
    delta = end - start
    if delta < timedelta(days=1):
        granularity = "10min"
    elif delta < timedelta(days=7):
        granularity = "1h"
    elif delta < timedelta(days=365):
        granularity = "24h"
    else:
        granularity = "1month"
    return TimeRange(start, end, start, end, granularity, f"{start_text} ~ {end_text}", [])


def _time_range_from_tokens(tokens: List[str]) -> TimeRange:
    if not tokens:
        return _calc_preset("1d", 0)
    if len(tokens) == 1:
        return _calc_preset(tokens[0], 0)
    if len(tokens) == 2 and tokens[0] in {"1d", "1w", "1m", "1y", "all", "last"}:
        try:
            offset = int(tokens[1])
        except Exception:
            offset = 0
        return _calc_preset(tokens[0], offset)
    if len(tokens) >= 2:
        return _parse_custom_range(tokens[0], tokens[1])
    return _calc_preset("1d", 0)


def _series_to_xy(series: List[Tuple[int, int]], boundaries: List[datetime], unit: float, tr: TimeRange) -> Tuple[List[str], List[float]]:
    if not boundaries:
        return [], []
    ts_to_val = {int(ts): val for ts, val in series}
    x, y = [], []
    for b in boundaries:
        # label = b.strftime("%m-%d %H:%M")
        label = ""
        if tr.granularity == "1h":
            hour_num = b.hour - 1
            if hour_num == -1:
                hour_num = 23
            label = f'{hour_num}时'
        elif tr.granularity == "24h":
            day_num = b.day - 1
            if day_num == 0:
                day_num = (b - timedelta(days=1)).day
            label = f'{day_num}日'
        elif tr.granularity == "1month":
            month_num = b.month - 1
            if month_num == 0:
                month_num = 12
            label = f'{month_num}月'
        elif tr.granularity == "10min":
            label = int((b - boundaries[-1]).total_seconds() / 60)
        x.append(label)
        y.append(ts_to_val.get(int(b.timestamp()), 0) * unit)
    return x, y


def _get_player_by_name(name: str) -> Optional[models.Player]:
    with get_db_context() as db:
        return crud.get_player_by_name(db, name)


def _player_from_qq(sender_qq: Optional[str]) -> Optional[models.Player]:
    if not sender_qq:
        return None
    with get_db_context() as db:
        user = db.query(models.User).filter(models.User.qq == str(sender_qq)).first()
        if not user or not getattr(user, "bound_player_id", None):
            return None
        return db.query(models.Player).filter(models.Player.id == user.bound_player_id).first()


def _metrics_sum(series: List[Tuple[int, int]]) -> Tuple[int, int]:
    if not series:
        return 0, 0
    start_val = series[0][1]
    end_val = series[-1][1]
    return end_val, end_val - start_val


def _build_totals(player_uuid: str, tr: TimeRange, server_ids: List[int]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for label, metrics, unit, formatter in TOTAL_ITEMS:
        series_map = stats_service.get_total_series(
            player_uuids=[player_uuid], metrics=metrics, granularity=tr.granularity,
            start=tr.start.isoformat(), end=tr.end.isoformat(), server_ids=server_ids
        )
        series = series_map.get(player_uuid, [])
        total, delta = _metrics_sum(series)
        if total:
            out.append({"label": label, "total": total, "delta": delta, "label_total": _format_number(total * unit, formatter), "label_delta": _format_number(delta * unit, formatter)})
    return out


def _build_charts(player_uuid: str, tr: TimeRange, server_ids: List[int]) -> List[Dict[str, object]]:
    boundaries = _build_boundaries(tr)
    charts: List[Dict[str, object]] = []
    for label, metrics, unit, is_delta in CHART_ITEMS:
        if is_delta:
            series_map = stats_service.get_delta_series(
                player_uuids=[player_uuid], metrics=metrics, granularity=tr.granularity,
                start=tr.start.isoformat(), end=tr.end.isoformat(), server_ids=server_ids
            )
            series = series_map.get(player_uuid, [])
            x, y = _series_to_xy(series, boundaries, unit, tr)
            total = round(sum(val for val in y), 2)
            if not any(y):
                continue
        else:
            series_map = stats_service.get_total_series(
                player_uuids=[player_uuid], metrics=metrics, granularity=tr.granularity,
                start=tr.start.isoformat(), end=tr.end.isoformat(), fill_missing=True, server_ids=server_ids
            )
            series = series_map.get(player_uuid, [])
            x, y = _series_to_xy(series, boundaries, unit, tr)
            total = y[-1] if y else 0
        charts.append({"label": label, "x": x, "y": y, "total": total})
    return charts


def _get_last_seen_str(db: Session, player: models.Player, server_ids: List[int]) -> str:
    # 1. Check PlayerSession
    stmt = select(models.PlayerSession.logout_time).where(
        models.PlayerSession.player_uuid == player.uuid,
        models.PlayerSession.logout_time.isnot(None)
    )
    if server_ids:
        stmt = stmt.where(models.PlayerSession.server_id.in_(server_ids))
    
    last_session_time = db.scalar(stmt.order_by(models.PlayerSession.logout_time.desc()).limit(1))
    
    if last_session_time:
        last_session_time = convert_to_tz(last_session_time)
        return last_session_time.strftime("%Y-%m-%d %H:%M")
    
    # 2. Check Metrics (custom.leave_game)
    cat_key = "minecraft:custom"
    item_key = "minecraft:leave_game"
    metric_id = db.scalar(select(models.MetricsDim.metric_id).where(
        models.MetricsDim.category == cat_key,
        models.MetricsDim.item == item_key
    ))
    
    if not metric_id:
        return "N/A"
        
    latest_timestamp = 0
    now_ts = int(datetime.now(timezone.utc).timestamp())
    
    target_servers = server_ids if server_ids else []
    
    for sid in target_servers:
        q = select(models.PlayerMetrics.ts).where(
            models.PlayerMetrics.server_id == sid,
            models.PlayerMetrics.player_id == player.id,
            models.PlayerMetrics.metric_id == metric_id,
            models.PlayerMetrics.ts <= now_ts,
        ).order_by(models.PlayerMetrics.ts.desc()).limit(2)
        
        rows = db.execute(q).scalars().all()
        # "If the found value is the first value for that player in that server (no earlier values) then discard it."
        # If we have at least 2 rows, the latest (rows[0]) has a predecessor (rows[1]).
        if len(rows) >= 2:
            ts = rows[0]
            if ts > latest_timestamp:
                latest_timestamp = ts
    
    if latest_timestamp > 0:
        dt = datetime.fromtimestamp(latest_timestamp, tz=timezone.utc)
        dt = convert_to_tz(dt)
        return f"至少于 {dt.strftime('%Y-%m-%d %H:%M')} 前"
    
    return "N/A"


def _get_session_range_for_last(db: Session, player: models.Player, server_ids: List[int], offset: int, is_online: bool) -> Optional[TimeRange]:
    stmt = select(models.PlayerSession).where(
        models.PlayerSession.player_uuid == player.uuid
    )
    if server_ids:
        stmt = stmt.where(models.PlayerSession.server_id.in_(server_ids))
    
    stmt = stmt.order_by(models.PlayerSession.login_time.desc())
    
    # If online, offset=1 means index 1 (previous). If offline, offset=1 means index 0 (last).
    idx = (1 if is_online else 0) + (offset - 1)
    limit = idx + 1
    
    sessions = db.execute(stmt.limit(limit)).scalars().all()

    if 0 <= idx < len(sessions):
        s = sessions[idx]
        start = s.login_time
        end = s.logout_time
        start = convert_to_tz(start)
        if not end:
            end = datetime.now(timezone.utc)
        end = convert_to_tz(end)
        if offset == 0:
            label = f"上次在线({start.strftime('%Y-%m-%d %H:%M')} ~ {end.strftime('%Y-%m-%d %H:%M')})"
        else:
            label = f"倒数第{offset + 1}次在线({start.strftime('%Y-%m-%d %H:%M')} ~ {end.strftime('%Y-%m-%d %H:%M')})"
        c_start = _floor_to_10min(start)
        c_end = _ceil_to_10min(end) if end else None
        
        return TimeRange(c_start, c_end, start, end, "10min", label, [])
    
    return None


def _calculate_time_range(tokens: List[str], player: models.Player, is_online: bool, db: Session, server_ids: List[int]) -> TimeRange:
    now = get_now_tz()
    
    is_last = False
    offset = 0
    if tokens and tokens[0] == "last":
        is_last = True
        offset = 1
        if len(tokens) > 1 and tokens[1].isdigit():
            offset = int(tokens[1])
    
    if is_last:
        tr = _get_session_range_for_last(db, player, server_ids, offset, is_online)
        if tr:
            return tr
        return _calc_preset("1d", 0)
    
    if is_online and not tokens:
        # Online default: Login to Now, 10min
        stmt = select(models.PlayerSession.login_time).where(
            models.PlayerSession.player_uuid == player.uuid,
            models.PlayerSession.logout_time.is_(None)
        )
        if server_ids:
            stmt = stmt.where(models.PlayerSession.server_id.in_(server_ids))
        
        start = db.scalar(stmt.order_by(models.PlayerSession.login_time.desc()).limit(1))
        if not start:
            start = now - timedelta(hours=1)
        end = _ceil_to_10min(get_now_tz())
        start = convert_to_tz(start)
        label = f"本次在线({start.strftime('%Y-%m-%d %H:%M')} ~ 现在)"
        c_start = _floor_to_10min(start)
        return TimeRange(c_start, end, start, get_now_tz(), "10min", label, [])
    
    # Offline default or specific tokens
    if not tokens:
        return _calc_preset("1d", 0)
        
    return _time_range_from_tokens(tokens)


def _image_to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def build_stats_picture(
    player: models.Player,
    tr: TimeRange,
    avatars: Dict[str, str],
    is_online: bool = False,
    server_name: Optional[str] = None,
    server_ids: List[int] = None,
    data_source_text: str = "",
    last_seen_text: Optional[str] = None
) -> str:
    # 构造头像链接（如果未提供）
    qq_avatar = avatars.get("qq")
    if not qq_avatar and avatars.get("sender_qq"):
        # 使用 QQ 官方头像接口
        qq_avatar = f"http://q1.qlogo.cn/g?b=qq&nk={avatars['sender_qq']}&s=640"

    mc_avatar = avatars.get("mc")
    if not mc_avatar:
        # 使用 Cravatar 头像接口
        # 注意：这里假设 player.uuid 是带连字符的，如果不是需要处理
        # Cravatar 支持无连字符 UUID，但带连字符更标准
        mc_avatar = f"https://cravatar.eu/helmavatar/{player.uuid}/128.png"

    data = {
        "qq_avatar": qq_avatar,
        "mc_avatar": mc_avatar,
        "player_name": player.player_name or "Unknown",
        "uuid": player.uuid,
        "last_seen": last_seen_text, 
        "time_range_label": tr.label,
        "is_online": is_online,
        "in_server": server_name,
        "data_source_text": data_source_text,
        "generated_at": get_now_tz().strftime("%Y-%m-%d %H:%M:%S")
    }
    # 默认使用 [3] 如果未提供 server_ids，防止报错
    effective_server_ids = server_ids if server_ids else [3]

    data["totals"] = _build_totals(player.uuid, tr, effective_server_ids)
    data["charts"] = _build_charts(player.uuid, tr, effective_server_ids)
    # 位置/路径
    map_config = {
        "nether_json": _resolve_map_json_path(DEFAULT_MAP_CONFIG.get("nether_json")),
        "end_json": _resolve_map_json_path(DEFAULT_MAP_CONFIG.get("end_json")),
    }
    positions: List[models.PlayerPosition] = []
    fallback_location: Optional[Dict[str, Any]] = None
    with get_db_context() as db:
        try:
            positions = crud.get_player_positions(db, player.id, tr.real_start.astimezone(timezone.utc), tr.real_end.astimezone(timezone.utc), effective_server_ids)
        except Exception:
            positions = []
        # 若该时段无轨迹，则回退到该数据源服务器内“最后一次”位置（避免玩家未移动导致无轨迹）
        if not positions:
            try:
                q = db.query(models.PlayerPosition).filter(models.PlayerPosition.player_id == player.id)
                if effective_server_ids:
                    q = q.filter(models.PlayerPosition.server_id.in_(effective_server_ids))
                last_pos = q.order_by(models.PlayerPosition.ts.desc()).first()
                if last_pos:
                    positions = [last_pos]
            except Exception:
                positions = positions or []
        # 若数据库仍无位置数据，则从首个数据源服务器的 playerdata 文件读取
        if not positions:
            try:
                sid0 = int(effective_server_ids[0]) if effective_server_ids else None
                srv = crud.get_server_by_id(db, sid0) if sid0 else None
                if srv and getattr(srv, "path", None):
                    fallback_location = _read_location_from_playerdata(str(srv.path), player.uuid)
            except Exception:
                fallback_location = fallback_location
        try:
            map_config = _pick_map_config(db, effective_server_ids, server_name, positions)
        except Exception:
            pass
    if positions:
        pts = [(float(p.x), float(p.z), _dim_to_int(p.dim)) for p in positions if p.x is not None and p.z is not None]
        if len(pts) == 1:
            data["location"] = {"x": pts[0][0], "z": pts[0][1], "dim": pts[0][2]}
        elif len(pts) > 1:
            data["path"] = pts
    elif fallback_location and fallback_location.get("x") is not None and fallback_location.get("z") is not None:
        loc = {
            "x": float(fallback_location["x"]),
            "z": float(fallback_location["z"]),
            "dim": _dim_to_int(fallback_location.get("dim")),
        }
        if fallback_location.get("yaw") is not None:
            try:
                loc["yaw"] = float(fallback_location["yaw"])
            except Exception:
                pass
        data["location"] = loc
        

    img = render_combined_view(data, map_config)
    logger.debug(f"生成统计图成功 | player={player.player_name} uuid={player.uuid} range={tr.start}~{tr.end} path={'yes' if 'path' in data else 'no'}")
    return _image_to_base64(img)


def bind_player_for_user(sender_qq: str, target_name: str) -> str:
    with get_db_context() as db:
        user = db.query(models.User).filter(models.User.qq == str(sender_qq)).first()
        if not user:
            return "未找到对应的面板用户，无法绑定"
        player = crud.get_player_by_name(db, target_name)
        if not player:
            return f"未找到玩家 {target_name} 的数据"
        user.bound_player_id = player.id
        db.add(user)
        db.commit()
        db.refresh(user)
        return f"已将账号绑定到玩家 {target_name}"


def _get_qq_from_player(player_id: int) -> Optional[str]:
    with get_db_context() as db:
        user = db.query(models.User).filter(models.User.bound_player_id == player_id).first()
        if user and user.qq:
            return user.qq
    return None

def build_report_from_command(
    tokens: List[str],
    sender_qq: Optional[str],
    avatars: Dict[str, str],
    online_players_map: Optional[Dict[str, Any]] = None,
    group_id: Optional[int] = None
) -> Tuple[bool, str]:
    # if tokens and tokens[0].lower() == "bind":
    #     if len(tokens) < 2:
    #         return False, "用法：## bind <玩家名>"
    #     return False, bind_player_for_user(sender_qq or "", tokens[1])

    with get_db_context() as db:
        # 获取服务器组配置
        server_ids = []  # 默认
        data_source_text = ""
        
        if group_id:
            group = crud.get_server_link_group_by_id(db, group_id)
            if group:
                try:
                    import json
                    ds_ids = json.loads(group.data_source_ids or "[]")
                    srv_ids = json.loads(group.server_ids or "[]")
                    target_ids = ds_ids if ds_ids else srv_ids
                    if target_ids:
                        server_ids = [int(i) for i in target_ids]
                        
                        # 构建数据来源文本
                        names = []
                        for sid in server_ids:
                            s = crud.get_server_by_id(db, sid)
                            if s:
                                names.append(s.name)
                        if names:
                            data_source_text = f"数据来源：{', '.join(names)}"
                except Exception:
                    logger.warning(f"解析服务器组 {group_id} 配置失败，使用默认配置")

        target_qq = None
        player = None
        range_tokens = []

        # 尝试解析目标玩家
        if not tokens and sender_qq:
            # Case 1: ## (无参数，查自己)
            user = db.query(models.User).filter(models.User.qq == str(sender_qq)).first()
            if user and getattr(user, "bound_player_id", None):
                player = db.query(models.Player).filter(models.Player.id == user.bound_player_id).first()
            target_qq = sender_qq
            range_tokens = []
        else:
            # Case 2: 有参数，可能是 "## 玩家名 [args]" 或 "## [args]" (查自己)
            possible_name = tokens[0]
            found_player = crud.get_player_by_name(db, possible_name)
            
            if found_player:
                # tokens[0] 是有效的玩家名 -> ## 玩家名 [args]
                player = found_player
                range_tokens = tokens[1:]
                
                # 尝试查找该玩家绑定的 QQ
                user = db.query(models.User).filter(models.User.bound_player_id == player.id).first()
                if user and user.qq:
                    target_qq = user.qq
                elif sender_qq and not target_qq:
                    # 如果查的是自己（名字匹配），fallback到sender_qq
                    user_sender = db.query(models.User).filter(models.User.qq == str(sender_qq)).first()
                    if user_sender and user_sender.bound_player_id == player.id:
                        target_qq = sender_qq

            else:
                # tokens[0] 不是玩家名 -> 假设是 ## [args] (查自己)
                # 例如 ## last, ## 1d
                if tokens[0] not in ['last', '1w', '1m', '1y', '1d', 'all']:
                    return False, f"未找到玩家 '{possible_name}' 的数据"
                if sender_qq:
                    user = db.query(models.User).filter(models.User.qq == str(sender_qq)).first()
                    if user and getattr(user, "bound_player_id", None):
                        player = db.query(models.Player).filter(models.Player.id == user.bound_player_id).first()
                    target_qq = sender_qq
                    range_tokens = tokens # 所有 tokens 都是参数

        if not player:
            if tokens:
                 return False, f"未找到玩家 '{tokens[0]}'，且您尚未绑定无法查询自身。"
            return False, "未找到玩家或尚未绑定（请前往：http://assx.top:5173/ 注册，注册时绑定QQ与游戏名）"

        # 设置用于生成头像的 QQ 号
        if target_qq:
            avatars["sender_qq"] = target_qq
        else:
            # 明确移除 sender_qq，避免使用了命令发送者的 QQ 头像
            avatars.pop("sender_qq", None)
            avatars.pop("qq", None)

        # 判断在线状态
        is_online = False
        server_name = None
        if online_players_map and player.player_name:
            for srv_name, players in online_players_map.items():
                if player.player_name in players:
                    is_online = True
                    server_name = srv_name
                    break

        tr = _calculate_time_range(range_tokens, player, is_online, db, server_ids)
        
        last_seen_text = None
        if not is_online:
            last_seen_text = _get_last_seen_str(db, player, server_ids)

        try:
            img_b64 = build_stats_picture(
                player, tr, avatars, is_online=is_online, server_name=server_name,
                server_ids=server_ids, data_source_text=data_source_text,
                last_seen_text=last_seen_text
            )
        except Exception as exc:
            logger.opt(exception=exc).warning("生成统计图失败")
            return False, "生成统计图失败，请稍后重试"
        return True, img_b64
