# backend/services/ws.py

import json
import asyncio
import time
import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional, Set

from backend.core.utils import to_local_dt
from backend.core.ws import sio
from backend.core.logger import logger
from backend.core.api import get_uuid_by_name
from pathlib import Path
from backend.core.database import get_db_context
from backend.core import crud, models as models, schemas
from backend.core.dependencies import mcdr_manager
from backend.services import onebot

PLAYERS_BY_SERVER: Dict[str, Set[str]] = {}
LAST_ADDED_TIME: Dict[str, Dict[str, float]] = {}
JOINED_TIME: Dict[str, Dict[str, float]] = {}
SERVER_LAST_BOUNDARY: Dict[str, float] = {}
_PLAYTIME_TASK: Optional[asyncio.Task] = None
_PLAYER_SYNC_LOCK = asyncio.Lock()

onebot.set_players_provider(lambda: PLAYERS_BY_SERVER)


def _get_server_path_by_name(server_name: str) -> Optional[str]:
    try:
        with get_db_context() as db:
            for s in crud.get_all_servers(db):
                try:
                    if Path(s.path).name == server_name:
                        return s.path
                except Exception:
                    continue
    except Exception:
        return None
    return None


def _is_proxy_server(server_name: str) -> bool:
    """根据数据库记录判断该服务器是否为代理（velocity/bungeecord）。"""
    try:
        with get_db_context() as db:
            for s in crud.get_all_servers(db):
                try:
                    if Path(s.path).name != server_name:
                        continue
                    import json as _json
                    cfg = _json.loads(s.core_config or "{}")
                    stype = (cfg.get("server_type") or "").lower()
                    if stype in {"velocity", "bungeecord"}:
                        return True
                except Exception:
                    continue
    except Exception:
        return False
    return False


async def _playtime_tick_loop():
    """
    每分钟遍历在线表，将在线满 60s 的玩家对应服务器的 play_time += 1200（gt）。
    仅当该玩家在数据库中存在记录且其 play_time[server_name] 键存在时才累计。
    """
    from backend.core.database import get_db_context as _db_ctx
    while True:
        try:
            await asyncio.sleep(60)
            now = time.time()
            increments_total = 0
            per_server: Dict[str, int] = {}
            with _db_ctx() as db:
                for server_name, players in list(PLAYERS_BY_SERVER.items()):
                    server_path = _get_server_path_by_name(server_name)
                    world_dir = Path(server_path) / 'server' / 'world' if server_path else None
                    if not server_path or not world_dir.exists():
                        # world 不存在则清理键
                        try:
                            for p in players:
                                rec = crud.get_player_by_name(db, p)
                                if rec:
                                    crud.remove_server_from_player_play_time(db, rec, server_name)
                        except Exception:
                            pass
                        # 边界对齐也推进，避免后续离开时过大尾差
                        SERVER_LAST_BOUNDARY[server_name] = float(now)
                        continue
                    # 计算本轮分钟边界：以本次循环时刻为边界（不与整点对齐，避免漂移造成尾差异常）
                    boundary_now = float(now)
                    boundary_prev = SERVER_LAST_BOUNDARY.get(server_name, boundary_now - 60.0)
                    # 对上一完整周期 [boundary_prev, boundary_now) 进行累加：仅对整分钟内全程在线的玩家
                    for p in list(players):
                        try:
                            rec = crud.get_player_by_name(db, p)
                            if not rec or rec.player_name is None:
                                continue
                            try:
                                pt = json.loads(rec.play_time or '{}')
                            except Exception:
                                pt = {}
                            if server_name not in pt:
                                continue
                            joined = (JOINED_TIME.get(server_name, {}) or {}).get(p)
                            if joined is None:
                                # 未记录加入时间，跳过
                                continue
                            if float(joined) <= boundary_prev:
                                crud.add_player_play_time_ticks(db, rec, server_name, 1200)
                                logger.debug(f"[MCDR-WS] 为玩家 {p} 在服务器 {server_name} 累计了 1200 ticks（完整分钟）")
                                increments_total += 1
                                per_server[server_name] = per_server.get(server_name, 0) + 1
                        except Exception:
                            continue
                    # 推进服务器分钟边界
                    SERVER_LAST_BOUNDARY[server_name] = boundary_now
            logger.debug(
                f"[MCDR-WS] 本轮时长结算完成 | 活跃服务器={len(PLAYERS_BY_SERVER)} 累计次数={increments_total} 明细={per_server}"
            )
        except asyncio.CancelledError:
            break
        except Exception:
            try:
                logger.exception("[MCDR-WS] playtime_tick_loop 异常")
            except Exception:
                pass


