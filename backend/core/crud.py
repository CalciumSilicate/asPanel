# backend/core/crud.py

import json
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Any, List, Optional, Type, Tuple
import datetime

from backend.core import models, models as _models, schemas
from backend.core.models import Server
from backend.core.schemas import ServerCoreConfig
from backend.core.security import get_password_hash


# --- User CRUD ---
def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_group_permissions(db: Session, user_id: int) -> List[models.UserGroupPermission]:
    return db.query(models.UserGroupPermission).filter(models.UserGroupPermission.user_id == user_id).all()


def update_user_group_permissions(db: Session, user_id: int, permissions: List[schemas.GroupPermission]):
    # Delete existing
    db.query(models.UserGroupPermission).filter(models.UserGroupPermission.user_id == user_id).delete()
    # Add new
    for perm in permissions:
        db_perm = models.UserGroupPermission(
            user_id=user_id,
            group_id=perm.group_id,
            role=perm.role.value
        )
        db.add(db_perm)
    db.commit()


def create_user(db: Session, user: schemas.UserCreate, role: Optional[schemas.Role] = None, bound_player_id: Optional[int] = None, server_link_group_ids: Optional[List[int]] = None) -> models.User:
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        hashed_password=hashed_password,
        role=role,
        email=getattr(user, 'email', None),
        qq=str(getattr(user, 'qq', '') or ''),
        bound_player_id=bound_player_id,
        # server_link_group_ids is deprecated, we use it only for legacy compatibility if needed, but here we set empty
        server_link_group_ids="[]", 
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Initialize group permissions based on server_link_group_ids if provided (Legacy migration during create)
    # Assign DEFAULT_USER_ROLE (USER) for these groups
    if server_link_group_ids:
        for gid in server_link_group_ids:
            perm = models.UserGroupPermission(user_id=db_user.id, group_id=gid, role="USER")
            db.add(perm)
        db.commit()
    
    return db_user


def update_user_avatar(db: Session, username: str, avatar_url: str) -> Tuple[Optional[models.User], str]:
    db_user = get_user_by_username(db, username)
    legacy_avatar = db_user.avatar_url
    if db_user:
        db_user.avatar_url = avatar_url
        db.commit()
        db.refresh(db_user)
    return db_user, legacy_avatar


def get_all_users(db: Session) -> List[models.User]:
    return db.query(models.User).all()


def list_users_sorted(db: Session, *, search: Optional[str] = None, role: Optional[str] = None) -> list[dict]:
    q = db.query(models.User)
    if role:
        q = q.filter(models.User.role == str(role))
    users = q.order_by(models.User.id.asc()).all()
    rows: list[dict] = []
    pid_set = {u.bound_player_id for u in users if getattr(u, 'bound_player_id', None)}
    pmap: dict[int, models.Player] = {}
    if pid_set:
        pmap = {p.id: p for p in db.query(models.Player).filter(models.Player.id.in_(pid_set)).all()}

    # Fetch permissions for all users in one go to avoid N+1
    # Simple strategy: fetch all permissions and group by user_id
    all_perms = db.query(models.UserGroupPermission).all()
    perms_map = {}
    for p in all_perms:
        if p.user_id not in perms_map:
            perms_map[p.user_id] = []
        perms_map[p.user_id].append({'group_id': p.group_id, 'role': p.role})

    for u in users:
        # Legacy parsing
        try:
            slg_ids = json.loads(getattr(u, 'server_link_group_ids', None) or '[]')
        except Exception:
            slg_ids = []
            
        row = {
            'id': u.id,
            'username': u.username,
            'avatar_url': u.avatar_url,
            'role': u.role,
            'email': getattr(u, 'email', None),
            'qq': getattr(u, 'qq', None),
            'bound_player_id': getattr(u, 'bound_player_id', None),
            'mc_uuid': None,
            'mc_name': None,
            'server_link_group_ids': slg_ids, # Keep for legacy compat in response
            'group_permissions': perms_map.get(u.id, [])
        }
        bp = pmap.get(getattr(u, 'bound_player_id', None)) if getattr(u, 'bound_player_id', None) else None
        if bp is not None:
            row['mc_uuid'] = bp.uuid
            row['mc_name'] = bp.player_name
        rows.append(row)
    if search:
        sq = (search or '').strip().lower()
        if sq:
            def _hit(r: dict) -> bool:
                return any((str(r.get(k) or '').lower().find(sq) >= 0) for k in ['username', 'email', 'qq', 'mc_uuid', 'mc_name'])
            rows = [r for r in rows if _hit(r)]
    return rows


