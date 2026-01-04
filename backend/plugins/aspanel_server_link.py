# backend/plugins/aspanel_server_link.py
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any, List, Optional
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
_SERVER_ID: Optional[int] = None
_SERVER_GROUPS: List[str] = []
_LOCAL_PLAYERS: set[str] = set()
_HANDLER: str = ""
_IS_PROXY_SERVER: bool = False
_CQ_PATTERN = re.compile(r"\[CQ:[^\]]*\]")
_JOINED_LOCAL_PATTERN = re.compile(r"\[local\]\s+logged in with entity id\b")

_POS_THREAD: Optional[threading.Thread] = None
_POS_STOP = threading.Event()

# QQ群成员列表响应缓存
_QQLIST_RESPONSE: Optional[List[dict[str, Any]]] = None
_QQLIST_EVENT = threading.Event()
_QQLIST_SERVER: Optional["ServerInterface"] = None

# 命令输出解析：data get entity <player> Pos / Dimension
_POS_PATTERN = re.compile(
    r"\[([\-0-9\.eE]+)d?,\s*([\-0-9\.eE]+)d?,\s*([\-0-9\.eE]+)d?\]"
)
_DIM_PATTERN = re.compile(r"data:\s*\"?([A-Za-z0-9_:]+)\"?")

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


def _query_pos_by_command(
    server: ServerInterface, player: str
) -> tuple[Optional[tuple[float, float, float]], Optional[str]]:
    """通过 vanilla data 命令获取坐标与维度，运行在服务端线程，无需 Data API。"""
    pos = None
    dim = None
    try:
        out = server.rcon_query(f"data get entity {player} Pos")
        m = _POS_PATTERN.search(str(out))
        if m:
            pos = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    except Exception:
        server.logger.warning(f"Failed to query position for player {player}")
        pos = None
    try:
        out = server.rcon_query(f"data get entity {player} Dimension")
        m = _DIM_PATTERN.search(str(out))
        if m:
            dim = m.group(1)
    except Exception:
        dim = None
    return pos, dim


def _query_save_all(server: ServerInterface) -> bool:
    """通过 rcon 强制保存世界。"""
    try:
        out = server.rcon_query("save-off")
        if "Saving is already turned off" not in str(out):
            server.rcon_query("save-all")
            server.rcon_query("save-on")
            return True
    except Exception:
        return False


def _read_aspanel_port() -> int:
    """
    读取 ASPanel 的 config.yaml 获取端口。
    插件运行在 MCDR 服务器目录，ASPanel 配置文件在上级目录。
    查找顺序：
    1. 当前目录向上查找 config.yaml / config.yml
    2. 环境变量 ASPANEL_PORT
    3. 默认值 8013
    """
    # 从当前目录向上查找 config.yaml
    current = Path(".").resolve()
    for _ in range(10):  # 最多向上查找 10 层
        for name in ["config.yaml", "config.yml"]:
            cfg_path = current / name
            if cfg_path.exists() and cfg_path.is_file():
                try:
                    import yaml
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    server_cfg = data.get("server") or {}
                    port = server_cfg.get("port")
                    if isinstance(port, int) and port > 0:
                        return port
                except Exception:
                    pass
        parent = current.parent
        if parent == current:
            break
        current = parent
    
    # 回退到环境变量
    env_port = os.getenv("ASPANEL_PORT")
    if env_port and env_port.isdigit():
        return int(env_port)
    
    # 默认值
    return 8013


def _read_env_config() -> dict[str, Any]:
    def _int_env(name: str, default: int) -> int:
        v = os.getenv(name)
        return int(v) if v is not None and v != "" else default

    # 读取 ASPanel 端口，用于构建默认 WS URL
    aspanel_port = _read_aspanel_port()
    default_ws_url = f"ws://127.0.0.1:{aspanel_port}/aspanel/mcdr"

    cfg = {
        "ws_url": os.getenv("ASPANEL_WS_URL", default_ws_url),
        "connect_timeout": _int_env("ASPANEL_WS_CONNECT_TIMEOUT", 5),
        "reconnect_interval": _int_env("ASPANEL_WS_RECONNECT_INTERVAL", 3),
        "max_queue": _int_env("ASPANEL_WS_MAX_QUEUE", 2000),
        "flush_interval_ms": _int_env("ASPANEL_WS_FLUSH_INTERVAL_MS", 200),
    }
    return cfg


