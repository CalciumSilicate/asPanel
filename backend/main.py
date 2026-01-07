# backend/main.py

import time
import sys
import asyncio
import json
import secrets
import socketio
from sqlalchemy import text
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    http_exception_handler as fastapi_http_exception_handler,
    request_validation_exception_handler as fastapi_validation_exception_handler,
)
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core import models, crud
from backend.core.config import get_config
from backend.core.database import engine, SessionLocal
from backend.core.constants import (
    ALLOWED_ORIGINS, AVATAR_STORAGE_PATH, AVATAR_URL_PREFIX, ARCHIVE_STORAGE_PATH, ARCHIVE_URL_PREFIX,
    UVICORN_HOST, UVICORN_PORT, UVICORN_LOG_LEVEL
)
from backend.core.security import get_password_hash
from backend.routers import users, system, archives, servers, versions, plugins, tools
from backend.routers import players as players_router
from backend.routers import stats as stats_router
from backend.routers import settings as settings_router
from backend.routers import mods as mods_router
from backend.routers import configuration as configuration_router
from backend.services.ws import router as ws_router
from backend.services import onebot
from backend.routers.system import cpu_sampler
from backend.services import stats_service
from backend.core.dependencies import task_manager
from backend.core.api import *
from backend.core.ws import sio
from backend.core.logger import logger
from backend.core.schemas import ServerCoreConfig
from backend.core.dependencies import mcdr_manager

models.Base.metadata.create_all(bind=engine)

# 数据库迁移：添加缺失的列
def _migrate_database():
    """检查并添加缺失的数据库列"""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    
    # 检查 users 表的 token_version 列
    if 'users' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('users')]
        if 'token_version' not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 0"))
                conn.commit()
                logger.info("数据库迁移：已添加 users.token_version 列")

_migrate_database()


def _ensure_default_admin():
    """检查是否有用户，没有则创建默认管理员并提示"""
    with SessionLocal() as db:
        user_count = db.query(models.User).count()
        if user_count > 0:
            return  # 已有用户，跳过
        
        # 生成随机密码
        default_password = secrets.token_urlsafe(12)
        default_username = "admin"
        
        # 创建管理员用户
        hashed_password = get_password_hash(default_password)
        admin_user = models.User(
            username=default_username,
            hashed_password=hashed_password,
            role="OWNER",
            email="",
            qq="",
        )
        db.add(admin_user)
        db.commit()
        
        # 打印提示信息
        print()
        print("=" * 60)
        print("  默认管理员账号已创建")
        print("=" * 60)
        print()
        print(f"  用户名: {default_username}")
        print(f"  密码:   {default_password}")
        print()
        print("  请登录后立即修改密码！")
        print("=" * 60)
        print()


_ensure_default_admin()


app = FastAPI(title="AS Panel API")


