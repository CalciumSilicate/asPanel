from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from backend.core.config import MCDR_ROOT_PATH
from backend.database import get_db_context
from backend.logger import logger
from backend import crud, models


UUID_HYPHEN_PATTERN = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _is_valid_hyphen_uuid(s: str) -> bool:
    return bool(UUID_HYPHEN_PATTERN.match(s or ""))


def _get_all_server_world_dirs() -> List[Tuple[str, Path]]:
    """
    返回 (server_name, world_dir) 列表；若 world 不存在，world_dir 也返回（不存在由调用方判断）。
    server_name = 服务器目录名（Path(server.path).name）
    """
    from backend.database import get_db_context
    from backend import crud
    res: List[Tuple[str, Path]] = []
    with get_db_context() as db:
        for s in crud.get_all_servers(db):
            try:
                name = Path(s.path).name
                world = Path(s.path) / 'server' / 'world'
                res.append((name, world))
            except Exception:
                continue
    return res


def ensure_players_from_worlds() -> dict:
    """
    逻辑1：扫描 storages/mcdr-servers/*/server/world/playerdata/*.dat，提取 UUID（带连字符），
    对于不存在于数据库的 UUID，插入记录：uuid=UUID, player_name=None, play_time={}, is_offline=False。
    返回统计信息。
    """
    added = 0
    seen = set()
    for mcdr in (MCDR_ROOT_PATH.iterdir() if MCDR_ROOT_PATH.exists() else []):
        try:
            pd = mcdr / 'server' / 'world' / 'playerdata'
            if not pd.exists():
                continue
            for f in pd.glob('*.dat'):
                uuid = f.stem
                if _is_valid_hyphen_uuid(uuid):
                    seen.add(uuid)
        except Exception:
            continue
    with get_db_context() as db:
        for u in sorted(seen):
            if not crud.get_player_by_uuid(db, u):
                crud.create_player(db, uuid=u, player_name=None, play_time={}, is_offline=False)
                added += 1
    return {"added": added, "found": len(seen)}


def _fetch_official_name(uuid_hyphen: str) -> Optional[str]:
    """尝试从 Mojang SessionServer 获取玩家名。失败返回 None。
    注意：API 需要去掉连字符的 UUID。
    """
    try:
        u = uuid_hyphen.replace('-', '')
        url = f"https://sessionserver.mojang.com/session/minecraft/profile/{u}"
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            name = data.get('name')
            if isinstance(name, str) and name:
                return name
        return None
    except Exception:
        return None


def refresh_missing_official_names() -> dict:
    """
    逻辑2：当 player_name 为 None 且 is_offline == False，尝试获取 player_name；
    若失败，将 is_offline=True；若成功，写入 player_name。
    返回统计：updated / marked_offline。
    """
    updated = 0
    marked_offline = 0
    with get_db_context() as db:
        players = db.query(models.Player).filter(models.Player.player_name.is_(None), models.Player.is_offline == False).all()  # noqa: E712
        for p in players:
            name = _fetch_official_name(p.uuid)
            if name:
                crud.update_player_name(db, p, name=name, is_offline=False)
                updated += 1
            else:
                crud.update_player_name(db, p, name=None, is_offline=True)
                marked_offline += 1
    return {"updated": updated, "marked_offline": marked_offline}


def refresh_offline_names() -> dict:
    """逻辑3：为所有 is_offline==True 的记录再次尝试获取官方玩家名；若获取成功且不同则更新，并将 is_offline=False。"""
    updated = 0
    with get_db_context() as db:
        players = db.query(models.Player).filter(models.Player.is_offline == True).all()  # noqa: E712
        for p in players:
            name = _fetch_official_name(p.uuid)
            if name and name != (p.player_name or None):
                crud.update_player_name(db, p, name=name, is_offline=False)
                updated += 1
    return {"updated": updated}


def _read_ticks_from_stats(stats_file: Path) -> int:
    try:
        if not stats_file.exists():
            return 0
        data = json.loads(stats_file.read_text(encoding='utf-8'))
        val = (
            data.get('stats', {})
            .get('minecraft:custom', {})
            .get('minecraft:play_time', None)
        )
        if isinstance(val, int):
            return max(0, int(val))
        # 回退键名（旧版本）
        val2 = (
            data.get('stats', {})
            .get('minecraft:custom', {})
            .get('minecraft:play_one_minute', None)
        )
        if isinstance(val2, int):
            return max(0, int(val2))
    except Exception:
        pass
    return 0


def recalc_all_play_time() -> dict:
    """
    逻辑4：若某玩家 play_time 为空（{}），则从各服务器 world/stats/<UUID>.json 获取 ticks；
    若 world 不存在则保持该 server_name 不在 play_time；若 stats 缺失记为 0。
    前端按钮“刷新时长”要求：无论是否为空，都应重新计算一次（因此本函数按全部重算实现）。
    返回：统计信息。
    """
    total_updated = 0
    servers = _get_all_server_world_dirs()
    with get_db_context() as db:
        players = db.query(models.Player).all()
        for p in players:
            for server_name, world_dir in servers:
                if not world_dir.exists():
                    # 确保该键不存在
                    crud.remove_server_from_player_play_time(db, p, server_name)
                    continue
                stats_file = world_dir / 'stats' / f"{p.uuid}.json"
                ticks = _read_ticks_from_stats(stats_file)
                crud.set_player_play_time_for_server(db, p, server_name, ticks)
                total_updated += 1
    return {"servers": len(servers), "players": len(players), "updated": total_updated}


def on_server_created(server_name: str, server_path: str) -> dict:
    """
    逻辑4（创建服务器时的增量）：若存在 world 存档，为每个玩家添加该 server_name 的时长键（默认 0）；
    若 world 不存在，则确保键不存在。
    """
    world_dir = Path(server_path) / 'server' / 'world'
    added = 0
    removed = 0
    with get_db_context() as db:
        players = db.query(models.Player).all()
        for p in players:
            if world_dir.exists():
                crud.set_player_play_time_for_server(db, p, server_name, 0)
                added += 1
            else:
                crud.remove_server_from_player_play_time(db, p, server_name)
                removed += 1
    return {"added": added, "removed": removed}


def on_server_deleted(server_name: str) -> dict:
    """逻辑4（删除服务器时的清理）：移除所有玩家 play_time 中的该 server_name 键。"""
    with get_db_context() as db:
        n = crud.bulk_remove_server_from_all_players(db, server_name)
    return {"removed": n}