def _read_mcdr_handler() -> str:
    """
    读取 MCDR config.yml 中的 handler 字段。
    为避免额外依赖，这里使用简单的正则扫描。
    """
    cfg_path = Path("config.yml")
    if not cfg_path.exists():
        return ""
    try:
        text = cfg_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    m = re.search(r"^handler\\s*:\\s*([A-Za-z0-9_\\-]+)", text, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()
    return ""


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
        self._t = threading.Thread(
            target=self._run, name="aspanel-ws-sender", daemon=True
        )
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
            merged.setdefault("server", _SERVER_NAME)
            merged.setdefault("server_groups", list(_SERVER_GROUPS))
        except Exception:
            merged = data
        payload = {"event": event, "ts": _utc_iso(), "data": merged}
        try:
            if hasattr(self.server, "logger") and self.server.logger:
                self.server.logger.debug(
                    f"[asPanel] 入队事件: {event} | 内容: {_safe_json_dumps(payload)}"
                )
            else:
                print(
                    f"[asPanel] 入队事件: {event} | 内容: {_safe_json_dumps(payload)}"
                )
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
                logger.warning(
                    "[asPanel] 未检测到 websocket-client 依赖，WS 上报被禁用"
                )
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
                                obj = json.loads(
                                    msg
                                    if isinstance(msg, str)
                                    else msg.decode("utf-8", "ignore")
                                )
                                if isinstance(obj, dict):
                                    ev = obj.get("event")
                                    data = obj.get("data") or {}
                                    if ev == "sl.group_update":
                                        if (
                                            isinstance(data, dict)
                                            and str(data.get("server")) == _SERVER_NAME
                                        ):
                                            groups = data.get("server_groups") or []
                                            if isinstance(groups, list):
                                                global _SERVER_GROUPS
                                                _SERVER_GROUPS = [
                                                    str(x) for x in groups
                                                ]
                                                try:
                                                    sid = data.get("server_id")
                                                    if isinstance(sid, int):
                                                        global _SERVER_ID
                                                        _SERVER_ID = sid
                                                except Exception:
                                                    pass
                                                try:
                                                    if logger:
                                                        logger.info(
                                                            f"[asPanel] 收到组更新：{_SERVER_GROUPS}"
                                                        )
                                                except Exception:
                                                    pass
                                    elif ev == "sl.save_all":
                                        if (
                                            isinstance(data, dict)
                                            and str(data.get("server")) == _SERVER_NAME
                                        ):
                                            if _query_save_all(self.server):
                                                logger.debug(
                                                    "[asPanel] 收到保存世界请求，已执行 save-all"
                                                )
                                                _send_event(
                                                    self.server,
                                                    "mcdr.save_all_executed",
                                                    {"server": _SERVER_NAME},
                                                )
                                            else:
                                                logger.warning(
                                                    "[asPanel] 收到保存世界请求，但执行 save-all 失败 (saving 可能被pb关闭)， 将延迟15秒后重试"
                                                )

                                                # 15秒后再次尝试保存(非阻塞)
                                                def _delayed_save():
                                                    time.sleep(15)
                                                    if _query_save_all(self.server):
                                                        logger.debug(
                                                            "[asPanel] 延迟保存世界请求已执行 save-all"
                                                        )
                                                    else:
                                                        logger.warning(
                                                            "[asPanel] 延迟保存世界请求执行 save-all 失败 (saving 可能被pb关闭)"
                                                        )
                                                    _send_event(
                                                        self.server,
                                                        "mcdr.save_all_executed",
                                                        {"server": _SERVER_NAME},
                                                    )

                                                threading.Thread(
                                                    target=_delayed_save, daemon=True
                                                ).start()

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
                                    # QQ群成员列表响应
                                    elif ev == "qqlist.response":
                                        try:
                                            _handle_qqlist_response(self.server, data)
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
                            f"[asPanel] WS 连接失败或中断，{self.reconnect_interval}s 后重试 | url={self.ws_url}"
                        )
                    else:
                        print(
                            f"[asPanel] WS 连接失败或中断，{self.reconnect_interval}s 后重试 | url={self.ws_url}"
                        )
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
            data.setdefault("server", _SERVER_NAME)
            data.setdefault("server_groups", list(_SERVER_GROUPS))
            if _SERVER_ID is not None:
                data.setdefault("server_id", _SERVER_ID)
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


# ----------------------------- 位置上报 -----------------------------


def _collect_player_positions(server: ServerInterface) -> List[dict[str, Any]]:
    """获取玩家坐标与维度：仅使用 data 命令 + RCON。"""
    if _IS_PROXY_SERVER:
        return []
    try:
        players = list(_LOCAL_PLAYERS)
    except Exception:
        players = []
    if not players:
        return []

    res: List[dict[str, Any]] = []
    done = threading.Event()

    def _task():
        try:
            for p in players:
                try:
                    pos = None
                    dim = None
                    if pos is None or dim is None:
                        cmd_pos, cmd_dim = _query_pos_by_command(server, p)
                        if pos is None:
                            pos = cmd_pos
                        if dim is None:
                            dim = cmd_dim
                    if pos is None:
                        continue
                    x, y, z = pos
                    res.append(
                        {
                            "player": p,
                            "position": {"x": float(x), "y": float(y), "z": float(z)},
                            "dimension": dim,
                        }
                    )
                except Exception:
                    continue
        finally:
            done.set()

    # 始终在独立后台线程里调用，避免阻塞 MCDR 任务线程
    try:
        t = threading.Thread(target=_task, name="aspanel-pos-query", daemon=True)
        t.start()
    except Exception:
        return []

    t.join(timeout=2.0)
    return res


