# backend/plugins/aspanel_server_link.py
from __future__ import annotations

import re
import json
import os
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from queue import Queue, Full, Empty
from typing import Any, Optional, List
from urllib.parse import urlparse, urlunparse
from mcdreforged.api.all import *

# Dependency：websocket-client（pip 包名：websocket-client）
try:
    import websocket
    _HAS_WS = True
except (ModuleNotFoundError, ImportError):
    websocket = None
    _HAS_WS = False

_SERVER_NAME = Path(".").resolve().name
_SERVER_GROUPS: List[str] = []
_LOCAL_PLAYERS: set[str] = set()
_CQ_PATTERN = re.compile(r"\[CQ:[^\]]*\]")
_JOINED_LOCAL_PATTERN = re.compile(r"\[local\]\s+logged in with entity id\b")

# ----------------------------- 工具函数与配置 -----------------------------

PLUGIN_METADATA = {
    "id": "aspanel_server_link",
    "version": "0.1.0",
    "author": "CalciumSilicate",
    "name": "asPanel Server Link",
    "description": "将 MCDR 事件通过 WS 上报到 aspanel，并携带服务器分组信息",
    "requirements": ["mcdreforged>=2.0.0"],
}


# 统一日志辅助（有 logger 用 logger；否则退化为 print）
def _log_debug(server: ServerInterface, msg: str):
    try:
        if hasattr(server, "logger") and server.logger:
            server.logger.debug(msg)
        else:
            print(msg)
    except Exception:
        pass


def _log_info(server: ServerInterface, msg: str):
    try:
        if hasattr(server, "logger") and server.logger:
            server.logger.info(msg)
        else:
            print(msg)
    except Exception:
        pass


def _log_warn(server: ServerInterface, msg: str):
    try:
        if hasattr(server, "logger") and server.logger:
            server.logger.warning(msg)
        else:
            print(msg)
    except Exception:
        pass



def _is_bot_joined(info: Info):
    """检测是否为本地(local)登录的机器人/控制台伪玩家加入日志。

    旧实现错误地访问了不存在的捕获组，导致在匹配时抛出异常，
    进一步影响后续事件处理。这里改为安全的 search 检测。
    """
    try:
        content = str(getattr(info, "content", "") or "")
    except Exception:
        return False
    return bool(_JOINED_LOCAL_PATTERN.search(content))


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _info_to_dict(info: Info) -> dict[str, Any]:
    def g(obj: Any, name: str, default: Any = None) -> Any:
        return getattr(obj, name, default)

    return {
        "server": _SERVER_NAME,
        "content": g(info, "content"),
        "raw_content": g(info, "raw_content"),
        "is_user": g(info, "is_user"),
        "player": g(info, "player"),
        "source": str(g(info, "source")),
        "timestamp": g(info, "timestamp", None),
    }


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except json.JSONDecodeError:
        return json.dumps(str(obj), ensure_ascii=False)


def _read_env_config() -> dict[str, Any]:
    def _int_env(name: str, default: int) -> int:
        v = os.getenv(name)
        return int(v) if v is not None and v != "" else default

    cfg = {
        "ws_url": os.getenv("ASPANEL_WS_URL", "ws://127.0.0.1:8013/aspanel/mcdr"),
        "connect_timeout": _int_env("ASPANEL_WS_CONNECT_TIMEOUT", 5),
        "reconnect_interval": _int_env("ASPANEL_WS_RECONNECT_INTERVAL", 3),
        "max_queue": _int_env("ASPANEL_WS_MAX_QUEUE", 2000),
        "flush_interval_ms": _int_env("ASPANEL_WS_FLUSH_INTERVAL_MS", 200),
    }
    return cfg


# ----------------------------- WS 发送后台线程 -----------------------------