def _ensure_playtime_task():
    global _PLAYTIME_TASK
    if _PLAYTIME_TASK is None or _PLAYTIME_TASK.done():
        loop = asyncio.get_event_loop()
        _PLAYTIME_TASK = loop.create_task(_playtime_tick_loop())


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
        if event in ["mcdr.mcdr_start", "mcdr.server_start_pre", "mcdr.server_start"]:
            mcdr_manager.set_external_status(server_id, "pending", None)
            try:
                if event == "mcdr.server_start_pre":
                    logger.info(f"[MCDR-WS] 服务器正在启动 | server={server_name} id={server_id} event={event}")
            except Exception:
                pass
        elif event == "mcdr.server_startup":
            mcdr_manager.set_external_status(server_id, "running", None)
            # 启动成功后清理非零返回码
            mcdr_manager.return_code.pop(server_id, None)
            try:
                logger.info(f"[MCDR-WS] 服务器已启动 | server={server_name} id={server_id}")
            except Exception:
                pass
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
            try:
                logger.info(f"[MCDR-WS] 服务器已停止 | server={server_name} id={server_id} return_code={rc}")
            except Exception:
                pass
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


async def broadcast_chat_to_plugins(*, level: str, group_id: Optional[int], user: str, message: str, source: str = "web", avatar: Optional[str] = None, sender_qq: Optional[str] = None, message_id: Optional[Any] = None) -> None:
    data = {
        "level": level,
        "message": message,
        "user": user,
        "avatar": avatar,
        "group_id": group_id,
        "source": source,
        "sender_qq": sender_qq,
        "message_id": message_id,
    }
    payload = json.dumps({"event": "chat.message", "ts": "-", "data": data}, ensure_ascii=False)

    target_servers: Set[str] = set()
    if level == "ALERT" or group_id is None:
        for _, bound in list(_PLUGIN_CLIENTS.items()):
            if bound:
                target_servers.add(bound)
    else:
        try:
            with get_db_context() as db:
                rec = crud.get_server_link_group_by_id(db, int(group_id))
                if rec:
                    import json as _json
                    try:
                        ids = list(map(int, _json.loads(rec.server_ids or "[]")))
                    except Exception:
                        ids = []
                    for sid in ids:
                        srv = crud.get_server_by_id(db, sid)
                        if not srv:
                            continue
                        try:
                            name = Path(srv.path).name
                        except Exception:
                            name = None
                        if name:
                            target_servers.add(name)
        except Exception:
            target_servers = set()

    dead: List[WebSocket] = []
    for ws, bound_name in list(_PLUGIN_CLIENTS.items()):
        try:
            if level == "ALERT" or bound_name in target_servers:
                await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _PLUGIN_CLIENTS.pop(ws, None)


onebot.register_plugin_broadcaster(broadcast_chat_to_plugins)


async def _handle_qqlist_request(server_name: str) -> None:
    """处理来自插件的 !!qqlist 请求，返回QQ群成员列表"""
    try:
        # 找到该服务器对应的组
        with get_db_context() as db:
            target = None
            for s in crud.get_all_servers(db):
                try:
                    if Path(s.path).name == server_name:
                        target = s
                        break
                except Exception:
                    continue
            if not target:
                return
            
            # 获取该服务器所属的所有组
            group_ids = []
            for g in crud.list_server_link_groups(db):
                try:
                    ids = list(map(int, json.loads(g.server_ids or '[]')))
                except Exception:
                    ids = []
                if target.id in ids:
                    group_ids.append(g.id)
        
        if not group_ids:
            return
        
        # 获取所有组的QQ群成员列表（合并去重）
        all_speakers: Dict[str, Dict[str, Any]] = {}
        for gid in group_ids:
            speakers = onebot.get_qq_group_speakers(gid)
            for s in speakers:
                qq = s.get("qq")
                if qq and qq not in all_speakers:
                    all_speakers[qq] = s
                elif qq and s.get("last_time", 0) > all_speakers.get(qq, {}).get("last_time", 0):
                    all_speakers[qq] = s
        
        # 转换为列表并排序
        speakers_list = list(all_speakers.values())
        speakers_list.sort(key=lambda x: x.get("last_time", 0), reverse=True)
        
        # 发送响应给请求的服务器
        response = {
            "event": "qqlist.response",
            "ts": "-",
            "data": {
                "server": server_name,
                "speakers": speakers_list,
            }
        }
        payload_text = json.dumps(response, ensure_ascii=False)
        
        for ws, bound in list(_PLUGIN_CLIENTS.items()):
            try:
                if bound == server_name:
                    await ws.send_text(payload_text)
            except Exception:
                pass
    except Exception:
        logger.opt(exception=True).warning("[MCDR-WS] 处理 qqlist 请求失败")


