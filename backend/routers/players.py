# backend/routers/players.py

import json
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path

from backend.core import crud, models, schemas
from backend.core.auth import require_role
from backend.core.database import get_db
from backend.core.schemas import Role
from pydantic import BaseModel
from backend.services import player_manager

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

