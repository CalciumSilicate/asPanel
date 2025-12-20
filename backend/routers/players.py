# backend/routers/players.py

import json
import ipaddress
import uuid
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path

from backend.core import crud, models, schemas
from backend.core.auth import require_role
from backend.core.api import get_uuid_by_name
from backend.core.database import get_db
from backend.core.schemas import Role
from backend.core.dependencies import mcdr_manager
from pydantic import BaseModel
from backend.services import player_manager
from backend.core.constants import UUID_HYPHEN_PATTERN

router = APIRouter(
    prefix="/api/players",
    tags=["Players"],
)


@router.get("", response_model=List[schemas.Player])
async def list_players(scope: Optional[str] = "all", db: Session = Depends(get_db),
                       _user: models.User = Depends(require_role(Role.USER))):
    scope = scope or "all"
    if scope not in ("all", "official_only", "include_cracked"):
        scope = "all"
    items = crud.list_players(db, scope=scope)
    # 直接返回 ORM；Pydantic v2 会按 from_attributes 转换，并通过字段验证器解析 play_time
    return items


@router.post("/refresh-uuids")
async def refresh_uuids(_user: models.User = Depends(require_role(Role.ADMIN))):
    """逻辑1：扫描所有服务器 world/playerdata，补全数据库中的玩家 UUID 记录。"""
    return player_manager.ensure_players_from_worlds()


@router.post("/refresh-names-official")
async def refresh_names_official(background_tasks: BackgroundTasks,
                                 _user: models.User = Depends(require_role(Role.ADMIN))):
    """逻辑2（触发）：为 player_name 为空且 is_offline=False 的记录尝试解析正版玩家名；失败则标记 is_offline=True。
    后台异步执行，避免阻塞请求。
    """
    background_tasks.add_task(player_manager.refresh_missing_official_names)
    return {"scheduled": True, "task": "refresh-names-official"}


@router.post("/refresh-names-offline")
async def refresh_names_offline(_user: models.User = Depends(require_role(Role.ADMIN))):
    """逻辑3（触发）：为 is_offline=True 的记录再次尝试解析玩家名；若成功则更新并设置 is_offline=False。"""
    return await player_manager.refresh_offline_names()


@router.post("/refresh-playtime")
async def refresh_playtime(background_tasks: BackgroundTasks,
                           _user: models.User = Depends(require_role(Role.ADMIN))):
    """逻辑4（触发）：为所有玩家重算各服务器的时长（读取 world/stats/<uuid>.json）。
    后台异步执行，避免阻塞请求。
    """
    background_tasks.add_task(player_manager.recalc_all_play_time)
    return {"scheduled": True, "task": "refresh-playtime"}


@router.post("/refresh-all-names")
async def refresh_names_official(background_tasks: BackgroundTasks,
                                 _user: models.User = Depends(require_role(Role.ADMIN))):
    """逻辑2+3（触发）：为所有玩家尝试解析正版玩家名，失败则标记为离线玩家；为离线玩家再次尝试解析玩家名。"""
    background_tasks.add_task(player_manager.refresh_all_names)
    return {"scheduled": True, "task": "refresh-all-names"}


@router.get("/whitelist-uuids", response_model=List[str])
async def get_whitelist_uuids(db: Session = Depends(get_db),
                              _user: models.User = Depends(require_role(Role.USER))):
    """聚合所有服务器 `<server_path>/server/whitelist.json` 中的 uuid 并去重返回。
    - 文件不存在或解析失败的服务器将跳过。
    - whitelist.json 典型为数组对象，包含键 `uuid` 与 `name`。
    """
    uuids: set[str] = set()
    servers = crud.get_all_servers(db)
    for s in servers:
        try:
            server_root = Path(s.path) / 'server'
            wl = server_root / 'whitelist.json'
            if not wl.exists():
                continue
            data = json.loads(wl.read_text(encoding='utf-8'))
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        u = item.get('uuid')
                        if isinstance(u, str) and u:
                            uuids.add(u)
        except Exception:
            # 单个服务器异常忽略，继续收集其他服务器
            continue
    return sorted(uuids)


class DataSourceSelectionUpdate(BaseModel):
    servers: List[str]


@router.get("/data-source-selection", response_model=List[str])
async def get_data_source_selection(db: Session = Depends(get_db),
                                    _user: models.User = Depends(require_role(Role.USER))):
    """获取玩家管理页面最近一次保存的数据来源（服务器名列表）。"""
    data = crud.get_system_settings_data(db)
    lst = data.get('player_manager_selected_servers') or []
    if isinstance(lst, list):
        return [str(x) for x in lst]
    return []