def _report_positions(server: ServerInterface, reason: str) -> None:
    """上报当前位置列表。reason: tick/join/leave"""
    payload = _collect_player_positions(server)
    if not payload:
        try:
            server.logger.debug(
                f"[asPanel] 位置上报跳过：未获取到玩家位置 | reason={reason}"
            )
        except Exception:
            pass
        return
    try:
        server.logger.debug(
            f"[asPanel] 上报玩家位置：reason={reason} count={len(payload)}"
        )
    except Exception:
        pass
    _send_event(
        server,
        "mcdr.player_position",
        {
            "reason": reason,
            "positions": payload,
        },
    )


def _position_loop(server: ServerInterface):
    """每 10 整秒上报一次位置。"""
    while not _POS_STOP.is_set():
        now = time.time()
        # sleep 到下一个 10 秒边界
        sleep_sec = max(0.1, 5 - (now % 5))
        _POS_STOP.wait(sleep_sec)
        if _POS_STOP.is_set():
            break
        try:
            _report_positions(server, "tick")
        except Exception:
            try:
                server.logger.debug("[asPanel] 定时位置上报失败")
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


def _parse_share_card(seg_type: str, data_str: str) -> dict[str, Any] | None:
    """解析 XML/JSON 分享卡片，提取标题、描述、链接等信息。
    
    支持：B站视频分享、网易云音乐、微博、公众号文章等常见分享格式。
    """
    if not data_str:
        return None
    
    result: dict[str, Any] = {}
    
    try:
        if seg_type == "json":
            # 尝试解析 JSON 格式
            import json as _json
            try:
                obj = _json.loads(data_str)
            except _json.JSONDecodeError:
                return None
            
            # B站视频分享格式 (新版)
            # {"app":"com.tencent.structmsg", "meta":{"news":{"title":"...", "desc":"...", "jumpUrl":"..."}}}
            # 或 {"app":"com.tencent.miniapp_01", "meta":{"detail_1":{"title":"...", "desc":"...", "qqdocurl":"..."}}}
            meta = obj.get("meta") or {}
            
            # 尝试多种可能的结构
            for key in ["news", "detail_1", "detail", "music", "video"]:
                if key in meta:
                    item = meta[key]
                    result["title"] = item.get("title") or item.get("desc") or ""
                    result["desc"] = item.get("desc") or item.get("preview") or ""
                    result["url"] = (
                        item.get("jumpUrl") or 
                        item.get("qqdocurl") or 
                        item.get("url") or 
                        item.get("musicUrl") or
                        ""
                    )
                    # 来源标识
                    tag = item.get("tag") or item.get("source") or ""
                    if "bilibili" in str(result.get("url", "")).lower() or "b23.tv" in str(result.get("url", "")).lower():
                        result["title"] = item.get("desc")
                        result["source"] = "B站"
                    elif "music.163" in str(result.get("url", "")).lower():
                        result["source"] = "网易云"
                    elif "weibo" in str(result.get("url", "")).lower():
                        result["source"] = "微博"
                    elif "mp.weixin" in str(result.get("url", "")).lower():
                        result["source"] = "公众号"
                    elif "douyin" in str(result.get("url", "")).lower():
                        result["source"] = "抖音"
                    elif tag:
                        result["source"] = tag
                    else:
                        result["source"] = "分享"
                    break
            
            # B站小程序格式
            if not result.get("title") and obj.get("prompt"):
                result["title"] = obj.get("prompt") or ""
                result["source"] = "分享"
            
            # 直接在顶层的格式
            if not result.get("title"):
                result["title"] = obj.get("title") or obj.get("prompt") or ""
                result["desc"] = obj.get("desc") or ""
                result["url"] = obj.get("url") or obj.get("jumpUrl") or ""
        
        elif seg_type == "xml":
            # 尝试解析 XML 格式
            # 常见格式: <msg><item><title>...</title><summary>...</summary><url>...</url></item></msg>
            import re as _re
            
            # 提取标题
            title_match = _re.search(r'<title[^>]*>([^<]*)</title>', data_str, _re.IGNORECASE)
            if title_match:
                result["title"] = _cq_unescape(title_match.group(1))
            
            # 提取摘要/描述
            summary_match = _re.search(r'<summary[^>]*>([^<]*)</summary>', data_str, _re.IGNORECASE)
            if summary_match:
                result["desc"] = _cq_unescape(summary_match.group(1))
            else:
                desc_match = _re.search(r'<des[^>]*>([^<]*)</des>', data_str, _re.IGNORECASE)
                if desc_match:
                    result["desc"] = _cq_unescape(desc_match.group(1))
            
            # 提取链接
            url_match = _re.search(r'<url[^>]*>([^<]*)</url>', data_str, _re.IGNORECASE)
            if url_match:
                result["url"] = _cq_unescape(url_match.group(1))
            else:
                # 尝试从属性中提取
                action_match = _re.search(r'action="([^"]*)"', data_str)
                if action_match:
                    result["url"] = _cq_unescape(action_match.group(1))
            
            # 来源
            source_match = _re.search(r'<source[^>]*name="([^"]*)"', data_str, _re.IGNORECASE)
            if source_match:
                result["source"] = source_match.group(1)
            else:
                name_match = _re.search(r'name="([^"]*)"', data_str)
                if name_match:
                    result["source"] = name_match.group(1)
            
            # 根据 URL 判断来源
            url = result.get("url", "")
            if "bilibili" in url.lower() or "b23.tv" in url.lower():
                result["source"] = "B站"
            elif "music.163" in url.lower():
                result["source"] = "网易云"
        
        # 确保有标题才返回
        if result.get("title"):
            return result
        return None
    
    except Exception:
        return None


