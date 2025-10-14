from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import crud, models, schemas
from backend.auth import require_role
from backend.database import get_db
from backend.schemas import Role


router = APIRouter(
    prefix="/api/settings",
    tags=["Settings"],
)


@router.get("", response_model=schemas.SystemSettings)
async def get_settings(db: Session = Depends(get_db), _user: models.User = Depends(require_role(Role.ADMIN))):
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
                          _user: models.User = Depends(require_role(Role.ADMIN))):
    """更新系统级设置（部分字段）。需要 ADMIN 权限。"""
    data = crud.update_system_settings(db, payload.model_dump(exclude_unset=True))
    return schemas.SystemSettings(**data)
