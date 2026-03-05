# backend/core/ws.py

import socketio
from typing import Dict, List

from backend.core.database import get_db_context
from backend.core.dependencies import mcdr_manager
from backend.core import crud
from backend.core.logger import logger
from backend.core.constants import ALLOWED_ORIGINS

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=ALLOWED_ORIGINS)
mcdr_manager.sio = sio

CHAT_USERS: Dict[int, Dict[str, dict]] = {}
CHAT_SID_GROUP: Dict[str, int] = {}

# console 会话追踪：sid → {server_id, server_name, user_id, user_name}
CONSOLE_SID_INFO: Dict[str, dict] = {}


def _get_server_name(server_id: int) -> str:
    try:
        with get_db_context() as db:
            s = crud.get_server_by_id(db, server_id)
            return s.name if s else str(server_id)
    except Exception:
        return str(server_id)


def _write_console_audit(action: str, info: dict) -> None:
    try:
        from backend.core.audit import write_audit
        write_audit(
            category="SERVER",
            action=action,
            actor_id=info.get("user_id"),
            actor_name=info.get("user_name"),
            target_type="server",
            target_id=info.get("server_id"),
            target_name=info.get("server_name"),
        )
    except Exception:
        pass


@sio.on('join_console_room')
async def join_console_room(sid, data):
    server_id = data.get('server_id')
    if server_id is None:
        return
    user = data.get('user') or {}
    server_name = _get_server_name(int(server_id))
    info = {
        "server_id": server_id,
        "server_name": server_name,
        "user_id": user.get("id"),
        "user_name": user.get("username"),
    }
    CONSOLE_SID_INFO[sid] = info
    await sio.enter_room(sid, f'server_console_{server_id}')
    logger.info(f"Socket {sid} joined console room for server {server_id} ({server_name})")
    _write_console_audit("console_open", info)


@sio.on('leave_console_room')
async def leave_console_room(sid, data):
    info = CONSOLE_SID_INFO.pop(sid, None)
    if info:
        server_id = info.get("server_id")
        await sio.leave_room(sid, f'server_console_{server_id}')
        logger.info(f"Socket {sid} left console room for server {server_id}")
        _write_console_audit("console_close", info)


@sio.on('console_command')
async def handle_console_command(sid, data):
    server_id, command = int(data.get('server_id')), data.get('command')
    with get_db_context() as db:
        db_server = crud.get_server_by_id(db, server_id)
    if server_id is not None and command:
        await mcdr_manager.send_command(db_server, command)


# ========== ChatRoom 相关：在线用户/玩家推送 ==========
async def _emit_chat_presence(group_id: int):
    """
    广播该组的在线面板用户与组内在线玩家列表。
    面板用户来自本模块的 CHAT_USERS；玩家来自 services.ws 中的 PLAYERS_BY_SERVER。
    """
    # 汇总面板用户
    web_users = list((CHAT_USERS.get(group_id) or {}).values())

    # 汇总该组内服务器的在线玩家
    try:
        from backend.services.ws import get_group_players  # 避免循环导入
        players: List[dict] = get_group_players(group_id)
    except Exception:
        players = []

    await sio.emit(
        'chat_presence',
        { 'group_id': group_id, 'web_users': web_users, 'players': players },
        room=f'chat_group_{group_id}'
    )


@sio.on('join_chat_group')
async def handle_join_chat_group(sid, data):
    """
    前端进入某个聊天室分组时调用。
    data: { group_id: number, user: { id, username, avatar_url } }
    """
    try:
        group_id = int(data.get('group_id'))
    except Exception:
        return
    user = data.get('user') or {}

    # 加入房间
    await sio.enter_room(sid, f'chat_group_{group_id}')

    # 记录在线用户
    CHAT_USERS.setdefault(group_id, {})[sid] = {
        'id': user.get('id'),
        'username': user.get('username'),
        'avatar_url': user.get('avatar_url'),
    }
    CHAT_SID_GROUP[sid] = group_id

    # 广播在线列表
    await _emit_chat_presence(group_id)


@sio.on('leave_chat_group')
async def handle_leave_chat_group(sid, data):
    """前端离开聊天室时调用。"""
    try:
        group_id = int(data.get('group_id'))
    except Exception:
        group_id = CHAT_SID_GROUP.get(sid)
    if not group_id:
        return

    # 从记录中移除
    try:
        CHAT_USERS.get(group_id, {}).pop(sid, None)
    except Exception:
        pass
    CHAT_SID_GROUP.pop(sid, None)

    # 离开房间
    try:
        await sio.leave_room(sid, f'chat_group_{group_id}')
    except Exception:
        pass

    # 广播更新
    await _emit_chat_presence(group_id)


@sio.event
async def disconnect(sid):
    """Socket 断开时清理在线用户并广播。"""
    # console 会话清理
    console_info = CONSOLE_SID_INFO.pop(sid, None)
    if console_info:
        _write_console_audit("console_close", console_info)

    group_id = CHAT_SID_GROUP.pop(sid, None)
    if group_id:
        try:
            CHAT_USERS.get(group_id, {}).pop(sid, None)
        except Exception:
            pass
        await _emit_chat_presence(group_id)
