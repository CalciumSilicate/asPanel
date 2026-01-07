# backend/core/models.py

import json
import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLAlchemyEnum, Text, Boolean, PrimaryKeyConstraint, \
    UniqueConstraint, ForeignKey, Index, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from backend.core.constants import DEFAULT_CORE_CONFIG, DEFAULT_USER_ROLE

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    # 新权限模型：is_owner 和 is_admin 布尔字段
    is_owner = Column(Boolean, default=False, nullable=False)  # 超级管理员，可管理所有人权限
    is_admin = Column(Boolean, default=False, nullable=False)  # 管理员，可管理组权限但不能改全局权限
    # role 字段保留用于兼容迁移，之后可移除 (DEPRECATED)
    role = Column(String, nullable=True, default=None)
    avatar_url = Column(String, nullable=True)
    email = Column(String, nullable=True)
    qq = Column(String, nullable=True)
    bound_player_id = Column(Integer, nullable=True)
    server_link_group_ids = Column(String, nullable=True, default="[]")  # JSON array of group IDs (DEPRECATED)
    token_version = Column(Integer, default=0, nullable=False)


class UserGroupPermission(Base):
    __tablename__ = "user_group_permissions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id = Column(Integer, ForeignKey("server_link_groups.id", ondelete="CASCADE"), index=True)
    role = Column(String, default=DEFAULT_USER_ROLE)
    
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_user_group_permission"),
    )


class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer)
    name = Column(String, unique=True)
    path = Column(String)
    core_config = Column(String, default=json.dumps(DEFAULT_CORE_CONFIG))
    map = Column(String, default="{}")


class Download(Base):
    __tablename__ = "downloads"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String)
    path = Column(String)
    file_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ArchiveType(enum.Enum):
    SERVER = "SERVER"
    UPLOADED = "UPLOADED"


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
    __tablename__ = "server_link_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    server_ids = Column(String, default="[]")
    data_source_ids = Column(String, default="[]")
    chat_bindings = Column(String, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GroupServer(Base):
    """服务器组与服务器的关联表 - 替代 ServerLinkGroup.server_ids JSON 字段"""
    __tablename__ = "group_servers"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("server_link_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("group_id", "server_id", name="uq_group_server"),
    )


class GroupDataSource(Base):
    """服务器组与数据源的关联表 - 替代 ServerLinkGroup.data_source_ids JSON 字段"""
    __tablename__ = "group_data_sources"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("server_link_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    data_source_id = Column(Integer, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("group_id", "data_source_id", name="uq_group_data_source"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, nullable=True)
    level = Column(String, default="NORMAL")
    source = Column(String, default="web")
    content = Column(Text)
    sender_user_id = Column(Integer, nullable=True)
    sender_username = Column(String, nullable=True)
    server_name = Column(String, nullable=True)
    player_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SystemSettings(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, index=True)
    data = Column(String, default="{}")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, nullable=False)
    player_name = Column(String, nullable=True)
    play_time = Column(String, default="{}")
    is_offline = Column(Boolean, default=False, nullable=False)
    is_bot = Column(Boolean, default=False, nullable=False)

class MetricsDim(Base):
    __tablename__ = "metrics_dim"
    metric_id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String)
    item = Column(String)
    __table_args__ = (UniqueConstraint("category", "item", name="uq_metric_ns_cat_item"),)


class PlayerMetrics(Base):
    __tablename__ = "player_metrics"
    ts = Column(Integer)
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
    last_read_time = Column(Integer, nullable=True)
    __table_args__ = (
        UniqueConstraint("server_id", "json_file_name", name="uq_json_dim_server_file"),
        Index("idx_json_dim_server", "server_id"),
    )


class PlayerSession(Base):
    __tablename__ = "player_sessions"
    id = Column(Integer, primary_key=True, index=True)
    player_uuid = Column(String, index=True, nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    login_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    logout_time = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_player_sessions_lookup", "player_uuid", "server_id", "logout_time"),
    )


class PlayerPosition(Base):
    __tablename__ = "player_positions"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    x = Column(Float, nullable=True)
    y = Column(Float, nullable=True)
    z = Column(Float, nullable=True)
    dim = Column(String, nullable=True)
