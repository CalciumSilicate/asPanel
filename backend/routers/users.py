# backend/routers/users.py

import os
import uuid
import shutil
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pathlib import Path

from backend.core import security, crud, models, schemas
from backend.core.logger import logger
from backend.core.database import get_db
from backend.core.auth import get_current_user, require_role
from backend.core.constants import AVATAR_STORAGE_PATH, AVATAR_URL_PREFIX, ALLOW_REGISTER, AVATAR_MC_PATH, \
    UUID_HYPHEN_PATTERN
from backend.core.utils import get_str_md5, is_valid_mc_name
from backend.core.schemas import Role, UserUpdate

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
    # QQ 必填且为数字字符串（不强制长度）
    if not getattr(user, 'qq', None):
        raise HTTPException(400, "QQ 为必填项")
    qq_str = str(user.qq).strip()
    if not qq_str.isdigit():
        raise HTTPException(400, "QQ 必须为纯数字")
    # 创建用户；create_user 内部会尝试根据 player_name 绑定玩家
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


def _assert_role_change_allowed(db: Session, actor: models.User, target: models.User, new_role: Role):
    actor_role = Role(actor.role)
    target_role = Role(target.role)
    if actor_role == Role.ADMIN:
        # 仅可在 GUEST/USER/HELPER 间调整；且不能作用于 ADMIN/OWNER
        if new_role not in (Role.GUEST, Role.USER, Role.HELPER):
            raise HTTPException(403, "ADMIN 仅可调整至 GUEST/USER/HELPER")
        if target_role in (Role.ADMIN, Role.OWNER):
            raise HTTPException(403, "ADMIN 无法调整 ADMIN/OWNER 的权限")
    elif actor_role == Role.OWNER:
        # OWNER 可调整到 ADMIN 及以下；设为 OWNER 需全局唯一
        if new_role == Role.OWNER:
            owners = crud.count_owners(db)
            if owners >= 1 and target_role != Role.OWNER:
                raise HTTPException(400, "OWNER 最多 1 个")
    else:
        raise HTTPException(403, "无权调整权限")

    # 保底：不得将唯一 OWNER 降级
    if target_role == Role.OWNER and new_role != Role.OWNER:
        if crud.count_owners(db) <= 1:
            raise HTTPException(400, "必须至少保留 1 个 OWNER，无法降级唯一 OWNER")