def _get_url_source(url: str) -> str | None:
    """根据 URL 识别来源平台"""
    if not url:
        return None
    url_lower = url.lower()
    if "bilibili.com" in url_lower or "b23.tv" in url_lower:
        return "B站"
    elif "music.163.com" in url_lower:
        return "网易云"
    elif "weibo.com" in url_lower or "weibo.cn" in url_lower:
        return "微博"
    elif "mp.weixin.qq.com" in url_lower:
        return "公众号"
    elif "douyin.com" in url_lower:
        return "抖音"
    elif "xiaohongshu.com" in url_lower or "xhslink.com" in url_lower:
        return "小红书"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "X"
    elif "github.com" in url_lower:
        return "GitHub"
    elif "zhihu.com" in url_lower:
        return "知乎"
    elif "taobao.com" in url_lower or "tb.cn" in url_lower:
        return "淘宝"
    elif "jd.com" in url_lower:
        return "京东"
    elif "qq.com" in url_lower:
        return "腾讯"
    return None


# URL 匹配正则
_URL_PATTERN = re.compile(r'(https?://[^\s<>\[\]]+)')


def _text_to_rtext_with_urls(text: str) -> RText:
    """将文本转换为 RText，识别其中的 URL 并添加点击事件和来源标识"""
    if not text:
        return _rtext_gray("")
    
    # 查找所有 URL
    matches = list(_URL_PATTERN.finditer(text))
    if not matches:
        return _rtext_gray(text)
    
    result: RText | None = None
    last_end = 0
    
    for match in matches:
        start, end = match.span()
        url = match.group(1)
        
        # 添加 URL 前的普通文本
        if start > last_end:
            prefix_text = text[last_end:start]
            part = _rtext_gray(prefix_text)
            result = part if result is None else result + part
        
        # 处理 URL
        source = _get_url_source(url)
        if source:
            # 有来源标识的 URL
            source_part = RText(f"[{source}]", color=RColor.aqua)
            source_part.set_click_event(RAction.open_url, url)
            source_part.set_hover_text(f"点击打开链接\n{url}")
            result = source_part if result is None else result + source_part
        else:
            # 普通 URL
            url_part = RText("[链接]", color=RColor.aqua)
            url_part.set_click_event(RAction.open_url, url)
            url_part.set_hover_text(f"点击打开链接\n{url}")
            result = url_part if result is None else result + url_part
        
        last_end = end
    
    # 添加最后一段普通文本
    if last_end < len(text):
        suffix_text = text[last_end:]
        part = _rtext_gray(suffix_text)
        result = part if result is None else result + part
    
    return result if result is not None else _rtext_gray(text)


