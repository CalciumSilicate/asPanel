from fastapi import APIRouter, Query
from typing import List, Tuple, Optional, Dict

from backend.services import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/series/delta", response_model=Dict[str, List[Tuple[int, int]]])
def api_delta_series(
    player_uuid: List[str] = Query(..., description="玩家 UUID 列表，可重复传参，如 ?player_uuid=a&player_uuid=b"),
    metric: List[str] = Query(..., description="指标列表，可重复传参，如 ?metric=custom.play_one_minute&metric=minecraft:used.minecraft:diamond_pickaxe"),
    granularity: str = Query("10min", description="粒度：10min,30min,1h,12h,24h,1week,1month,6month,1year"),
    start: Optional[str] = Query(None, description="起始时间 ISO8601，可为空"),
    end: Optional[str] = Query(None, description="结束时间 ISO8601，可为空"),
    namespace: str = Query("minecraft", description="命名空间，默认 minecraft"),
):
    """按时间桶返回 delta（ticks）序列（按玩家分别返回）。"""
    return stats_service.get_delta_series(
        player_uuids=player_uuid,
        metrics=metric,
        granularity=granularity,
        start=start,
        end=end,
        namespace=namespace,
    )


@router.get("/series/total", response_model=Dict[str, List[Tuple[int, int]]])
def api_total_series(
    player_uuid: List[str] = Query(..., description="玩家 UUID 列表，可重复传参，如 ?player_uuid=a&player_uuid=b"),
    metric: List[str] = Query(..., description="指标列表，可重复传参，如 ?metric=custom.play_one_minute&metric=minecraft:used.minecraft:diamond_pickaxe"),
    granularity: str = Query("10min", description="粒度：10min,30min,1h,12h,24h,1week,1month,6month,1year"),
    start: Optional[str] = Query(None, description="起始时间 ISO8601，可为空"),
    end: Optional[str] = Query(None, description="结束时间 ISO8601，可为空"),
    namespace: str = Query("minecraft", description="命名空间，默认 minecraft"),
):
    """按时间桶返回 total（ticks）序列（按玩家分别返回；多指标累加）。"""
    return stats_service.get_total_series(
        player_uuids=player_uuid,
        metrics=metric,
        granularity=granularity,
        start=start,
        end=end,
        namespace=namespace,
    )