class WsSender:
    def __init__(self, server: ServerInterface, cfg: dict[str, Any]):
        self.server = server
        self.ws_url: str = str(cfg.get("ws_url"))
        self.connect_timeout: int = int(cfg.get("connect_timeout", 5))
        self.reconnect_interval: int = int(cfg.get("reconnect_interval", 3))
        self.flush_interval_ms: int = int(cfg.get("flush_interval_ms", 50))
        self.queue: Queue[Any] = Queue(maxsize=int(cfg.get("max_queue", 2000)))
        self._stop = threading.Event()
        self._t: Optional[threading.Thread] = None
        self._ws = None
        self._stop_sentinel = object()

    def start(self) -> None:
        if self._t and self._t.is_alive():
            return
        self._t = threading.Thread(target=self._run, name="aspanel-ws-sender", daemon=True)
        self._t.start()
        _log_info(self.server, f"[asPanel] WS 发送线程已启动 | url={self.ws_url}")

    def stop(self, wait_seconds: float = 0.5) -> None:
        self._stop.set()
        try:
            self.queue.put_nowait(self._stop_sentinel)
        except Exception:
            pass
        if self._t:
            self._t.join(timeout=max(0.1, float(wait_seconds)))
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass
        _log_info(self.server, "[asPanel] WS 发送线程已停止")

    def enqueue(self, event: str, data: dict[str, Any]) -> None:
        # 统一追加 server 与 server_groups 字段
        try:
            merged = dict(data)
            merged.setdefault("server", _SERVER_NAME)
            merged.setdefault("server_groups", list(_SERVER_GROUPS))
        except Exception:
            merged = data
        payload = {"event": event, "ts": _utc_iso(), "data": merged}
        try:
            if hasattr(self.server, "logger") and self.server.logger:
                self.server.logger.debug(f"[asPanel] 入队事件: {event} | 内容: {_safe_json_dumps(payload)}")
            else:
                print(f"[asPanel] 入队事件: {event} | 内容: {_safe_json_dumps(payload)}")
        except Exception:
            pass
        try:
            self.queue.put_nowait(payload)
            try:
                _log_debug(self.server, f"[asPanel] 事件入队成功 | event={event} 队列长度={self.queue.qsize()}")
            except Exception:
                pass
        except Full:
            try:
                _ = self.queue.get_nowait()
            except Empty:
                pass
            try:
                self.queue.put_nowait(payload)
                _log_warn(self.server, f"[asPanel] 事件队列已满，丢弃最早一条后入队 | event={event}")
            except Exception:
                _log_warn(self.server, f"[asPanel] 事件入队失败（队列满且替换失败）| event={event}")

    def _run(self) -> None:
        logger = getattr(self.server, "logger", None)
        if not _HAS_WS:
            if logger:
                logger.warning("[asPanel] 未检测到 websocket-client 依赖，WS 上报被禁用")
            return
        flush_sec = max(0.01, float(self.flush_interval_ms) / 1000.0)
        while not self._stop.is_set():
            try:
                if logger:
                    logger.info(f"[asPanel] 正在连接 WS: {self.ws_url}")
                else:
                    print(f"[asPanel] 正在连接 WS: {self.ws_url}")
                self._ws = websocket.create_connection(self.ws_url, timeout=self.connect_timeout)  # type: ignore
                if logger:
                    logger.info(f"[asPanel] WS 已连接: {self.ws_url}")
                else:
                    print(f"[asPanel] WS 已连接: {self.ws_url}")

                try:
                    # 设置较短的 recv 超时，便于轮询接收服务端事件
                    self._ws.settimeout(max(0.05, flush_sec / 3))  # type: ignore
                except Exception:
                    pass

                batch: list[dict[str, Any]] = []
                last_flush = time.monotonic()
                while not self._stop.is_set():
                    timeout = min(0.2, max(0.02, flush_sec / 4))
                    # 先尝试接收服务端下发事件（非阻塞）
                    try:
                        msg = self._ws.recv()  # type: ignore
                        if isinstance(msg, (str, bytes)):
                            try:
                                obj = json.loads(msg if isinstance(msg, str) else msg.decode("utf-8", "ignore"))
                                if isinstance(obj, dict):
                                    ev = obj.get("event")
                                    data = obj.get("data") or {}
                                    if ev == "sl.group_update":
                                        if isinstance(data, dict) and str(data.get("server")) == _SERVER_NAME:
                                            groups = data.get("server_groups") or []
                                            if isinstance(groups, list):
                                                global _SERVER_GROUPS
                                                _SERVER_GROUPS = [str(x) for x in groups]
                                                try:
                                                    if logger:
                                                        logger.info(f"[asPanel] 收到组更新：{_SERVER_GROUPS}")
                                                except Exception:
                                                    pass
                                    # 转发的 mcdr 事件（来自其他同组服务器）
                                    elif isinstance(ev, str) and ev.startswith("mcdr."):
                                        _log_debug(self.server, f"[asPanel] 收到远端 MCDR 事件 | event={ev} src={data.get('server')}")
                                        try:
                                            _handle_forward_event(self.server, ev, data)
                                        except Exception:
                                            _log_warn(self.server, f"[asPanel] 处理远端 MCDR 事件异常 | event={ev}")
                                    # 来自 Web 的聊天消息
                                    elif ev == "chat.message":
                                        try:
                                            _log_info(self.server, f"[asPanel] 收到 Web 聊天消息 | level={str(data.get('level')).upper()} gid={data.get('group_id')} user={data.get('user')} src={data.get('source')}")
                                        except Exception:
                                            pass
                                        try:
                                            _handle_chat_message(self.server, data)
                                        except Exception:
                                            _log_warn(self.server, "[asPanel] 处理 Web 聊天消息异常")
                            except Exception:
                                _log_warn(self.server, "[asPanel] 无法解析服务端消息（JSON 解析失败）")
                    except Exception:
                        # 超时或接收失败，忽略
                        # 仅在 debug 级别记录超时噪声，不影响主循环
                        # _log_debug(self.server, "[asPanel] WS 收取超时/无新消息")

                    # 取发送队列
                    try:
                        item = self.queue.get(timeout=timeout)
                    except Empty:
                        item = None
                    if item is self._stop_sentinel:
                        if batch:
                            try:
                                pkt = {"batch": True, "ts": _utc_iso(), "items": batch}
                                self._ws.send(_safe_json_dumps(pkt))
                            except Exception:
                                pass
                        break
                    if isinstance(item, dict):
                        batch.append(item)
                    now = time.monotonic()
                    if (now - last_flush) >= flush_sec and batch:
                        try:
                            pkt = {"batch": True, "ts": _utc_iso(), "items": batch}
                            self._ws.send(_safe_json_dumps(pkt))
                            try:
                                _log_debug(self.server, f"[asPanel] 已发送批次 | 条数={len(batch)} 队列余量≈{self.queue.qsize()}")
                            except Exception:
                                pass
                            batch = []
                            last_flush = now
                        except Exception:
                            break

            except Exception:
                try:
                    _log_warn(self.server, f"[asPanel] WS 连接失败或中断，{self.reconnect_interval}s 后重试 | url={self.ws_url}")
                except Exception:
                    pass
                time.sleep(self.reconnect_interval)
            finally:
                try:
                    if self._ws is not None:
                        self._ws.close()
                except Exception:
                    pass
                self._ws = None
                _log_warn(self.server, "[asPanel] WS 连接已关闭，等待重连")