async def _handle_single(payload: Dict[str, Any]):
    """处理单条 mcdr 事件，广播至 Socket.IO"""
    if not isinstance(payload, dict):
        return
    event = payload.get("event")
    
    # 处理 !!qqlist 请求事件
    if event == "mcdr.qqlist_request":
        try:
            data = payload.get("data", {})
            server_name = data.get("server")
            if server_name:
                await _handle_qqlist_request(server_name)
        except Exception:
            pass
        return
    
    if not isinstance(event, str) or not event.startswith("mcdr."):
        # 不识别的事件格式，忽略
        return
    # 记录日志：接收到的单条事件
    try:
        logger.debug(f"[MCDR-WS] 收到事件: {event}")
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
                with get_db_context() as db:
                    # 将该消息落库到所有该服务器所在分组
                    groups = _get_groups_for_server_name(db, src_server)
                    try:
                        logger.debug(f"[MCDR-WS] 收到用户消息 | server={src_server} player={player} len={len(content)} 目标组={groups}")
                    except Exception:
                        pass
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
                    saved = 0
                    emitted = 0
                    for g in crud.list_server_link_groups(db):
                        import json as _json
                        try:
                            ids = list(map(int, _json.loads(g.server_ids or '[]')))
                        except Exception:
                            ids = []
                        # 将该 server 属于的组写入
                        target = None
                        for s in crud.get_all_servers(db):
                            try:
                                if Path(s.path).name == src_server and s.id in ids:
                                    target = g
                                    break
                            except Exception:
                                continue
                        if target is None:
                            continue
                        row = models.ChatMessage(
                            group_id=g.id,
                            level="NORMAL",
                            source="game",
                            content=content,
                            server_name=src_server,
                            player_name=str(player),
                        )
                        row = crud.create_chat_message(db, row)
                        saved += 1
                        # 使用 Pydantic 模型进行 JSON 序列化，避免 datetime 直接传递导致的序列化问题
                        out_model = schemas.ChatMessageOut.model_validate(row)
                        try:
                            if getattr(row, 'created_at', None):
                                out_model = out_model.model_copy(update={"created_at": to_local_dt(row.created_at)})
                        except Exception:
                            pass
                        out = out_model.model_dump(mode='json')
                        await sio.emit("chat_message", out)
                        emitted += 1
                    try:
                        logger.debug(f"[MCDR-WS] 用户消息已处理 | server={src_server} save={saved} emit={emitted}")
                    except Exception:
                        pass
                await onebot.handle_prefixed_game_chat(str(src_server), str(player), content)
        except Exception:
            pass

    # 7) 玩家在线表维护与游玩时长累计：基于 player_joined/left & server_startup/stop
    try:
        from backend.services import player_manager as _pm
        _ensure_playtime_task()
        if event == "mcdr.bot_joined" and isinstance(data, dict):
            # 为机器人玩家标记is_bot
            server_name = str(data.get("server") or "")
            player = str(data.get("player") or "")
            if server_name and player:
                with get_db_context() as db:
                    crud.set_player_is_bot(db, player, True)
        if event in {"mcdr.player_joined", "mcdr.player_left", "mcdr.player_position"} and isinstance(data, dict):
            server_name = str(data.get("server") or "")
            if server_name and _is_proxy_server(server_name):
                try:
                    logger.debug(f"[MCDR-WS] 代理服务器事件已忽略 | server={server_name} event={event}")
                except Exception:
                    pass
                return

        if event == "mcdr.player_position" and isinstance(data, dict):
            server_name = str(data.get("server") or "")
            positions = data.get("positions") or []
            server_id = data.get("server_id")
            if not server_id and server_name:
                try:
                    with get_db_context() as db:
                        for s in crud.get_all_servers(db):
                            if Path(s.path).name == server_name:
                                server_id = s.id
                                break
                except Exception:
                    server_id = None
            ts_now = datetime.datetime.now(datetime.timezone.utc)
            lens = 0
            if server_id:
                try:
                    with get_db_context() as db:
                        for item in positions:
                            try:
                                player_name = item.get("player")
                                pos = item.get("position") or {}
                                x = pos.get("x")
                                y = pos.get("y")
                                z = pos.get("z")
                                dim = item.get("dimension")
                                if player_name is None or x is None or y is None or z is None:
                                    continue
                                p = crud.get_player_by_name(db, str(player_name))
                                if not p:
                                    continue
                                # 去重：若与该服最后一条位置相同则跳过
                                last_pos = (
                                    db.query(models.PlayerPosition)
                                    .filter(
                                        models.PlayerPosition.player_id == p.id,
                                        models.PlayerPosition.server_id == int(server_id),
                                    )
                                    .order_by(models.PlayerPosition.ts.desc())
                                    .first()
                                )
                                same_as_last = (
                                    last_pos
                                    and last_pos.x == float(x)
                                    and last_pos.y == float(y)
                                    and last_pos.z == float(z)
                                    and (str(dim) if dim is not None else None) == last_pos.dim
                                )
                                if same_as_last:
                                    continue
                                lens += 1
                                crud.add_player_position(
                                    db,
                                    p.id,
                                    int(server_id),
                                    ts_now,
                                    float(x),
                                    float(y),
                                    float(z),
                                    str(dim) if dim is not None else None,
                                )
                            except Exception:
                                continue
                except Exception:
                    logger.exception("[MCDR-WS] 位置上报入库失败")
            try:
                if lens:
                    logger.debug(f"[MCDR-WS] 收到位置上报 | server={server_name} id={server_id} count={lens} reason={data.get('reason')}")
            except Exception as e:
                logger.error(f"[MCDR-WS] 位置上报日志记录失败: {e}")
                pass
            return

        if event == "mcdr.player_joined" and isinstance(data, dict):
            server_name = str(data.get("server") or "")
            player = str(data.get("player") or "")
            if server_name and player:
                PLAYERS_BY_SERVER.setdefault(server_name, set()).add(player)
                await _emit_presence_for_server(server_name)
                try:
                    online_cnt = len(PLAYERS_BY_SERVER.get(server_name, set()))
                    logger.info(f"[MCDR-WS] 玩家加入 | server={server_name} player={player} 在线={online_cnt}")
                except Exception:
                    pass
                # 记录玩家加入的时间，用于满60秒判断
                try:
                    JOINED_TIME.setdefault(server_name, {})[player] = time.time()
                except Exception:
                    pass
                # 若数据库不存在该玩家记录，则补齐 UUID 并刷新玩家名（避免每次加入都全量扫描）
                try:
                    need_sync = False
                    with get_db_context() as db:
                        need_sync = crud.get_player_by_name(db, player) is None
                        need_identify_online = crud.get_player_by_name(db, player) is not None and crud.get_player_by_name(db, player).is_offline is False
                    if need_sync:
                        async with _PLAYER_SYNC_LOCK:
                            stats = _pm.ensure_players_from_worlds()
                            try:
                                await _pm.refresh_missing_official_names()
                            except Exception:
                                pass
                            if (stats or {}).get('added'):
                                logger.info(
                                    f"[MCDR-WS] 新增玩家UUID记录 | 新增={stats.get('added')} 总计扫描={stats.get('found')}"
                                )
                                try:
                                    _pm.ensure_play_time_if_empty()
                                except Exception:
                                    pass
                    elif need_identify_online:
                        async with _PLAYER_SYNC_LOCK:
                            try:
                                uuid = await get_uuid_by_name(player)
                                await _pm.refresh_offline_names([uuid] if uuid is not None else None)
                            except Exception:
                                pass
                except Exception:
                    pass
                # 记录会话开始 (Session)
                try:
                    with get_db_context() as db:
                        rec = crud.get_player_by_name(db, player)
                        if rec and rec.uuid:
                            server_path = _get_server_path_by_name(server_name)
                            if server_path:
                                srv = crud.get_server_by_path(db, server_path)
                                if srv:
                                    crud.create_player_session(db, srv.id, rec.uuid)
                except Exception:
                    pass
                try:
                    await onebot.handle_player_join(server_name, player)
                except Exception:
                    pass
        elif event == "mcdr.player_left" and isinstance(data, dict):
            server_name = str(data.get("server") or "")
            player = str(data.get("player") or "")
            if server_name:
                s = PLAYERS_BY_SERVER.setdefault(server_name, set())
                if player:
                    s.discard(player)
                await _emit_presence_for_server(server_name)
                try:
                    online_cnt = len(PLAYERS_BY_SERVER.get(server_name, set()))
                    logger.info(f"[MCDR-WS] 玩家离开 | server={server_name} player={player} 在线={online_cnt}")
                except Exception:
                    pass
                # 同步补齐可能新增的 UUID（例如玩家首次出现后立即离开）
                try:
                    stats = _pm.ensure_players_from_worlds()
                    if (stats or {}).get('added'):
                        logger.info(f"[MCDR-WS] 新增玩家UUID记录 | 新增={stats.get('added')} 总计扫描={stats.get('found')}")
                        try:
                            _pm.ensure_play_time_if_empty()
                        except Exception:
                            pass
                except Exception:
                    pass
                # 刷新该玩家最后一次“整分钟边界”后的尾差（秒*20）
                try:
                    now = time.time()
                    boundary = SERVER_LAST_BOUNDARY.get(server_name, float(now))
                    joined = (JOINED_TIME.get(server_name, {}) or {}).get(player)
                    base = max(float(joined) if joined is not None else now, float(boundary))
                    with get_db_context() as db:
                        rec = crud.get_player_by_name(db, player)
                        if rec and rec.player_name is not None:
                            sp = _get_server_path_by_name(server_name)
                            world_exists = bool(sp and (Path(sp) / 'server' / 'world').exists())
                            try:
                                pt = json.loads(rec.play_time or '{}')
                            except Exception:
                                pt = {}
                            has_key = server_name in pt
                            if world_exists and has_key:
                                delta_ticks = int(max(0.0, (now - base) * 20.0))
                                if delta_ticks > 0:
                                    crud.add_player_play_time_ticks(db, rec, server_name, delta_ticks)
                                    logger.debug(f"[MCDR-WS] 为玩家 {player} 在服务器 {server_name} 累计了 {delta_ticks} ticks（离开尾差）")
                            else:
                                # 不满足累计条件：删除该 server 键
                                crud.remove_server_from_player_play_time(db, rec, server_name)
                    # 清理加入时间与旧的 per-player last 映射
                    try:
                        LAST_ADDED_TIME.get(server_name, {}).pop(player, None)
                    except Exception:
                        pass
                    try:
                        JOINED_TIME.get(server_name, {}).pop(player, None)
                    except Exception:
                        pass
                except Exception:
                    pass
                # 记录会话结束 (Session)
                try:
                    with get_db_context() as db:
                        rec = crud.get_player_by_name(db, player)
                        if rec and rec.uuid:
                            server_path = _get_server_path_by_name(server_name)
                            if server_path:
                                srv = crud.get_server_by_path(db, server_path)
                                if srv:
                                    crud.close_player_session(db, srv.id, rec.uuid)
                except Exception:
                    pass
                try:
                    await onebot.handle_player_leave(server_name, player)
                except Exception:
                    pass
        elif event in ("mcdr.server_startup", "mcdr.server_stop") and isinstance(data, dict):
            server_name = str(data.get("server") or "")
            if server_name:
                if event == "mcdr.server_startup":
                    # 启动时清空（重新学习）
                    PLAYERS_BY_SERVER[server_name] = set()
                    JOINED_TIME[server_name] = {}
                    SERVER_LAST_BOUNDARY[server_name] = float(time.time())
                    try:
                        await onebot.handle_server_reset(server_name)
                    except Exception:
                        pass
                else:
                    # 停止时清空
                    # 在清空前对仍在线玩家进行尾差累计（以分钟边界为基准）
                    try:
                        now = time.time()
                        boundary = SERVER_LAST_BOUNDARY.get(server_name, float(now))
                        joined_map = JOINED_TIME.get(server_name) or {}
                        with get_db_context() as db:
                            sp = _get_server_path_by_name(server_name)
                            world_exists = bool(sp and (Path(sp) / 'server' / 'world').exists())
                            for player, joined in list(joined_map.items()):
                                try:
                                    rec = crud.get_player_by_name(db, player)
                                    if not rec or rec.player_name is None:
                                        continue
                                    try:
                                        pt = json.loads(rec.play_time or '{}')
                                    except Exception:
                                        pt = {}
                                    if world_exists and server_name in pt:
                                        base = max(float(joined), float(boundary))
                                        delta_ticks = int(max(0.0, (now - base) * 20.0))
                                        if delta_ticks > 0:
                                            crud.add_player_play_time_ticks(db, rec, server_name, delta_ticks)
                                    else:
                                        crud.remove_server_from_player_play_time(db, rec, server_name)
                                except Exception:
                                    continue
                    except Exception:
                        pass
                    try:
                        await onebot.handle_server_reset(server_name)
                    except Exception:
                        pass
                    # 最后清空在线与时间表
                    PLAYERS_BY_SERVER.pop(server_name, None)
                    JOINED_TIME[server_name] = {}
                await _emit_presence_for_server(server_name)
                # 推进服务器边界，防止后续尾差偏大
                SERVER_LAST_BOUNDARY[server_name] = float(time.time())
                # 清理旧映射
                LAST_ADDED_TIME[server_name] = {}
                JOINED_TIME[server_name] = {}
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
        "mcdr.bot_joined",
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
    forwarded = 0
    for ws, bound_name in list(_PLUGIN_CLIENTS.items()):
        try:
            if not bound_name or bound_name == src_server:
                continue
            with get_db_context() as db:
                dst_groups = _get_groups_for_server_name(db, bound_name)
            if any(g in src_groups for g in dst_groups):
                await ws.send_text(text)
                forwarded += 1
        except Exception:
            dead.append(ws)
    for ws in dead:
        _PLUGIN_CLIENTS.pop(ws, None)
    try:
        if forwarded:
            logger.debug(f"[MCDR-WS] 事件转发 | event={event} 源服务器={src_server} 转发客户端数={forwarded}")
    except Exception:
        pass


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
            payload = _safe_json_loads(text)
            if payload is None:
                continue
            # 批量 or 单条
            if isinstance(payload, dict) and payload.get("batch") is True:
                items: List[Dict[str, Any]] = payload.get("items", []) or []
                try:
                    if items > 1:
                        logger.debug(f"[MCDR-WS] 批量消息，数量={len(items)}")
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
    try:
        await onebot.refresh_bindings()
    except Exception:
        pass
    server_id: Optional[int] = None
    try:
        with get_db_context() as db:
            for s in crud.get_all_servers(db):
                if Path(s.path).name == server_name:
                    server_id = s.id
                    break
    except Exception:
        server_id = None
    dead: List[WebSocket] = []
    msg = json.dumps({
        "event": "sl.group_update",
        "ts": "-",
        "data": {"server": server_name, "server_groups": group_names, "server_id": server_id}
    }, ensure_ascii=False)
    sent = 0
    for ws, bound in list(_PLUGIN_CLIENTS.items()):
        try:
            if bound == server_name:
                await ws.send_text(msg)
                sent += 1
        except Exception:
            dead.append(ws)
    for ws in dead:
        _PLUGIN_CLIENTS.pop(ws, None)
    try:
        logger.debug(f"[MCDR-WS] 推送组更新 | server={server_name} 组={group_names} 客户端数={sent}")
    except Exception:
        pass

