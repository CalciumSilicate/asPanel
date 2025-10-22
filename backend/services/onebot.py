"""OneBot V11 Reverse WebSocket integration for QQ bridging."""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend import crud, models, schemas
from backend.core.config import to_local_dt
from backend.database import get_db_context
from backend.logger import logger
from backend.ws import sio
from backend.dependencies import mcdr_manager

router = APIRouter()

# Regex to strip CQ codes such as [CQ:at,...]
_CQ_CODE_RE = re.compile(r"\[CQ:[^\]]*\]")


@dataclass(eq=False)
class OneBotSession:
    websocket: WebSocket
    self_id: Optional[str] = None
    known_groups: Set[str] = field(default_factory=set)

    async def send(self, payload: Dict[str, Any]) -> None:
        await self.websocket.send_text(json.dumps(payload, ensure_ascii=False))

    def __hash__(self) -> int:  # pragma: no cover - trivial identity helper
        return id(self)

    def __eq__(self, other: object) -> bool:  # pragma: no cover - identity comparison
        return self is other


_SESSIONS: Set[OneBotSession] = set()
_GROUP_TO_QQ: Dict[int, str] = {}
_QQ_TO_GROUP: Dict[str, int] = {}
_GROUP_META: Dict[int, Dict[str, Any]] = {}
_SERVER_TO_GROUPS: Dict[str, List[int]] = {}
_GROUP_PLAYERS: Dict[int, Set[str]] = {}
_PLAYER_EVENT_SUPPRESS_WINDOW = 1.0


@dataclass
class _PendingPlayerEvent:
    event_type: str
    timestamp: float
    qq_group: str
    message: str
    task: Optional[asyncio.Task] = None


_PENDING_PLAYER_EVENTS: Dict[Tuple[int, str], _PendingPlayerEvent] = {}


async def _queue_player_event(
    group_id: int,
    player: str,
    event_type: str,
    qq_group: str,
    message: str,
) -> None:
    loop = asyncio.get_running_loop()
    key = (group_id, player)
    now = loop.time()

    existing = _PENDING_PLAYER_EVENTS.get(key)
    if existing:
        if existing.task:
            existing.task.cancel()
        if (
            existing.event_type != event_type
            and now - existing.timestamp <= _PLAYER_EVENT_SUPPRESS_WINDOW
        ):
            _PENDING_PLAYER_EVENTS.pop(key, None)
            return
        _PENDING_PLAYER_EVENTS.pop(key, None)

    pending = _PendingPlayerEvent(
        event_type=event_type,
        timestamp=now,
        qq_group=qq_group,
        message=message,
    )
    task = asyncio.create_task(_delayed_send_player_event(key, pending))
    pending.task = task
    _PENDING_PLAYER_EVENTS[key] = pending


async def _delayed_send_player_event(
    key: Tuple[int, str], event: _PendingPlayerEvent
) -> None:
    try:
        await asyncio.sleep(_PLAYER_EVENT_SUPPRESS_WINDOW)
        await _send_group_text(event.qq_group, event.message)
    except asyncio.CancelledError:
        pass
    finally:
        current = _PENDING_PLAYER_EVENTS.get(key)
        if current is event:
            _PENDING_PLAYER_EVENTS.pop(key, None)
_REFRESH_LOCK = asyncio.Lock()

_PLAYERS_PROVIDER: Callable[[], Dict[str, Set[str]]] = lambda: {}
_PLUGIN_BROADCASTER: Optional[Callable[[str, Optional[int], str, str], asyncio.Future]] = None


def set_players_provider(provider: Callable[[], Dict[str, Set[str]]]) -> None:
    global _PLAYERS_PROVIDER
    _PLAYERS_PROVIDER = provider


def register_plugin_broadcaster(func: Callable[..., asyncio.Future]) -> None:
    global _PLUGIN_BROADCASTER
    _PLUGIN_BROADCASTER = func


async def _compute_group_players(group_id: int) -> Set[str]:
    meta = _GROUP_META.get(group_id)
    if not meta:
        return set()
    players_map = _PLAYERS_PROVIDER() or {}
    result: Set[str] = set()
    for srv in meta.get("servers", []):
        server_name = srv.get("dir")
        if not server_name:
            continue
        result.update(players_map.get(server_name, set()))
    return result


