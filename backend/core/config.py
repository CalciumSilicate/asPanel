# core/config.py

from pathlib import Path
import os
import secrets


# --- API Configure ---
MINECRAFT_VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
VELOCITY_VERSION_MANIFEST_URL = "https://fill.papermc.io/v3/projects/velocity/versions"
VELOCITY_BUILD_MANIFEST_URL = "https://fill.papermc.io/v3/projects/velocity/versions/{0}/builds"
FABRIC_GAME_VERSION_LIST_MANIFEST_URL = "https://meta.fabricmc.net/v2/versions/game"
FABRIC_LOADER_VERSION_LIST_MANIFEST_URL = "https://meta.fabricmc.net/v2/versions/loader/{0}"
FABRIC_LOADER_VERSION_MANIFEST_URL = "https://meta.fabricmc.net/v2/versions/loader/{0}/{1}"
FABRIC_REPO_URL = "https://maven.fabricmc.net/"
MCDR_PLUGINS_CATALOGUE_URL = "https://api.mcdreforged.com/catalogue/everything_slim.json"

# --- Path Configure ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Directory that stores All files generated ---
_STORAGE_DIRNAME = "storages"
STORAGE_ROOT_PATH = BASE_DIR / _STORAGE_DIRNAME
STORAGE_ROOT_PATH.mkdir(exist_ok=True)

# --- Database Configure ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./{}/asPanel.db".format(_STORAGE_DIRNAME)
DATABASE_CONNECT_ARGS = {"check_same_thread": False}

# --- Directory that stores All MCDR Instances ---
MCDR_ROOT_PATH = STORAGE_ROOT_PATH / "mcdr-servers"
MCDR_ROOT_PATH.mkdir(exist_ok=True)

# --- Directory that stores All users' avatar ---
AVATAR_STORAGE_PATH = STORAGE_ROOT_PATH / "avatars"
AVATAR_STORAGE_PATH.mkdir(exist_ok=True)
AVATAR_URL_PREFIX = "/avatars/"

# --- Directory that stores All archives ---
ARCHIVE_STORAGE_PATH = STORAGE_ROOT_PATH / "archives"
ARCHIVE_STORAGE_PATH.mkdir(exist_ok=True)
ARCHIVE_URL_PREFIX = "/archives/"  # 用于下载

# --- Directory that stores uploaded plugins ---
UPLOADED_PLUGINS_PATH = STORAGE_ROOT_PATH / "uploaded-plugins"
UPLOADED_PLUGINS_PATH.mkdir(exist_ok=True)

# --- Directory that stores downloads temp ---
TEMP_PATH = STORAGE_ROOT_PATH / "temp"
TEMP_PATH.mkdir(exist_ok=True)

# --- Directory that stores uploaded plugins ---
UPLOADED_LITEMATIC_PATH = STORAGE_ROOT_PATH / "litematic" / "uploaded-litematic"
LITEMATIC_COMMAND_LIST_PATH = STORAGE_ROOT_PATH / "litematic" / "command-list"
UPLOADED_LITEMATIC_PATH.mkdir(exist_ok=True, parents=True)
LITEMATIC_COMMAND_LIST_PATH.mkdir(exist_ok=True, parents=True)

# --- Logger Configuration ---
LOG_LEVEL = "INFO"
LOG_FILE_LEVEL = "DEBUG"
LOG_STORAGE = STORAGE_ROOT_PATH / "logs"

# --- Security and verification ---
# 优先从环境变量读取 JWT 密钥；未提供时从 storages/secret.key 读取/生成并持久化（不纳入 git）。
_SECRET_KEY_ENV = os.getenv("ASPANEL_SECRET_KEY") or os.getenv("SECRET_KEY")
_SECRET_KEY_FILE = STORAGE_ROOT_PATH / "secret.key"

if _SECRET_KEY_ENV and _SECRET_KEY_ENV.strip():
    SECRET_KEY = _SECRET_KEY_ENV.strip()
else:
    if _SECRET_KEY_FILE.exists():
        SECRET_KEY = _SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
        if not SECRET_KEY:
            SECRET_KEY = secrets.token_hex(32)
            _SECRET_KEY_FILE.write_text(SECRET_KEY, encoding="utf-8")
    else:
        SECRET_KEY = secrets.token_hex(32)
        _SECRET_KEY_FILE.write_text(SECRET_KEY, encoding="utf-8")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10080  # 7 days

# --- CORS Configure ---
ALLOWED_ORIGINS = [
    "*",
]

# --- DEFAULT Server Config ---
DEFAULT_CORE_CONFIG = {
    "server_type": "vanilla",
    "core_version": None,
    "is_fabric": False,
    "loader_version": None,
    "launcher_jar": "server.jar",
    "server_jar": "server.jar"
}

DEFAULT_SERVER_PROPERTIES_CONFIG = {
    "online-mode": True, "server-port": 25565,
    "view-distance": 10, "max-players": 20,
    "motd": "A Minecraft Server",
    "gamemode": "survival", "difficulty": "hard",
    "hardcore": False, "enable-command-block": True,
    "enable-rcon": False, "rcon.password": "",
    "rcon.port": 25575, "level-seed": ""
}

# --- USER SETTING ---
ALLOW_REGISTER = True
DEFAULT_USER_ROLE = "OWNER"

# --- CONSOLE LOG SETTING ---
LOG_EMIT_INTERVAL_MS = 200

# --- WS PUSH INTERVAL (for MCDR events batching) ---
WS_PUSH_INTERVAL_MS = 200

# --- PUBLIC PLUGINS DIRECTORIES SETTING ---
PUBLIC_PLUGINS_DIRECTORIES = [
    'plugins',
    str(BASE_DIR / 'backend' / 'plugins')
]

# --- Python Executable ---
PYTHON_EXECUTABLE = "python"

CPU_PERCENT_INTERVAL = 1
