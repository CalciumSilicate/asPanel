# main.py
import asyncio

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
import socketio

from backend import models
from backend.database import engine
from backend.core.config import (
    ALLOWED_ORIGINS, AVATAR_STORAGE_PATH, AVATAR_URL_PREFIX, ARCHIVE_STORAGE_PATH, ARCHIVE_URL_PREFIX
)

from backend.routers import users, system, archives, servers, versions, plugins, tools
from backend.routers import players as players_router
from backend.routers import settings as settings_router
from backend.routers import mods as mods_router
from backend.routers import configuration as configuration_router
from backend.services.ws import router as ws_router
from backend.routers.system import cpu_sampler
from backend.core.api import *
from backend.ws import sio
import time
from backend.logger import logger
import sys

models.Base.metadata.create_all(bind=engine)
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
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


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


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
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
app.include_router(settings_router.router)
app.include_router(players_router.router)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cpu_sampler())
    await get_minecraft_versions_raw()
    await get_velocity_versions_raw()
    await get_fabric_game_version_list()
    await get_mcdr_plugins_catalogue()
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

main_asgi_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path='/ws/socket.io')


@app.get("/api/health")
def read_root():
    return {"status": "ok"}
