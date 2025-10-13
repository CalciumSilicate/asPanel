"""
后端 WS 接口：接收来自 MCDR 插件（aspanel_ws_reporter.py）的事件上报

协议：
- 单条：{"event": "mcdr.xxx", "ts": "...", "data": {...}}
- 批量：{"batch": true, "ts": "...", "items": [<单条>, <单条>, ...]}

行为：
- 校验与解析消息；转发到 Socket.IO（事件名："mcdr_event"，并同时按具体事件名广播）。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import socketio

from backend.ws import sio
from backend.logger import logger
from backend.database import get_db_context
from backend import crud
from pathlib import Path
from backend.database import get_db_context
from backend import crud
from backend.dependencies import mcdr_manager

# 服务器在线玩家：key=服务器目录名，value=玩家名集合
PLAYERS_BY_SERVER: Dict[str, Set[str]] = {}


async def _update_status_from_event(event: str, data: Dict[str, Any]) -> None:
    """
    根据来自插件的事件更新后端中的服务器状态：
    - mcdr.mcdr_start    -> 启动中 (pending)
    - mcdr.server_startup-> 运行中 (running)
    - mcdr.server_stop   -> 未启动/错误 (stopped/error) 由 return_code 决定
    需要 data 中包含 server 字段（为服务器目录名/名称），以及可选 return_code。
    """
    try:
        server_name: Optional[str] = None
        if isinstance(data, dict):
            server_name = data.get("server")
        if not server_name:
            return

        with get_db_context() as db:
            # 通过目录名匹配（更稳健）：路径最后一段 == 插件上报的 server 名称
            db_servers = crud.get_all_servers(db)
            matched = None
            for s in db_servers:
                try:
                    if str(s.path).rstrip('/').split('/')[-1] == server_name:
                        matched = s
                        break
                except Exception:
                    continue
            if not matched:
                # 回退：按名称匹配（若用户名称与目录名一致时可用）
                matched = crud.get_server_by_name(db, server_name)
            if not matched:
                return
            server_id = matched.id

        # 更新 mcdr_manager 的外部状态视图
        if event == "mcdr.mcdr_start":
            mcdr_manager.set_external_status(server_id, "pending", None)
        elif event == "mcdr.server_startup":
            mcdr_manager.set_external_status(server_id, "running", None)
            # 启动成功后清理非零返回码
            mcdr_manager.return_code.pop(server_id, None)
        elif event == "mcdr.server_stop":
            # 仅按 return_code 判别错误与否
            rc = None
            try:
                rc = int(data.get("return_code")) if isinstance(data.get("return_code"), (int, str)) else None
            except Exception:
                rc = None
            if rc is not None:
                mcdr_manager.return_code[server_id] = rc
            # 结束后撤销外部状态覆盖（交由 get_status + return_code 判定）
            mcdr_manager.clear_external_status(server_id)
        else:
            return

        # 广播统一的 server_status_update，前端两个页面均已监听
        await mcdr_manager._notify_server_update(server_id)
    except Exception:
        try:
            logger.exception("[MCDR-WS] 处理状态更新事件异常")
        except Exception:
            pass


router = APIRouter()

# 记录已连接的插件 WebSocket 客户端以及其关联的服务器目录名（从其上报的数据里学习）
# 注意：仅用于简单推送，不做复杂会话管理
_PLUGIN_CLIENTS: Dict[WebSocket, Optional[str]] = {}


def _safe_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


async def _handle_single(payload: Dict[str, Any]):
    """处理单条 mcdr 事件，广播至 Socket.IO"""
    if not isinstance(payload, dict):
        return
    event = payload.get("event")
    if not isinstance(event, str) or not event.startswith("mcdr."):
        # 不识别的事件格式，忽略
        return
    # 记录日志：接收到的单条事件
    try:
        logger.info(f"[MCDR-WS] 收到事件: {event} | 内容: {json.dumps(payload, ensure_ascii=False)}")
    except Exception:
        pass

    # 学习关联关系：从 payload.data.server 获取该连接对应的 server 目录名
    try:
        server_name = None
        if isinstance(payload.get("data"), dict):
            server_name = payload["data"].get("server")
        # 由于 WebSocket 对象仅在 mcdr_ws_endpoint 中可见，这里通过上下文变量保存
        # 此函数由该 endpoint 内调用，因此可以通过最近一个连接上下文进行标注（见 endpoint 内调用方式）
    except Exception:
        server_name = None
    # 广播通道：
    # 1) 通用聚合事件（便于客户端统一接入）
    await sio.emit("mcdr_event", payload)
    # 2) 具体事件名（便于客户端订阅精准主题）
    await sio.emit(event, payload)
    # 3) 将特定生命周期事件映射为 asPanel 的服务器状态
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    await _update_status_from_event(event, data)

    # 4) 当插件上报 "mcdr.plugin_loaded" 时，立即把该服务器当前的分组推送给对应插件
    if event == "mcdr.plugin_loaded" and isinstance(data, dict):
        try:
            server_name = data.get("server")
            if server_name:
                # 计算并广播该服务器的组名列表
                with get_db_context() as db:
                    # 通过目录名匹配 DB 服务器
                    target = None
                    for s in crud.get_all_servers(db):
                        try:
                            if Path(s.path).name == server_name:
                                target = s
                                break
                        except Exception:
                            continue
                    if target is not None:
                        import json as _json
                        groups = []
                        for g in crud.list_server_link_groups(db):
                            try:
                                ids = list(map(int, _json.loads(g.server_ids or '[]')))
                            except Exception:
                                ids = []
                            if target.id in ids:
                                groups.append(g.name)
                        await broadcast_server_link_update(server_name, groups)
        except Exception:
            # 推送失败不影响主流程
            pass

    # 5) 将关键事件转发给其他插件客户端（按分组交集筛选）
    try:
        await _forward_event_to_plugins(event, data, payload)
    except Exception:
        pass

    # 6) 记录并广播聊天消息（来自游戏端的用户消息）
    if event == "mcdr.user_info" and isinstance(data, dict):
        try:
            info = data.get("info") or data
            is_user = bool((info or {}).get("is_user"))
            player = (info or {}).get("player")
            content = str((info or {}).get("content") or (info or {}).get("raw_content") or "")
            src_server = data.get("server")
            if is_user and player and isinstance(src_server, str) and src_server:
                from backend import models as _models, crud as _crud
                with get_db_context() as db:
                    # 将该消息落库到所有该服务器所在分组
                    groups = _get_groups_for_server_name(db, src_server)
                    # 为 Web 前端构建统一输出结构
                    base = {
                        "group_id": None,
                        "level": "NORMAL",
                        "source": "game",
                        "content": content,
                        "sender_user_id": None,
                        "sender_username": None,
                        "sender_avatar": None,
                        "server_name": src_server,
                        "player_name": str(player),
                    }
                    for g in crud.list_server_link_groups(db):
                        import json as _json
                        try:
                            ids = list(map(int, _json.loads(g.server_ids or '[]')))
                        except Exception:
                            ids = []
                        # 将该 server 属于的组写入
                        target = None
                        for s in _crud.get_all_servers(db):
                            try:
                                if Path(s.path).name == src_server and s.id in ids:
                                    target = g
                                    break
                            except Exception:
                                continue
                        if target is None:
                            continue
                        row = _models.ChatMessage(
                            group_id=g.id,
                            level="NORMAL",
                            source="game",
                            content=content,
                            server_name=src_server,
                            player_name=str(player),
                        )
                        row = _crud.create_chat_message(db, row)
                        # 使用 Pydantic 模型进行 JSON 序列化，避免 datetime 直接传递导致的序列化问题
                        from backend import schemas as _schemas
                        out_model = _schemas.ChatMessageOut.model_validate(row)
                        out = out_model.model_dump(mode='json')
                        await sio.emit("chat_message", out)
        except Exception:
            pass

    # 7) 玩家在线表维护：基于 player_joined/left & server_startup/stop
    try:
        if event == "mcdr.player_joined" and isinstance(data, dict):
            server_name = str(data.get("server") or "")
            player = str(data.get("player") or "")
            if server_name and player:
                PLAYERS_BY_SERVER.setdefault(server_name, set()).add(player)
                await _emit_presence_for_server(server_name)
        elif event == "mcdr.player_left" and isinstance(data, dict):
            server_name = str(data.get("server") or "")
            player = str(data.get("player") or "")
            if server_name:
                s = PLAYERS_BY_SERVER.setdefault(server_name, set())
                if player:
                    s.discard(player)
                await _emit_presence_for_server(server_name)
        elif event in ("mcdr.server_startup", "mcdr.server_stop") and isinstance(data, dict):
            server_name = str(data.get("server") or "")
            if server_name:
                if event == "mcdr.server_startup":
                    # 启动时清空（重新学习）
                    PLAYERS_BY_SERVER[server_name] = set()
                else:
                    # 停止时清空
                    PLAYERS_BY_SERVER.pop(server_name, None)
                await _emit_presence_for_server(server_name)
    except Exception:
        pass


def _get_groups_for_server_name(db: Session | None, server_name: str) -> List[str]:
    if db is None:
        with get_db_context() as _db:
            return _get_groups_for_server_name(_db, server_name)
    target = None
    for s in crud.get_all_servers(db):
        try:
            if Path(s.path).name == server_name:
                target = s
                break
        except Exception:
            continue
    if not target:
        return []
    import json as _json
    names: List[str] = []
    for g in crud.list_server_link_groups(db):
        try:
            ids = list(map(int, _json.loads(g.server_ids or '[]')))
        except Exception:
            ids = []
        if target.id in ids:
            names.append(g.name)
    return names


async def _forward_event_to_plugins(event: str, data: Dict[str, Any], original_payload: Dict[str, Any]):
    FORWARD_EVENTS = {
        "mcdr.user_info",
        "mcdr.server_startup",
        "mcdr.server_stop",
        "mcdr.player_joined",
        "mcdr.player_left",
    }
    if event not in FORWARD_EVENTS:
        return
    src_server = data.get("server")
    if not isinstance(src_server, str) or not src_server:
        return
    # 源分组
    src_groups = data.get("server_groups")
    if not isinstance(src_groups, list):
        with get_db_context() as db:
            src_groups = _get_groups_for_server_name(db, src_server)
    src_groups = [str(x) for x in (src_groups or [])]

    # 将原始 payload 转发给符合条件的客户端
    dead: List[WebSocket] = []
    text = json.dumps(original_payload, ensure_ascii=False)
    for ws, bound_name in list(_PLUGIN_CLIENTS.items()):
        try:
            if not bound_name or bound_name == src_server:
                continue
            with get_db_context() as db:
                dst_groups = _get_groups_for_server_name(db, bound_name)
            if any(g in src_groups for g in dst_groups):
                await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _PLUGIN_CLIENTS.pop(ws, None)


@router.websocket("/aspanel/mcdr")
async def mcdr_ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        logger.info("[MCDR-WS] 连接已建立 /aspanel/mcdr")
    except Exception:
        pass
    # 注册连接
    _PLUGIN_CLIENTS[ws] = None
    try:
        while True:
            text = await ws.receive_text()
            try:
                # 记录原始消息内容
                logger.info(f"[MCDR-WS] 收到原始消息: {text}")
            except Exception:
                pass
            payload = _safe_json_loads(text)
            if payload is None:
                continue
            # 批量 or 单条
            if isinstance(payload, dict) and payload.get("batch") is True:
                items: List[Dict[str, Any]] = payload.get("items", []) or []
                try:
                    logger.info(f"[MCDR-WS] 批量消息，数量={len(items)}")
                except Exception:
                    pass
                for it in items:
                    # 若包含 server 字段，则记录到注册表
                    try:
                        if isinstance(it.get("data"), dict) and it["data"].get("server"):
                            _PLUGIN_CLIENTS[ws] = it["data"]["server"]
                    except Exception:
                        pass
                    await _handle_single(it)
            else:
                try:
                    if isinstance(payload.get("data"), dict) and payload["data"].get("server"):
                        _PLUGIN_CLIENTS[ws] = payload["data"]["server"]
                except Exception:
                    pass
                await _handle_single(payload)
    except WebSocketDisconnect:
        # 客户端断开
        try:
            logger.info("[MCDR-WS] 连接已断开")
        except Exception:
            pass
        _PLUGIN_CLIENTS.pop(ws, None)
        return
    except Exception:
        # 任意异常时，结束连接（不抛出）
        try:
            logger.exception("[MCDR-WS] 处理消息异常")
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass
    finally:
        _PLUGIN_CLIENTS.pop(ws, None)


async def broadcast_server_link_update(server_name: str, group_names: List[str]):
    """向绑定了 server_name 的插件客户端推送分组变更事件。"""
    dead: List[WebSocket] = []
    msg = json.dumps({
        "event": "sl.group_update",
        "ts": "-",
        "data": {"server": server_name, "server_groups": group_names}
    }, ensure_ascii=False)
    for ws, bound in list(_PLUGIN_CLIENTS.items()):
        try:
            if bound == server_name:
                await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _PLUGIN_CLIENTS.pop(ws, None)


def get_group_players(group_id: int) -> List[dict]:
    """获取某个组内的所有在线玩家（聚合所有服务器）。
    返回列表元素形如 { 'server': 'srvA', 'player': 'Steve' }。
    """
    res: List[dict] = []
    try:
        with get_db_context() as db:
            rec = crud.get_server_link_group_by_id(db, int(group_id))
            if not rec:
                return res
            import json as _json
            try:
                ids = list(map(int, _json.loads(rec.server_ids or '[]')))
            except Exception:
                ids = []
            for sid in ids:
                s = crud.get_server_by_id(db, sid)
                if not s:
                    continue
                name = Path(s.path).name
                players = list(PLAYERS_BY_SERVER.get(name, set()))
                for p in players:
                    res.append({ 'server': name, 'player': p })
        return res
    except Exception:
        return res


async def _emit_presence_for_server(server_name: str):
    """当某个服务器的玩家集发生变化时，向其所在所有组广播 presence。"""
    try:
        with get_db_context() as db:
            groups = _get_groups_for_server_name(db, server_name)
            # 将组名转为组 id 列表
            gid_list: List[int] = []
            for g in crud.list_server_link_groups(db):
                if g.name in groups:
                    gid_list.append(g.id)
        # 导入 Chat 的在线用户表用于聚合
        from backend.ws import CHAT_USERS  # type: ignore
        for gid in gid_list:
            web_users = list((CHAT_USERS.get(gid) or {}).values())
            players = get_group_players(gid)
            await sio.emit('chat_presence', { 'group_id': gid, 'web_users': web_users, 'players': players }, room=f'chat_group_{gid}')
    except Exception:
        pass
