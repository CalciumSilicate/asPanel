# backend/core/auth.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Callable

from backend.core import security, crud, models, schemas
from backend.core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")


def require_role(required_role: schemas.Role) -> Callable:
    def role_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        user_role_level = schemas.ROLE_HIERARCHY.get(current_user.role, -1)
        required_role_level = schemas.ROLE_HIERARCHY[required_role]
        if user_role_level < required_role_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要 '{required_role.value}' 或更高权限才能执行此操作。"
            )

        return current_user

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
