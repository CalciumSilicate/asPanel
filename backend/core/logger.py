# backend/core/logger.py

import sys
from loguru import logger

from backend.core.constants import LOG_STORAGE, LOG_LEVEL, LOG_FILE_LEVEL

logger.remove()

log_path = LOG_STORAGE
log_path.mkdir(parents=True, exist_ok=True)
log_file_path = log_path / "app_{time:YYYY-MM-DD}.log"

logger.add(
    sys.stderr,
    level=LOG_LEVEL,
    colorize=True,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level}</level> | "
        "<level>{message}</level>"
    )
)

logger.add(
    log_file_path,
    level=LOG_FILE_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    encoding="utf-8",
    rotation="1 day",
    retention="7 days",
    compression="zip",
    enqueue=True  # 多进程安全
)

__all__ = ["logger"]
