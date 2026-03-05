# backend/core/audit.py
"""
审计日志服务：提供同步与异步两种写入接口。

用法：
    # 在 async 路由 / 事件处理中
    await audit(category="AUTH", action="login", actor_id=user.id, ...)

    # 在同步代码（如 mcdr_manager 回调）中
    write_audit(category="SERVER", action="crashed", ...)
"""

import json
import asyncio
from typing import Any, Dict, Optional

from backend.core.database import get_db_context
from backend.core import models
from backend.core.logger import logger


def write_audit(
    *,
    category: str,
    action: str,
    actor_id: Optional[int] = None,
    actor_name: Optional[str] = None,
    ip_address: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    target_name: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    result: str = "success",
    error_msg: Optional[str] = None,
) -> None:
    """同步写入审计日志，可在任意线程中调用（不依赖事件循环）。"""
    try:
        with get_db_context() as db:
            row = models.AuditLog(
                category=category,
                action=action,
                actor_id=actor_id,
                actor_name=actor_name,
                ip_address=ip_address,
                target_type=target_type,
                target_id=str(target_id) if target_id is not None else None,
                target_name=target_name,
                detail=json.dumps(detail, ensure_ascii=False) if detail is not None else None,
                result=result,
                error_msg=str(error_msg)[:500] if error_msg else None,
            )
            db.add(row)
            db.commit()
    except Exception as e:
        # 审计日志写入失败不应影响主流程
        try:
            logger.warning(f"[Audit] 写入审计日志失败: {e}")
        except Exception:
            pass


async def audit(
    *,
    category: str,
    action: str,
    actor_id: Optional[int] = None,
    actor_name: Optional[str] = None,
    ip_address: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    target_name: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    result: str = "success",
    error_msg: Optional[str] = None,
) -> None:
    """异步写入审计日志，不阻塞事件循环（推荐在 async 路由/服务中使用）。"""
    await asyncio.to_thread(
        write_audit,
        category=category,
        action=action,
        actor_id=actor_id,
        actor_name=actor_name,
        ip_address=ip_address,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        detail=detail,
        result=result,
        error_msg=error_msg,
    )


def get_client_ip(request) -> Optional[str]:
    """从 FastAPI Request 中提取客户端 IP（支持反代 X-Forwarded-For）。"""
    try:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else None
    except Exception:
        return None
