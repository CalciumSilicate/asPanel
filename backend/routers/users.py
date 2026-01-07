# backend/routers/users.py

import asyncio
import os
import uuid
import hashlib
import shutil
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Request
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pathlib import Path

from backend.core import security, crud, models, schemas
from backend.core.responses import success, error, ErrorCodes
from backend.core.api import get_uuid_by_name
from backend.core.logger import logger
from backend.core.database import get_db
from backend.core.auth import get_current_user, require_role, require_owner, require_admin, require_authenticated
from backend.core.constants import AVATAR_STORAGE_PATH, AVATAR_URL_PREFIX, AVATAR_MC_PATH, \
    UUID_HYPHEN_PATTERN
from backend.core.rate_limit import login_limiter
from backend.core.utils import get_str_md5, is_valid_mc_name
from backend.core.schemas import Role, UserUpdate, UserSelfUpdate, PasswordChange, GroupRole, GroupPermission
from backend.core.bind_verification import bind_verification_service
from backend.core.schemas import BindRequestCreate, BindRequestResponse, BindVerifyRequest, BindPendingResponse
from backend.services.permission_service import PermissionService

router = APIRouter(
    prefix="/api",
    tags=["Users & Auth"],
)


@router.post("/users/register", status_code=status.HTTP_201_CREATED, response_model=schemas.UserOut)
async def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # 从数据库读取是否允许注册
    sys_settings = crud.get_system_settings_data(db) or {}
    if not sys_settings.get("allow_register", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "禁止注册！")

    if crud.get_user_by_username(db, user.username):
        raise HTTPException(400, "用户名已存在")

    register_require_qq = bool(sys_settings.get("register_require_qq", True))
    register_require_player_name = bool(sys_settings.get("register_require_player_name", True))
    register_player_name_must_exist = bool(sys_settings.get("register_player_name_must_exist", True))

    # QQ：按系统设置决定是否必填
    qq_str = str(getattr(user, 'qq', '') or '').strip()
    if register_require_qq and not qq_str:
        raise HTTPException(400, "QQ 为必填项")
    if qq_str and not qq_str.isdigit():
        raise HTTPException(400, "QQ 必须为纯数字")
    # 归一化（去掉空白）
    try:
        user.qq = qq_str or None
    except Exception:
        pass

    # 玩家名：按系统设置决定是否必填；可选时允许不填
    player_name = str(getattr(user, 'player_name', '') or '').strip()
    if register_require_player_name and not player_name:
        raise HTTPException(400, "玩家名为必填项")

    bound_player_id = None
    server_link_group_ids: list[int] = []

    if player_name:
        if not is_valid_mc_name(player_name):
            raise HTTPException(400, "玩家名格式不正确")

        player = crud.get_player_by_name(db, player_name)
        if not player:
            if register_player_name_must_exist:
                raise HTTPException(400, "玩家不存在，请确认玩家名是否正确")

            def offline_uuid_for(name: str) -> str:
                raw = ("OfflinePlayer:" + name).encode("utf-8")
                md5 = bytearray(hashlib.md5(raw).digest())
                md5[6] = (md5[6] & 0x0F) | 0x30
                md5[8] = (md5[8] & 0x3F) | 0x80
                return str(uuid.UUID(bytes=bytes(md5)))

            uuid_to_use = await get_uuid_by_name(player_name)
            if uuid_to_use and UUID_HYPHEN_PATTERN.match(uuid_to_use):
                is_offline = False
            else:
                uuid_to_use = offline_uuid_for(player_name)
                is_offline = True

            existing_by_uuid = crud.get_player_by_uuid(db, uuid_to_use)
            if existing_by_uuid:
                player = existing_by_uuid
                try:
                    if (player.player_name or None) != player_name:
                        crud.update_player_name(db, player, name=player_name, is_offline=is_offline)
                except Exception:
                    pass
            else:
                player = crud.create_player(db, uuid=uuid_to_use, player_name=player_name, play_time={}, is_offline=is_offline)

        # 检查该玩家是否已被其他用户绑定
        existing_user = db.query(models.User).filter(models.User.bound_player_id == player.id).first()
        if existing_user:
            raise HTTPException(400, "该玩家已被其他账号绑定")

        # 根据玩家 UUID 查找加入过的服务器，然后获取对应的服务器组
        joined_servers = crud.get_servers_player_joined(db, player.uuid)
        server_ids = [s.id for s in joined_servers]
        server_link_group_ids = crud.get_server_link_groups_for_servers(db, server_ids)
        bound_player_id = player.id

    # 新用户默认不是管理员
    return crud.create_user(db, user, is_owner=False, is_admin=False, bound_player_id=bound_player_id, server_link_group_ids=server_link_group_ids)


