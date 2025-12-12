# backend/core/constants.py

import re
import os
import secrets
from pathlib import Path

# --- Uvicorn Configure ---
UVICORN_HOST = "0.0.0.0"
UVICORN_LOG_LEVEL = "warning"
UVICORN_PORT = 8013

# --- API Configure ---
MINECRAFT_VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
VELOCITY_VERSION_MANIFEST_URL = "https://fill.papermc.io/v3/projects/velocity/versions"
VELOCITY_BUILD_MANIFEST_URL = "https://fill.papermc.io/v3/projects/velocity/versions/{0}/builds"
FABRIC_GAME_VERSION_LIST_MANIFEST_URL = "https://meta.fabricmc.net/v2/versions/game"
FABRIC_LOADER_VERSION_LIST_MANIFEST_URL = "https://meta.fabricmc.net/v2/versions/loader/{0}"
FABRIC_LOADER_VERSION_MANIFEST_URL = "https://meta.fabricmc.net/v2/versions/loader/{0}/{1}"
FABRIC_REPO_URL = "https://maven.fabricmc.net/"
FORGE_PROMOTIONS_MANIFEST_URL = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
FORGE_MAVEN_REPO_URL = "https://maven.minecraftforge.net/"
FORGE_LOADER_VERSION_API_URL = "https://mc-versions-api.net/api/forge?version={0}"
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
AVATAR_MC_PATH = STORAGE_ROOT_PATH / "avatars" / "mc"
AVATAR_MC_PATH.mkdir(exist_ok=True)
AVATAR_URL_PREFIX = "/avatars/"

# --- Directory that stores uploaded map jsons (nether/overworld, end) ---
MAP_JSON_STORAGE_PATH = STORAGE_ROOT_PATH / "maps"
MAP_JSON_STORAGE_PATH.mkdir(exist_ok=True)

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
LOG_LEVEL = "DEBUG"
LOG_FILE_LEVEL = "DEBUG"
LOG_STORAGE = STORAGE_ROOT_PATH / "logs"

# --- Timezone Setting ---
TIMEZONE = os.getenv("ASPANEL_TIMEZONE", "Asia/Shanghai")

# --- Secret Key for authorization ---
_SECRET_KEY_FILE = STORAGE_ROOT_PATH / "secret.key"
SECRET_KEY = None

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

# --- DEFAULT Vanilla Server Properties ---
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
DEFAULT_USER_ROLE = "USER"

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

# --- CPU percentage sampler interval ---
CPU_PERCENT_INTERVAL = 1

# --- Stats metric whitelist/ blacklist setting ---
STATS_WHITELIST_ON = False
STATS_WHITELIST = [
    # for example
    # "minecraft:custom.minecraft:deaths", "minecraft:custom.minecraft:play_time",
    # "minecraft:custom.minecraft:play_one_minute", "minecraft:used.minecraft:totem_of_undying",
    # "minecraft:used.minecraft:*_pickaxe"
]
STATS_IGNORE = []

# --- UUID string schema ---
UUID_HYPHEN_PATTERN = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
