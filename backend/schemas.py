# schemas.py
from pydantic import BaseModel, Field, BeforeValidator, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import enum
import json

from typing import Annotated


def validate_core_config(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("core_config is an invalid JSON string")
    else:
        return v


# --- Enums ---
class ArchiveType(str, enum.Enum):
    SERVER = "SERVER"
    UPLOADED = "UPLOADED"


class TaskType(str, enum.Enum):
    DOWNLOAD = "DOWNLOAD"
    CREATE_ARCHIVE = "CREATE_ARCHIVE"
    UPLOAD_ARCHIVE = "UPLOAD_ARCHIVE"
    RESTORE_ARCHIVE = "RESTORE_ARCHIVE"
    IMPORT = "IMPORT"
    COMBINED = "COMBINED"


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ServerStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    NEW_SETUP = "new_setup"
    ERROR = "error"


class ServerType(str, enum.Enum):
    VANILLA = "vanilla"
    FORGE = "forge"
    VELOCITY = "velocity"


class Role(str, enum.Enum):
    GUEST = "GUEST"
    USER = "USER"
    HELPER = "HELPER"
    ADMIN = "ADMIN"
    OWNER = "OWNER"


class ServerPluginType(str, enum.Enum):
    MCDR = "MCDR"
    PYZ = "PYZ"
    FOLDER = "FOLDER"
    PY = "PY"


ROLE_HIERARCHY = {
    Role.GUEST: 0,
    Role.USER: 1,
    Role.HELPER: 2,
    Role.ADMIN: 3,
    Role.OWNER: 4
}


# --- User Schemas ---
class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    avatar_url: Optional[str] = None
    role: Role
    # 新增：联系与绑定信息
    email: Optional[str] = None
    qq: Optional[str] = None
    bound_player_id: Optional[int] = None
    mc_uuid: Optional[str] = None
    mc_name: Optional[str] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    qq: Optional[str] = None
    role: Optional[Role] = None
    bound_player_id: Optional[int] = None


# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# --- Server Schemas ---


class ServerBase(BaseModel):
    name: str


class ServerCreate(ServerBase):
    pass


class ServerCreateInternal(ServerBase):
    path: str
    creator_id: int


class ServerCoreConfig(BaseModel):
    server_type: ServerType = "vanilla"  # vanilla, forge, velocity
    core_version: Optional[str] = None  # for all servers
    is_fabric: bool = False  # only when server_type == vanilla it can be true
    loader_version: Optional[str] = None  # either fabric or forge loader
    launcher_jar: Optional[
        str] = None  # when vanilla and is_fabric==True or forge server, it will be different from server_jar, indicating loader_version
    server_jar: Optional[str] = "server.jar"  # indicates core_version


class Server(ServerBase):
    id: int
    path: str
    creator_id: int

    core_config: Annotated[ServerCoreConfig, BeforeValidator(validate_core_config)]

    class Config:
        from_attributes = True


class ServerConfigJvm(BaseModel):
    min_memory: Optional[str] = Field("1G", description="Minimum memory (e.g., 512M, 1G)")
    max_memory: Optional[str] = Field("4G", description="Maximum memory (e.g., 2G, 8G)")
    extra_args: Optional[str] = Field("", description="Extra JVM arguments")


class ServerConfigData(BaseModel):
    core_config: ServerCoreConfig = Field(default_factory=ServerCoreConfig)
    jvm: ServerConfigJvm = Field(default_factory=ServerConfigJvm)
    vanilla_server_properties: Dict[str, Any] = Field(default_factory=dict)
    velocity_toml: Optional[Dict[str, Any]] = Field(None, description="Configuration for velocity.toml")


class ServerConfigResponse(BaseModel):
    is_new_setup: bool
    core_file_exists: bool = Field(False, description="Indicates if the main server JAR file exists.")
    config_file_exists: bool = Field(False, description="Indicates if the main config file exists.")
    config: ServerConfigData


class ServerConfigPayload(BaseModel):
    server_id: int
    config: ServerConfigData


class ServerDetail(Server):
    status: str
    return_code: Optional[int]
    size_mb: Optional[float] = None
    port: Optional[Any] = None
    rcon_port: Optional[Any] = None
    rcon_password: Optional[Any] = None


class ServerDashboardInfo(ServerBase):
    status: ServerStatus
    cpu_percent: float = None
    mem_mb: float = None




class BatchActionPayload(BaseModel):
    ids: List[int]
    command: Optional[str] = None


class ServerImport(BaseModel):
    name: str = Field(..., description="为导入的服务器指定一个新名称")
    path: str = Field(..., description="服务器上MCDR实例的绝对路径")


# --- Task Schemas ---
class Task(BaseModel):
    id: str
    ids: Optional[List[str]] = None
    status: TaskStatus = "PENDING"  # pending, downloading, complete, failed
    progress: float = 0.0
    error: Optional[str] = None
    message: Optional[str] = None
    type: TaskType = None
    total: Optional[int] = None
    done: Optional[int] = None


# --- File Content Schemas ---
class FileContentUpdate(BaseModel):
    file_type: str
    content: str


# --- Minecraft Version Schemas ---
class MinecraftVersion(BaseModel):
    id: str
    type: str
    url: str
    time: datetime
    releaseTime: datetime


class MinecraftVersionManifest(BaseModel):
    latest: Dict[str, str]
    versions: List[MinecraftVersion]


class FabricGameVersionManifest(BaseModel):
    versions: List[str]


class FabricLoaderVersionManifest(BaseModel):
    versions: List[str]


class ForgeGameVersionManifest(BaseModel):
    versions: List[str]


class ForgeLoaderVersionManifest(BaseModel):
    versions: List[str]


class PortStatusResponse(BaseModel):
    is_available: bool


# --- Paper Version Schemas ---
class PaperVersion(BaseModel):
    version: str
    builds: List[int]


class PaperProject(BaseModel):
    id: str
    name: str


class PaperVersionManifest(BaseModel):
    project: PaperProject
    versions: List[str]


class PaperCheckSums(BaseModel):
    sha256: str


class PaperBuildDownload(BaseModel):
    name: str
    checksums: PaperCheckSums
    size: int
    url: str


class PaperBuild(BaseModel):
    id: int
    time: datetime
    channel: str
    commits: List[Dict]
    downloads: Dict[str, PaperBuildDownload]


# --- Server Plugin Schemas ---
class ServerPlugin(BaseModel):
    file_name: str
    path: str
    type: ServerPluginType
    size: int
    enabled: bool
    meta: Dict
    hash_md5: Optional[str]
    hash_sha256: Optional[str]
    read_meta_ok: bool


class ServerPlugins(BaseModel):
    data: List[ServerPlugin]


# --- Plugin Catalogue Schemas ---
class PluginMeta(BaseModel):
    schema_version: int
    id: str
    name: str
    version: str
    link: Optional[str]
    authors: List[str]
    dependencies: Optional[Dict]
    requirements: List[str]
    description: Optional[Dict]


class PluginInfo(BaseModel):
    class Plugin(BaseModel):
        schema_version: int
        id: str
        authors: List[str]
        repository: str
        branch: str
        related_path: str
        labels: List[str]
        introduction: Dict
        introduction_urls: Dict

    class PluginReleases(BaseModel):
        class PluginRelease(BaseModel):
            class PluginAsset(BaseModel):
                id: int
                name: str
                size: int
                download_count: int
                created_at: datetime
                browser_download_url: str
                hash_md5: str
                hash_sha256: str

            url: str
            name: str
            tag_name: str
            created_at: datetime
            description: Optional[str]
            prerelease: bool
            asset: PluginAsset
            meta: Optional[PluginMeta]

        schema_version: int
        id: str
        latest_version: Optional[str]
        latest_version_index: Optional[int]
        releases: List[PluginRelease]

    class PluginRepository(BaseModel):
        class PluginLicense(BaseModel):
            key: str
            name: str
            spdx_id: str
            url: Optional[str]

        url: str
        name: str
        full_name: str
        html_url: str
        description: Optional[str]
        archived: bool
        stargazers_count: int
        watchers_count: int
        forks_count: int
        readme: Optional[str]
        readme_url: Optional[str]
        license: Optional[PluginLicense]

    meta: Optional[PluginMeta]
    plugin: Plugin
    release: PluginReleases
    repository: PluginRepository


class PluginCatalogue(BaseModel):
    class PluginAuthors(BaseModel):
        class PluginAuthor(BaseModel):
            name: str
            link: str

        amount: int
        authors: Dict[str, PluginAuthor]

    timestamp: int
    authors: PluginAuthors
    plugins: Dict[str, PluginInfo]


# --- Archive Schemas ---
class ArchiveBase(BaseModel):
    name: str
    type: ArchiveType
    source_server_id: Optional[int] = None
    mc_version: Optional[str] = None
    path: str
    filename: str


class ArchiveCreate(ArchiveBase):
    pass


class Archive(ArchiveBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class RestorePayload(BaseModel):
    """
    [新增] 定义恢复存档时所需的请求体。
    """
    target_server_id: int


# --- Plugin Database Schemas ---
class PluginDBBase(BaseModel):
    file_name: str
    meta: Dict[str, Any] = Field(default_factory=dict)

    # Pydantic v2 的推荐方式
    @field_validator('meta', mode='before')
    @classmethod
    def parse_meta_from_json(cls, v: Any) -> Any:
        if isinstance(v, str):
            if not v:
                return {}
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("meta 字段包含无效的 JSON 字符串")

        return v

    class Config:
        from_attributes = True


class PluginDBCreate(PluginDBBase):
    path: str
    size: int
    hash_md5: Optional[str] = None
    hash_sha256: Optional[str] = None
    url: Optional[str] = None  # 用于记录从网络下载的源URL


class PluginDBRecord(PluginDBBase):
    id: int
    path: str
    size: int
    hash_md5: Optional[str] = None
    hash_sha256: Optional[str] = None
    url: Optional[str] = None
    servers_installed: List[int] = Field(default_factory=list)

    @field_validator('servers_installed', mode='before')
    def parse_servers_installed(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v

    class Config:
        from_attributes = True


# --- Mod Database Schemas ---
class ModDBBase(BaseModel):
    file_name: str
    meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('meta', mode='before')
    @classmethod
    def parse_meta_from_json_for_mods(cls, v: Any) -> Any:
        if isinstance(v, str):
            if not v:
                return {}
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("meta 字段包含无效的 JSON 字符串")
        return v

    class Config:
        from_attributes = True


class ModDBCreate(ModDBBase):
    path: str
    size: int
    hash_md5: Optional[str] = None
    hash_sha256: Optional[str] = None
    url: Optional[str] = None


class ModDBRecord(ModDBBase):
    id: int
    path: str
    size: int
    hash_md5: Optional[str] = None
    hash_sha256: Optional[str] = None
    url: Optional[str] = None
    servers_installed: List[int] = Field(default_factory=list)

    @field_validator('servers_installed', mode='before')
    def parse_servers_installed_mods(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v

    class Config:
        from_attributes = True


# --- Tools: SuperFlat Schemas ---
class LayerItem(BaseModel):
    block: str
    height: int = Field(ge=1)


class SuperFlatConfig(BaseModel):
    versionName: Optional[str] = Field(default=None)
    version: Optional[str] = Field(default=None)
    seed: Optional[Any] = Field(default=None)
    structureOverrides: List[str] = Field(default_factory=list)
    structure_overrides: Optional[List[str]] = None
    biomes: List[str] = Field(default_factory=list)
    biome: Optional[str] = None
    layers: List[LayerItem] = Field(default_factory=list)
    dimension_key: Optional[str] = None

    def to_generator_payload(self) -> dict:
        payload = {
            "versionName": self.versionName or self.version,
            "seed": self.seed,
            "layers": [li.model_dump() for li in self.layers],
            "structure_overrides": self.structure_overrides or self.structureOverrides or [],
        }
        if self.biomes:
            payload["biomes"] = self.biomes
        elif self.biome:
            payload["biome"] = self.biome
        if self.dimension_key:
            payload["dimension_key"] = self.dimension_key
        return payload


class ApplyRequest(SuperFlatConfig):
    server_id: int
    overwrite: bool = False


# --- Tools: Prime Backup Schemas ---
class PBUsage(BaseModel):
    bytes: int


class PBOverview(BaseModel):
    storage_root: str | None = None
    db_version: str | None = None
    backup_amount: int | None = None
    db_path: str | None = None
    db_file_size: int | None = None
    blob_stored_size: int | None = None
    blob_raw_size: int | None = None


class PBBackupItem(BaseModel):
    id: int
    date: str
    stored_size: int
    raw_size: int
    creator: str
    comment: str


class PBExportPayload(BaseModel):
    id: int


class PBExtractPayload(BaseModel):
    id: int
    src_path: str
    dest_path: str


class PBRestorePayload(BaseModel):
    id: int
    target_server_id: int


# --- Server Link Schemas ---
class ServerLinkGroupBase(BaseModel):
    name: str
    server_ids: List[int] = Field(default_factory=list)
    # chat_bindings 留空待定：使用 Any 数组占位，便于后续扩展结构
    chat_bindings: List[Any] = Field(default_factory=list)


class ServerLinkGroupCreate(ServerLinkGroupBase):
    pass


class ServerLinkGroupUpdate(BaseModel):
    name: Optional[str] = None
    server_ids: Optional[List[int]] = None
    chat_bindings: Optional[List[Any]] = None


class ServerLinkGroup(ServerLinkGroupBase):
    id: int
    created_at: datetime | None = None

    class Config:
        from_attributes = True

    # 解析数据库中的 JSON 字符串字段
    @field_validator('server_ids', 'chat_bindings', mode='before')
    @classmethod
    def parse_json_array(cls, v: Any):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v or []


# --- Chat Schemas ---
class ChatSendPayload(BaseModel):
    message: str
    level: str = Field("NORMAL", pattern="^(NORMAL|ALERT)$")
    group_id: Optional[int] = None  # NORMAL 时必须，ALERT 忽略


class ChatMessageOut(BaseModel):
    id: int
    group_id: Optional[int] = None
    level: str
    source: str
    content: str
    sender_user_id: Optional[int] = None
    sender_username: Optional[str] = None
    sender_avatar: Optional[str] = None
    server_name: Optional[str] = None
    player_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- System Settings Schemas ---
class SystemSettings(BaseModel):
    python_executable: str = Field(".venv/bin/python", description="服务器运行 MCDR 的 Python 可执行文件路径；相对路径以服务器目录为基准")
    java_command: str = Field("java", description="用于构建 MCDR start_command 的 Java 可执行文件")
    timezone: str = Field("Asia/Shanghai", description="前端显示使用的时区标识 e.g. Asia/Shanghai")
    stats_ignore_server: List[int] = Field(default_factory=list, description="忽略统计入库的服务器ID列表")


class SystemSettingsUpdate(BaseModel):
    python_executable: str | None = None
    java_command: str | None = None
    timezone: str | None = None
    stats_ignore_server: List[int] | None = None


# --- Player Schemas ---
class PlayerBase(BaseModel):
    uuid: str
    player_name: Optional[str] = None
    # 键为服务器名，值为 ticks（gt = 1/20 秒）
    play_time: Dict[str, int] = Field(default_factory=dict)
    is_offline: bool = False

    @field_validator('play_time', mode='before')
    @classmethod
    def parse_play_time(cls, v: Any):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v or {}

    class Config:
        from_attributes = True


class PlayerCreate(PlayerBase):
    pass


class Player(PlayerBase):
    id: int


class PlayerNameUpdate(BaseModel):
    name: str