def _cq_segment_to_rtext(segment: dict[str, Any]) -> RText | None:
    seg_type = str(segment.get("type") or "")
    data = segment.get("data") or {}
    raw = segment.get("raw")
    if seg_type == "text":
        text_content = str(segment.get("text") or "")
        # 解析文本中的 URL
        return _text_to_rtext_with_urls(text_content)
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
            label.set_click_event(RAction.suggest_command, url)
            label.set_hover_text(f"点击播放 {url}")
        else:
            label.set_hover_text("语音内容缺失")
        return label
    if seg_type == "video":
        return RText("[短视频]", color=RColor.gray)
    if seg_type == "at":
        target_qq = str(data.get("qq") or "")
        target_text = str(data.get("name") or "")
        # 优先使用 text 字段作为显示名，否则使用 qq 号
        if target_qq.lower() == "all" or target_text == "全体成员":
            display = "@全体成员"
        elif target_text:
            display = f"@{target_text}"
        elif target_qq:
            display = f"@{target_qq}"
        else:
            display = "@"
        # 显示为蓝色的 @用户名
        label = RText(display, color=RColor.aqua)
        if raw:
            label.set_click_event(RAction.suggest_command, f".{raw}")
            label.set_hover_text(f"点击提及 {target_text or target_qq}")
        return label
    if seg_type == "share":
        url = _normalize_media_url(
            data.get("url") or data.get("jumpUrl") or data.get("file")
        )
        title = str(data.get("title") or data.get("content") or url or "")
        label = RText("[链接]", color=RColor.aqua)
        if url:
            label.set_click_event(RAction.suggest_command, url)
        label.set_hover_text(title or "链接")
        return label
    if seg_type == "image":
        url = _normalize_media_url(data.get("url") or data.get("file"))
        label = RText("[图片]", color=RColor.aqua)
        if url:
            label.set_click_event(RAction.suggest_command, url)
            label.set_hover_text(f"点击打开图片 {url}")
        else:
            label.set_hover_text("图片地址缺失")
        return label
    if seg_type == "file":
        url = _normalize_media_url(data.get("url") or data.get("file"))
        label = RText("[文件]", color=RColor.aqua)
        if url:
            label.set_click_event(RAction.suggest_command, url)
            label.set_hover_text(f"点击打开文件 {url}")
        else:
            label.set_hover_text("文件地址缺失")
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
        detail = str(data.get("data") or "")
        # 尝试解析 B站/常见分享卡片
        parsed = _parse_share_card(seg_type, detail)
        if parsed:
            title = parsed.get("title") or ""
            desc = parsed.get("desc") or ""
            url = parsed.get("url") or ""
            source = parsed.get("source") or ""
            
            # 构建显示文本
            if source:
                label = RText(f"[{source}] ", color=RColor.aqua)
            else:
                label = RText("[分享] ", color=RColor.aqua)
            label.set_click_event(RAction.open_url, url)
            title_part = RText(title, color=RColor.white)
            if url:
                title_part.set_click_event(RAction.open_url, url)
                hover = f"{title}"
                if desc:
                    hover += f"\n{desc[:100]}{'...' if len(desc) > 100 else ''}"
                hover += f"\n点击打开链接"
                title_part.set_hover_text(hover)
                label.set_hover_text(hover)
            
            return label + title_part
        else:
            label = RText("[XML/JSON]", color=RColor.green)
            if detail:
                label.set_hover_text(detail[:300])
            return label
    if seg_type in {
        "rps",
        "dice",
        "shake",
        "anonymous",
        "contact",
        "location",
        "music",
        "redbag",
        "poke",
        "gift",
        "cardimage",
        "tts",
    }:
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


def _wrap_rtext_with_reply(rtext: RText, reply_cq: str) -> RText:
    """为 RText 添加回复点击事件的包装器"""
    # 创建一个包装 RText，设置点击事件
    wrapper = RText("")
    # 由于 RText 的 + 操作会返回 RTextList，我们需要特殊处理
    # 直接在原 rtext 上设置事件（如果它是简单的 RText）
    try:
        # 尝试直接设置点击事件
        rtext.set_click_event(RAction.suggest_command, f".{reply_cq}")
        rtext.set_hover_text("点击回复此消息")
        return rtext
    except Exception:
        # 如果失败，返回原文本
        return rtext