async def refresh_bindings() -> None:
    async with _REFRESH_LOCK:
        new_group_to_qq: Dict[int, str] = {}
        new_qq_to_group: Dict[str, int] = {}
        new_group_meta: Dict[int, Dict[str, Any]] = {}
        new_server_to_groups: Dict[str, List[int]] = {}

        with get_db_context() as db:
            groups = crud.list_server_link_groups(db)
            for g in groups:
                try:
                    chat_bindings = json.loads(g.chat_bindings or "[]") if g.chat_bindings else []
                except json.JSONDecodeError:
                    chat_bindings = []
                qq_group = None
                for item in chat_bindings:
                    s = str(item).strip()
                    if s.isdigit():
                        qq_group = s
                        break
                server_ids: List[int]
                try:
                    server_ids = list(map(int, json.loads(g.server_ids or "[]")))
                except Exception:
                    server_ids = []
                servers_meta: List[Dict[str, Any]] = []
                for sid in server_ids:
                    srv = crud.get_server_by_id(db, sid)
                    if not srv:
                        continue
                    dir_name = None
                    try:
                        dir_name = Path(srv.path).name
                    except Exception:
                        dir_name = None
                    if not dir_name:
                        continue
                    servers_meta.append({
                        "id": sid,
                        "name": srv.name,
                        "dir": dir_name,
                        "path": srv.path,
                    })
                    new_server_to_groups.setdefault(dir_name, []).append(g.id)
                new_group_meta[g.id] = {
                    "id": g.id,
                    "name": g.name,
                    "qq": qq_group,
                    "servers": servers_meta,
                }
                if qq_group:
                    new_group_to_qq[g.id] = qq_group
                    new_qq_to_group[qq_group] = g.id

        global _GROUP_TO_QQ, _QQ_TO_GROUP, _GROUP_META, _SERVER_TO_GROUPS, _GROUP_PLAYERS
        _GROUP_TO_QQ = new_group_to_qq
        _QQ_TO_GROUP = new_qq_to_group
        _GROUP_META = new_group_meta
        _SERVER_TO_GROUPS = new_server_to_groups

        # 重新同步每个组的在线玩家集合
        new_group_players: Dict[int, Set[str]] = {}
        for gid in _GROUP_META.keys():
            new_group_players[gid] = await _compute_group_players(gid)
        _GROUP_PLAYERS = new_group_players

        try:
            logger.info(f"[OneBot] 组绑定已刷新 | groups={len(_GROUP_META)}")
        except Exception:
            pass


def _extract_text(message: Any) -> str:
    if isinstance(message, str):
        text = message
    elif isinstance(message, list):
        parts: List[str] = []
        for seg in message:
            if isinstance(seg, dict) and seg.get("type") == "text":
                parts.append(str(seg.get("data", {}).get("text", "")))
        text = "".join(parts)
    else:
        text = ""
    text = _CQ_CODE_RE.sub("", text)
    return text.strip()


async def _send_group_text(qq_group: str, message: str) -> None:
    if not message or not qq_group:
        return
    payload = {"action": "send_group_msg", "params": {"group_id": int(qq_group), "message": message}}
    dead: List[OneBotSession] = []
    for session in list(_SESSIONS):
        try:
            await session.send(payload)
        except Exception:
            dead.append(session)
    for session in dead:
        _SESSIONS.discard(session)
    if dead:
        try:
            logger.warning(f"[OneBot] 清理失效连接 {len(dead)}")
        except Exception:
            pass


async def _emit_chat_message(group_id: int, nickname: str, message: str, *, sender_qq: Optional[str] = None) -> None:
    if not message:
        return
    with get_db_context() as db:
        # 解析 QQ 对应的面板用户与头像/绑定玩家
        panel_user = None
        ui_name = nickname
        sender_avatar = None
        try:
            if sender_qq:
                panel_user = db.query(models.User).filter(models.User.qq == str(sender_qq)).first()
        except Exception:
            panel_user = None
        if panel_user:
            # 绑定玩家名（若有） + 群昵称 作为 Web 展示名
            mc_name = None
            try:
                if getattr(panel_user, 'bound_player_id', None):
                    p = db.query(models.Player).filter(models.Player.id == panel_user.bound_player_id).first()
                    if p and p.player_name:
                        mc_name = p.player_name
            except Exception:
                mc_name = None
            if mc_name:
                ui_name = f"{mc_name}({nickname})@QQ"
            else:
                ui_name = f"{nickname}@QQ"
            # 头像优先面板头像，否则用绑定玩家的 MC 头像路径（由前端解析相对路径）
            if getattr(panel_user, 'avatar_url', None):
                sender_avatar = panel_user.avatar_url
            elif mc_name:
                # 留空：前端会 fallback 到 MC 头像接口
                sender_avatar = None
        else:
            ui_name = f"{nickname}@QQ"
        row = models.ChatMessage(
            group_id=group_id,
            level="NORMAL",
            source="qq",
            content=message,
            sender_user_id=(panel_user.id if panel_user else None),
            sender_username=ui_name,
        )
        row = crud.create_chat_message(db, row)
        out = schemas.ChatMessageOut.model_validate(row)
        created_at = None
        try:
            if getattr(row, "created_at", None):
                created_at = to_local_dt(row.created_at)
        except Exception:
            created_at = getattr(row, "created_at", None)
        out = out.model_copy(update={"sender_avatar": sender_avatar, "created_at": created_at, "sender_qq": sender_qq})
    await sio.emit("chat_message", out.model_dump(mode="json"))


