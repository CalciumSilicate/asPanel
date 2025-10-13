import os

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import uuid
import shutil

from backend import crud, models, schemas, security
from backend.database import get_db
from backend.auth import get_current_user
from backend.core.config import AVATAR_STORAGE_PATH, AVATAR_URL_PREFIX, ALLOW_REGISTER

router = APIRouter(
    prefix="/api",
    tags=["Users & Auth"],
)


@router.post("/users/register", status_code=status.HTTP_201_CREATED, response_model=schemas.UserOut)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if not ALLOW_REGISTER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "禁止注册！")
    if crud.get_user_by_username(db, user.username):
        raise HTTPException(400, "用户名已存在")
    return crud.create_user(db, user)


@router.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(401, "账号名或密码错误", {"WWW-Authenticate": "Bearer"})
    return {"access_token": security.create_access_token({"sub": user.username}), "token_type": "bearer"}


@router.get("/users/me", response_model=schemas.UserOut)
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/users/me/avatar", response_model=schemas.UserOut)
async def upload_avatar(
        file: UploadFile = File(...),
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="仅支持JPG、PNG格式的图片！")
    file_extension = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4().hex}.{file_extension}"
    file_path = AVATAR_STORAGE_PATH / filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件无法保存: {e}")
    avatar_url = f"{AVATAR_URL_PREFIX}{filename}"
    updated_user, legacy_avatar = crud.update_user_avatar(db, username=current_user.username, avatar_url=avatar_url)
    try:
        os.remove(AVATAR_STORAGE_PATH / legacy_avatar.replace(AVATAR_URL_PREFIX, ""))
    except FileNotFoundError:
        ...
    except AttributeError:
        ...
    return updated_user


@router.get("/users", response_model=list[schemas.UserOut])
async def list_users(db: Session = Depends(get_db)):
    return crud.get_all_users(db)