def update_user_fields(db: Session, user_id: int, payload: schemas.UserUpdate) -> models.User | None:
    u = get_user_by_id(db, user_id)
    if not u:
        return None
    if payload.username is not None:
        other = get_user_by_username(db, payload.username)
        if other and other.id != u.id:
            raise ValueError('用户名已存在')
        u.username = payload.username
    if payload.email is not None:
        u.email = payload.email
    if payload.qq is not None:
        u.qq = payload.qq
    if payload.bound_player_id is not None:
        if payload.bound_player_id == 0:
            u.bound_player_id = None
        else:
            bp = db.query(models.Player).filter(models.Player.id == payload.bound_player_id).first()
            if not bp:
                raise ValueError('绑定的玩家不存在')
            u.bound_player_id = payload.bound_player_id
    if payload.role is not None:
        u.role = payload.role
    
    # Update group permissions if provided
    if payload.group_permissions is not None:
        update_user_group_permissions(db, user_id, payload.group_permissions)

    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def count_owners(db: Session) -> int:
    return db.query(models.User).filter(models.User.role == schemas.Role.OWNER.value).count()


def delete_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    u = get_user_by_id(db, user_id)
    if not u:
        return None
    db.delete(u)
    db.commit()
    return u


def delete_users_by_ids(db: Session, ids: list[int]) -> list[int]:
    if not ids:
        return []
    rows = db.query(models.User).filter(models.User.id.in_(ids)).all()
    for r in rows:
        db.delete(r)
    db.commit()
    return [r.id for r in rows]


def reset_user_password(db: Session, user_id: int, new_password: str) -> Optional[models.User]:
    u = get_user_by_id(db, user_id)
    if not u:
        return None
    u.hashed_password = get_password_hash(new_password)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# --- Chat CRUD ---
def create_chat_message(db: Session, msg: models.ChatMessage) -> models.ChatMessage:
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def list_chat_messages_by_group(db: Session, group_id: int, limit: int = 200) -> List[models.ChatMessage]:
    return (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.group_id == group_id)
        .order_by(models.ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )


def delete_chat_messages_by_group(db: Session, group_id: int) -> int:
    q = db.query(models.ChatMessage).filter(models.ChatMessage.group_id == group_id)
    deleted = q.delete(synchronize_session=False)
    db.commit()
    return int(deleted)


# --- Server CRUD ---
def get_server_by_id(db: Session, server_id: int) -> Optional[models.Server]:
    return db.query(models.Server).filter(models.Server.id == server_id).first()


def get_server_by_path(db: Session, path: str):
    return db.query(models.Server).filter(models.Server.path == path).first()


def get_server_by_name(db: Session, name: str) -> Optional[models.Server]:
    return db.query(models.Server).filter(models.Server.name == name).first()


def rename_server(db: Session, server_id: int, new_name: str) -> Optional[models.Server]:
    """重命名服务器，返回更新后的服务器对象，如果名称已存在则抛出 ValueError"""
    db_server = get_server_by_id(db, server_id)
    if not db_server:
        return None
    # 检查名称是否重复（排除自己）
    existing = get_server_by_name(db, new_name)
    if existing and existing.id != server_id:
        raise ValueError(f"服务器名称 '{new_name}' 已存在")
    db_server.name = new_name
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return db_server


def get_all_servers(db: Session) -> list[Server]:
    return db.query(models.Server).all()


def update_server_core_config(db: Session, server_id: int, core_config: ServerCoreConfig) -> (
        tuple[Server | None, ServerCoreConfig] | None
):
    if db_server := get_server_by_id(db, server_id):
        legacy_core_config = ServerCoreConfig.model_validate(json.loads(db_server.core_config))
        db_server.core_config = core_config.model_dump_json()
        db.add(db_server)
        db.commit()
        db.refresh(db_server)
        return db_server, legacy_core_config
    return None


