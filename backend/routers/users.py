import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import uuid
import shutil
import httpx
from backend import crud, models, schemas, security
from backend.logger import logger
from backend.database import get_db
from backend.auth import get_current_user
from backend.core.config import AVATAR_STORAGE_PATH, AVATAR_URL_PREFIX, ALLOW_REGISTER, AVATAR_MC_PATH, \
    UUID_HYPHEN_PATTERN
from backend.core.utils import get_str_md5, is_valid_mc_name

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


async def download_avatar(mc_name_or_uuid: str, file_path: Path) -> bool:
    urls = [
        f"https://mc-heads.net/avatar/{mc_name_or_uuid}",
        f"https://api.mcheads.org/head/{mc_name_or_uuid}",
        f"https://mineskin.eu/helm/{mc_name_or_uuid}",
        f"https://crafatar.com/avatars/{mc_name_or_uuid}"
    ]
    file_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = file_path.with_suffix(".tmp")

    timeout = httpx.Timeout(10.0, connect=5.0)
    for url in urls:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and resp.content:
                    tmp_path.write_bytes(resp.content)
                    tmp_path.replace(file_path)
                    return True
                logger.error(f"Download Failed | status_code={resp.status_code} content={resp.content}")
                continue
            except httpx.HTTPError:
                continue
    return False


@router.get("/users/mc/avatar/{mc_name_or_uuid}")
async def mc_avatar(mc_name_or_uuid: str):
    is_uuid = bool(UUID_HYPHEN_PATTERN.fullmatch(mc_name_or_uuid))
    if "-" in mc_name_or_uuid and not is_uuid:
        logger.debug("Invalid UUID | uuid={}".format(mc_name_or_uuid))
        return await mc_avatar("nigger")

    if not is_uuid and not is_valid_mc_name(mc_name_or_uuid):
        logger.debug("Invalid MC Name | name={}".format(mc_name_or_uuid))
        return await mc_avatar("nigger")

    md5 = get_str_md5(mc_name_or_uuid)
    file_name = f"{md5}.png"
    file_path = Path(AVATAR_MC_PATH) / file_name

    if file_path.exists():
        import time
        if time.time() - file_path.stat().st_mtime < 7 * 24 * 60 * 60:
            return FileResponse(file_path, media_type="image/png")

    success = await download_avatar(mc_name_or_uuid, file_path)
    if not success:
        return await mc_avatar("nigger")

    return FileResponse(file_path, media_type="image/png")