def _handle_forward_event(server: ServerInterface, event: str, data: dict[str, Any]):
    # 仅处理与自己同组的事件
    if not _same_group(data.get("server_groups")):
        return
    src = str(data.get("server") or "?")
    # 不重复显示本服自己的上报
    if src == _SERVER_NAME:
        return

    # 构建可点击的服务器标签 [server]
    prefix = (
        _rtext_gray("[")
        + _rtext_gray(src).set_click_event(RAction.suggest_command, f"/server {src}")
        + _rtext_gray("] ")
    )

    if event == "mcdr.user_info":
        payload = _extract_user_info_payload(data) or {}
        is_user = bool(payload.get("is_user"))
        player = payload.get("player")
        content = str(payload.get("content") or payload.get("raw_content") or "")
        if is_user and player:
            # [server] <player> content
            p = _rtext_gray(f"<{player}> ").set_click_event(
                RAction.suggest_command, f"@ {player}"
            )
            server.say(prefix + p + _rtext_gray(content))
            # 提及检测：扫描本服在线玩家集合，匹配 @Name 或 @ Name（精确到完整 MC ID，不误匹配前缀）
            try:
                if "@" in content and _LOCAL_PLAYERS:
                    import re

                    notified = set()
                    for name in list(_LOCAL_PLAYERS):
                        # 匹配 @Name 或 @ Name，后面不能再跟字母/数字/下划线，避免匹配到更长的ID前缀
                        pattern = re.compile(
                            rf"@\s*{re.escape(name)}(?![A-Za-z0-9_])", re.IGNORECASE
                        )
                        if pattern.search(content):
                            notified.add(name)
                    for name in notified:
                        server.execute(
                            f"execute at {name} run playsound minecraft:entity.arrow.hit_player player {name}"
                        )
            except Exception:
                pass

    elif event == "mcdr.server_startup":
        # [server] ON
        server.say(prefix + _rtext_gray("ON"))

    elif event == "mcdr.server_stop":
        # [server] OFF
        server.say(prefix + _rtext_gray("OFF"))

    elif event in ["mcdr.player_joined", "mcdr.bot_joined"]:
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
    # data: { level, message, user, avatar, group_id, source, sender_qq, message_id, reply_info }
    level = str(data.get("level") or "NORMAL").upper()
    message = str(data.get("message") or "")
    user = str(data.get("user") or "")
    source = str(data.get("source") or "web").lower()
    gid = data.get("group_id")
    sender_qq = data.get("sender_qq")
    message_id = data.get("message_id")
    reply_info = data.get("reply_info")  # { user, content, sender_qq }
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
        t = (
            RText("[ALERT] ", color=RColor.red, styles=RStyle.italic)
            + RText(f"<{user}> ", color=RColor.red, styles=RStyle.italic)
            + RText(message, color=RColor.red, styles=RStyle.italic)
        )
        server.say(t)
    else:
        if source == "qq":
            # 获取额外字段
            at_bound_players = data.get("at_bound_players") or []  # 被艾特的绑定玩家列表
            
            # 收集需要播放提示音的玩家
            players_to_notify: set[str] = set()
            
            reply_line = None
            # 如果有回复信息，先显示回复行
            if reply_info and isinstance(reply_info, dict):
                reply_user = str(reply_info.get("user") or "")
                reply_content = str(reply_info.get("content") or "")
                reply_cq = reply_info.get("raw_cq")
                reply_sender_qq = reply_info.get("sender_qq")
                reply_msg_id = reply_info.get("message_id")  # 被回复消息的ID
                is_from_game = reply_info.get("is_from_game", False)  # 是否来自游戏
                game_player = reply_info.get("game_player")  # 游戏玩家名
                
                # 构建回复行: │ 回复 [QQ] <用户名> 消息 或 │ 回复 <玩家名> 消息
                reply_line = RText("│ ", color=RColor.dark_gray)
                reply_line = reply_line + RText("回复 ", color=RColor.light_purple)
                
                if is_from_game and game_player:
                    # 来自游戏的消息，不显示 [QQ]，用户名用白色
                    reply_user_part = RText(f"<{game_player}>", color=RColor.white)
                    reply_user_part.set_click_event(RAction.suggest_command, f"@ {game_player}")
                    reply_user_part.set_hover_text(f"点击提及 {game_player}")
                    reply_line = reply_line + reply_user_part + RText(" ", color=RColor.white)
                    
                    # 游戏消息的回复内容也用白色
                    max_reply_len = 40
                    # 去掉 <player> 前缀显示实际内容
                    actual_content = reply_content
                    if reply_content.startswith(f"<{game_player}> "):
                        actual_content = reply_content[len(f"<{game_player}> "):]
                    if len(actual_content) > max_reply_len:
                        reply_content_display = actual_content[:max_reply_len] + "..."
                    else:
                        reply_content_display = actual_content
                    
                    reply_content_part = RText(reply_content_display, color=RColor.white)
                    
                    # 检查被回复的游戏玩家是否在线，如果在线则加入通知列表
                    if game_player in _LOCAL_PLAYERS:
                        players_to_notify.add(game_player)
                else:
                    # 来自 QQ 的消息
                    reply_line = reply_line + RText("[QQ] ", color=RColor.dark_gray)
                    
                    # 被回复者用户名（可点击艾特）
                    if reply_sender_qq:
                        reply_at_cq = f"[CQ:at,qq={reply_sender_qq}]"
                        reply_user_part = RText(f"<{reply_user}>", color=RColor.dark_gray)
                        reply_user_part.set_click_event(RAction.suggest_command, f".{reply_at_cq} ")
                        reply_user_part.set_hover_text(f"点击提及 {reply_user}")
                    else:
                        reply_user_part = _rtext_gray(f"<{reply_user}>")
                    
                    reply_line = reply_line + reply_user_part + _rtext_gray(" ")
                    
                    reply_content_display = _cq_message_to_rtext(reply_cq)
                    
                    reply_content_part = reply_content_display.set_color(RColor.dark_gray)
                
                # 为回复内容添加点击事件，回复被回复的消息
                reply_mark = _rtext_gray(" [↑]")

                if reply_msg_id:
                    reply_to_original_cq = f"[CQ:reply,id={reply_msg_id}]"
                    reply_mark.set_click_event(RAction.suggest_command, f".{reply_to_original_cq} ")
                    reply_mark.set_hover_text("点击回复此消息")
                
                reply_line = reply_line + reply_content_part + reply_mark
                
            
            # 检查被艾特的绑定玩家是否在线
            for bound_player in at_bound_players:
                if bound_player in _LOCAL_PLAYERS:
                    players_to_notify.add(bound_player)
            
            # 播放提示音给需要通知的玩家
            for player_name in players_to_notify:
                try:
                    server.execute(
                        f"execute at {player_name} run playsound minecraft:entity.arrow.hit_player player {player_name}"
                    )
                except Exception:
                    pass
            
            # 显示回复行
            if reply_line is not None:
                server.say(reply_line)
            
            # [QQ] 可点击，提示输入 !!qqlist 命令
            prefix_qq = RText("[QQ]", color=RColor.gray)
            prefix_qq.set_click_event(RAction.suggest_command, "!!qqlist")
            prefix_qq.set_hover_text("点击查看QQ群成员列表")
            prefix = prefix_qq + _rtext_gray(" ")
            if reply_line is not None:
                prefix = RText("│ ", color=RColor.dark_gray) + prefix

            # <用户名> 可点击，复制艾特标记
            if sender_qq:
                at_cq = f"[CQ:at,qq={sender_qq}]"
                user_part = RText(f"<{user}>", color=RColor.gray)
                user_part.set_click_event(RAction.suggest_command, f".{at_cq} ")
                user_part.set_hover_text(f"点击提及 {user}")
            else:
                user_part = _rtext_gray(f"<{user}>")

            # 消息内容可点击，复制回复标记
            content_rtext = _cq_message_to_rtext(message)
            reply_mark = _rtext_gray(" [↑]")

            if message_id:
                reply_cq = f"[CQ:reply,id={message_id}]"
                reply_mark = _wrap_rtext_with_reply(reply_mark, reply_cq)
            t = prefix + user_part + _rtext_gray(" ") + content_rtext + reply_mark
        else:
            prefix = "[WEB] "
            t = _rtext_gray(prefix) + _rtext_gray(f"<{user}> ") + _rtext_gray(message)
        server.say(t)