def set_server_auto_start(db: Session, server_id: int, auto_start: bool) -> Optional[models.Server]:
    db_server = get_server_by_id(db, server_id)
    if not db_server:
        return None
    try:
        if hasattr(ServerCoreConfig, "model_validate_json"):
            core_config = ServerCoreConfig.model_validate_json(db_server.core_config)  # type: ignore[attr-defined]
        else:
            core_config = ServerCoreConfig.model_validate(json.loads(db_server.core_config))
    except Exception:
        core_config = ServerCoreConfig()

    core_config.auto_start = bool(auto_start)
    db_server.core_config = core_config.model_dump_json()
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return db_server


def create_server(db: Session, server: schemas.ServerCreateInternal, creator_id: int) -> models.Server:
    db_server = models.Server(name=server.name, path=server.path, creator_id=creator_id)
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return db_server


def delete_server(db: Session, server_id: int) -> Optional[models.Server]:
    db_server = get_server_by_id(db, server_id)
    if db_server:
        # Cleanup sessions
        db.query(models.PlayerSession).filter(models.PlayerSession.server_id == server_id).delete()
        # Cleanup player positions
        db.query(models.PlayerPosition).filter(models.PlayerPosition.server_id == server_id).delete()
        # Cleanup metrics record
        db.query(models.PlayerMetrics).filter(models.PlayerMetrics.server_id == server_id).delete()
        db.delete(db_server)
        db.commit()
    return db_server


# --- Download CRUD ---
def get_download_file_by_id(db: Session, download_id: int) -> Optional[models.Download]:
    return db.query(models.Download).filter(models.Download.id == download_id).first()


def get_download_file_by_path(db: Session, path: str) -> Optional[models.Download]:
    return db.query(models.Download).filter(models.Download.path == path).first()


def get_download_file_by_file_name(db: Session, file_name: str) -> Optional[models.Download]:
    return db.query(models.Download).filter(models.Download.file_name == file_name).first()


def get_download_file_by_url(db: Session, url: str) -> Optional[models.Download]:
    return db.query(models.Download).filter(models.Download.url == url).first()


def get_all_download_files(db: Session) -> list[models.Download]:
    return db.query(models.Download).all()


def create_download_file(db: Session, file_url: str, file_path: str, file_name: str) -> Tuple[models.Download, Session]:
    db_file = models.Download(url=file_url, path=file_path, file_name=file_name)
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file, db


def delete_download_file(db: Session, file_id: int) -> Optional[models.Download]:
    db_file = get_download_file_by_id(db, file_id)
    if db_file:
        db.delete(db_file)
        db.commit()
    return db_file


# --- Archive CRUD ---
def create_archive(db: Session, archive: schemas.ArchiveCreate) -> models.Archive:
    db_archive = models.Archive(**archive.model_dump())
    db.add(db_archive)
    db.commit()
    db.refresh(db_archive)
    return db_archive


def get_archives(db: Session, skip: int = 0, limit: int = 100) -> List[Type[models.Archive]]:
    return db.query(models.Archive).offset(skip).limit(limit).all()


def get_archive_by_id(db: Session, archive_id: int) -> Optional[models.Archive]:
    return db.query(models.Archive).filter(models.Archive.id == archive_id).first()


def delete_archive(db: Session, archive_id: int) -> Optional[models.Server]:
    db_archive = get_archive_by_id(db, archive_id)
    if db_archive:
        db.delete(db_archive)
        db.commit()
    return db_archive


def delete_archives_by_ids(db: Session, archive_ids: List[int]) -> list[type[models.Archive]]:
    """根据ID列表批量删除存档"""
    archives_to_delete = db.query(models.Archive).filter(models.Archive.id.in_(archive_ids)).all()
    if archives_to_delete:
        for archive in archives_to_delete:
            db.delete(archive)
        db.commit()
    return archives_to_delete


# --- Plugin CRUD (for central repository) ---
def get_plugin_by_id(db: Session, plugin_id: int) -> Optional[models.Plugin]:
    return db.query(models.Plugin).filter(models.Plugin.id == plugin_id).first()


def get_plugin_by_hash(db: Session, hash_md5: str) -> Optional[models.Plugin]:
    return db.query(models.Plugin).filter(models.Plugin.hash_md5 == hash_md5).first()


def get_all_plugins(db: Session, skip: int = 0, limit: int = 100) -> List[models.Plugin]:
    return db.query(models.Plugin).offset(skip).limit(limit).all()