async def broadcast_save_all(server_name: str):
    server_id: Optional[int] = None
    try:
        with get_db_context() as db:
            for s in crud.get_all_servers(db):
                if Path(s.path).name == server_name:
                    server_id = s.id
                    break
    except Exception:
        server_id = None
    msg = json.dumps({
        "event": "sl.save_all",
        "ts": "-",
        "data": {"server": server_name, "server_id": server_id}
    }, ensure_ascii=False)
    for ws, bound in list(_PLUGIN_CLIENTS.items()):
        try:
            if bound == server_name:
                await ws.send_text(msg)
        except Exception:
            _PLUGIN_CLIENTS.pop(ws, None)
    try:
        logger.debug(f"[MCDR-WS] 推送保存世界请求 | server={server_name}")
    except Exception:
        pass
mcdr_manager.save_all_method = broadcast_save_all # type: ignore

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
        from backend.core.ws import CHAT_USERS  # type: ignore
        for gid in gid_list:
            web_users = list((CHAT_USERS.get(gid) or {}).values())
            players = get_group_players(gid)
            await sio.emit('chat_presence', { 'group_id': gid, 'web_users': web_users, 'players': players }, room=f'chat_group_{gid}')
        try:
            logger.debug(f"[MCDR-WS] 广播在线列表 | server={server_name} 目标组={gid_list}")
        except Exception:
            pass
    except Exception:
        pass