async def _handle_chat_from_qq(group_id: int, qq_group: str, payload: Dict[str, Any]) -> None:
    nickname = None
    sender = payload.get("sender") or {}
    nickname = sender.get("card") or sender.get("nickname") or str(payload.get("user_id") or "QQ")
    text = _extract_text(payload.get("message"))
    if not text:
        return

    # 命令检测
    if await _maybe_handle_command(group_id, qq_group, nickname, text):
        return

    # QQ 号
    sender_qq = str(payload.get("user_id") or "") or None
    await _emit_chat_message(group_id, nickname, text, sender_qq=sender_qq)

    if _PLUGIN_BROADCASTER is not None:
        # 发送到游戏端：若该 QQ 号对应面板用户且绑定了玩家名，则显示为 [QQ] <MCName> message
        game_user = nickname
        try:
            if sender_qq:
                with get_db_context() as db:
                    u = db.query(models.User).filter(models.User.qq == str(sender_qq)).first()
                    if u and getattr(u, 'bound_player_id', None):
                        p = db.query(models.Player).filter(models.Player.id == u.bound_player_id).first()
                        if p and p.player_name:
                            game_user = p.player_name
                        else:
                            game_user = nickname
                    else:
                        game_user = nickname
        except Exception:
            game_user = nickname
        await _PLUGIN_BROADCASTER(
            level="NORMAL",
            group_id=group_id,
            user=game_user,
            message=text,
            source="qq",
            avatar=None,
        )


async def _maybe_handle_command(group_id: int, qq_group: str, nickname: str, text: str) -> bool:
    if not text:
        return False
    text = text.strip()
    split_text = text.split()
    cmd = text[0]
    if cmd not in {"#", "%", "&"}:
        return False
    body = text[1:].strip()
    if cmd == "#" and len(text) == 1:
        await _cmd_show_players(group_id, qq_group)
    elif cmd == "%" and len(split_text) in {1, 2, 3}:
        await _cmd_restart_server(group_id, qq_group, body)
    elif cmd == "&" and len(text) == 1:
        await _cmd_show_status(group_id, qq_group)
    return True


async def _cmd_show_players(group_id: int, qq_group: str) -> None:
    meta = _GROUP_META.get(group_id)
    if not meta:
        return
    current = await _compute_group_players(group_id)
    total = len(current)
    lines = [f"{meta.get('name', 'Group')} ({total}):"]
    players_map = _PLAYERS_PROVIDER() or {}
    for srv in meta.get("servers", []):
        dir_name = srv.get("dir")
        display = srv.get("name") or dir_name or "-"
        online = sorted(players_map.get(dir_name, set()))
        if online:
            lines.append(f"- {display} ({len(online)}): {' '.join(online)}")
    await _send_group_text(qq_group, "\n".join(lines))


async def _cmd_restart_server(group_id: int, qq_group: str, body: str) -> None:
    meta = _GROUP_META.get(group_id)
    if not meta:
        return
    tokens = body.split()
    if not tokens:
        await _send_group_text(qq_group, "用法：% <服务器名称> [-f]")
        return
    force = False
    filtered: List[str] = []
    for t in tokens:
        if t.lower() in {"-f", "--force"}:
            force = True
        else:
            filtered.append(t)
    if not filtered:
        await _send_group_text(qq_group, "请指定服务器名称")
        return
    target = filtered[0]
    entry = None
    for srv in meta.get("servers", []):
        if srv.get("name", "").lower() == target.lower() or srv.get("dir", "").lower() == target.lower():
            entry = srv
            break
    if not entry:
        await _send_group_text(qq_group, f"未找到服务器：{target}")
        return

    with get_db_context() as db:
        server = crud.get_server_by_id(db, entry["id"])
    if not server:
        await _send_group_text(qq_group, f"服务器 {target} 不存在")
        return

    status, _ = await mcdr_manager.get_status(server.id, server.path)
    players_map = _PLAYERS_PROVIDER() or {}
    online_players = list(players_map.get(entry.get("dir"), set()))

    if status == schemas.ServerStatus.RUNNING:
        if online_players and not force:
            await _send_group_text(qq_group, f"{server.name} 当前在线 {len(online_players)} 人，使用 % {target} -f 可强制重启")
            return
        success, msg = await mcdr_manager.restart(server, server.path)
        if success:
            await _send_group_text(qq_group, f"{server.name} 已执行重启命令 (PID={msg})")
        else:
            await _send_group_text(qq_group, f"{server.name} 重启失败：{msg}")
    elif status in {schemas.ServerStatus.STOPPED, schemas.ServerStatus.ERROR}:
        success, msg = await mcdr_manager.start(server)
        if success:
            await _send_group_text(qq_group, f"{server.name} 已执行启动命令 (PID={msg})")
        else:
            await _send_group_text(qq_group, f"{server.name} 启动失败：{msg}")
    elif status == schemas.ServerStatus.PENDING:
        await _send_group_text(qq_group, f"{server.name} 正在启动中，请稍候")
    else:
        await _send_group_text(qq_group, f"{server.name} 当前状态 {status.value}，暂不支持该操作")


