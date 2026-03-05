# backend/routers/world_map.py

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from backend.core import crud, models
from backend.core.auth import require_role
from backend.core.database import get_db
from backend.core.schemas import Role
from backend.core.constants import MAP_JSON_STORAGE_PATH

router = APIRouter(prefix="/api", tags=["WorldMap"])

DIM_FILES = {
    "nether": "the_nether.json",
    "end":    "the_end.json",
}

_EMPTY_MAP = {
    "svgViewBoxZoom": 100,
    "svgViewBoxMin": {"x": 0, "y": 0},
    "images": [],
    "graph": {"options": {"type": "directed", "multi": True, "allowSelfLoops": True},
              "attributes": {}, "nodes": [], "edges": []},
}


def _map_dir(server_id: int) -> Path:
    return MAP_JSON_STORAGE_PATH / str(server_id)


# ---------- servers with map data ----------

@router.get("/tools/world-map/servers")
def list_map_servers(
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.USER)),
):
    result = []
    if not MAP_JSON_STORAGE_PATH.exists():
        return result
    for entry in sorted(MAP_JSON_STORAGE_PATH.iterdir()):
        if not entry.is_dir():
            continue
        try:
            server_id = int(entry.name)
        except ValueError:
            continue
        server = crud.get_server_by_id(db, server_id)
        if not server:
            continue
        available = [dim for dim, fname in DIM_FILES.items() if (entry / fname).exists()]
        if not available:
            continue
        result.append({
            "id": server_id,
            "name": server.name or Path(server.path).name,
            "available_dims": available,
        })
    return result


# ---------- map data CRUD ----------

@router.get("/tools/world-map/{server_id}/map-data")
def get_map_data(
    server_id: int,
    dim: str = "nether",
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.USER)),
):
    if dim not in DIM_FILES:
        raise HTTPException(400, f"Unknown dim: {dim}")
    if not crud.get_server_by_id(db, server_id):
        raise HTTPException(404, "服务器不存在")
    p = _map_dir(server_id) / DIM_FILES[dim]
    if not p.exists():
        raise HTTPException(404, "地图不存在")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"读取地图数据失败: {e}")


@router.put("/tools/world-map/{server_id}/map-data")
def save_map_data(
    server_id: int,
    body: Any = Body(...),
    dim: str = "nether",
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.HELPER)),
):
    if dim not in DIM_FILES:
        raise HTTPException(400, f"Unknown dim: {dim}")
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(404, "服务器不存在")
    d = _map_dir(server_id)
    d.mkdir(parents=True, exist_ok=True)
    try:
        (d / DIM_FILES[dim]).write_text(
            json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        raise HTTPException(500, f"保存地图数据失败: {e}")
    # sync Server.map with the actual file path (consistent with upload endpoint)
    try:
        map_meta = json.loads(server.map or "{}")
    except Exception:
        map_meta = {}
    flag_key = "nether_json" if dim == "nether" else "end_json"
    map_meta[flag_key] = str(d / DIM_FILES[dim])
    server.map = json.dumps(map_meta, ensure_ascii=False)
    db.commit()
    return {"ok": True}


# ---------- per-server config (bluemap_url, etc.) ----------

@router.get("/tools/world-map/{server_id}/config")
def get_map_config(
    server_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.USER)),
):
    if not crud.get_server_by_id(db, server_id):
        raise HTTPException(404, "服务器不存在")
    p = _map_dir(server_id) / "config.json"
    if not p.exists():
        return {"bluemap_url": ""}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"bluemap_url": ""}


