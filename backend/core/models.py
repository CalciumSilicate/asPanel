# backend/core/models.py

import json
import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLAlchemyEnum, Text, Boolean, PrimaryKeyConstraint, \
    UniqueConstraint, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from backend.core.constants import DEFAULT_CORE_CONFIG, DEFAULT_USER_ROLE

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, nullable=False, default=DEFAULT_USER_ROLE)
    avatar_url = Column(String, nullable=True)
    email = Column(String, nullable=True)
    qq = Column(String, nullable=True)
    bound_player_id = Column(Integer, nullable=True)


class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer)
    name = Column(String, unique=True)
    path = Column(String)
    core_config = Column(String, default=json.dumps(DEFAULT_CORE_CONFIG))


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
    chat_bindings = Column(String, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


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