async def _cmd_show_status(group_id: int, qq_group: str) -> None:
    meta = _GROUP_META.get(group_id)
    if not meta:
        return
    entries = meta.get("servers", [])
    if not entries:
        await _send_group_text(qq_group, "该组未绑定服务器")
        return
    with get_db_context() as db:
        servers = {srv["id"]: crud.get_server_by_id(db, srv["id"]) for srv in entries}
    lines: List[str] = []
    for srv in entries:
        server = servers.get(srv["id"])
        if not server:
            continue
        status, _ = await mcdr_manager.get_status(server.id, server.path)
        mark = "✅" if status == schemas.ServerStatus.RUNNING else ("🔄️" if status == schemas.ServerStatus.PENDING else "❌")
        name = server.name or srv.get("dir")
        lines.append(f"{mark} {name}")
    await _send_group_text(qq_group, "\n".join(lines) if lines else "无服务器")


async def relay_web_message_to_qq(group_id: int, user: str, message: str) -> None:
    qq_group = _GROUP_TO_QQ.get(group_id)
    if not qq_group:
        return
    formatted = f"[WEB] <{user}> {message}"
    await _send_group_text(qq_group, formatted)


async def handle_prefixed_game_chat(server_name: str, player: str, content: str) -> None:
    if not content:
        return
    stripped = content.lstrip()
    if not stripped:
        return
    if stripped[0] not in {".", "。"}:
        return
    message = stripped[1:].lstrip()
    if not message:
        return
    groups = _SERVER_TO_GROUPS.get(server_name, [])
    for gid in groups:
        qq_group = _GROUP_TO_QQ.get(gid)
        if not qq_group:
            continue
        await _send_group_text(qq_group, f"<{player}> {message}")


async def handle_player_join(server_name: str, player: str) -> None:
    groups = _SERVER_TO_GROUPS.get(server_name, [])
    for gid in groups:
        prev = _GROUP_PLAYERS.get(gid, set())
        new = await _compute_group_players(gid)
        if player in new and player not in prev:
            qq_group = _GROUP_TO_QQ.get(gid)
            if qq_group:
                await _queue_player_event(
                    gid,
                    player,
                    "join",
                    qq_group,
                    f"+{player} ({len(prev)}→{len(new)})",
                )
        _GROUP_PLAYERS[gid] = new


async def handle_player_leave(server_name: str, player: str) -> None:
    groups = _SERVER_TO_GROUPS.get(server_name, [])
    for gid in groups:
        prev = _GROUP_PLAYERS.get(gid, set())
        new = await _compute_group_players(gid)
        if player not in new and player in prev:
            qq_group = _GROUP_TO_QQ.get(gid)
            if qq_group:
                await _queue_player_event(
                    gid,
                    player,
                    "leave",
                    qq_group,
                    f"-{player} ({len(prev)}→{len(new)})",
                )
        _GROUP_PLAYERS[gid] = new


async def handle_server_reset(server_name: str) -> None:
    groups = _SERVER_TO_GROUPS.get(server_name, [])
    for gid in groups:
        _GROUP_PLAYERS[gid] = await _compute_group_players(gid)


@router.websocket("/aspanel/onebot/ws")
async def onebot_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = OneBotSession(websocket=websocket)
    _SESSIONS.add(session)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            await _handle_incoming(session, payload)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            logger.opt(exception=exc).warning("[OneBot] 连接异常")
        except Exception:
            pass
    finally:
        _SESSIONS.discard(session)


async def _handle_incoming(session: OneBotSession, payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    post_type = payload.get("post_type")
    if post_type == "meta_event":
        if payload.get("meta_event_type") == "lifecycle":
            session.self_id = str(payload.get("self_id") or session.self_id)
        return
    if post_type == "message" and payload.get("message_type") == "group":
        qq_group = str(payload.get("group_id") or "")
        if not qq_group:
            return
        session.known_groups.add(qq_group)
        await refresh_bindings()
        group_id = _QQ_TO_GROUP.get(qq_group)
        if not group_id:
            return
        await _handle_chat_from_qq(group_id, qq_group, payload)


async def startup_sync() -> None:
    await refresh_bindings()