@router.post("/token", response_model=schemas.Token)
def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not login_limiter.check(client_ip):
        raise HTTPException(429, "登录尝试过于频繁，请5分钟后重试")
    
    user = crud.get_user_by_username(db, form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        login_limiter.record(client_ip)
        raise HTTPException(401, "账号名或密码错误", {"WWW-Authenticate": "Bearer"})
    
    # 登录时更新用户的 server_link_group_ids (Legacy & New)
    if user.bound_player_id:
        player = db.query(models.Player).filter(models.Player.id == user.bound_player_id).first()
        if player and player.uuid:
            import json
            joined_servers = crud.get_servers_player_joined(db, player.uuid)
            server_ids = [s.id for s in joined_servers]
            new_group_ids = crud.get_server_link_groups_for_servers(db, server_ids)
            
            # Legacy
            user.server_link_group_ids = json.dumps(new_group_ids)
            db.add(user)
            db.commit()

            # New: Update UserGroupPermission with default USER role
            # Note: This overwrites existing permissions if they came from auto-binding.
            # If we want to preserve manual ADMIN/HELPER roles, we should only ADD missing ones.
            # However, for now, let's assume auto-binding implies USER role for those groups.
            # To be safe, let's fetch existing and merge.
            existing_perms = crud.get_user_group_permissions(db, user.id)
            existing_map = {p.group_id: p.role for p in existing_perms}
            
            new_perms = []
            for gid in new_group_ids:
                role = existing_map.get(gid, "USER")
                new_perms.append(schemas.GroupPermission(group_id=gid, role=role))
            
            crud.update_user_group_permissions(db, user.id, new_perms)
    
    # 从数据库读取 token 过期时间
    sys_settings = crud.get_system_settings_data(db)
    expire_minutes = sys_settings.get("token_expire_minutes", 60)
    return {"access_token": security.create_access_token({"sub": user.username, "tv": getattr(user, "token_version", 0)}, expire_minutes=expire_minutes), "token_type": "bearer"}


@router.get("/users/me", response_model=schemas.UserOut)
async def read_users_me(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Fetch permissions
    perms = crud.get_user_group_permissions(db, current_user.id)
    
    # Fetch group names efficiently
    group_ids = [p.group_id for p in perms]
    groups = db.query(models.ServerLinkGroup).filter(models.ServerLinkGroup.id.in_(group_ids)).all()
    group_map = {g.id: g.name for g in groups}

    group_permissions = []
    for p in perms:
        gname = group_map.get(p.group_id, f"Group {p.group_id}")
        group_permissions.append({'group_id': p.group_id, 'group_name': gname, 'role': p.role})

    # 构建返回对象
    result = {
        'id': current_user.id,
        'username': current_user.username,
        'avatar_url': current_user.avatar_url,
        'is_owner': current_user.is_owner,
        'is_admin': current_user.is_admin,
        'email': current_user.email,
        'qq': current_user.qq,
        'bound_player_id': current_user.bound_player_id,
        'mc_uuid': None,
        'mc_name': None,
        'server_link_group_ids': current_user.server_link_group_ids,
        'group_permissions': group_permissions
    }
    # 如果绑定了玩家，查询玩家信息
    if current_user.bound_player_id:
        player = db.query(models.Player).filter(models.Player.id == current_user.bound_player_id).first()
        if player:
            result['mc_uuid'] = player.uuid
            result['mc_name'] = player.player_name
    return result


@router.patch("/users/me", response_model=schemas.UserOut)
async def update_current_user(
        payload: UserSelfUpdate,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """用户更新自己的个人资料（邮箱、QQ、绑定玩家）"""
    if payload.email is not None:
        current_user.email = payload.email
    if payload.qq is not None:
        qq_str = str(payload.qq).strip()
        if qq_str and not qq_str.isdigit():
            raise HTTPException(400, "QQ 必须为纯数字")
        current_user.qq = qq_str
    
    # 处理玩家绑定 - 现在只能通过验证流程绑定
    if payload.player_name is not None:
        raise HTTPException(400, "玩家绑定需要通过验证流程，请使用 /users/me/bind-request 接口")
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    # Fetch latest permissions with names
    perms = crud.get_user_group_permissions(db, current_user.id)
    group_ids = [p.group_id for p in perms]
    groups = db.query(models.ServerLinkGroup).filter(models.ServerLinkGroup.id.in_(group_ids)).all()
    group_map = {g.id: g.name for g in groups}

    group_permissions = []
    for p in perms:
        gname = group_map.get(p.group_id, f"Group {p.group_id}")
        group_permissions.append({'group_id': p.group_id, 'group_name': gname, 'role': p.role})

    # 构建返回对象，包含 mc_uuid 和 mc_name
    result = {
        'id': current_user.id,
        'username': current_user.username,
        'avatar_url': current_user.avatar_url,
        'role': current_user.role,
        'email': current_user.email,
        'qq': current_user.qq,
        'bound_player_id': current_user.bound_player_id,
        'mc_uuid': None,
        'mc_name': None,
        'server_link_group_ids': current_user.server_link_group_ids,
        'group_permissions': group_permissions
    }
    # 如果绑定了玩家，查询玩家信息
    if current_user.bound_player_id:
        bound_player = db.query(models.Player).filter(models.Player.id == current_user.bound_player_id).first()
        if bound_player:
            result['mc_uuid'] = bound_player.uuid
            result['mc_name'] = bound_player.player_name
    return result


@router.post("/users/me/bind-request", response_model=BindRequestResponse)
async def request_player_bind(
    payload: BindRequestCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """请求绑定玩家 - 返回验证码，需在游戏内确认"""
    player_name = payload.player_name.strip()
    if not player_name:
        raise HTTPException(400, "玩家名不能为空")
    if not is_valid_mc_name(player_name):
        raise HTTPException(400, "玩家名格式不正确")
    
    # 检查玩家是否存在
    player = crud.get_player_by_name(db, player_name)
    if not player:
        raise HTTPException(400, f"玩家 '{player_name}' 不存在")
    
    # 检查是否已被绑定
    existing_user = db.query(models.User).filter(
        models.User.bound_player_id == player.id,
        models.User.id != current_user.id
    ).first()
    if existing_user:
        raise HTTPException(400, "该玩家已被其他账号绑定")
    
    # 创建绑定请求
    code = bind_verification_service.create_bind_request(current_user.id, player_name)
    
    return BindRequestResponse(
        code=code,
        player_name=player_name,
        expires_in_seconds=300,
        message=f"请在游戏内执行 /aspanel bind {code} 确认绑定"
    )


@router.get("/users/me/bind-pending", response_model=BindPendingResponse)
async def get_pending_bind(current_user: models.User = Depends(get_current_user)):
    """获取当前待验证的绑定请求"""
    pending = bind_verification_service.get_pending_request(current_user.id)
    if pending:
        import time
        return BindPendingResponse(
            has_pending=True,
            player_name=pending.player_name,
            code=pending.code,
            expires_at=pending.expires_at
        )
    return BindPendingResponse(has_pending=False)


@router.delete("/users/me/bind-request")
async def cancel_bind_request(current_user: models.User = Depends(get_current_user)):
    """取消绑定请求"""
    cancelled = bind_verification_service.cancel_request(current_user.id)
    return {"cancelled": cancelled}


@router.post("/bind/verify")
async def verify_player_bind(
    payload: BindVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    服务器回调验证绑定 - 由 MCDR 插件调用
    验证成功后完成玩家绑定
    """
    result = bind_verification_service.verify_code(payload.code)
    if not result:
        raise HTTPException(400, "验证码无效或已过期")
    
    user_id, expected_player_name = result
    
    # 验证玩家名匹配（不区分大小写）
    if payload.player_name.lower() != expected_player_name.lower():
        raise HTTPException(400, "玩家名不匹配")
    
    # 获取用户和玩家
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(400, "用户不存在")
    
    player = crud.get_player_by_name(db, payload.player_name)
    if not player:
        raise HTTPException(400, "玩家不存在")
    
    # 检查是否已被绑定
    existing = db.query(models.User).filter(
        models.User.bound_player_id == player.id,
        models.User.id != user_id
    ).first()
    if existing:
        raise HTTPException(400, "该玩家已被其他账号绑定")
    
    # 执行绑定
    user.bound_player_id = player.id
    
    # 更新服务器组权限
    import json
    joined_servers = crud.get_servers_player_joined(db, player.uuid)
    server_ids = [s.id for s in joined_servers]
    server_link_group_ids = crud.get_server_link_groups_for_servers(db, server_ids)
    user.server_link_group_ids = json.dumps(server_link_group_ids)  # Legacy
    
    # Sync permissions
    existing_perms = crud.get_user_group_permissions(db, user.id)
    existing_map = {p.group_id: p.role for p in existing_perms}
    new_perms = []
    for gid in server_link_group_ids:
        role = existing_map.get(gid, "USER")
        new_perms.append(schemas.GroupPermission(group_id=gid, group_name="", role=role))
    crud.update_user_group_permissions(db, user.id, new_perms)
    
    # 增加 token_version 使旧 token 失效
    from backend.services.permission_service import PermissionService
    PermissionService.increment_token_version(db, user)
    
    return success({"bound": True, "player_name": player.player_name})


@router.post("/users/me/password")
async def change_password(
        payload: PasswordChange,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """用户修改自己的密码"""
    if not security.verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(400, "原密码错误")
    if len(payload.new_password) < 6:
        raise HTTPException(400, "新密码长度至少6位")
    current_user.hashed_password = security.get_password_hash(payload.new_password)
    db.add(current_user)
    db.commit()
    return {"success": True, "message": "密码修改成功"}


@router.get("/users/me/stats")
async def get_my_stats(
        range: str = Query("1d", description="时间范围: 1d, 1w, 1m, 1y, all"),
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取当前用户绑定玩家的统计数据"""
    import json
    from backend.services.qq_stats_command import (
        _calc_preset, _build_totals, _build_charts, TOTAL_ITEMS, CHART_ITEMS
    )
    from backend.services import stats_service
    
    if not current_user.bound_player_id:
        raise HTTPException(400, "您尚未绑定玩家，无法查看统计数据")
    
    player = db.query(models.Player).filter(models.Player.id == current_user.bound_player_id).first()
    if not player or not player.uuid:
        raise HTTPException(400, "绑定的玩家不存在或无效")
    
    # 获取用户可访问的服务器组的数据源服务器
    server_ids = []
    try:
        group_ids = json.loads(current_user.server_link_group_ids or '[]')
        for gid in group_ids:
            group = crud.get_server_link_group_by_id(db, gid)
            if group:
                ds_ids = json.loads(group.data_source_ids or "[]")
                srv_ids = json.loads(group.server_ids or "[]")
                target_ids = ds_ids if ds_ids else srv_ids
                server_ids.extend([int(i) for i in target_ids])
    except Exception:
        pass
    
    # 去重
    server_ids = list(set(server_ids)) if server_ids else []
    
    # 计算时间范围
    tr = _calc_preset(range, 0, server_ids)
    
    # 构建统计数据
    effective_server_ids = server_ids if server_ids else [3]  # 默认使用 server_id=3
    totals = _build_totals(player.uuid, tr, effective_server_ids)
    charts = _build_charts(player.uuid, tr, effective_server_ids)
    
    return {
        "player_name": player.player_name,
        "player_uuid": player.uuid,
        "time_range": {
            "label": tr.label,
            "start": tr.start.isoformat(),
            "end": tr.end.isoformat(),
            "granularity": tr.granularity,
        },
        "totals": totals,
        "charts": charts,
        "server_ids": effective_server_ids,
    }


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


def _assert_permission_change_allowed(db: Session, actor: models.User, target: models.User, payload: UserUpdate):
    """检查权限变更是否允许"""
    # 只有 OWNER 可以修改全局权限 (is_owner/is_admin)
    if payload.is_owner is not None or payload.is_admin is not None:
        if not actor.is_owner:
            raise HTTPException(403, "只有 OWNER 可以修改用户的全局权限")
        # OWNER 不能降级自己
        if actor.id == target.id:
            if payload.is_owner is False:
                raise HTTPException(400, "不能降级自己的 OWNER 权限")
        # 保护唯一 OWNER
        if target.is_owner and payload.is_owner is False:
            if crud.count_owners(db) <= 1:
                raise HTTPException(400, "必须至少保留 1 个 OWNER")
    
    # ADMIN 可以修改组权限（非 OWNER 用户的）
    if payload.group_permissions is not None:
        if not (actor.is_owner or actor.is_admin):
            raise HTTPException(403, "需要管理员权限才能修改组权限")
        if target.is_owner and not actor.is_owner:
            raise HTTPException(403, "非 OWNER 不能修改 OWNER 的组权限")


@router.patch("/users/{user_id}", response_model=schemas.UserOut)
async def update_user(
        user_id: int,
        payload: UserUpdate,
        db: Session = Depends(get_db),
        actor: models.User = Depends(require_admin()),
):
    u = crud.get_user_by_id(db, user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    
    # OWNER 保护
    if u.is_owner and not actor.is_owner:
        # 非 OWNER 只能修改 OWNER 的组权限（如果 ADMIN 被允许的话）
        if payload.is_owner is not None or payload.is_admin is not None:
            raise HTTPException(403, "非 OWNER 不能修改 OWNER 的全局权限")
    
    # 检查权限变更是否允许
    _assert_permission_change_allowed(db, actor, u, payload)
    
    # 如果权限变更，增加 token_version
    if payload.is_owner is not None or payload.is_admin is not None:
        PermissionService.increment_token_version(db, u)
    
    try:
        u = crud.update_user_fields(db, user_id, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # 返回更新后的用户信息
    for r in crud.list_users_sorted(db):
        if r['id'] == u.id:
            return r
    return u


@router.get("/users", response_model=list[schemas.UserOut])
async def list_users(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_owner()),
        search: str | None = Query(default=None),
        is_admin: bool | None = Query(default=None),
):
    return crud.list_users_sorted(db, search=search, is_admin_filter=is_admin)


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
            if not await asyncio.to_thread(yml_path.exists):
                results.append({ 'server': dir_name, 'path': str(yml_path), 'error': 'missing_file' })
                continue
            try:
                yml_content = await asyncio.to_thread(yml_path.read_text, encoding='utf-8')
                data = yaml.safe_load(yml_content) or {}
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
        f"https://api.mcheads.org/avatar/{mc_name_or_uuid}",
        f"https://mineskin.eu/helm/{mc_name_or_uuid}",
        f"https://crafatar.com/avatars/{mc_name_or_uuid}",
        f"https://mc-heads.net/avatar/{mc_name_or_uuid}"
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
                logger.error(f"Download Failed | mc_name_or_uuid={mc_name_or_uuid} status_code={resp.status_code} content={resp.content}")
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
        actor: models.User = Depends(require_admin()),
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
        actor: models.User = Depends(require_admin()),
):
    u = crud.get_user_by_id(db, user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    
    # OWNER 保护
    if u.is_owner and not actor.is_owner:
        raise HTTPException(403, "非 OWNER 不能重置 OWNER 的密码")
    
    new_password = uuid.uuid4().hex[:12]
    crud.reset_user_password(db, user_id, new_password)
    u.token_version = (u.token_version or 0) + 1
    db.commit()
    return success({"id": user_id}, message="密码已重置")


@router.delete("/users/{user_id}")
async def delete_user(
        user_id: int,
        db: Session = Depends(get_db),
        actor: models.User = Depends(require_admin()),
):
    u = crud.get_user_by_id(db, user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    
    # OWNER 保护
    if u.is_owner and not actor.is_owner:
        raise HTTPException(403, "非 OWNER 不能删除 OWNER 用户")
    
    if u.is_owner and crud.count_owners(db) <= 1:
        raise HTTPException(400, "系统必须至少保留 1 个 OWNER，无法删除唯一的 OWNER")
    crud.delete_user_by_id(db, user_id)
    return success({"id": user_id, "deleted": True})


@router.delete("/users")
async def batch_delete_users(
        payload: schemas.BatchActionPayload,
        db: Session = Depends(get_db),
        actor: models.User = Depends(require_admin()),
):
    ids = list(payload.ids or [])
    # 保护 OWNER
    if ids:
        to_keep = []
        for uid in ids:
            u = crud.get_user_by_id(db, uid)
            if u and u.is_owner:
                if not actor.is_owner or crud.count_owners(db) <= 1:
                    continue
            to_keep.append(uid)
        ids = to_keep
    deleted = crud.delete_users_by_ids(db, ids)
    return success({"deleted": deleted})