# ----------------------------- 插件事件回调实现 -----------------------------

_SENDER: Optional[WsSender] = None


def _get_sender(server: ServerInterface) -> WsSender:
    global _SENDER
    if _SENDER is None:
        cfg = _read_env_config()
        _SENDER = WsSender(server, cfg)
        _log_debug(server, f"[asPanel] 初始化 WsSender | ws_url={_SENDER.ws_url} queue_max={cfg.get('max_queue')} flush_interval_ms={cfg.get('flush_interval_ms')}")
        _SENDER.start()
    return _SENDER


def _send_event(server: ServerInterface, event: str, data: dict[str, Any]) -> None:
    try:
        # 附带 server 与当前 server_groups 字段
        try:
            data = dict(data)
            data.setdefault("server", _SERVER_NAME)
            data.setdefault("server_groups", list(_SERVER_GROUPS))
        except Exception:
            pass
        # 事件级别日志
        try:
            preview = _safe_json_dumps({"event": event, "ts": _utc_iso(), "data": data})
            if hasattr(server, "logger") and server.logger:
                server.logger.debug(f"[asPanel] 上报事件: {event} | {preview}")
            else:
                print(f"[asPanel] 上报事件: {event} | {preview}")
        except Exception:
            pass
        _get_sender(server).enqueue(event, data)
    except Exception:
        try:
            server.logger.debug(f"[asPanel] 事件入队失败: {event}")
        except Exception:
            pass


# ----------------------------- 远端事件处理（转发显示） -----------------------------

def _same_group(data_groups: Any) -> bool:
    try:
        groups = [str(x) for x in (data_groups or [])]
        ok = any(g in _SERVER_GROUPS for g in groups)
        return ok
    except Exception:
        return False