@router.put("/tools/world-map/{server_id}/config")
def save_map_config(
    server_id: int,
    body: dict,
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.HELPER)),
):
    if not crud.get_server_by_id(db, server_id):
        raise HTTPException(404, "服务器不存在")
    d = _map_dir(server_id)
    d.mkdir(parents=True, exist_ok=True)
    filtered = {k: v for k, v in body.items() if k in {"bluemap_url"}}
    try:
        (d / "config.json").write_text(json.dumps(filtered, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        raise HTTPException(500, f"保存配置失败: {e}")
    return {"ok": True}


# ---------- players + positions ----------

@router.get("/tools/world-map/{server_id}/players")
def get_map_players(
    server_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.USER)),
):
    """Return all players with a recorded position on this server (last 365 days)
    plus any currently online player even without a position.
    """
    from backend.services.ws import PLAYERS_BY_SERVER

    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(404, "服务器不存在")

    server_name = Path(server.path).name
    online_names: set = set(PLAYERS_BY_SERVER.get(server_name, set()))

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=365)

    # latest position per player for this server
    latest_ts_sub = (
        db.query(
            models.PlayerPosition.player_id,
            sqlfunc.max(models.PlayerPosition.ts).label("max_ts"),
        )
        .filter(
            models.PlayerPosition.server_id == server_id,
            models.PlayerPosition.ts >= cutoff,
        )
        .group_by(models.PlayerPosition.player_id)
        .subquery()
    )
    latest_rows = (
        db.query(models.PlayerPosition)
        .join(
            latest_ts_sub,
            (models.PlayerPosition.player_id == latest_ts_sub.c.player_id)
            & (models.PlayerPosition.ts == latest_ts_sub.c.max_ts),
        )
        .filter(models.PlayerPosition.server_id == server_id)
        .all()
    )

    seen_names: set = set()
    result = []
    for pos in latest_rows:
        player = db.query(models.Player).filter(models.Player.id == pos.player_id).first()
        if not player or not player.player_name:
            continue
        seen_names.add(player.player_name)
        result.append({
            "player_name": player.player_name,
            "uuid": player.uuid,
            "is_online": player.player_name in online_names,
            "is_bot": player.is_bot,
            "is_offline_mode": player.is_offline,
            "x": pos.x,
            "y": pos.y,
            "z": pos.z,
            "dim": pos.dim,
            "updated_at": pos.ts.isoformat() if pos.ts else None,
        })

    # also include online players without any recorded position
    for name in online_names:
        if name in seen_names:
            continue
        p = crud.get_player_by_name(db, name)
        if p:
            result.append({
                "player_name": p.player_name,
                "uuid": p.uuid,
                "is_online": True,
                "is_bot": p.is_bot,
                "is_offline_mode": p.is_offline,
                "x": None, "y": None, "z": None, "dim": None,
                "updated_at": None,
            })

    return result


# ---------- trajectory ----------

@router.get("/tools/world-map/{server_id}/trajectory/{player_name}")
def get_player_trajectory(
    server_id: int,
    player_name: str,
    since: Optional[str] = None,
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.USER)),
):
    """Return the player's trajectory. If `since` is provided (ISO datetime), load from that time;
    otherwise load the most recent login session."""
    if not crud.get_server_by_id(db, server_id):
        raise HTTPException(404, "服务器不存在")

    player = crud.get_player_by_name(db, player_name)
    if not player:
        raise HTTPException(404, "玩家不存在")

    if since:
        try:
            start = datetime.fromisoformat(since)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "无效的时间格式")
        end = datetime.now(tz=timezone.utc)
    else:
        # find most recent login session (open or closed)
        session = (
            db.query(models.PlayerSession)
            .filter(
                models.PlayerSession.player_uuid == player.uuid,
                models.PlayerSession.server_id == server_id,
            )
            .order_by(models.PlayerSession.login_time.desc())
            .first()
        )

        if session:
            start = session.login_time
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            end = session.logout_time or datetime.now(tz=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
        else:
            # No session record (e.g. panel restarted): fall back to last 6 hours
            end = datetime.now(tz=timezone.utc)
            start = end - timedelta(hours=6)

    positions = crud.get_player_positions(db, player.id, start, end, server_ids=[server_id])
    return [
        {"x": p.x, "y": p.y, "z": p.z, "dim": p.dim, "ts": (p.ts.isoformat() + "Z") if p.ts else None}
        for p in positions
    ]


@router.get("/tools/world-map/{server_id}/sessions/{player_name}")
def get_player_sessions(
    server_id: int,
    player_name: str,
    since: Optional[str] = None,
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.USER)),
):
    """Return login sessions for a player on a server, matching the same time range as the trajectory endpoint."""
    if not crud.get_server_by_id(db, server_id):
        raise HTTPException(404, "服务器不存在")

    player = crud.get_player_by_name(db, player_name)
    if not player:
        raise HTTPException(404, "玩家不存在")

    if since:
        try:
            start = datetime.fromisoformat(since)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "无效的时间格式")
        end = datetime.now(tz=timezone.utc)
    else:
        session = (
            db.query(models.PlayerSession)
            .filter(
                models.PlayerSession.player_uuid == player.uuid,
                models.PlayerSession.server_id == server_id,
            )
            .order_by(models.PlayerSession.login_time.desc())
            .first()
        )
        if session:
            start = session.login_time
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            end = session.logout_time or datetime.now(tz=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
        else:
            end = datetime.now(tz=timezone.utc)
            start = end - timedelta(hours=6)

    sessions = (
        db.query(models.PlayerSession)
        .filter(
            models.PlayerSession.player_uuid == player.uuid,
            models.PlayerSession.server_id == server_id,
            models.PlayerSession.login_time >= start,
            models.PlayerSession.login_time <= end,
        )
        .order_by(models.PlayerSession.login_time)
        .all()
    )
    return [
        {
            "login": (s.login_time.isoformat() + "Z") if s.login_time else None,
            "logout": (s.logout_time.isoformat() + "Z") if s.logout_time else None,
        }
        for s in sessions
    ]
