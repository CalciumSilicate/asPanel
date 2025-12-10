# backend/services/onebot.py

import asyncio
import json
import re
import httpx
import base64
import hashlib
import mimetypes
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from backend.core import crud, models, schemas
from backend.core.utils import to_local_dt
from backend.core.constants import TEMP_PATH
from backend.core.database import get_db_context
from backend.core.logger import logger
from backend.core.ws import sio
from backend.core.dependencies import mcdr_manager
from backend.services import qq_stats_command

router = APIRouter()

# Regex helpers for CQ codes such as [CQ:at,...]
_CQ_CODE_RE = re.compile(r"\[CQ:[^\]]*\]")


def _cq_unescape(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("&amp;", "&")
        .replace("&#91;", "[")
        .replace("&#93;", "]")
        .replace("&#44;", ",")
    )


def _cq_escape_text(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
    )


def _cq_escape_value(text: str) -> str:
    if not text:
        return ""
    return (
        _cq_escape_text(text)
        .replace(",", "&#44;")
    )


@dataclass
class _CQSegment:
    type: str
    data: Dict[str, str]
    raw: Optional[str] = None


def _parse_cq_code(raw: str) -> _CQSegment:
    inner = raw[4:-1]
    type_name, _, rest = inner.partition(",")
    data: Dict[str, str] = {}
    if rest:
        for part in rest.split(","):
            if not part:
                continue
            key, _, value = part.partition("=")
            data[key] = _cq_unescape(value)
    return _CQSegment(type=type_name, data=data, raw=raw)


def _build_cq_code(segment: _CQSegment) -> str:
    if segment.type == "text":
        return segment.data.get("text", "")
    params = []
    for key, value in segment.data.items():
        if value is None:
            continue
        params.append(f"{key}={_cq_escape_value(str(value))}")
    joined = ",".join(params)
    return f"[CQ:{segment.type}{(',' + joined) if joined else ''}]"


def _parse_message_segments(message: Any) -> List[_CQSegment]:
    if isinstance(message, str):
        segments: List[_CQSegment] = []
        last = 0
        for match in _CQ_CODE_RE.finditer(message):
            if match.start() > last:
                text_part = message[last:match.start()]
                if text_part:
                    segments.append(
                        _CQSegment(type="text", data={"text": _cq_unescape(text_part)})
                    )
            segments.append(_parse_cq_code(match.group(0)))
            last = match.end()
        if last < len(message):
            tail = message[last:]
            if tail:
                segments.append(
                    _CQSegment(type="text", data={"text": _cq_unescape(tail)})
                )
        return segments
    if isinstance(message, list):
        segments = []
        for seg in message:
            if isinstance(seg, dict):
                seg_type = str(seg.get("type") or "text")
                raw_data = seg.get("data") or {}
                data = {str(k): str(v) for k, v in raw_data.items() if v is not None}
                if seg_type == "text":
                    segments.append(_CQSegment(type="text", data={"text": data.get("text", "")}))
                else:
                    segments.append(
                        _CQSegment(
                            type=seg_type,
                            data=data,
                            raw=_build_cq_code(_CQSegment(type=seg_type, data=data)),
                        )
                    )
            elif seg is not None:
                segments.append(_CQSegment(type="text", data={"text": str(seg)}))
        return segments
    if message:
        return [_CQSegment(type="text", data={"text": str(message)})]
    return []

# ------------------------
# QQ 图片缓存与本地链接提供
# ------------------------

_QQ_IMG_CACHE_DIR = TEMP_PATH / "qq_img"
_QQ_IMG_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

def _safe_ext_from_ct(ct: Optional[str]) -> str:
    if not ct:
        return ".jpg"
    ct = ct.lower().strip()
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    return mapping.get(ct, ".jpg")

def _pick_ext_from_url(url: str) -> Optional[str]:
    try:
        p = Path(url.split("?", 1)[0])
        ext = p.suffix.lower()
        if ext in _ALLOWED_EXT:
            return ext
        return None
    except Exception:
        return None

async def _download_bytes(url: str) -> tuple[bytes, Optional[str]]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        ct = r.headers.get("content-type")
        return (r.content, ct)

