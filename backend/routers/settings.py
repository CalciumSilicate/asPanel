# backend/routers/settings.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core import crud, models, schemas
from backend.core.auth import require_role
from backend.core.database import get_db
from backend.core.schemas import Role
from backend.core.utils import find_local_java_commands


router = APIRouter(
    prefix="/api/settings",
    tags=["Settings"],
)


@router.get("", response_model=schemas.SystemSettings)
async def get_settings(db: Session = Depends(get_db), _user: models.User = Depends(require_role(Role.GUEST))):
    """获取系统级设置。

    说明：
    - python_executable：运行 MCDR 的 Python 路径（相对路径以服务器目录为基准）。
    - java_command：用于保存到 MCDR 的 start_command。
    - timezone：用于前端展示时间。
    """
    data = crud.get_system_settings_data(db)
    return schemas.SystemSettings(**data)


@router.patch("", response_model=schemas.SystemSettings)
async def update_settings(payload: schemas.SystemSettingsUpdate,
                          db: Session = Depends(get_db),
                          _user: models.User = Depends(require_role(Role.OWNER))):
    """更新系统级设置（部分字段）。需要 OWNER 权限。"""
    data = crud.update_system_settings(db, payload.model_dump(exclude_unset=True))
    return schemas.SystemSettings(**data)


@router.get("/java-options", response_model=list[str])
async def get_java_options(db: Session = Depends(get_db), _user: models.User = Depends(require_role(Role.OWNER))):
    """获取本机可用的 Java 命令候选列表（用于下拉选择）。需要 OWNER 权限。"""
    try:
        current = (crud.get_system_settings_data(db) or {}).get("java_command") or "java"
    except Exception:
        current = "java"

    out: list[str] = []
    seen: set[str] = set()

    def add(x: str | None):
        if not x:
            return
        s = str(x).strip()
        if not s or s in seen:
            return
        seen.add(s)
        out.append(s)

    add(current)
    for cmd in find_local_java_commands():
        add(cmd)

    return out
