# -*- coding: utf-8 -*-
"""
MCDReforged 插件：aspanel_server_link

在原 aspanel_ws_reporter 基础上增强：
- 事件 data 中新增 server_groups（该服务器所在的所有组名列表）
- 首次不再通过 HTTP 拉取分组；当服务端收到插件的 on_load（mcdr.plugin_loaded）后，会通过 WS 下发 sl.group_update 更新
- 在 WS 连接上被动接收服务端事件 sl.group_update，动态更新本地 server_groups
"""

from __future__ import annotations

import re
from pathlib import Path

from mcdreforged.api.all import *  # 采用与仓库现有插件一致的导入风格

import json
import os
import threading
import time
from datetime import datetime, timezone
from queue import Queue, Full, Empty
from typing import Any, Optional, List

# 可选依赖：websocket-client（pip 包名：websocket-client）
try:
    import websocket  # type: ignore

    _HAS_WS = True
except Exception:
    websocket = None  # type: ignore
    _HAS_WS = False

server_name = Path(".").resolve().name
_SERVER_GROUPS: List[str] = []  # 当前服务器所在的组名列表
# 本服在线玩家集（用于 @mention 播放音效与存在性判断）
_LOCAL_PLAYERS: set[str] = set()

# ----------------------------- 工具函数与配置 -----------------------------

PLUGIN_METADATA = {
    "id": "aspanel_server_link",
    "version": "0.1.0",
    "author": "CalciumSilicate",
    "name": "asPanel Server Link",
    "description": "将 MCDR 事件通过 WS 上报到 aspanel，并携带服务器分组信息",
    "requirements": ["mcdreforged>=2.0.0"],
}


def _is_bot_joined(info: Info):
    joined_player = re.match(
        r"(\w+)\[([0-9\.\:\/]+|local)\] logged in with entity id", info.content
    )
    if joined_player:
        if joined_player.group(2) == "local":
            return True
    return False


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _info_to_dict(info: Info) -> dict[str, Any]:
    def g(obj: Any, name: str, default: Any = None) -> Any:
        try:
            return getattr(obj, name)
        except Exception:
            return default

    return {
        "server": server_name,
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
    except Exception:
        return json.dumps(str(obj), ensure_ascii=False)


def _read_env_config() -> dict[str, Any]:
    def _int_env(name: str, default: int) -> int:
        try:
            v = os.getenv(name)
            return int(v) if v is not None and v != "" else default
        except Exception:
            return default

    cfg = {
        "ws_url": os.getenv("ASPANEL_WS_URL", "ws://127.0.0.1:8000/aspanel/mcdr"),
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

    def enqueue(self, event: str, data: dict[str, Any]) -> None:
        # 统一追加 server 与 server_groups 字段
        try:
            merged = dict(data)
            merged.setdefault("server", server_name)
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
        except Full:
            try:
                _ = self.queue.get_nowait()
            except Empty:
                pass
            try:
                self.queue.put_nowait(payload)
            except Exception:
                pass

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
                                        if isinstance(data, dict) and str(data.get("server")) == server_name:
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
                                        try:
                                            _handle_forward_event(self.server, ev, data)
                                        except Exception:
                                            pass
                                    # 来自 Web 的聊天消息
                                    elif ev == "chat.message":
                                        try:
                                            _handle_chat_message(self.server, data)
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                    except Exception:
                        # 超时或接收失败，忽略
                        pass

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
                            batch = []
                            last_flush = now
                        except Exception:
                            break

            except Exception:
                try:
                    if logger:
                        logger.warning(
                            f"[asPanel] WS 连接失败或中断，{self.reconnect_interval}s 后重试 | url={self.ws_url}")
                    else:
                        print(f"[asPanel] WS 连接失败或中断，{self.reconnect_interval}s 后重试 | url={self.ws_url}")
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


# ----------------------------- 插件事件回调实现 -----------------------------

_SENDER: Optional[WsSender] = None


def _get_sender(server: ServerInterface) -> WsSender:
    global _SENDER
    if _SENDER is None:
        cfg = _read_env_config()
        _SENDER = WsSender(server, cfg)
        _SENDER.start()
    return _SENDER


def _send_event(server: ServerInterface, event: str, data: dict[str, Any]) -> None:
    try:
        # 附带 server 与当前 server_groups 字段
        try:
            data = dict(data)
            data.setdefault("server", server_name)
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
        return any(g in _SERVER_GROUPS for g in groups)
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


def _handle_forward_event(server: ServerInterface, event: str, data: dict[str, Any]):
    # 仅处理与自己同组的事件
    if not _same_group(data.get("server_groups")):
        return
    src = str(data.get("server") or "?")
    # 不重复显示本服自己的上报
    if src == server_name:
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
    else:
        if source == "qq":
            prefix = "[QQ] "
        else:
            prefix = "[WEB] "
        t = _rtext_gray(prefix) + _rtext_gray(f"<{user}> ") + _rtext_gray(message)
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
    _send_event(server, "mcdr.user_info", {"info": _info_to_dict(info)})


# ---- Server lifecycle ----

def on_server_start_pre(server: ServerInterface):
    _send_event(server, "mcdr.server_start_pre", {"server": server_name})


def on_server_start(server: ServerInterface):
    _send_event(server, "mcdr.server_start", {"server": server_name})


def on_server_startup(server: ServerInterface):
    _send_event(server, "mcdr.server_startup", {"server": server_name})
    # 本服玩家列表：启动时清空
    try:
        _LOCAL_PLAYERS.clear()
    except Exception:
        pass


def on_server_stop(server: ServerInterface, server_return_code: int):
    _send_event(server, "mcdr.server_stop", {"server": server_name, "return_code": int(server_return_code)})
    # 本服玩家列表：停止时清空
    try:
        _LOCAL_PLAYERS.clear()
    except Exception:
        pass


# ---- MCDR lifecycle ----

def on_mcdr_start(server: ServerInterface):
    _send_event(server, "mcdr.mcdr_start", {"server": server_name})


def on_mcdr_stop(server: ServerInterface):
    _send_event(server, "mcdr.mcdr_stop", {"server": server_name})
    try:
        global _SENDER
        if _SENDER is not None:
            _SENDER.stop(wait_seconds=0.5)
    except Exception:
        pass


# ---- Player events ----

def on_player_joined(server: ServerInterface, player: str, info: Info):
    if _is_bot_joined(info):
        return
    _send_event(server, "mcdr.player_joined", {"player": str(player), "info": _info_to_dict(info)})
    try:
        _LOCAL_PLAYERS.add(str(player))
    except Exception:
        pass


def on_player_left(server: ServerInterface, player: str):
    if str(player) not in _LOCAL_PLAYERS:
        return
    _send_event(server, "mcdr.player_left", {"player": str(player)})
    try:
        _LOCAL_PLAYERS.discard(str(player))
    except Exception:
        pass