def _save_image_bytes(data: bytes, *, prefer_ext: Optional[str] = None, content_type: Optional[str] = None) -> str:
    # 基于内容生成稳定文件名
    h = hashlib.sha256(data).hexdigest()[:32]
    ext = prefer_ext or _safe_ext_from_ct(content_type)
    if ext not in _ALLOWED_EXT:
        ext = _safe_ext_from_ct(content_type)
    fname = f"{h}{ext}"
    path = _QQ_IMG_CACHE_DIR / fname
    if not path.exists():
        path.write_bytes(data)
    return fname

async def _cache_cq_image_and_get_path(seg: _CQSegment) -> Optional[str]:
    # 解析 CQ:image 的数据源，支持 url / http file / base64://
    url = seg.data.get("url") or seg.data.get("file") or ""
    if not url:
        return None
    try:
        if isinstance(url, str) and url.startswith("base64://"):
            b64 = url[len("base64://"):]
            try:
                data = base64.b64decode(b64, validate=True)
            except Exception:
                data = base64.b64decode(b64 + "==")
            fname = _save_image_bytes(data, prefer_ext=".png")
            return f"/api/img/{fname}"
        if isinstance(url, str) and (url.startswith("http://") or url.startswith("https://")):
            data, ct = await _download_bytes(url)
            prefer_ext = _pick_ext_from_url(url) or _safe_ext_from_ct(ct)
            fname = _save_image_bytes(data, prefer_ext=prefer_ext, content_type=ct)
            return f"/api/img/{fname}"
        # 其他情况暂不支持（例如 go-cqhttp 本地文件路径），保持原样
        return None
    except Exception:
        return None

async def _rewrite_image_segments_to_local(segments: List[_CQSegment]) -> List[_CQSegment]:
    changed: List[_CQSegment] = []
    for seg in segments:
        if seg.type == "image":
            local = await _cache_cq_image_and_get_path(seg)
            if local:
                # 将 CQ 内的链接替换为本地 API 链接（同时写入 file 与 url 以兼容前端解析器）
                seg.data["url"] = local
                seg.data["file"] = local
                seg.raw = None
        changed.append(seg)
    return changed

@router.get("/api/img/{filename}")
async def get_cached_qq_image(filename: str):
    # 基本安全检查，禁止路径穿越
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    path = (_QQ_IMG_CACHE_DIR / filename).resolve()
    base = _QQ_IMG_CACHE_DIR.resolve()
    try:
        if not path.is_relative_to(base):
            raise HTTPException(status_code=403, detail="forbidden")
    except AttributeError:
        # Python <3.9 兼容
        if str(base) not in str(path):
            raise HTTPException(status_code=403, detail="forbidden")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    # 简单根据扩展名返回类型
    mime, _ = mimetypes.guess_type(str(path))
    media_type = mime or "image/jpeg"
    return FileResponse(str(path), media_type=media_type)


def _segments_to_cq_string(segments: List[_CQSegment]) -> str:
    parts: List[str] = []
    for seg in segments:
        if seg.type == "text":
            parts.append(seg.data.get("text", ""))
        else:
            parts.append(seg.raw or _build_cq_code(seg))
    return "".join(parts)


def _segments_to_plain_text(segments: List[_CQSegment]) -> str:
    parts: List[str] = []
    for seg in segments:
        if seg.type == "text":
            parts.append(seg.data.get("text", ""))
        elif seg.type == "face":
            parts.append("[表情]")
        elif seg.type == "record":
            parts.append("[语音]")
        elif seg.type == "video":
            parts.append("[短视频]")
        elif seg.type == "at":
            target = seg.data.get("text") or seg.data.get("qq") or ""
            if str(target).lower() == "all":
                parts.append("@全体成员")
            elif target:
                parts.append(f"@{target}")
            else:
                parts.append("@")
        elif seg.type in {"rps", "dice", "shake", "anonymous", "contact", "location", "music", "redbag", "poke", "gift", "cardimage", "tts"}:
            parts.append(f"[{seg.type}]")
        elif seg.type == "share":
            parts.append("[链接]")
        elif seg.type == "image":
            parts.append("[图片]")
        elif seg.type == "reply":
            parts.append("[回复]")
        elif seg.type == "forward":
            parts.append("[合并转发]")
        elif seg.type == "xml":
            parts.append("[XML消息]")
        elif seg.type == "json":
            parts.append("[JSON消息]")
        else:
            parts.append(f"[{seg.type}]")
    return "".join(parts).strip()


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


