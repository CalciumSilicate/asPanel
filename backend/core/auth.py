# backend/core/auth.py
"""
认证与授权模块

权限层级:
- OWNER: 超级管理员，可控制一切
- ADMIN: 平台管理员，可控制系统设置和所有服务器，但不能修改权限字段
- 组权限: 通过 PermissionService 检查
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Callable

from backend.core import security, crud, models, schemas
from backend.core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """获取当前登录用户"""
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


def require_owner() -> Callable:
    """要求用户是 OWNER（超级管理员）
    
    OWNER 可以:
    - 控制一切，包括修改他人的 is_admin/is_owner
    - 绕过组隔离访问所有组
    """
    async def owner_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if not current_user.is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要 OWNER 权限才能执行此操作"
            )
        return current_user
    return owner_checker


def require_admin() -> Callable:
    """要求用户是 ADMIN 或 OWNER（平台管理员）
    
    ADMIN 可以:
    - 管理系统设置
    - 访问和管理所有服务器
    - 管理用户的组权限（但不能修改 is_owner/is_admin）
    
    ADMIN 不可以:
    - 修改 is_owner 或 is_admin 字段
    - 这些只能由 OWNER 修改
    """
    async def admin_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if not (current_user.is_owner or current_user.is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要管理员权限才能执行此操作"
            )
        return current_user
    return admin_checker


def require_authenticated() -> Callable:
    """只要求用户已登录"""
    async def auth_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        return current_user
    return auth_checker


def require_role(required_role: schemas.Role) -> Callable:
    """根据角色要求检查权限
    
    新权限模型映射:
    - OWNER: 需要 is_owner
    - ADMIN: 需要 is_owner 或 is_admin
    - HELPER/USER/GUEST: 需要登录（具体的组权限由服务层检查）
    
    注意: 这个函数只检查全局权限，组内权限需要通过 PermissionService 检查
    """
    async def role_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        # OWNER 权限只有 is_owner 才能满足
        if required_role == schemas.Role.OWNER:
            if not current_user.is_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="需要 OWNER 权限才能执行此操作"
                )
            return current_user
        
        # ADMIN 权限需要 is_owner 或 is_admin
        if required_role == schemas.Role.ADMIN:
            if not (current_user.is_owner or current_user.is_admin):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="需要管理员权限才能执行此操作"
                )
            return current_user
        
        # HELPER/USER/GUEST 只需要登录
        # 具体的组权限由服务层的 PermissionService 检查
        # 这里只做基本的登录检查
        return current_user
    
    return role_checker
