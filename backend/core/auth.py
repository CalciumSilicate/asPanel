# backend/core/auth.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Callable

from backend.core import security, crud, models, schemas
from backend.core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")


def require_owner() -> Callable:
    """要求用户是 OWNER（超级管理员）"""
    def owner_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if not current_user.is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要 OWNER 权限才能执行此操作"
            )
        return current_user
    return owner_checker


def require_admin() -> Callable:
    """要求用户是 ADMIN 或 OWNER"""
    def admin_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if not (current_user.is_owner or current_user.is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要管理员权限才能执行此操作"
            )
        return current_user
    return admin_checker


def require_authenticated() -> Callable:
    """只要求用户已登录"""
    def auth_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        return current_user
    return auth_checker


# DEPRECATED: 保留用于向后兼容，逐步迁移
def require_role(required_role: schemas.Role) -> Callable:
    """DEPRECATED: 使用 require_owner/require_admin 替代"""
    from backend.services.permission_service import PermissionService
    
    def role_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        # 新权限模型：OWNER/ADMIN 拥有所有权限
        if current_user.is_owner or current_user.is_admin:
            return current_user
        
        # 对于旧代码兼容：非管理员只能访问 USER 级别的功能
        if required_role in (schemas.Role.GUEST, schemas.Role.USER):
            return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"需要管理员权限才能执行此操作"
        )
    return role_checker


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    token_version = payload.get("tv", 0)
    if token_version != getattr(user, "token_version", 0):
        raise credentials_exception
    return user