def _extract_user_info_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    # 兼容 {info: {...}} 或扁平结构
    if isinstance(data, dict):
        if "info" in data and isinstance(data["info"], dict):
            return data["info"]
        return data
    return None


def _rtext_gray(text: str) -> RText:
    return RText(text, color=RColor.gray)


def _cq_unescape(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""
    return (
        text.replace("&amp;", "&")
        .replace("&#91;", "[")
        .replace("&#93;", "]")
        .replace("&#44;", ",")
    )


def _cq_parse_code(raw: str) -> dict[str, Any]:
    inner = raw[4:-1]
    type_name, _, rest = inner.partition(",")
    data: dict[str, str] = {}
    if rest:
        for part in rest.split(","):
            if not part:
                continue
            key, _, value = part.partition("=")
            data[key] = _cq_unescape(value)
    return {"type": type_name, "data": data, "raw": raw}


def _cq_parse_message(message: str) -> list[dict[str, Any]]:
    if not message:
        return []
    text = str(message)
    result: list[dict[str, Any]] = []
    last = 0
    for match in _CQ_PATTERN.finditer(text):
        start, end = match.span()
        if start > last:
            piece = text[last:start]
            if piece:
                result.append({"type": "text", "text": _cq_unescape(piece)})
        result.append(_cq_parse_code(match.group(0)))
        last = end
    if last < len(text):
        tail = text[last:]
        if tail:
            result.append({"type": "text", "text": _cq_unescape(tail)})
    return result


def _normalize_media_url(url: Any) -> str:
    if not url:
        return ""
    cleaned = str(url).strip()
    if not cleaned:
        return ""
    try:
        parsed = urlparse(cleaned)
    except Exception:
        return cleaned
    if parsed.scheme == "http" and parsed.netloc.endswith("qpic.cn"):
        parsed = parsed._replace(scheme="https")
        return urlunparse(parsed)
    return cleaned


def _cq_segment_to_rtext(segment: dict[str, Any]) -> RText | None:
    seg_type = str(segment.get("type") or "")
    data = segment.get("data") or {}
    raw = segment.get("raw")
    if seg_type == "text":
        return _rtext_gray(str(segment.get("text") or ""))
    if seg_type == "face":
        label = RText("[表情]", color=RColor.yellow)
        if raw:
            label.set_click_event(RAction.suggest_command, f".{raw}")
            label.set_hover_text(f"点击复制 {raw}")
        return label
    if seg_type == "record":
        url = str(data.get("url") or data.get("file") or "")
        label = RText("[语音]", color=RColor.aqua)
        if url:
            label.set_click_event(RAction.open_url, url)
            label.set_hover_text(f"点击播放 {url}")
        else:
            label.set_hover_text("语音内容缺失")
        return label
    if seg_type == "video":
        return RText("[短视频]", color=RColor.gray)
    if seg_type == "at":
        target = str(data.get("text") or data.get("qq") or "")
        if target.lower() == "all":
            display = "@全体成员"
        elif target:
            display = f"@{target}"
        else:
            display = "@"
        label = RText("[@]", color=RColor.gold)
        if raw:
            label.set_click_event(RAction.suggest_command, f".{raw}")
        label.set_hover_text(display)
        return label
    if seg_type == "share":
        url = _normalize_media_url(data.get("url") or data.get("jumpUrl") or data.get("file"))
        title = str(data.get("title") or data.get("content") or url or "")
        label = RText("[链接]", color=RColor.aqua)
        if url:
            label.set_click_event(RAction.open_url, url)
        label.set_hover_text(title or "链接")
        return label
    if seg_type == "image":
        url = _normalize_media_url(data.get("url") or data.get("file"))
        label = RText("[图片]", color=RColor.aqua)
        if url:
            label.set_click_event(RAction.open_url, url)
            label.set_hover_text(f"点击打开图片 {url}")
        else:
            label.set_hover_text("图片地址缺失")
        return label
    if seg_type == "reply":
        label = RText("[回复]", color=RColor.light_purple)
        if raw:
            label.set_click_event(RAction.suggest_command, f".{raw}")
            label.set_hover_text("点击复制回复标记")
        return label
    if seg_type == "forward":
        return RText("[合并转发]", color=RColor.gray)
    if seg_type in {"xml", "json"}:
        label = RText("[XML/JSON]", color=RColor.green)
        detail = str(data.get("data") or "")
        if detail:
            label.set_hover_text(detail[:300])
        return label
    if seg_type in {"rps", "dice", "shake", "anonymous", "contact", "location", "music", "redbag", "poke", "gift", "cardimage", "tts"}:
        return RText(f"[{seg_type}]", color=RColor.gray)
    return RText(f"[{seg_type}]", color=RColor.gray)


def _cq_message_to_rtext(message: str) -> RText:
    segments = _cq_parse_message(message)
    combined: RText | None = None
    for seg in segments:
        part = _cq_segment_to_rtext(seg)
        if part is None:
            continue
        combined = part if combined is None else combined + part
    return combined if combined is not None else _rtext_gray(str(message or ""))


def _handle_forward_event(server: ServerInterface, event: str, data: dict[str, Any]):
    # 仅处理与自己同组的事件
    if not _same_group(data.get("server_groups")):
        _log_debug(server, f"[asPanel] 忽略不同组的远端事件 | event={event} src={data.get('server')} groups={data.get('server_groups')} 本服组={_SERVER_GROUPS}")
        return
    src = str(data.get("server") or "?")
    # 不重复显示本服自己的上报
    if src == _SERVER_NAME:
        _log_debug(server, f"[asPanel] 忽略本服事件重复显示 | event={event} src={src}")
        return

    # 构建可点击的服务器标签 [server]
    prefix = _rtext_gray("[") + _rtext_gray(src).set_click_event(RAction.suggest_command,
                                                                 f"/server {src}") + _rtext_gray("] ")

    if event == "mcdr.user_info":
        payload = _extract_user_info_payload(data) or {}
        is_user = bool(payload.get("is_user"))
        player = payload.get("player")
        content = str(payload.get("content") or payload.get("raw_content") or "")
        if is_user and player:
            # [server] <player> content
            p = _rtext_gray(f"<{player}> ").set_click_event(RAction.suggest_command, f"@ {player}")
            server.say(prefix + p + _rtext_gray(content))
            # 提及检测：扫描本服在线玩家集合，匹配 @Name 或 @ Name（精确到完整 MC ID，不误匹配前缀）
            try:
                if '@' in content and _LOCAL_PLAYERS:
                    import re
                    notified = set()
                    for name in list(_LOCAL_PLAYERS):
                        # 匹配 @Name 或 @ Name，后面不能再跟字母/数字/下划线，避免匹配到更长的ID前缀
                        pattern = re.compile(rf"@\s*{re.escape(name)}(?![A-Za-z0-9_])", re.IGNORECASE)
                        if pattern.search(content):
                            notified.add(name)
                    for name in notified:
                        server.execute(
                            f"execute at {name} run playsound minecraft:entity.arrow.hit_player player {name}")
                    _log_debug(server, f"[asPanel] 远端消息触发 @ 提示 | 目标数={len(notified)} 内容长度={len(content)}")
            except Exception:
                pass

    elif event == "mcdr.server_startup":
        # [server] ON
        server.say(prefix + _rtext_gray("ON"))

    elif event == "mcdr.server_stop":
        # [server] OFF
        server.say(prefix + _rtext_gray("OFF"))

    elif event == "mcdr.player_joined":
        # [server] player joined
        player = str(data.get("player") or "?")
        p = _rtext_gray(player).set_click_event(RAction.suggest_command, f"@ {player}")
        server.say(prefix + p + _rtext_gray(" joined"))

    elif event == "mcdr.player_left":
        # [server] player left
        player = str(data.get("player") or "?")
        p = _rtext_gray(player).set_click_event(RAction.suggest_command, f"@ {player}")
        server.say(prefix + p + _rtext_gray(" left"))


def _handle_chat_message(server: ServerInterface, data: dict[str, Any]):
    # data: { level, message, user, avatar, group_id }
    level = str(data.get("level") or "NORMAL").upper()
    message = str(data.get("message") or "")
    user = str(data.get("user") or "")
    source = str(data.get("source") or "web").lower()
    gid = data.get("group_id")
    # NORMAL: 仅当该消息目标组与本服组有交集（实际上 gid 在某一组）才显示；ALERT: 全服显示
    if level != "ALERT":
        try:
            # gid 为空或不在本服组则忽略
            if not gid:
                _log_debug(server, f"[asPanel] 丢弃消息：缺少 group_id | user={user} source={source} level={level}")
                return
        except Exception:
            return
    # 打印
    if level == "ALERT":
        # [ALERT] <user> message （红色粗体）
        t = RText("[ALERT] ", color=RColor.red, styles=RStyle.bold) + RText(f"<{user}> ", color=RColor.red,
                                                                            styles=RStyle.bold) + RText(message,
                                                                                                        color=RColor.red,
                                                                                                        styles=RStyle.bold)
        server.say(t)
        _log_debug(server, f"[asPanel] 显示消息到游戏端 | source={source} gid={gid} user={user} len={len(message)}")
    else:
        if source == "qq":
            prefix = "[QQ] "
        else:
            prefix = "[WEB] "
        content_rtext = _cq_message_to_rtext(message) if source == "qq" else _rtext_gray(message)
        t = _rtext_gray(prefix) + _rtext_gray(f"<{user}> ") + content_rtext
        server.say(t)


# ---- Plugin lifecycle ----

def on_load(server: ServerInterface, prev_module: Any):
    try:
        server.register_help_message("!!aspanel_link", "asPanel Server Link：WS 上报 & 组同步")
    except Exception:
        pass
    cfg = _read_env_config()
    try:
        server.logger.info(f"[asPanel] 插件加载 | WS={cfg.get('ws_url')}")
    except Exception:
        pass
    _get_sender(server)
    _send_event(server, "mcdr.plugin_loaded", {"plugin": PLUGIN_METADATA, "reload": prev_module is not None})


def on_unload(server: ServerInterface):
    _send_event(server, "mcdr.plugin_unloaded", {"plugin": PLUGIN_METADATA})
    try:
        global _SENDER
        if _SENDER is not None:
            _SENDER.stop(wait_seconds=0.5)
    except Exception:
        pass


# ---- General / User Info ----
def on_user_info(server: ServerInterface, info: Info):
    try:
        _log_debug(server, f"[asPanel] on_user_info | is_user={getattr(info, 'is_user', None)} player={getattr(info, 'player', None)} len={len(str(getattr(info, 'content', '') or '') )}")
    except Exception:
        pass
    _send_event(server, "mcdr.user_info", {"info": _info_to_dict(info)})


# ---- Server lifecycle ----

def on_server_start_pre(server: ServerInterface):
    _send_event(server, "mcdr.server_start_pre", {"server": _SERVER_NAME})


def on_server_start(server: ServerInterface):
    _send_event(server, "mcdr.server_start", {"server": _SERVER_NAME})


def on_server_startup(server: ServerInterface):
    _send_event(server, "mcdr.server_startup", {"server": _SERVER_NAME})
    # 本服玩家列表：启动时清空
    try:
        _LOCAL_PLAYERS.clear()
    except Exception:
        pass


def on_server_stop(server: ServerInterface, server_return_code: int):
    _send_event(server, "mcdr.server_stop", {"server": _SERVER_NAME, "return_code": int(server_return_code)})
    # 本服玩家列表：停止时清空
    try:
        _LOCAL_PLAYERS.clear()
    except Exception:
        pass


# ---- MCDR lifecycle ----

def on_mcdr_start(server: ServerInterface):
    _send_event(server, "mcdr.mcdr_start", {"server": _SERVER_NAME})


def on_mcdr_stop(server: ServerInterface):
    _send_event(server, "mcdr.mcdr_stop", {"server": _SERVER_NAME})
    try:
        global _SENDER
        if _SENDER is not None:
            _SENDER.stop(wait_seconds=0.5)
    except Exception:
        pass


# ---- Player events ----

def on_player_joined(server: ServerInterface, player: str, info: Info):
    if _is_bot_joined(info):
        _log_debug(server, f"[asPanel] 忽略本地/机器人加入日志 | player={player}")
        return
    _send_event(server, "mcdr.player_joined", {"player": str(player), "info": _info_to_dict(info)})
    try:
        _LOCAL_PLAYERS.add(str(player))
    except Exception:
        pass


def on_player_left(server: ServerInterface, player: str):
    if str(player) not in _LOCAL_PLAYERS:
        _log_debug(server, f"[asPanel] 忽略离开事件（不在在线表）| player={player}")
        return
    _send_event(server, "mcdr.player_left", {"player": str(player)})
    try:
        _LOCAL_PLAYERS.discard(str(player))
    except Exception:
        pass
