# backend/routers/audit.py
"""审计日志查询接口（需要平台 ADMIN 权限）。"""

import json
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.core import models
from backend.core.database import get_db
from backend.core.auth import require_admin
from backend.core.utils import to_local_dt

router = APIRouter(
    prefix="/api/audit",
    tags=["Audit"],
)


@router.get("/logs")
async def list_audit_logs(
    db: Session = Depends(get_db),
    _actor: models.User = Depends(require_admin()),
    category: Optional[str] = Query(None, description="事件分类，如 SERVER / AUTH / USER / PLAYER / PLUGIN / ARCHIVE / SETTINGS / SYSTEM"),
    action: Optional[str] = Query(None, description="具体动作关键字，模糊匹配"),
    actor_id: Optional[int] = Query(None, description="操作人用户 ID"),
    actor_name: Optional[str] = Query(None, description="操作人用户名，模糊匹配"),
    target_type: Optional[str] = Query(None, description="对象类型，如 server / user / player"),
    target_id: Optional[str] = Query(None, description="对象 ID"),
    target_name: Optional[str] = Query(None, description="对象名称，模糊匹配"),
    result: Optional[str] = Query(None, description="结果：success 或 failure"),
    start_ts: Optional[datetime] = Query(None, description="起始时间（ISO 8601）"),
    end_ts: Optional[datetime] = Query(None, description="结束时间（ISO 8601）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """查询审计日志，支持多条件过滤与分页。"""
    q = db.query(models.AuditLog)

    if category:
        q = q.filter(models.AuditLog.category == category.upper())
    if action:
        q = q.filter(models.AuditLog.action.contains(action))
    if actor_id is not None:
        q = q.filter(models.AuditLog.actor_id == actor_id)
    if actor_name:
        q = q.filter(models.AuditLog.actor_name.contains(actor_name))
    if target_type:
        q = q.filter(models.AuditLog.target_type == target_type)
    if target_id is not None:
        q = q.filter(models.AuditLog.target_id == str(target_id))
    if target_name:
        q = q.filter(models.AuditLog.target_name.contains(target_name))
    if result:
        q = q.filter(models.AuditLog.result == result)
    if start_ts:
        q = q.filter(models.AuditLog.ts >= start_ts)
    if end_ts:
        q = q.filter(models.AuditLog.ts <= end_ts)

    total = q.count()
    rows = (
        q.order_by(desc(models.AuditLog.ts))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for r in rows:
        detail_parsed = None
        if r.detail:
            try:
                detail_parsed = json.loads(r.detail)
            except Exception:
                detail_parsed = r.detail
        items.append({
            "id": r.id,
            "ts": to_local_dt(r.ts).isoformat() if r.ts else None,
            "category": r.category,
            "action": r.action,
            "actor_id": r.actor_id,
            "actor_name": r.actor_name,
            "ip_address": r.ip_address,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "target_name": r.target_name,
            "detail": detail_parsed,
            "result": r.result,
            "error_msg": r.error_msg,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get("/categories")
async def list_categories(_actor: models.User = Depends(require_admin())):
    """返回所有可用的事件分类（用于前端下拉）。"""
    return [
        {"value": "SYSTEM",   "label": "系统"},
        {"value": "AUTH",     "label": "认证"},
        {"value": "USER",     "label": "用户管理"},
        {"value": "SERVER",   "label": "服务器"},
        {"value": "PLAYER",   "label": "玩家"},
        {"value": "PLUGIN",   "label": "插件"},
        {"value": "ARCHIVE",  "label": "存档"},
        {"value": "SETTINGS", "label": "系统设置"},
    ]