@router.patch("/data-source-selection", response_model=List[str])
async def set_data_source_selection(payload: DataSourceSelectionUpdate,
                                    db: Session = Depends(get_db),
                                    _user: models.User = Depends(require_role(Role.USER))):
    """保存玩家管理页面数据来源（服务器名列表）。"""
    # 存入系统设置 JSON 中
    current = crud.update_system_settings(db, {'player_manager_selected_servers': payload.servers or []})
    lst = current.get('player_manager_selected_servers') or []
    if isinstance(lst, list):
        return [str(x) for x in lst]
    return []


@router.patch("/{player_id}/name", response_model=schemas.Player)
async def set_offline_player_name(player_id: int, payload: schemas.PlayerNameUpdate, db: Session = Depends(get_db),
                                  _user: models.User = Depends(require_role(Role.ADMIN))):
    """仅当该玩家记录 is_offline=True 时，允许设置/修改名字。正版玩家（is_offline=False）不可修改。"""
    rec = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not rec:
        raise HTTPException(404, "玩家不存在")
    if rec.is_offline is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="正版玩家不可修改名字")
    if not payload.name or not isinstance(payload.name, str):
        raise HTTPException(400, "无效的名字")
    rec = crud.update_player_name(db, rec, name=payload.name, is_offline=True)
    return rec


def _server_dir_name(s: models.Server) -> str:
    try:
        return Path(s.path).name
    except Exception:
        return str(s.name)


def _server_type(s: models.Server) -> str:
    try:
        cfg = json.loads(s.core_config or "{}")
        return str(cfg.get("server_type") or "").lower()
    except Exception:
        return ""


def _load_json_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_json_atomic(path: Path, data: object):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


class PlayerWhitelistAddRequest(BaseModel):
    player_name: str
    is_official: bool = True
    servers: List[str]


@router.post("/whitelist")
async def add_player_to_whitelist(payload: PlayerWhitelistAddRequest,
                                  db: Session = Depends(get_db),
                                  _user: models.User = Depends(require_role(Role.ADMIN))):
    player_name = (payload.player_name or "").strip()
    if not player_name:
        raise HTTPException(status_code=400, detail="无效的玩家名")
    target_names = [str(x).strip() for x in (payload.servers or []) if str(x).strip()]
    if not target_names:
        raise HTTPException(status_code=400, detail="请选择至少一个服务器")

    def offline_uuid_for(name: str) -> str:
        raw = ("OfflinePlayer:" + name).encode("utf-8")
        md5 = bytearray(hashlib.md5(raw).digest())
        md5[6] = (md5[6] & 0x0F) | 0x30
        md5[8] = (md5[8] & 0x3F) | 0x80
        return str(uuid.UUID(bytes=bytes(md5)))

    def is_process_running(server_id: int) -> bool:
        proc = mcdr_manager.processes.get(server_id)
        return proc is not None and proc.returncode is None

    servers = crud.get_all_servers(db)
    by_dir = {_server_dir_name(s): s for s in servers}

    updated: list[str] = []
    via_command: list[str] = []
    via_file: list[str] = []
    skipped_velocity: list[str] = []
    not_found: list[str] = []
    errors: list[dict] = []
    file_uuids: dict[str, str] = {}

    official_uuid: Optional[str] = None
    try:
        p = crud.get_player_by_name(db, player_name)
        if p and p.uuid and p.is_offline is False and UUID_HYPHEN_PATTERN.match(p.uuid):
            official_uuid = p.uuid
    except Exception:
        official_uuid = None

    for server_name in target_names:
        s = by_dir.get(server_name)
        if not s:
            not_found.append(server_name)
            continue
        if _server_type(s) == "velocity":
            skipped_velocity.append(server_name)
            continue
        try:
            server_root = Path(s.path) / "server"
            wl_path = server_root / "whitelist.json"
            wl = _load_json_list(wl_path)

            uuid_to_use: Optional[str] = None
            if payload.is_official is True:
                if official_uuid is None:
                    official_uuid = await get_uuid_by_name(player_name)
                uuid_to_use = official_uuid
                if not uuid_to_use or not UUID_HYPHEN_PATTERN.match(uuid_to_use):
                    raise HTTPException(status_code=400, detail=f"无法解析正版 UUID：{player_name}")
            else:
                uuid_to_use = offline_uuid_for(player_name)

            found = False
            for item in wl:
                if not isinstance(item, dict):
                    continue
                if str(item.get("uuid") or "") == uuid_to_use:
                    item["name"] = player_name
                    found = True
                    break
            if not found:
                wl.append({"uuid": uuid_to_use, "name": player_name})

            _write_json_atomic(wl_path, wl)
            file_uuids[server_name] = uuid_to_use
            updated.append(server_name)
            via_file.append(server_name)

            if is_process_running(int(s.id)):
                try:
                    await mcdr_manager.send_command(s, "whitelist reload")
                    via_command.append(server_name)
                except Exception:
                    pass
        except Exception as e:
            errors.append({"server": server_name, "error": str(e)})

    return {
        "player_name": player_name,
        "updated": updated,
        "via_command": via_command,
        "via_file": via_file,
        "file_uuids": file_uuids,
        "skipped_velocity": skipped_velocity,
        "not_found": not_found,
        "errors": errors,
    }