@router.patch("/users/{user_id}", response_model=schemas.UserOut)
async def update_user(
        user_id: int,
        payload: UserUpdate,
        db: Session = Depends(get_db),
        actor: models.User = Depends(require_role(Role.ADMIN)),
):
    u = crud.get_user_by_id(db, user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    if payload.role is not None:
        _assert_role_change_allowed(db, actor, u, payload.role)
    try:
        u = crud.update_user_fields(db, user_id, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # 展开 mc 信息
    for r in crud.list_users_sorted(db):
        if r['id'] == u.id:
            return r
    return u


@router.get("/users", response_model=list[schemas.UserOut])
async def list_users(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_role(Role.ADMIN)),
        search: str | None = Query(default=None),
        role: str | None = Query(default=None),
):
    return crud.list_users_sorted(db, search=search, role=role)


@router.get("/users/permissions/check")
async def check_permissions_config(db: Session = Depends(get_db), actor: models.User = Depends(require_role(Role.ADMIN))):
    """
    检查所有服务器的 permission.yml：
    - 针对角色为 GUEST 或 HELPER/ADMIN/OWNER 的用户，若绑定了玩家且有玩家名，检查对应分组是否包含该玩家名。
    返回形如：[{ server: 'dir', path: '/abs/.../permission.yml', player: 'Steve', expected: 'helper', actual: 'user' | null | 'ok' }]
    """
    import yaml
    results: list[dict] = []
    # 角色 -> yml 键映射
    role_map = {
        'GUEST': 'guest',
        'USER': 'user',  # 虽未要求校验 USER，这里保留映射以备扩展
        'HELPER': 'helper',
        'ADMIN': 'admin',
        'OWNER': 'owner',
    }
    # 仅校验 GUEST 与 HELPER/ADMIN/OWNER
    roles_to_check = {'GUEST', 'HELPER', 'ADMIN', 'OWNER'}
    # 收集玩家映射
    users = crud.get_all_users(db)
    bound: list[tuple[str, str]] = []  # (mc_name, expected_bucket)
    for u in users:
        try:
            if u.role not in roles_to_check:
                continue
            if not getattr(u, 'bound_player_id', None):
                continue
            p = db.query(models.Player).filter(models.Player.id == u.bound_player_id).first()
            if not p or not p.player_name:
                continue
            expected = role_map.get(u.role)
            if not expected:
                continue
            bound.append((p.player_name, expected))
        except Exception:
            continue
    # 遍历服务器
    servers = crud.get_all_servers(db)
    for s in servers:
        try:
            from pathlib import Path
            dir_name = Path(s.path).name
            yml_path = Path(s.path) / 'permission.yml'
            if not yml_path.exists():
                results.append({ 'server': dir_name, 'path': str(yml_path), 'error': 'missing_file' })
                continue
            try:
                data = yaml.safe_load(yml_path.read_text(encoding='utf-8')) or {}
            except Exception:
                results.append({ 'server': dir_name, 'path': str(yml_path), 'error': 'parse_failed' })
                continue
            buckets = { k: set(v or []) for k, v in (data or {}).items() if isinstance(v, list) }
            # Normalize known buckets
            for key in ['owner','admin','helper','user','guest']:
                if key not in buckets:
                    buckets[key] = set()
            for mc_name, expected in bound:
                actual = None
                for bk in ['owner','admin','helper','user','guest']:
                    if mc_name in buckets.get(bk, set()):
                        actual = bk
                        break
                if actual == expected:
                    continue
                results.append({ 'server': dir_name, 'path': str(yml_path), 'player': mc_name, 'expected': expected, 'actual': actual })
        except Exception:
            continue
    return results


async def download_avatar(mc_name_or_uuid: str, file_path: Path) -> bool:
    urls = [
        f"https://mc-heads.net/avatar/{mc_name_or_uuid}",
        f"https://api.mcheads.org/avatar/{mc_name_or_uuid}",
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


@router.post("/users/{user_id}/avatar", response_model=schemas.UserOut)
async def upload_avatar_for_user(
        user_id: int,
        file: UploadFile = File(...),
        actor: models.User = Depends(require_role(Role.ADMIN)),
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
    target_user = crud.get_user_by_id(db, user_id)
    if not target_user:
        raise HTTPException(404, "用户不存在")
    legacy_avatar = target_user.avatar_url
    target_user.avatar_url = avatar_url
    db.add(target_user)
    db.commit()
    db.refresh(target_user)
    try:
        if legacy_avatar:
            os.remove(AVATAR_STORAGE_PATH / legacy_avatar.replace(AVATAR_URL_PREFIX, ""))
    except Exception:
        pass
    for r in crud.list_users_sorted(db):
        if r['id'] == target_user.id:
            return r
    return target_user


@router.post("/users/{user_id}/reset-password")
async def reset_password(
        user_id: int,
        db: Session = Depends(get_db),
        actor: models.User = Depends(require_role(Role.ADMIN)),
):
    u = crud.get_user_by_id(db, user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    # 允许重置密码；删除/降级在其它接口限制
    new_password = uuid.uuid4().hex[:12]
    crud.reset_user_password(db, user_id, new_password)
    return {"id": user_id, "new_password": new_password}


@router.delete("/users/{user_id}")
async def delete_user(
        user_id: int,
        db: Session = Depends(get_db),
        actor: models.User = Depends(require_role(Role.ADMIN)),
):
    u = crud.get_user_by_id(db, user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    if u.role == Role.OWNER.value and crud.count_owners(db) <= 1:
        raise HTTPException(400, "系统必须至少保留 1 个 OWNER，无法删除唯一的 OWNER")
    crud.delete_user_by_id(db, user_id)
    return {"id": user_id, "deleted": True}


@router.delete("/users")
async def batch_delete_users(
        payload: schemas.BatchActionPayload,
        db: Session = Depends(get_db),
        actor: models.User = Depends(require_role(Role.ADMIN)),
):
    ids = list(payload.ids or [])
    # 保护唯一 OWNER
    if ids:
        to_keep = []
        for uid in ids:
            u = crud.get_user_by_id(db, uid)
            if u and u.role == Role.OWNER.value and crud.count_owners(db) <= 1:
                continue
            to_keep.append(uid)
        ids = to_keep
    deleted = crud.delete_users_by_ids(db, ids)
    return {"deleted": deleted}