def create_plugin_record(db: Session, plugin: schemas.PluginDBCreate) -> models.Plugin:
    db_plugin = models.Plugin(
        file_name=plugin.file_name,
        path=plugin.path,
        url=plugin.url,
        hash_md5=plugin.hash_md5,
        hash_sha256=plugin.hash_sha256,
        size=plugin.size,
        meta=json.dumps(plugin.meta)
    )
    db.add(db_plugin)
    db.commit()
    db.refresh(db_plugin)
    return db_plugin


def delete_plugin_record(db: Session, plugin_id: int) -> Optional[models.Plugin]:
    db_plugin = get_plugin_by_id(db, plugin_id)
    if db_plugin:
        db.delete(db_plugin)
        db.commit()
    return db_plugin


# --- Mods CRUD (dedicated table) ---
def get_mod_by_id(db: Session, mod_id: int) -> Optional[models.Mod]:
    return db.query(models.Mod).filter(models.Mod.id == mod_id).first()


def get_mod_by_hash(db: Session, hash_md5: str) -> Optional[models.Mod]:
    return db.query(models.Mod).filter(models.Mod.hash_md5 == hash_md5).first()


def get_all_mods(db: Session, skip: int = 0, limit: int = 100) -> List[models.Mod]:
    return db.query(models.Mod).offset(skip).limit(limit).all()


def create_mod_record(db: Session, mod: schemas.ModDBCreate) -> models.Mod:
    db_mod = models.Mod(
        file_name=mod.file_name,
        path=mod.path,
        url=mod.url,
        hash_md5=mod.hash_md5,
        hash_sha256=mod.hash_sha256,
        size=mod.size,
        meta=json.dumps(mod.meta)
    )
    db.add(db_mod)
    db.commit()
    db.refresh(db_mod)
    return db_mod


def get_mod_by_path(db: Session, path: str) -> Optional[models.Mod]:
    return db.query(models.Mod).filter(models.Mod.path == path).first()


def update_mod_record(db: Session, mod_rec: models.Mod, *, file_name: Optional[str] = None,
                      path: Optional[str] = None, url: Optional[str] = None,
                      hash_md5: Optional[str] = None, hash_sha256: Optional[str] = None,
                      size: Optional[int] = None, meta: Optional[dict] = None) -> models.Mod:
    if file_name is not None:
        mod_rec.file_name = file_name
    if path is not None:
        mod_rec.path = path
    if url is not None:
        mod_rec.url = url
    if hash_md5 is not None:
        mod_rec.hash_md5 = hash_md5
    if hash_sha256 is not None:
        mod_rec.hash_sha256 = hash_sha256
    if size is not None:
        mod_rec.size = size
    if meta is not None:
        mod_rec.meta = json.dumps(meta)
    db.add(mod_rec)
    db.commit()
    db.refresh(mod_rec)
    return mod_rec


def delete_mod_record(db: Session, mod_id: int) -> Optional[models.Mod]:
    db_mod = get_mod_by_id(db, mod_id)
    if db_mod:
        db.delete(db_mod)
        db.commit()
    return db_mod


def delete_mod_by_path(db: Session, path: str) -> Optional[models.Mod]:
    rec = get_mod_by_path(db, path)
    if rec:
        db.delete(rec)
        db.commit()
        return rec
    return None


def add_server_to_mod(db: Session, mod_id: int, server_id: int):
    db_mod = get_mod_by_id(db, mod_id)
    if db_mod:
        installed_list = json.loads(db_mod.servers_installed or '[]')
        if server_id not in installed_list:
            installed_list.append(server_id)
            db_mod.servers_installed = json.dumps(installed_list)
            db.commit()


def remove_server_from_mod(db: Session, mod_id: int, server_id: int):
    db_mod = get_mod_by_id(db, mod_id)
    if db_mod:
        installed_list = json.loads(db_mod.servers_installed or '[]')
        if server_id in installed_list:
            installed_list.remove(server_id)
            db_mod.servers_installed = json.dumps(installed_list)
            db.commit()


# --- Mods cleanup for server deletion ---
def list_mods_by_path_prefix(db: Session, prefix: str) -> List[models.Mod]:
    return db.query(models.Mod).filter(models.Mod.path.like(f"{prefix}%")).all()