def _handle_qqlist_response(server: ServerInterface, data: dict[str, Any]):
    """处理来自后端的QQ群成员列表响应"""
    global _QQLIST_RESPONSE, _QQLIST_SERVER
    speakers = data.get("speakers") or []
    _QQLIST_RESPONSE = speakers
    _QQLIST_SERVER = server
    _QQLIST_EVENT.set()


def _request_qqlist(server: ServerInterface):
    """发送请求获取QQ群成员列表"""
    global _QQLIST_RESPONSE
    _QQLIST_RESPONSE = None
    _QQLIST_EVENT.clear()
    _send_event(server, "mcdr.qqlist_request", {"server": _SERVER_NAME})


def _display_qqlist(server: ServerInterface):
    """显示QQ群成员列表"""
    global _QQLIST_RESPONSE
    speakers = _QQLIST_RESPONSE or []

    if not speakers:
        server.say(_rtext_gray("暂无QQ群成员发言记录"))
        return

    # 标题
    title = RText("=== QQ群成员列表 ===", color=RColor.gold)
    server.say(title)

    # 显示成员列表（限制显示前20个）
    import time as _time

    now = _time.time()
    for i, speaker in enumerate(speakers[:20]):
        qq = speaker.get("qq", "")
        nickname = speaker.get("nickname", "")
        last_time = speaker.get("last_time", 0)

        # 计算距离最后发言的时间
        if last_time > 0:
            delta = now - last_time
            if delta < 60:
                time_str = "刚刚"
            elif delta < 3600:
                time_str = f"{int(delta / 60)}分钟前"
            elif delta < 86400:
                time_str = f"{int(delta / 3600)}小时前"
            else:
                time_str = f"{int(delta / 86400)}天前"
        else:
            time_str = ""

        # 创建可点击的成员条目
        # 序号
        num = RText(f"{i + 1}. ", color=RColor.gray)

        # 昵称（可点击艾特）
        at_cq = f"[CQ:at,qq={qq}]"
        name_text = RText(nickname or qq, color=RColor.aqua)
        name_text.set_click_event(RAction.suggest_command, f".{at_cq} ")
        name_text.set_hover_text(f"点击提及 {nickname or qq}\nQQ: {qq}")

        # 时间
        time_text = (
            RText(f" ({time_str})", color=RColor.gray) if time_str else RText("")
        )

        server.say(num + name_text + time_text)

    if len(speakers) > 20:
        server.say(_rtext_gray(f"... 还有 {len(speakers) - 20} 人"))