async def _send_group_image(qq_group: str, image_b64: str) -> None:
    if not image_b64:
        return
    cq = f"[CQ:image,file=base64://{image_b64}]"
    await _send_group_text(qq_group, cq)


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
    segments = _parse_message_segments(payload.get("message"))
    if not segments:
        return
    # 将图片段落的链接改写为本地缓存API，便于前端安全读取
    try:
        segments = await _rewrite_image_segments_to_local(segments)
    except Exception:
        pass
    raw_message = _segments_to_cq_string(segments)
    if not raw_message:
        return
    plain_text = _segments_to_plain_text(segments)

    sender_qq = str(payload.get("user_id") or "") or None

    # 命令检测
    if await _maybe_handle_command(group_id, qq_group, nickname, plain_text, sender_qq=sender_qq):
        return

    # QQ 号
    await _emit_chat_message(group_id, nickname, raw_message, sender_qq=sender_qq)

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
            message=raw_message,
            source="qq",
            avatar=None,
        )


async def _maybe_handle_command(group_id: int, qq_group: str, nickname: str, text: str, *, sender_qq: Optional[str] = None) -> bool:
    if not text:
        return False
    text = text.strip()
    split_text = text.split()

    if text.startswith("##"):
        body = text[2:].strip()
        tokens = body.split()
        online_map = _PLAYERS_PROVIDER() or {}
        success, payload = qq_stats_command.build_report_from_command(
            tokens,
            sender_qq,
            {"qq": None, "mc": None},
            online_players_map=online_map,
            group_id=group_id
        )
        if success:
            await _send_group_image(qq_group, payload)
        else:
            await _send_group_text(qq_group, payload)
        return True

    cmd = text[0]
    if cmd not in {"#", "%", "&", "^"}:
        return False
    body = text[1:].strip()
    if cmd == "#" and len(text) == 1:
        await _cmd_show_players(group_id, qq_group)
    elif cmd == "%" and len(split_text) in {1, 2, 3}:
        await _cmd_restart_server(group_id, qq_group, body)
    elif cmd == "&" and len(text) == 1:
        await _cmd_show_status(group_id, qq_group)
    elif cmd == "^" and len(split_text) >= 2:
        await _cmd_kick_player(group_id, qq_group, body)
    elif cmd == "^":
        await _send_group_text(qq_group, "用法：^ <玩家名> [reason]")
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


async def _cmd_kick_player(group_id: int, qq_group: str, body: str) -> None:
    meta = _GROUP_META.get(group_id)
    if not meta:
        return
    tokens = body.split()
    if not tokens:
        await _send_group_text(qq_group, "用法：^ <玩家名> [reason]")
        return

    player = tokens[0]
    reason = " ".join(tokens[1:]).strip()
    players_map = _PLAYERS_PROVIDER() or {}
    targets: List[Dict[str, Any]] = []
    for srv in meta.get("servers", []):
        dir_name = srv.get("dir")
        if dir_name and player in players_map.get(dir_name, set()):
            targets.append(srv)

    if not targets:
        await _send_group_text(qq_group, f"未在该服务器组内找到玩家 {player}")
        return

    command = f"kick {player}{(' ' + reason) if reason else ''}"
    executed: List[str] = []
    with get_db_context() as db:
        for srv in targets:
            server = crud.get_server_by_id(db, srv["id"])
            if not server:
                continue
            await mcdr_manager.send_command(server, command)
            executed.append(srv.get("name") or srv.get("dir") or "-")

    if executed:
        await _send_group_text(qq_group, f"已在服务器 {', '.join(executed)} 执行：{command}")


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
    try:
        logger.debug(f"[OneBot] 前缀消息检查 | server={server_name} player={player} len={len(message)} 目标组={groups}")
    except Exception:
        pass
    for gid in groups:
        qq_group = _GROUP_TO_QQ.get(gid)
        if not qq_group:
            continue
        await _send_group_text(qq_group, f"<{player}> {message}")
        try:
            logger.debug(f"[OneBot] 向 QQ 群发送前缀消息 | gid={gid} qq_group={qq_group}")
        except Exception:
            pass


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


@router.websocket("/api/aspanel/onebot/ws")
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