def cleanup_mods_for_server_path(db: Session, server_id: int, server_path: str) -> dict:
    """在删除服务器时清理 mods 表：
    - 删除 path 位于该服务器 mods / plugins(velocity) 目录下的记录
    - 从其他记录的 servers_installed 中移除该 server_id
    返回删除与更新的数量统计。
    """
    from pathlib import Path
    base = Path(server_path).resolve()
    prefixes = [
        str((base / 'server' / 'mods').resolve()),
        str((base / 'server' / 'plugins').resolve()),  # 兼容 Velocity
    ]

    # 1) 删除该服务器下的记录（mods 与 plugins）
    deleted = 0
    for prefix in prefixes:
        to_delete = list_mods_by_path_prefix(db, prefix)
        for rec in to_delete:
            try:
                db.delete(rec)
                deleted += 1
            except Exception:
                # 保底：如果删除失败，至少移除安装关系
                try:
                    lst = json.loads(rec.servers_installed or '[]')
                    if server_id in lst:
                        lst.remove(server_id)
                        rec.servers_installed = json.dumps(lst)
                        db.add(rec)
                except Exception:
                    pass
    db.commit()

    # 2) 其他记录中移除该 server_id 的安装关系（可能存在非该路径下的关联残留）
    updated = 0
    candidates = db.query(models.Mod).filter(models.Mod.servers_installed.like(f"%{server_id}%")).all()
    for rec in candidates:
        try:
            lst = json.loads(rec.servers_installed or '[]')
            if server_id in lst:
                lst.remove(server_id)
                rec.servers_installed = json.dumps(lst)
                db.add(rec)
                updated += 1
        except Exception:
            continue
    db.commit()
    return {"deleted": deleted, "updated": updated}


def add_server_to_plugin(db: Session, plugin_id: int, server_id: int):
    db_plugin = get_plugin_by_id(db, plugin_id)
    if db_plugin:
        installed_list = json.loads(db_plugin.servers_installed)
        if server_id not in installed_list:
            installed_list.append(server_id)
            db_plugin.servers_installed = json.dumps(installed_list)
            db.commit()


def remove_server_from_plugin(db: Session, plugin_id: int, server_id: int):
    db_plugin = get_plugin_by_id(db, plugin_id)
    if db_plugin:
        installed_list = json.loads(db_plugin.servers_installed)
        if server_id in installed_list:
            installed_list.remove(server_id)
            db_plugin.servers_installed = json.dumps(installed_list)
            db.commit()


def cleanup_plugins_for_server(db: Session, server_id: int) -> int:
    """从 plugin 表的 servers_installed JSON 中移除指定 server_id。
    返回更新的记录数。
    """
    updated = 0
    candidates = db.query(_models.Plugin).filter(_models.Plugin.servers_installed.like(f"%{server_id}%")).all()
    for rec in candidates:
        try:
            lst = json.loads(rec.servers_installed or '[]')
            if server_id in lst:
                lst.remove(server_id)
                rec.servers_installed = json.dumps(lst)
                db.add(rec)
                updated += 1
        except Exception:
            continue
    db.commit()
    return updated


# --- Server Link Group CRUD ---
def get_server_link_group_by_id(db: Session, group_id: int) -> Optional[models.ServerLinkGroup]:
    return db.query(models.ServerLinkGroup).filter(models.ServerLinkGroup.id == group_id).first()


def get_server_link_group_by_name(db: Session, name: str) -> Optional[models.ServerLinkGroup]:
    return db.query(models.ServerLinkGroup).filter(models.ServerLinkGroup.name == name).first()


def list_server_link_groups(db: Session) -> List[models.ServerLinkGroup]:
    return db.query(models.ServerLinkGroup).all()


def _normalize_chat_bindings(bindings: Optional[List[Any]]) -> List[str]:
    result: List[str] = []
    for item in bindings or []:
        try:
            text = str(item).strip()
        except Exception:
            continue
        if text.isdigit():
            result.append(text)
            break
    return result


