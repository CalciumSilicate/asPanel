# backend/core/config.py
"""
配置加载模块
首次启动时生成 config.yaml 并退出，提示用户编辑
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8013, description="监听端口")
    log_level: str = Field(default="warning", description="uvicorn 日志级别")


class DatabaseConfig(BaseModel):
    """数据库配置"""
    url: str = Field(
        default="sqlite:///./storages/asPanel.db",
        description="数据库连接字符串"
    )


class StorageConfig(BaseModel):
    """存储配置"""
    root: str = Field(default="storages", description="存储根目录")


class CorsConfig(BaseModel):
    """CORS 配置"""
    origins: List[str] = Field(default=["*"], description="允许的源列表")
    allow_credentials: bool = Field(default=False, description="是否允许携带凭证")


class LogConfig(BaseModel):
    """日志配置"""
    level: str = Field(default="DEBUG", description="控制台日志级别")
    file_level: str = Field(default="INFO", description="文件日志级别")


class AppConfig(BaseModel):
    """应用总配置"""
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)
    log: LogConfig = Field(default_factory=LogConfig)


# 配置文件模板内容
CONFIG_TEMPLATE = """# ASPanel 配置文件
# 请根据需要修改以下配置，然后重新启动服务

# AS Panel 日志配置
log:
  level: INFO         # 控制台日志级别: DEBUG, INFO, WARNING, ERROR
  file_level: INFO     # 文件日志级别

# 服务器配置
server:
  host: 0.0.0.0        # 监听地址
  port: 8013           # 监听端口
  log_level: warning   # uvicorn 日志级别: debug, info, warning, error

# 数据库配置
database:
  # SQLite 连接字符串，相对于项目根目录
  # 如需使用其他数据库，修改为对应的连接字符串
  # 例如 PostgreSQL: postgresql://user:pass@localhost/dbname
  url: sqlite:///./storages/asPanel.db

# 存储配置
storage:
  # 存储根目录，所有生成的文件都会放在这里
  root: storages

# CORS 跨域配置
cors:
  # 允许的源列表，["*"] 表示允许所有
  origins:
    - "*"

"""


def _get_base_dir() -> Path:
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent.parent


def _get_config_path() -> Path:
    """获取配置文件路径"""
    return _get_base_dir() / "config.yaml"


def _find_config_file() -> Optional[Path]:
    """查找配置文件"""
    base_dir = _get_base_dir()
    
    # 按优先级查找配置文件
    candidates = [
        base_dir / "config.yaml",
        base_dir / "config.yml",
    ]
    
    for path in candidates:
        if path and path.exists() and path.is_file():
            return path
    
    return None


def _generate_config_and_exit():
    """生成配置文件并退出"""
    config_path = _get_config_path()
    
    print("=" * 60)
    print("  ASPanel 首次启动")
    print("=" * 60)
    print()
    print(f"正在生成配置文件: {config_path}")
    
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(CONFIG_TEMPLATE)
        print()
        print("配置文件已生成！")
        print()
        print("请编辑配置文件后重新启动服务：")
        print(f"  1. 编辑 {config_path}")
        print("  2. 根据需要修改配置项")
        print("  3. 重新运行启动命令")
        print()
        print("=" * 60)
    except Exception as e:
        print(f"生成配置文件失败: {e}")
    
    sys.exit(0)


def load_config() -> AppConfig:
    """加载配置文件，未找到则生成并退出"""
    config_file = _find_config_file()
    
    if config_file is None:
        # 没有配置文件，生成并退出
        _generate_config_and_exit()
        # 这行不会执行，但为了类型检查
        raise SystemExit(0)
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}
        
        return AppConfig(**raw_config)
    except Exception as e:
        print(f"[Error] 加载配置文件失败 {config_file}: {e}")
        print("[Error] 请检查配置文件格式是否正确")
        sys.exit(1)


# 全局配置实例（单例）
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> AppConfig:
    """重新加载配置"""
    global _config
    _config = load_config()
    return _config
