from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLAlchemyEnum, Text, Boolean, PrimaryKeyConstraint, \
    UniqueConstraint, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import json
import enum

from backend import schemas
from backend.core.constants import DEFAULT_CORE_CONFIG, DEFAULT_USER_ROLE

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, nullable=False, default=DEFAULT_USER_ROLE)
    avatar_url = Column(String, nullable=True)
    # 新增：联系与绑定信息（为用户管理视图提供数据）
    email = Column(String, nullable=True)
    qq = Column(String, nullable=True)
    # 绑定的 MC 玩家（存 players.id），为兼容旧库不强制外键约束
    bound_player_id = Column(Integer, nullable=True)


class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer)
    name = Column(String, unique=True)
    path = Column(String)
    core_config = Column(String, default=json.dumps(DEFAULT_CORE_CONFIG))
    # Core Config:
    # Vanilla (without Fabric): {
    #   "server_type": "vanilla"
    #   "core_version": "1.12.8",
    #   "is_fabric": false,
    #   "loader_version": null,
    #   "launcher_jar": "server.jar",
    #   "server_jar": "server.jar",
    # }
    # Vanilla (with Fabric): {
    #   "server_type": "vanilla"
    #   "core_version": "1.12.8",
    #   "is_fabric": true,
    #   "loader_version": "0.15.16",
    #   "launcher_jar": "fabric-server-launcher.jar",
    #   "server_jar": "server.jar",
    # }
    # Velocity: {
    #   "server_type": "velocity"
    #   "core_version": "3.4.0-523",
    #   "launcher_jar": "server.jar",
    #   "server_jar": "server.jar",
    # }


class Download(Base):
    __tablename__ = "downloads"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String)
    path = Column(String)
    file_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ArchiveType(enum.Enum):
    SERVER = "SERVER"  # 从服务器生成的
    UPLOADED = "UPLOADED"  # 用户上传的


class Archive(Base):
    __tablename__ = "archives"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(SQLAlchemyEnum(ArchiveType))
    source_server_id = Column(Integer, nullable=True)
    mc_version = Column(String, nullable=True)
    filename = Column(String, unique=True)
    path = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Plugin(Base):
    __tablename__ = "plugin"
    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String)
    path = Column(String, unique=True)
    url = Column(String, unique=True)
    hash_md5 = Column(String)
    hash_sha256 = Column(String)
    size = Column(Integer)
    meta = Column(String, default="{}")
    servers_installed = Column(String, default="[]")


class Mod(Base):
    __tablename__ = "mods"
    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String)
    path = Column(String, unique=True)
    url = Column(String, nullable=True)
    hash_md5 = Column(String, nullable=True)
    hash_sha256 = Column(String, nullable=True)
    size = Column(Integer)
    meta = Column(String, default="{}")
    servers_installed = Column(String, default="[]")


class ServerLinkGroup(Base):
    """服务器组（用于 Server Link 功能）

    - server_ids: JSON 字符串（int 数组）
    - chat_bindings: JSON 字符串（占位，后续扩展绑定聊天群等）
    """
    __tablename__ = "server_link_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    server_ids = Column(String, default="[]")
    chat_bindings = Column(String, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    # 为空表示 ALERT（全局）
    group_id = Column(Integer, nullable=True)
    level = Column(String, default="NORMAL")  # NORMAL / ALERT
    source = Column(String, default="web")    # web / game
    content = Column(Text)
    # 发送者（web）
    sender_user_id = Column(Integer, nullable=True)
    sender_username = Column(String, nullable=True)
    # 来自游戏的附加信息
    server_name = Column(String, nullable=True)
    player_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SystemSettings(Base):
    """
    系统级设置（单行表）：
    - data: JSON 字符串，保存键值，如：
      {
        "python_executable": ".venv/bin/python",
        "java_command": "java",
        "timezone": "Asia/Shanghai"
      }
    """
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, index=True)
    data = Column(String, default="{}")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    # 作为唯一标识符（从 world/playerdata/*.dat 文件名提取）
    uuid = Column(String, unique=True, index=True, nullable=False)
    # 玩家名（可为空，在线/正版账号可通过 API 获取；离线服允许手动设置）
    player_name = Column(String, nullable=True)
    # 各服务器游玩时长（JSON 字符串：{server_name: ticks}，单位为 gt=1/20 秒）
    play_time = Column(String, default="{}")
    # 是否为离线/盗版（当从官方接口无法解析时标记为 True）
    is_offline = Column(Boolean, default=False, nullable=False)


class MetricsDim(Base):
    __tablename__ = "metrics_dim"
    metric_id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String) # with namespace, such as minecraft:custom
    item = Column(String) # with namespace, such as minecraft:deaths
    __table_args__ = (UniqueConstraint("category", "item", name="uq_metric_ns_cat_item"),)


class PlayerMetrics(Base):
    __tablename__ = "player_metrics"
    ts = Column(Integer)  # epoch seconds, aligned to 10-min
    server_id = Column(Integer, ForeignKey("servers.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    metric_id = Column(Integer, ForeignKey("metrics_dim.metric_id"))
    total = Column(Integer)
    delta = Column(Integer)
    __table_args__ = (
        PrimaryKeyConstraint("server_id", "player_id", "metric_id", "ts", name="pk_player_metrics"),
        Index("idx_player_metrics_ts", "ts"),
        Index("idx_player_metrics_metric_ts", "metric_id", "ts"),
    )


class JsonDim(Base):
    __tablename__ = "json_dim"
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    json_file_name = Column(String, nullable=False)
    # 上次读取时间（epoch 秒）；允许为 NULL（未读取过，仅占位）
    last_read_time = Column(Integer, nullable=True)
    __table_args__ = (
        UniqueConstraint("server_id", "json_file_name", name="uq_json_dim_server_file"),
        Index("idx_json_dim_server", "server_id"),
    )
