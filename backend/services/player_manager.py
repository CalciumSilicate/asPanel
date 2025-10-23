from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.core.api import async_client

from backend.core.constants import MCDR_ROOT_PATH, UUID_HYPHEN_PATTERN
from backend.database import get_db_context
from backend.logger import logger
from backend import crud, models




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
    try:
        logger.debug(f"[PlayerManager] 发现服务器数量={len(res)} | 列表={[n for n,_ in res]}")
    except Exception:
        pass
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
    stats = {"added": added, "found": len(seen)}
    try:
        if added:
            logger.info(f"[PlayerManager] UUID 扫描完成 | 新增={added} 总计扫描={len(seen)}")
        else:
            logger.debug(f"[PlayerManager] UUID 扫描完成 | 无新增 总计扫描={len(seen)}")
    except Exception:
        pass
    return stats


async def fetch_official_name(uuid_hyphen: str) -> Optional[str]:
    """尝试从 Mojang SessionServer 获取玩家名。失败返回 None。
    注意：API 需要去掉连字符的 UUID。
    """
    try:
        u = uuid_hyphen.replace('-', '')
        url = f"https://sessionserver.mojang.com/session/minecraft/profile/{u}"
        r = await async_client.get(url, timeout=6)
        if r.status_code == 200:
            data = r.json()
            name = data.get('name')
            if isinstance(name, str) and name:
                try:
                    logger.debug(f"[PlayerManager] 官方名解析成功 | uuid={uuid_hyphen} name={name}")
                except Exception:
                    pass
                return name
        try:
            logger.debug(f"[PlayerManager] 官方名解析失败 | uuid={uuid_hyphen} status={r.status_code}")
        except Exception:
            pass
        return None
    except Exception:
        try:
            logger.debug(f"[PlayerManager] 官方名解析异常 | uuid={uuid_hyphen}")
        except Exception:
            pass
        return None


async def refresh_missing_official_names() -> dict:
    """
    逻辑2：当 player_name 为 None 且 is_offline == False，尝试获取 player_name；
    若失败，将 is_offline=True；若成功，写入 player_name。
    返回统计：updated / marked_offline。
    """
    updated = 0
    marked_offline = 0
    tried = 0
    with get_db_context() as db:
        players = db.query(models.Player).filter(models.Player.player_name.is_(None), models.Player.is_offline == False).all()  # noqa: E712
        for p in players:
            tried += 1
            name = await fetch_official_name(p.uuid)
            if name:
                crud.update_player_name(db, p, name=name, is_offline=False)
                updated += 1
                try:
                    logger.debug(f"[PlayerManager] 设置玩家名成功 | uuid={p.uuid} name={name}")
                except Exception:
                    pass
            else:
                crud.update_player_name(db, p, name=None, is_offline=True)
                marked_offline += 1
                try:
                    logger.debug(f"[PlayerManager] 标记为离线 | uuid={p.uuid}")
                except Exception:
                    pass
    stats = {"updated": updated, "marked_offline": marked_offline, "tried": tried}
    try:
        logger.info(f"[PlayerManager] 刷新正版玩家名 | 成功={updated} 标记离线={marked_offline} 尝试={tried}")
    except Exception:
        pass
    return stats


async def refresh_offline_names() -> dict:
    """逻辑3：为所有 is_offline==True 的记录再次尝试获取官方玩家名；若获取成功且不同则更新，并将 is_offline=False。"""
    updated = 0
    tried = 0
    with get_db_context() as db:
        players = db.query(models.Player).filter(models.Player.is_offline == True).all()  # noqa: E712
        for p in players:
            tried += 1
            name = await fetch_official_name(p.uuid)
            if name and name != (p.player_name or None):
                crud.update_player_name(db, p, name=name, is_offline=False)
                updated += 1
                try:
                    logger.debug(f"[PlayerManager] 离线改正版成功 | uuid={p.uuid} name={name}")
                except Exception:
                    pass
    stats = {"updated": updated, "tried": tried}
    try:
        logger.info(f"[PlayerManager] 重试离线玩家名 | 成功={updated} 尝试={tried}")
    except Exception:
        pass
    return stats


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
            ticks = max(0, int(val))
            try:
                logger.debug(f"[PlayerManager] 读取时长 | path={stats_file} ticks={ticks} key=play_time")
            except Exception:
                pass
            return ticks
        # 回退键名（旧版本）
        val2 = (
            data.get('stats', {})
            .get('minecraft:custom', {})
            .get('minecraft:play_one_minute', None)
        )
        if isinstance(val2, int):
            ticks = max(0, int(val2))
            try:
                logger.debug(f"[PlayerManager] 读取时长 | path={stats_file} ticks={ticks} key=play_one_minute")
            except Exception:
                pass
            return ticks
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
    per_server: Dict[str, int] = {}
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
                per_server[server_name] = per_server.get(server_name, 0) + 1
    stats = {"servers": len(servers), "players": len(players), "updated": total_updated, "per_server": per_server}
    try:
        logger.info(f"[PlayerManager] 重算时长完成 | 服务器={stats['servers']} 玩家={stats['players']} 写入次数={stats['updated']} 明细={per_server}")
    except Exception:
        pass
    return stats


def ensure_play_time_if_empty() -> dict:
    """
    仅当玩家记录的 play_time 完全为空时，才初始化：
    - 对所有服务器：若存在 world 存档，则读取 stats/<UUID>.json 的 play_time（或 play_one_minute）并写入；
      读取失败记为 0；
    - 若 world 不存在，则不写入该 server 的键（确保键缺失）。
    返回：初始化的玩家数与写入总数。
    """
    inited_players = 0
    writes = 0
    servers = _get_all_server_world_dirs()
    with get_db_context() as db:
        players = db.query(models.Player).all()
        for p in players:
            try:
                pt = json.loads(p.play_time or '{}')
            except Exception:
                pt = {}
            if pt:
                continue
            # 仅对空字典进行初始化
            changed = False
            for server_name, world_dir in servers:
                if not world_dir.exists():
                    # 保证键缺失
                    continue
                stats_file = world_dir / 'stats' / f"{p.uuid}.json"
                ticks = _read_ticks_from_stats(stats_file)
                crud.set_player_play_time_for_server(db, p, server_name, ticks)
                writes += 1
                changed = True
            if changed:
                inited_players += 1
    try:
        logger.info(f"[PlayerManager] 初始化空白游玩时长 | 初始化玩家数={inited_players} 写入总数={writes}")
    except Exception:
        pass
    return {"players_inited": inited_players, "writes": writes}


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
    stats = {"added": added, "removed": removed, "world_exists": world_dir.exists()}
    try:
        logger.info(f"[PlayerManager] 新服务器初始化玩家时长键 | server={server_name} world={stats['world_exists']} 添加={added} 移除={removed}")
    except Exception:
        pass
    return stats


def on_server_deleted(server_name: str) -> dict:
    """逻辑4（删除服务器时的清理）：移除所有玩家 play_time 中的该 server_name 键。"""
    with get_db_context() as db:
        n = crud.bulk_remove_server_from_all_players(db, server_name)
    try:
        logger.info(f"[PlayerManager] 删除服务器时清理玩家时长键 | server={server_name} 移除={n}")
    except Exception:
        pass
    return {"removed": n}
