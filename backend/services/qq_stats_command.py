import base64
import io
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from PIL import Image

from backend.core import crud, models
from backend.core.database import get_db_context
from backend.core.logger import logger
from backend.core.utils import get_tz_info
from backend.services import stats_service
from backend.services.qq_stats_image import render_combined_view

MAP_CONFIG = {
    "nether_json": "the_nether.json",
    "end_json": "the_end.json",
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

TOTAL_ITEMS = [
    ("上线次数", ["custom.leave_game"], 1, "count"),
    ("在线时长 (hr)", ["custom.play_one_minute", "custom.play_time"], 1 / 20 / 3600, "round1"),
    ("挖掘方块", _BREAK_METRICS, 1, "count"),
    ("飞行距离", ["custom.aviate_one_cm"], 0.00001, "round2"),
    ("珍珠距离", ["custom.ender_pearl_one_cm"], 0.00001, "round2"),
    ("烟花次数", ["custom.firework_boost"], 1, "count"),
    ("图腾次数", ["used.totem_of_undying"], 1, "count"),
    ("破基岩次数", ["custom.break_bedrock"], 1, "count"),
]

CHART_ITEMS = [
    ("上线活跃度 (min)", ["custom.play_one_minute", "custom.play_time"], 1 / 20 / 60, True),
    ("鞘翅飞行距离 (m)", ["custom.aviate_one_cm"], 0.01, True),
    ("挖掘方块", _BREAK_METRICS, 1, False),
]


@dataclass
class TimeRange:
    start: datetime
    end: datetime
    granularity: str
    label: str
    x_labels: List[str]


def _format_number(val: float, mode: str) -> float:
    if mode == "round1":
        return round(val, 1)
    if mode == "round2":
        return round(val, 2)
    return int(val)


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
        while cur <= tr.end:
            pts.append(cur)
            cur = cur + delta
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
    if pts[-1] != tr.end:
        pts.append(tr.end)
    return pts


def _calc_preset(label: str, offset: int = 0) -> TimeRange:
    now = datetime.now()
    if label == "1d":
        start = (now - timedelta(days=offset)).replace(hour=1, minute=0, second=0, microsecond=0)
        if offset:
            end = (start + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            end = start + timedelta(hours=now.hour)
        display = "今天" if offset == 0 else "昨天" if offset == 1 else f"{offset}天前"
        return TimeRange(start, end, "1h", f"{display}", [])
    if label == "1w":
        weekday = now.weekday()
        start = (now - timedelta(days=weekday + offset * 7 - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if offset:
            end = (start + timedelta(days=6))
        else:
            end = start + timedelta(days=now.weekday())
        week_num = int(start.strftime("%W")) + 1
        prefix = "本周" if offset == 0 else "上周" if offset == 1 else f"{offset}周前"
        return TimeRange(start, end, "24h", f"{prefix}（{start.year}年第{week_num}周）", [])
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

        return TimeRange(start, end, "24h", f"{prefix}（{start.year}年{start.month}月）", [])
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

        return TimeRange(start, end, "1month", f"{prefix}（{target_year}年）", [])
    if label == "all":
        start = now - timedelta(days=365 * 5)
        end = now

        return TimeRange(start, end, "1month", "全部记录", [])
    if label == "last":
        min = (now.minute // 10 + 1) * 10
        end = now.replace(microsecond=0, second=0, minute=min if min != 60 else 0)
        if min == 60:
            end + timedelta(hours=1)
        start = end - timedelta(days=1)
        return TimeRange(start, end, "10min", "上次在线", [])
    return TimeRange(now - timedelta(days=1), now, "1h", "最近", [])


def _parse_custom_range(start_text: str, end_text: str) -> TimeRange:
    fmt = "%Y-%m-%d %H:%M"
    start = datetime.strptime(start_text, fmt)
    end = datetime.strptime(end_text, fmt)
    delta = end - start
    if delta < timedelta(days=1):
        granularity = "10min"
    elif delta < timedelta(days=7):
        granularity = "1h"
    elif delta < timedelta(days=365):
        granularity = "24h"
    else:
        granularity = "1month"
    return TimeRange(start, end, granularity, f"{start_text} ~ {end_text}", [])


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
            label = b.hour - 1
        elif tr.granularity == "24h":
            label = b.day - 1
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


def _build_totals(player_uuid: str, tr: TimeRange) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for label, metrics, unit, mode in TOTAL_ITEMS:
        series_map = stats_service.get_total_series(
            player_uuids=[player_uuid], metrics=metrics, granularity=tr.granularity,
            start=tr.start.isoformat(), end=tr.end.isoformat(), server_ids=[3]
        )
        series = series_map.get(player_uuid, [])
        total, delta = _metrics_sum(series)
        out.append({"label": label, "total": _format_number(total * unit, mode), "delta": _format_number(delta * unit, mode)})
    return out


def _build_charts(player_uuid: str, tr: TimeRange) -> List[Dict[str, object]]:
    boundaries = _build_boundaries(tr)
    charts: List[Dict[str, object]] = []
    for label, metrics, unit, is_delta in CHART_ITEMS:
        if is_delta:
            series_map = stats_service.get_delta_series(
                player_uuids=[player_uuid], metrics=metrics, granularity=tr.granularity,
                start=tr.start.isoformat(), end=tr.end.isoformat(), server_ids=[3]
            )
            series = series_map.get(player_uuid, [])
            x, y = _series_to_xy(series, boundaries, unit, tr)
            total = round(sum(val for val in y), 2)
            logger.debug([player_uuid])
            logger.debug(metrics)
            logger.debug(tr.granularity)
            logger.debug(tr.start.isoformat())
            logger.debug(tr.end.isoformat())
        
            logger.debug(label)
            logger.debug(', '.join(str(i) for i in x))
            logger.debug(', '.join(str(i) for i in y))
            if not any(y):
                continue
        else:
            series_map = stats_service.get_total_series(
                player_uuids=[player_uuid], metrics=metrics, granularity=tr.granularity,
                start=tr.start.isoformat(), end=tr.end.isoformat(), fill_missing=True, server_ids=[3]
            )
            series = series_map.get(player_uuid, [])
            x, y = _series_to_xy(series, boundaries, unit, tr)
            total = y[-1] if y else 0
            logger.debug([player_uuid])
            logger.debug(metrics)
            logger.debug(tr.granularity)
            logger.debug(tr.start.isoformat())
            logger.debug(tr.end.isoformat())
        
            logger.debug(label)
            logger.debug(', '.join(str(i) for i in x))
            logger.debug(', '.join(str(i) for i in y))
        charts.append({"label": label, "x": x, "y": y, "total": total})
    return charts


def _image_to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def build_stats_picture(player: models.Player, tr: TimeRange, avatars: Dict[str, str]) -> str:
    data = {
        "qq_avatar": avatars.get("qq"),
        "mc_avatar": avatars.get("mc"),
        "player_name": player.player_name or "Unknown",
        "uuid": player.uuid,
        "last_seen": datetime.now(get_tz_info()).strftime("%Y-%m-%d %H:%M"),
        "time_range_label": tr.label,
    }
    data["totals"] = _build_totals(player.uuid, tr)
    data["charts"] = _build_charts(player.uuid, tr)
    img = render_combined_view(data, MAP_CONFIG)
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


def build_report_from_command(tokens: List[str], sender_qq: Optional[str], avatars: Dict[str, str]) -> Tuple[bool, str]:
    if tokens and tokens[0].lower() == "bind":
        if len(tokens) < 2:
            return False, "用法：## bind <玩家名>"
        return False, bind_player_for_user(sender_qq or "", tokens[1])

    if not tokens and sender_qq:
        player = _player_from_qq(sender_qq)
    else:
        player_name = tokens[0] if tokens else None
        player = _get_player_by_name(player_name) if player_name else _player_from_qq(sender_qq)
    if not player:
        return False, "未找到玩家或尚未绑定"

    range_tokens = tokens[1:] if len(tokens) > 1 else []
    tr = _time_range_from_tokens(range_tokens)
    try:
        img_b64 = build_stats_picture(player, tr, avatars)
    except Exception as exc:
        logger.opt(exception=exc).warning("生成统计图失败")
        return False, "生成统计图失败，请稍后重试"
    return True, img_b64