@router.get("/op-servers", response_model=dict)
async def get_player_op_servers(uuids: Optional[List[str]] = None,
                                db: Session = Depends(get_db),
                                _user: models.User = Depends(require_role(Role.ADMIN))):
    uuid_filter = None
    if uuids is not None:
        uuid_filter = {str(u).strip() for u in uuids if str(u).strip()}

    result: dict[str, list[str]] = {}
    if uuid_filter is not None:
        for u in uuid_filter:
            result[u] = []

    servers = crud.get_all_servers(db)
    for s in servers:
        if _server_type(s) == "velocity":
            continue
        server_name = _server_dir_name(s)
        ops_path = Path(s.path) / "server" / "ops.json"
        ops = _load_json_list(ops_path)
        for item in ops:
            if not isinstance(item, dict):
                continue
            u = item.get("uuid")
            if not isinstance(u, str) or not u:
                continue
            if uuid_filter is not None and u not in uuid_filter:
                continue
            result.setdefault(u, [])
            if server_name not in result[u]:
                result[u].append(server_name)

    for u in list(result.keys()):
        result[u] = sorted(result[u])
    return result


class PlayerBanRequest(BaseModel):
    type: str  # "player" | "ip"
    servers: List[str]
    uuid: Optional[str] = None
    name: Optional[str] = None
    ip: Optional[str] = None
    reason: Optional[str] = None


@router.post("/ban")
async def ban_player_or_ip(payload: PlayerBanRequest,
                           db: Session = Depends(get_db),
                           _user: models.User = Depends(require_role(Role.ADMIN))):
    ban_type = (payload.type or "").strip().lower()
    if ban_type not in ("player", "ip"):
        raise HTTPException(status_code=400, detail="无效的封禁类型")

    target_names = [str(x).strip() for x in (payload.servers or []) if str(x).strip()]
    if not target_names:
        raise HTTPException(status_code=400, detail="请选择至少一个服务器")

    uuid = (payload.uuid or "").strip()
    ip = (payload.ip or "").strip()
    name = (payload.name or "").strip()
    reason = (payload.reason or "").strip() or "Banned by ASPanel"

    if ban_type == "player":
        if not UUID_HYPHEN_PATTERN.match(uuid):
            raise HTTPException(status_code=400, detail="无效的 UUID")
        if not name:
            p = crud.get_player_by_uuid(db, uuid)
            if p and p.player_name:
                name = str(p.player_name)
    else:
        try:
            ipaddress.ip_address(ip)
        except Exception:
            raise HTTPException(status_code=400, detail="无效的 IP")

    servers = crud.get_all_servers(db)
    by_dir = {_server_dir_name(s): s for s in servers}

    updated: list[str] = []
    skipped_velocity: list[str] = []
    not_found: list[str] = []
    errors: list[dict] = []

    created = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %z")
    for server_name in target_names:
        s = by_dir.get(server_name)
        if not s:
            not_found.append(server_name)
            continue
        if _server_type(s) == "velocity":
            skipped_velocity.append(server_name)
            continue
        try:
            server_root = Path(s.path) / "server"
            if ban_type == "player":
                ban_path = server_root / "banned-players.json"
                bans = _load_json_list(ban_path)
                exists = False
                for item in bans:
                    if isinstance(item, dict) and str(item.get("uuid") or "") == uuid:
                        exists = True
                        break
                if not exists:
                    bans.append({
                        "uuid": uuid,
                        "name": name or "",
                        "created": created,
                        "source": "ASPanel",
                        "expires": "forever",
                        "reason": reason,
                    })
                _write_json_atomic(ban_path, bans)
            else:
                ban_path = server_root / "banned-ips.json"
                bans = _load_json_list(ban_path)
                exists = False
                for item in bans:
                    if isinstance(item, dict) and str(item.get("ip") or "") == ip:
                        exists = True
                        break
                if not exists:
                    bans.append({
                        "ip": ip,
                        "created": created,
                        "source": "ASPanel",
                        "expires": "forever",
                        "reason": reason,
                    })
                _write_json_atomic(ban_path, bans)

            updated.append(server_name)
        except Exception as e:
            errors.append({"server": server_name, "error": str(e)})

    return {
        "type": ban_type,
        "updated": updated,
        "skipped_velocity": skipped_velocity,
        "not_found": not_found,
        "errors": errors,
    }
