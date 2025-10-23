# backend/core/ws.py

import socketio
from typing import Dict, List

from backend.core.database import get_db_context
from backend.core.dependencies import mcdr_manager
from backend.core import crud
from backend.core.logger import logger

# Socket.IO 实例
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
mcdr_manager.sio = sio

# 在线聊天室用户：group_id -> { sid -> user(dict) }
CHAT_USERS: Dict[int, Dict[str, dict]] = {}
# 反查：sid -> group_id，用于断开/离开时清理
CHAT_SID_GROUP: Dict[str, int] = {}


@sio.event
async def join_console_room(sid, data):
    server_id = data.get('server_id')
    if server_id is not None:
        await sio.enter_room(sid, f'server_console_{server_id}')
        logger.info(f"Socket {sid} joined room for server {server_id}")


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
    group_id = CHAT_SID_GROUP.pop(sid, None)
    if group_id:
        try:
            CHAT_USERS.get(group_id, {}).pop(sid, None)
        except Exception:
            pass
        await _emit_chat_presence(group_id)
