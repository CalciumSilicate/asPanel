# backend/routers/stats.py

import json
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Tuple, Optional, Dict

from backend.services import stats_service
from backend.core import crud, models
from backend.core.database import get_db
from backend.core.auth import require_role, get_current_user
from backend.core.schemas import Role
from backend.services.permission_service import PermissionService

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _get_allowed_server_ids(db: Session, user: models.User) -> Optional[set]:
    """
    获取用户允许访问的服务器 ID 集合。
    平台管理员返回 None（表示可以访问所有）。
    普通用户返回其组权限中可访问的服务器 ID 集合。
    """
    if PermissionService.is_platform_admin(user):
        return None  # 可以访问所有
    
    accessible_ids = PermissionService.get_accessible_servers(db, user)
    return set(accessible_ids) if accessible_ids else set()


def _filter_server_ids(requested_ids: Optional[List[int]], allowed_ids: Optional[set]) -> Optional[List[int]]:
    """
    根据允许的服务器 ID 过滤请求的服务器 ID。
    如果 allowed_ids 为 None，表示允许所有，直接返回 requested_ids。
    如果 requested_ids 为 None，返回 allowed_ids 转为列表（或 None）。
    """
    if allowed_ids is None:
        return requested_ids
    
    if requested_ids is None:
        return list(allowed_ids) if allowed_ids else []
    
    # 只返回用户有权限的服务器 ID
    return [sid for sid in requested_ids if sid in allowed_ids]


@router.get("/series/delta", response_model=Dict[str, List[Tuple[int, int]]])
def api_delta_series(
    player_uuid: List[str] = Query(..., description="玩家 UUID 列表，可重复传参，如 ?player_uuid=a&player_uuid=b"),
    metric: List[str] = Query(..., description="指标列表（支持通配符），可重复传参，如 ?metric=custom.play_one_minute&metric=minecraft:used.minecraft:diamond_pickaxe 或 ?metric=broken.* 或 ?metric=*.diamond_pickaxe"),
    granularity: str = Query("10min", description="粒度：10min,20min,30min,1h,6h,12h,24h,1week,1month,3month,6month,1year"),
    start: Optional[str] = Query(None, description="起始时间 ISO8601，可为空"),
    end: Optional[str] = Query(None, description="结束时间 ISO8601，可为空"),
    namespace: str = Query("minecraft", description="命名空间，默认 minecraft"),
    server_id: Optional[List[int]] = Query(None, description="参与聚合的数据源服务器ID；留空聚合全部"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(Role.USER)),
):
    """按时间桶返回 delta（ticks）序列（按玩家分别返回）。"""
    allowed_ids = _get_allowed_server_ids(db, current_user)
    filtered_server_ids = _filter_server_ids(server_id, allowed_ids)
    
    return stats_service.get_delta_series(
        player_uuids=player_uuid,
        metrics=metric,
        granularity=granularity,
        start=start,
        end=end,
        namespace=namespace,
        server_ids=filtered_server_ids,
    )


@router.get("/series/total", response_model=Dict[str, List[Tuple[int, int]]])
def api_total_series(
    player_uuid: List[str] = Query(..., description="玩家 UUID 列表，可重复传参，如 ?player_uuid=a&player_uuid=b"),
    metric: List[str] = Query(..., description="指标列表（支持通配符），可重复传参，如 ?metric=custom.play_one_minute&metric=minecraft:used.minecraft:diamond_pickaxe 或 ?metric=used.*_pickaxe"),
    granularity: str = Query("10min", description="粒度：10min,20min,30min,1h,6h,12h,24h,1week,1month,3month,6month,1year"),
    start: Optional[str] = Query(None, description="起始时间 ISO8601，可为空"),
    end: Optional[str] = Query(None, description="结束时间 ISO8601，可为空"),
    namespace: str = Query("minecraft", description="命名空间，默认 minecraft"),
    server_id: Optional[List[int]] = Query(None, description="参与聚合的数据源服务器ID；留空聚合全部"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(Role.USER)),
):
    """按时间桶返回 total（ticks）序列（按玩家分别返回；多指标累加）。"""
    allowed_ids = _get_allowed_server_ids(db, current_user)
    filtered_server_ids = _filter_server_ids(server_id, allowed_ids)
    
    return stats_service.get_total_series(
        player_uuids=player_uuid,
        metrics=metric,
        granularity=granularity,
        start=start,
        end=end,
        namespace=namespace,
        server_ids=filtered_server_ids,
    )


@router.get("/metrics", response_model=List[str])
def list_metrics(q: Optional[str] = Query(None, description="关键字过滤"),
                 limit: int = Query(50, ge=1, le=500, description="最大返回数"),
                 namespace: str = Query("minecraft", description="命名空间"),
                 _user: models.User = Depends(require_role(Role.USER))):
    with stats_service.SessionLocal() as db:  # 重用会话工厂
        return stats_service.list_metrics(db, q=q, limit=limit, namespace=namespace)


@router.get("/leaderboard/total")
def leaderboard_total(metric: List[str] = Query(..., description="指标列表（支持通配符），多值"),
                      at: Optional[str] = Query(None, description="统计时刻，ISO；默认当前"),
                      server_id: Optional[List[int]] = Query(None, description="数据源服务器ID"),
                      namespace: str = Query("minecraft", description="命名空间"),
                      limit: int = Query(50, ge=1),
                      db: Session = Depends(get_db),
                      current_user: models.User = Depends(require_role(Role.USER))):
    allowed_ids = _get_allowed_server_ids(db, current_user)
    filtered_server_ids = _filter_server_ids(server_id, allowed_ids)
    
    return stats_service.leaderboard_total(metrics=metric, at=at, server_ids=filtered_server_ids,
                                           namespace=namespace, limit=limit)


@router.get("/leaderboard/delta")
def leaderboard_delta(metric: List[str] = Query(..., description="指标列表（支持通配符），多值"),
                      start: Optional[str] = Query(None, description="起始时间，ISO"),
                      end: Optional[str] = Query(None, description="结束时间，ISO"),
                      server_id: Optional[List[int]] = Query(None, description="数据源服务器ID"),
                      namespace: str = Query("minecraft", description="命名空间"),
                      limit: int = Query(50, ge=1),
                      db: Session = Depends(get_db),
                      current_user: models.User = Depends(require_role(Role.USER))):
    allowed_ids = _get_allowed_server_ids(db, current_user)
    filtered_server_ids = _filter_server_ids(server_id, allowed_ids)
    
    return stats_service.leaderboard_delta(metrics=metric, start=start, end=end,
                                           server_ids=filtered_server_ids, namespace=namespace, limit=limit)