def _qqlist_command_handler(server: ServerInterface, source: Any):
    """处理 !!qqlist 命令"""

    def _do_request():
        _request_qqlist(server)
        # 等待响应（最多3秒）
        if _QQLIST_EVENT.wait(timeout=3.0):
            _display_qqlist(server)
        else:
            server.say(_rtext_gray("获取QQ群成员列表超时"))

    # 在后台线程中执行，避免阻塞
    t = threading.Thread(target=_do_request, daemon=True)
    t.start()


# ---- Plugin lifecycle ----


def on_load(server: ServerInterface, prev_module: Any):
    try:
        server.register_help_message(
            "!!aspanel_link", "asPanel Server Link：WS 上报 & 组同步"
        )
    except Exception:
        pass
    try:
        server.register_help_message(
            "!!qqlist", "查看QQ群成员列表（按最后发言时间排序）"
        )
    except Exception:
        pass
    # 读取 handler，确定是否为代理服
    global _HANDLER, _IS_PROXY_SERVER
    _HANDLER = _read_mcdr_handler()
    _IS_PROXY_SERVER = _HANDLER in {"velocity_handler", "bungeecord_handler"}
    try:
        server.logger.info(
            f"[asPanel] 当前 handler={_HANDLER or '未设置'} proxy={_IS_PROXY_SERVER}"
        )
    except Exception:
        pass
    cfg = _read_env_config()
    try:
        server.logger.info(f"[asPanel] 插件加载 | WS={cfg.get('ws_url')}")
    except Exception:
        pass
    _get_sender(server)
    _send_event(
        server,
        "mcdr.plugin_loaded",
        {"plugin": PLUGIN_METADATA, "reload": prev_module is not None},
    )
    # 启动位置上报线程（非代理服）
    global _POS_THREAD
    if not _IS_PROXY_SERVER:
        _POS_STOP.clear()
        _POS_THREAD = threading.Thread(
            target=_position_loop,
            args=(server,),
            name="aspanel-pos-reporter",
            daemon=True,
        )
        _POS_THREAD.start()


def on_unload(server: ServerInterface):
    _send_event(server, "mcdr.plugin_unloaded", {"plugin": PLUGIN_METADATA})
    try:
        global _SENDER
        if _SENDER is not None:
            _SENDER.stop(wait_seconds=0.5)
    except Exception:
        pass
    try:
        _POS_STOP.set()
        if _POS_THREAD and _POS_THREAD.is_alive():
            _POS_THREAD.join(timeout=0.5)
    except Exception:
        pass


# ---- General / User Info ----
def on_user_info(server: ServerInterface, info: Info):
    content = str(getattr(info, "content", "") or "").strip()

    # 处理 !!qqlist 命令
    if content == "!!qqlist":
        _qqlist_command_handler(server, info)
        return

    if content == "!test":
        _report_positions(server, "test_command")
        server.say("[asPanel] 测试位置上报已发送")
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
    _send_event(
        server,
        "mcdr.server_stop",
        {"server": _SERVER_NAME, "return_code": int(server_return_code)},
    )
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
    try:
        _POS_STOP.set()
        if _POS_THREAD and _POS_THREAD.is_alive():
            _POS_THREAD.join(timeout=0.5)
    except Exception:
        pass


# ---- Player events ----


def on_player_joined(server: ServerInterface, player: str, info: Info):
    if _is_bot_joined(info):
        _send_event(
            server,
            "mcdr.bot_joined",
            {"player": str(player), "info": _info_to_dict(info)},
        )
        return
    if _IS_PROXY_SERVER:
        return
    _send_event(
        server,
        "mcdr.player_joined",
        {"player": str(player), "info": _info_to_dict(info)},
    )
    try:
        _LOCAL_PLAYERS.add(str(player))
    except Exception:
        pass
    try:
        _report_positions(server, "join")
        server.logger.debug(f"[asPanel] 玩家加入：{player}，上报位置")
    except Exception:
        pass


def on_player_left(server: ServerInterface, player: str):
    if _IS_PROXY_SERVER:
        return
    if str(player) not in _LOCAL_PLAYERS:
        return
    _send_event(server, "mcdr.player_left", {"player": str(player)})
    try:
        _LOCAL_PLAYERS.discard(str(player))
    except Exception:
        pass