# ------------------------
# 全局异常处理与兜底日志
# ------------------------
def _global_excepthook(exc_type, exc, tb):
    """捕获进程级未处理异常，通过 logger 输出。

    注意：KeyboardInterrupt 直接透传，避免影响正常中断行为。
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # 还原默认行为（保持 Ctrl+C 语义）
        return
    # 使用 loguru 的 opt(exception=...) 输出完整堆栈
    logger.opt(exception=(exc_type, exc, tb)).error("未处理的顶层异常")


sys.excepthook = _global_excepthook


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP 异常：记录为 warning，并复用 FastAPI 默认处理逻辑。"""
    logger.warning(
        f"HTTP异常 {exc.status_code} | {request.method} {request.url.path} | detail={getattr(exc, 'detail', '')}"
    )
    return await fastapi_http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求校验异常：记录为 warning，并复用 FastAPI 默认处理逻辑。"""
    logger.warning(
        f"请求校验异常 | {request.method} {request.url.path} | errors={exc.errors()}"
    )
    return await fastapi_validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """兜底异常：记录为 error，返回 500。"""
    # 显式附带异常对象，确保记录完整堆栈
    logger.opt(exception=exc).error(
        f"未捕获异常 | {request.method} {request.url.path}"
    )
    return JSONResponse(status_code=500, content={"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal Server Error"}})


@app.middleware("http")
async def request_timer_middleware(request: Request, call_next):
    """
    为每个 HTTP 请求计时，并通过 logger.info 输出，同时把耗时写入响应头：
    X-Process-Time: {秒}s
    """
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = time.perf_counter() - start
        # 给响应头加上耗时（注意：需要在 return 之前设置；用 finally 时可在 response 已创建时设置）
        try:
            # response 可能在异常路径上为 None，这里防守式处理
            if "response" in locals() and response is not None:
                response.headers["X-Process-Time"] = f"{elapsed:.6f}s"
                response.headers["Server-Timing"] = f"app;dur={elapsed * 1000:.2f}"
        except Exception:
            # 不让计时器影响主流程
            pass

        # 统一日志输出（方法、路径、状态码、用时）
        status = getattr(locals().get("response", None), "status_code", "-")
        log_msg = "[{host}] {method} {path} -> {status} | {elapsed:.2f} ms".format(
            host=request.client.host if request.client else "-",
            method=request.method,
            path=request.url.path,
            status=status,
            elapsed=elapsed * 1000,
        )
        logger.info(log_msg)


_allow_credentials = get_config().cors.allow_credentials
if "*" in ALLOWED_ORIGINS:
    _allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(ARCHIVE_URL_PREFIX.rstrip('/'), StaticFiles(directory=ARCHIVE_STORAGE_PATH), name="archives")
app.mount(AVATAR_URL_PREFIX.rstrip('/'), StaticFiles(directory=AVATAR_STORAGE_PATH), name="avatars")

app.include_router(users.router)
app.include_router(servers.router)
app.include_router(archives.router)
app.include_router(system.router)
app.include_router(versions.router)
app.include_router(plugins.router)
app.include_router(tools.router)
app.include_router(mods_router.router)
app.include_router(configuration_router.router)
app.include_router(ws_router)
app.include_router(onebot.router)
app.include_router(settings_router.router)
app.include_router(players_router.router)
app.include_router(stats_router.router)


async def warmup_cache():
    logger.debug(f"后台任务：开始获取版本列表...")
    try:
        # 这里依然可以使用 gather 来加速
        await asyncio.gather(
            get_minecraft_versions_raw(),
            get_velocity_versions_raw(),
            get_fabric_game_version_list(),
            get_forge_game_version_list(),
            get_mcdr_plugins_catalogue()
        )
        logger.info("后台任务：版本列表全部更新完毕")
    except Exception as e:
        logger.error(f"后台预热失败: {e}")


async def _auto_start_servers_on_boot():
    """启动 ASPanel 时自动启动标记了 core_config.auto_start 的服务器。"""
    # 给其他启动初始化任务一点时间（例如 OneBot / ws / task broadcaster）
    await asyncio.sleep(1.0)
    try:
        with SessionLocal() as db:
            servers = crud.get_all_servers(db)
    except Exception as e:
        logger.warning(f"自动启动：读取服务器列表失败：{e}")
        return

    targets = []
    for s in servers:
        try:
            if hasattr(ServerCoreConfig, "model_validate_json"):
                cfg = ServerCoreConfig.model_validate_json(s.core_config)  # type: ignore[attr-defined]
            else:
                cfg = ServerCoreConfig.model_validate(json.loads(s.core_config))
        except Exception:
            cfg = ServerCoreConfig()
        if bool(getattr(cfg, "auto_start", False)):
            targets.append(s)

    if not targets:
        logger.info("自动启动：没有开启 auto_start 的服务器")
        return

    started, skipped, failed = 0, 0, 0
    for s in targets:
        try:
            st, _ = await mcdr_manager.get_status(int(s.id), str(s.path))
            if st in ("running", "pending", "new_setup"):
                skipped += 1
                continue
            ok, msg = await mcdr_manager.start(s)
            if ok:
                started += 1
                logger.info(f"自动启动：已启动 server_id={s.id} name={getattr(s, 'name', '')}")
            else:
                failed += 1
                logger.warning(f"自动启动：启动失败 server_id={s.id} | {msg}")
        except Exception as e:
            failed += 1
            logger.warning(f"自动启动：启动异常 server_id={getattr(s, 'id', None)}：{e}")
        # 避免同时拉起过多进程造成瞬时 IO/CPU 峰值
        await asyncio.sleep(0.3)

    logger.info(f"自动启动完成：started={started} skipped={skipped} failed={failed} total={len(targets)}")


@app.on_event("startup")
async def startup_event():
    logger.warning(f"服务器启动中")
    await task_manager.register_coroutine("cpu_sampler", cpu_sampler())
    await task_manager.register_coroutine("warmup_cache", warmup_cache())
    try:
        await onebot.startup_sync()
    except Exception:
        logger.warning("OneBot 绑定初始化失败", exc_info=True)
    # 启动时收集/补全玩家 UUID 列表
    try:
        from backend.services import player_manager as _pm
        _pm.ensure_players_from_worlds()
        await _pm.refresh_missing_official_names()
        _pm.ensure_play_time_if_empty()
    except Exception:
        pass
    # 设置 asyncio 事件循环异常处理，捕获后台任务未处理错误
    loop = asyncio.get_running_loop()

    def _asyncio_exception_handler(loop, context):
        msg = context.get("message", "")
        exc = context.get("exception")
        if exc is not None:
            logger.opt(exception=exc).error(f"异步任务未处理异常 | {msg}")
        else:
            logger.error(f"异步任务异常 | {msg} | context={context}")

    loop.set_exception_handler(_asyncio_exception_handler)
    logger.success("服务器启动完成")
    # 启动统计入库定时任务（每逢 10 分钟整点）
    try:
        await task_manager.register_coroutine("stats_ingest", stats_service.ingest_scheduler_loop())
        logger.info("统计入库后台任务已启动（10min 对齐）")
    except Exception as e:
        logger.warning(f"启动统计入库任务失败：{e}")

    # TaskManager：Socket.IO 实时任务推送
    try:
        task_manager.attach_socketio(sio)
        task_manager.start_broadcaster()
        logger.info("TaskManager 实时任务推送已启动")
    except Exception as e:
        logger.warning(f"TaskManager 实时推送启动失败：{e}")

    # 自动启动：按 core_config.auto_start 拉起服务器
    try:
        await task_manager.register_coroutine("auto_start_servers", _auto_start_servers_on_boot())
        logger.info("自动启动后台任务已创建")
    except Exception as e:
        logger.warning(f"创建自动启动任务失败：{e}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.warning("服务器关闭中...")
    await task_manager.cancel_all_coroutines()
    logger.success("服务器已关闭")


main_asgi_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path='/ws/socket.io')


@app.get("/api/health")
def read_root():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:main_asgi_app",
        host=UVICORN_HOST,
        port=UVICORN_PORT,
        log_level=UVICORN_LOG_LEVEL
    )
