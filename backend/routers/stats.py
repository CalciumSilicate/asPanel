from fastapi import APIRouter, Query
from typing import List, Tuple, Optional, Dict

from backend.services import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/series/delta", response_model=Dict[str, List[Tuple[int, int]]])
def api_delta_series(
    player_uuid: List[str] = Query(..., description="玩家 UUID 列表，可重复传参，如 ?player_uuid=a&player_uuid=b"),
    metric: List[str] = Query(..., description="指标列表，可重复传参，如 ?metric=custom.play_one_minute&metric=minecraft:used.minecraft:diamond_pickaxe"),
    granularity: str = Query("10min", description="粒度：10min,20min,30min,1h,6h,12h,24h,1week,1month,3month,6month,1year"),
    start: Optional[str] = Query(None, description="起始时间 ISO8601，可为空"),
    end: Optional[str] = Query(None, description="结束时间 ISO8601，可为空"),
    namespace: str = Query("minecraft", description="命名空间，默认 minecraft"),
    server_id: Optional[List[int]] = Query(None, description="参与聚合的数据源服务器ID；留空聚合全部"),
):
    """按时间桶返回 delta（ticks）序列（按玩家分别返回）。"""
    return stats_service.get_delta_series(
        player_uuids=player_uuid,
        metrics=metric,
        granularity=granularity,
        start=start,
        end=end,
        namespace=namespace,
        server_ids=server_id,
    )


@router.get("/series/total", response_model=Dict[str, List[Tuple[int, int]]])
def api_total_series(
    player_uuid: List[str] = Query(..., description="玩家 UUID 列表，可重复传参，如 ?player_uuid=a&player_uuid=b"),
    metric: List[str] = Query(..., description="指标列表，可重复传参，如 ?metric=custom.play_one_minute&metric=minecraft:used.minecraft:diamond_pickaxe"),
    granularity: str = Query("10min", description="粒度：10min,20min,30min,1h,6h,12h,24h,1week,1month,3month,6month,1year"),
    start: Optional[str] = Query(None, description="起始时间 ISO8601，可为空"),
    end: Optional[str] = Query(None, description="结束时间 ISO8601，可为空"),
    namespace: str = Query("minecraft", description="命名空间，默认 minecraft"),
    server_id: Optional[List[int]] = Query(None, description="参与聚合的数据源服务器ID；留空聚合全部"),
):
    """按时间桶返回 total（ticks）序列（按玩家分别返回；多指标累加）。"""
    return stats_service.get_total_series(
        player_uuids=player_uuid,
        metrics=metric,
        granularity=granularity,
        start=start,
        end=end,
        namespace=namespace,
        server_ids=server_id,
    )


@router.get("/metrics", response_model=List[str])
def list_metrics(q: Optional[str] = Query(None, description="关键字过滤"),
                 limit: int = Query(50, ge=1, le=500, description="最大返回数"),
                 namespace: str = Query("minecraft", description="命名空间")):
    with stats_service.SessionLocal() as db:  # 重用会话工厂
        return stats_service.list_metrics(db, q=q, limit=limit, namespace=namespace)


@router.get("/leaderboard/total")
def leaderboard_total(metric: List[str] = Query(..., description="指标列表，多值"),
                      at: Optional[str] = Query(None, description="统计时刻，ISO；默认当前"),
                      server_id: Optional[List[int]] = Query(None, description="数据源服务器ID"),
                      namespace: str = Query("minecraft", description="命名空间"),
                      limit: int = Query(50, ge=1)):
    return stats_service.leaderboard_total(metrics=metric, at=at, server_ids=server_id,
                                           namespace=namespace, limit=limit)


@router.get("/leaderboard/delta")
def leaderboard_delta(metric: List[str] = Query(..., description="指标列表，多值"),
                      start: Optional[str] = Query(None, description="起始时间，ISO"),
                      end: Optional[str] = Query(None, description="结束时间，ISO"),
                      server_id: Optional[List[int]] = Query(None, description="数据源服务器ID"),
                      namespace: str = Query("minecraft", description="命名空间"),
                      limit: int = Query(50, ge=1)):
    return stats_service.leaderboard_delta(metrics=metric, start=start, end=end,
                                           server_ids=server_id, namespace=namespace, limit=limit)