def create_server_link_group(db: Session, payload: schemas.ServerLinkGroupCreate) -> models.ServerLinkGroup:
    if get_server_link_group_by_name(db, payload.name):
        raise ValueError("该服务器组名称已存在")
    rec = models.ServerLinkGroup(
        name=payload.name,
        server_ids=json.dumps(payload.server_ids or []),
        data_source_ids=json.dumps(payload.data_source_ids or []),
        chat_bindings=json.dumps(_normalize_chat_bindings(payload.chat_bindings)),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def update_server_link_group(db: Session, group_id: int, payload: schemas.ServerLinkGroupUpdate) -> Optional[
    models.ServerLinkGroup]:
    rec = get_server_link_group_by_id(db, group_id)
    if not rec:
        return None
    if payload.name is not None:
        # 检查重名（排除自己）
        other = get_server_link_group_by_name(db, payload.name)
        if other and other.id != rec.id:
            raise ValueError("该服务器组名称已存在")
        rec.name = payload.name
    if payload.server_ids is not None:
        rec.server_ids = json.dumps(payload.server_ids)
    if payload.data_source_ids is not None:
        rec.data_source_ids = json.dumps(payload.data_source_ids)
    if payload.chat_bindings is not None:
        rec.chat_bindings = json.dumps(_normalize_chat_bindings(payload.chat_bindings))
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def delete_server_link_group(db: Session, group_id: int) -> Optional[models.ServerLinkGroup]:
    rec = get_server_link_group_by_id(db, group_id)
    if not rec:
        return None
    # 从所有用户的 server_link_group_ids 中移除该组
    cleanup_users_for_server_link_group(db, group_id)
    db.delete(rec)
    db.commit()
    return rec


def cleanup_users_for_server_link_group(db: Session, group_id: int) -> int:
    """从所有用户的 server_link_group_ids JSON 中移除指定 group_id，返回更新的用户数量。"""
    users = get_all_users(db)
    updated = 0
    for u in users:
        try:
            ids = json.loads(u.server_link_group_ids or '[]')
            if group_id in ids:
                ids.remove(group_id)
                u.server_link_group_ids = json.dumps(ids)
                db.add(u)
                updated += 1
        except Exception:
            continue
    db.commit()
    return updated


def cleanup_server_link_groups_for_server(db: Session, server_id: int) -> int:
    """从所有 server_link_groups 的 server_ids JSON 中移除 server_id，返回更新的组数量。"""
    groups = list_server_link_groups(db)
    updated = 0
    for g in groups:
        try:
            ids = json.loads(g.server_ids or '[]')
            if server_id in ids:
                ids.remove(server_id)
                g.server_ids = json.dumps(ids)
                db.add(g)
                updated += 1
        except Exception:
            continue
    db.commit()
    return updated


def add_server_to_groups(db: Session, server_id: int, group_ids: List[int]) -> int:
    """将服务器添加到多个服务器组的 server_ids 中，返回更新的组数量。"""
    if not group_ids:
        return 0
    updated = 0
    for gid in group_ids:
        rec = get_server_link_group_by_id(db, gid)
        if not rec:
            continue
        try:
            ids = json.loads(rec.server_ids or '[]')
            if server_id not in ids:
                ids.append(server_id)
                rec.server_ids = json.dumps(ids)
                db.add(rec)
                updated += 1
        except Exception:
            continue
    db.commit()
    return updated


# --- Player Session CRUD ---
def create_player_session(db: Session, server_id: int, player_uuid: str) -> models.PlayerSession:
    # 强制结束该玩家在该服可能存在的未关闭会话
    close_player_session(db, server_id, player_uuid)
    
    sess = models.PlayerSession(
        server_id=server_id,
        player_uuid=player_uuid,
        logout_time=None
    )
    # login_time 有 server_default，但也可用 python 传
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def close_player_session(db: Session, server_id: int, player_uuid: str):
    from sqlalchemy.sql import func
    # 查找所有未结束的会话并关闭（理论上应该只有一个，但为了稳健处理所有）
    sessions = db.query(models.PlayerSession).filter(
        models.PlayerSession.server_id == server_id,
        models.PlayerSession.player_uuid == player_uuid,
        models.PlayerSession.logout_time.is_(None)
    ).all()
    if sessions:
        player = get_player_by_uuid(db, player_uuid)
        now = datetime.datetime.now(datetime.timezone.utc)
        for s in sessions:
            s.logout_time = func.now()
            db.add(s)

        db.commit()


# --- Player Position CRUD ---
def add_player_position(
    db: Session,
    player_id: int,
    server_id: int,
    ts: datetime,
    x: float,
    y: float,
    z: float,
    dim: Optional[str] = None,
) -> models.PlayerPosition:
    row = models.PlayerPosition(
        player_id=player_id,
        server_id=server_id,
        ts=ts,
        x=x,
        y=y,
        z=z,
        dim=dim,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_player_positions(
    db: Session,
    player_id: int,
    start: datetime,
    end: datetime,
    server_ids: Optional[List[int]] = None,
) -> List[models.PlayerPosition]:
    q = db.query(models.PlayerPosition).filter(
        models.PlayerPosition.player_id == player_id,
        models.PlayerPosition.ts >= start,
        models.PlayerPosition.ts <= end,
    )
    if server_ids:
        q = q.filter(models.PlayerPosition.server_id.in_(server_ids))
    return q.order_by(models.PlayerPosition.ts.asc()).all()


def delete_player_positions_for_server(db: Session, server_id: int) -> int:
    return db.query(models.PlayerPosition).filter(models.PlayerPosition.server_id == server_id).delete()


# --- System Settings CRUD ---
DEFAULT_SYSTEM_SETTINGS = {
    "python_executable": ".venv/bin/python",
    "java_command": "java",
    "timezone": "Asia/Shanghai",
    "stats_ignore_server": [],  # 忽略入库的服务器ID列表
    # 新增网页可配置项
    "token_expire_minutes": 10080,  # Token 有效期（分钟），默认 7 天
    "allow_register": True,  # 是否允许新用户注册
    "register_require_qq": True,  # 注册时 QQ 是否为必填
    "register_require_player_name": True,  # 注册时玩家名是否为必填
    "register_player_name_must_exist": True,  # 注册时填写的玩家名是否必须已存在
    "default_user_role": "USER",  # 新用户默认角色
    "copy_limit_mbps": 1024.0,  # 文件复制速度限制（MB/s）
}


def _ensure_system_settings_row(db: Session) -> models.SystemSettings:
    rec = db.query(models.SystemSettings).first()
    if not rec:
        rec = models.SystemSettings(data=json.dumps(DEFAULT_SYSTEM_SETTINGS))
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return rec


def get_system_settings(db: Session) -> models.SystemSettings:
    return _ensure_system_settings_row(db)


def get_system_settings_data(db: Session) -> dict:
    rec = _ensure_system_settings_row(db)
    try:
        data = json.loads(rec.data or "{}")
    except json.JSONDecodeError:
        data = {}
    # 用默认值填充缺失项
    merged = {**DEFAULT_SYSTEM_SETTINGS, **(data or {})}
    return merged


def update_system_settings(db: Session, patch: dict) -> dict:
    rec = _ensure_system_settings_row(db)
    try:
        current = json.loads(rec.data or "{}")
    except json.JSONDecodeError:
        current = {}
    current = current or {}
    current.update({k: v for k, v in (patch or {}).items() if v is not None})
    rec.data = json.dumps(current)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    # 返回合并后的全量配置（带默认值）
    merged = {**DEFAULT_SYSTEM_SETTINGS, **current}
    return merged


# --- JsonDim CRUD ---
def get_json_dim_map_for_server(db: Session, server_id: int) -> dict[str, int | None]:
    """返回 {json_file_name: last_read_time or None} 的映射。"""
    rows = db.query(models.JsonDim).filter(models.JsonDim.server_id == server_id).all()
    out = {}
    for r in rows:
        out[r.json_file_name] = r.last_read_time if r.last_read_time is not None else None
    return out


def upsert_json_dim_last_read(db: Session, server_id: int, json_file_name: str, last_read_time: int) -> models.JsonDim:
    rec = (
        db.query(models.JsonDim)
        .filter(models.JsonDim.server_id == server_id, models.JsonDim.json_file_name == json_file_name)
        .first()
    )
    if rec is None:
        rec = models.JsonDim(server_id=server_id, json_file_name=json_file_name, last_read_time=last_read_time)
        db.add(rec)
    else:
        rec.last_read_time = last_read_time
        db.add(rec)
    return rec


# --- Player CRUD ---
def get_player_by_id(db: Session, id: int) -> Optional[models.Player]:
    return db.query(models.Player).filter(models.Player.id == id).first()


def get_player_by_uuid(db: Session, uuid: str) -> Optional[models.Player]:
    return db.query(models.Player).filter(models.Player.uuid == uuid).first()


def get_player_by_name(db: Session, name: str) -> Optional[models.Player]:
    return db.query(models.Player).filter(models.Player.player_name == name).first()

def get_player_by_name_non_sensitive(db: Session, name: str) -> Optional[models.Player]:
    return db.query(models.Player).filter(models.Player.player_name.ilike(name)).first()

def set_player_is_bot(db: Session, name: str, is_bot: bool = True) -> Optional[models.Player]:
    rec = get_player_by_name(db, name)
    if rec:
        rec.is_bot = is_bot
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return rec


def list_players(db: Session, *, scope: str = "all") -> list[models.Player]:
    q = db.query(models.Player)
    if scope == "official_only":
        # 仅正版：is_offline == False
        q = q.filter(models.Player.is_offline == False)  # noqa: E712
    elif scope == "include_cracked":
        # 包括盗版：is_offline == False 或者 已设置名字（允许离线服手动命名）
        q = q.filter(((models.Player.is_offline == False) | (models.Player.player_name.isnot(None))))  # noqa: E712
    else:
        # all
        pass
    return q.all()


def create_player(db: Session, *, uuid: str, player_name: Optional[str] = None,
                  play_time: Optional[dict] = None, is_offline: bool = False) -> models.Player:
    rec = models.Player(uuid=uuid, player_name=player_name, play_time=json.dumps(play_time or {}),
                        is_offline=is_offline)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def update_player_name(db: Session, rec: models.Player, *, name: Optional[str],
                       is_offline: Optional[bool] = None) -> models.Player:
    rec.player_name = name
    if is_offline is not None:
        rec.is_offline = bool(is_offline)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def set_player_play_time_for_server(db: Session, rec: models.Player, server_name: str, ticks: int) -> models.Player:
    try:
        pt = json.loads(rec.play_time or '{}')
    except Exception:
        pt = {}
    pt[server_name] = int(max(0, ticks))
    rec.play_time = json.dumps(pt)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def add_player_play_time_ticks(db: Session, rec: models.Player, server_name: str, ticks_delta: int) -> models.Player:
    try:
        pt = json.loads(rec.play_time or '{}')
    except Exception:
        pt = {}
    current = int(pt.get(server_name, 0) or 0)
    pt[server_name] = max(0, current + int(ticks_delta))
    rec.play_time = json.dumps(pt)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def remove_server_from_player_play_time(db: Session, rec: models.Player, server_name: str) -> models.Player:
    try:
        pt = json.loads(rec.play_time or '{}')
    except Exception:
        pt = {}
    if server_name in pt:
        del pt[server_name]
    rec.play_time = json.dumps(pt)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def bulk_remove_server_from_all_players(db: Session, server_name: str) -> int:
    updated = 0
    players = db.query(models.Player).all()
    for rec in players:
        try:
            pt = json.loads(rec.play_time or '{}')
        except Exception:
            pt = {}
        if server_name in pt:
            del pt[server_name]
            rec.play_time = json.dumps(pt)
            db.add(rec)
            updated += 1
    db.commit()
    return updated


def get_servers_player_joined(db: Session, player_uuid: str) -> List[models.Server]:
    """
    根据玩家 UUID 检查所有服务器的 playerdata 目录，
    返回该玩家加入过的服务器列表。
    """
    from pathlib import Path
    servers = get_all_servers(db)
    joined_servers: List[models.Server] = []
    for server in servers:
        try:
            playerdata_path = Path(server.path) / 'server' / 'world' / 'playerdata' / f'{player_uuid}.dat'
            if playerdata_path.exists():
                joined_servers.append(server)
        except Exception:
            continue
    return joined_servers


def get_server_link_groups_for_servers(db: Session, server_ids: List[int]) -> List[int]:
    """
    根据服务器 ID 列表，找到这些服务器所属的服务器组 ID 列表（去重）。
    """
    if not server_ids:
        return []
    groups = list_server_link_groups(db)
    group_ids: set[int] = set()
    for g in groups:
        try:
            ids = json.loads(g.server_ids or '[]')
            for sid in server_ids:
                if sid in ids:
                    group_ids.add(g.id)
                    break
        except Exception:
            continue
    return list(group_ids)


def get_server_link_groups_for_player(db: Session, player_uuid: str) -> List[dict]:
    """
    根据玩家 UUID 获取其所属的服务器组列表（包含组ID和名称）。
    """
    joined_servers = get_servers_player_joined(db, player_uuid)
    if not joined_servers:
        return []
    server_ids = [s.id for s in joined_servers]
    group_ids = get_server_link_groups_for_servers(db, server_ids)
    if not group_ids:
        return []
    groups = list_server_link_groups(db)
    return [{'id': g.id, 'name': g.name} for g in groups if g.id in group_ids]
