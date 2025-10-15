from fastapi import APIRouter, Query
from typing import List, Tuple, Optional

from backend.services import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/series/delta", response_model=List[Tuple[int, int]])
def api_delta_series(
    player_uuid: str = Query(..., description="玩家 UUID"),
    metric: str = Query(..., description="指标，例如 'custom.play_one_minute' 或 'minecraft:custom.minecraft:play_one_minute'"),
    granularity: str = Query("10min", description="聚合粒度，如 10min,1h,6h 等"),
    start: Optional[str] = Query(None, description="起始时间 ISO8601，可为空"),
    end: Optional[str] = Query(None, description="结束时间 ISO8601，可为空"),
    namespace: str = Query("minecraft", description="命名空间，默认 minecraft"),
):
    """按时间桶返回 delta（ticks）序列。"""
    return stats_service.get_delta_series(
        player_uuid=player_uuid,
        metric=metric,
        granularity=granularity,
        start=start,
        end=end,
        namespace=namespace,
    )


@router.get("/series/total", response_model=List[Tuple[int, int]])
def api_total_series(
    player_uuid: str = Query(..., description="玩家 UUID"),
    metric: str = Query(..., description="指标，例如 'custom.play_one_minute' 或 'minecraft:custom.minecraft:play_one_minute'"),
    granularity: str = Query("10min", description="聚合粒度，如 10min,1h,6h 等"),
    start: Optional[str] = Query(None, description="起始时间 ISO8601，可为空"),
    end: Optional[str] = Query(None, description="结束时间 ISO8601，可为空"),
    namespace: str = Query("minecraft", description="命名空间，默认 minecraft"),
):
    """按时间桶返回重建的 total（ticks）序列。"""
    return stats_service.get_total_series(
        player_uuid=player_uuid,
        metric=metric,
        granularity=granularity,
        start=start,
        end=end,
        namespace=namespace,
    )

