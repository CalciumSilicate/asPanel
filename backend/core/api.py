# backend/core/api.py

import httpx
from typing import Any, Dict, List, Optional
from cache import AsyncTTL
from fastapi.exceptions import HTTPException
import uuid

# --- API ---
MINECRAFT_VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
VELOCITY_VERSION_MANIFEST_URL = "https://fill.papermc.io/v3/projects/velocity/versions"
VELOCITY_BUILD_MANIFEST_URL = "https://fill.papermc.io/v3/projects/velocity/versions/{0}/builds"
FABRIC_GAME_VERSION_LIST_MANIFEST_URL = "https://meta.fabricmc.net/v2/versions/game"
FABRIC_LOADER_VERSION_LIST_MANIFEST_URL = "https://meta.fabricmc.net/v2/versions/loader/{0}"
FABRIC_LOADER_VERSION_MANIFEST_URL = "https://meta.fabricmc.net/v2/versions/loader/{0}/{1}"
FORGE_PROMOTIONS_MANIFEST_URL = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
FORGE_MAVEN_REPO_URL = "https://maven.minecraftforge.net/"
FORGE_LOADER_VERSION_API_URL = "https://mc-versions-api.net/api/forge?version={0}"
MCDR_PLUGINS_CATALOGUE_URL = "https://api.mcdreforged.com/catalogue/everything_slim.json"
MOJANG_PLAYER_PROFILE_URL = "https://api.mojang.com/users/profiles/minecraft/{0}"

async_client = httpx.AsyncClient(timeout=10)


async def async_get(url: str) -> httpx.Response:
    try:
        response = await async_client.get(url)
        response.raise_for_status()
        return response
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch {url}: {e}")


async def async_get_json(url: str) -> Dict | List:
    response = await async_get(url)
    response.raise_for_status()
    return response.json()


@AsyncTTL(time_to_live=3600, maxsize=1)
async def get_minecraft_versions_raw() -> Dict:
    return await async_get_json(MINECRAFT_VERSION_MANIFEST_URL)


@AsyncTTL(time_to_live=3600, maxsize=1)
async def get_velocity_versions_raw() -> Dict:
    return await async_get_json(VELOCITY_VERSION_MANIFEST_URL)


@AsyncTTL(time_to_live=3600, maxsize=128)
async def get_minecraft_version_detail(version_url: str) -> Dict[str, Any]:
    return await async_get_json(version_url)


@AsyncTTL(time_to_live=3600, maxsize=128)
async def get_minecraft_version_detail_by_version_id(version_id: str) -> Dict[str, Any] | None:
    manifest = await get_minecraft_versions_raw()
    for version in manifest.get("versions"):
        if version.get("id") == version_id:
            return await get_minecraft_version_detail(version.get("url"))
    return None


@AsyncTTL(time_to_live=3600, maxsize=128)
async def get_velocity_version_detail(version: str, build: str | int) -> Dict[str, Any]:
    _ = await async_get_json(VELOCITY_BUILD_MANIFEST_URL.format(version))
    _build: Dict | None = None
    build: int = int(build)
    for b in _:
        if b["id"] == build:
            _build = b
            break
    if _build is None:
        raise HTTPException(status_code=404)
    return _build


@AsyncTTL(time_to_live=3600, maxsize=1)
async def get_fabric_game_version_list() -> List:
    _ = await async_get_json(FABRIC_GAME_VERSION_LIST_MANIFEST_URL)
    return list(x['version'] for x in _)


@AsyncTTL(time_to_live=3600, maxsize=128)
async def get_fabric_loader_version_list(vanilla_core_version: str) -> List:
    _ = await async_get_json(FABRIC_LOADER_VERSION_LIST_MANIFEST_URL.format(vanilla_core_version))
    return list(x['loader']['version'] for x in _)


@AsyncTTL(time_to_live=3600, maxsize=1024)
async def get_fabric_version_meta(vanilla_core_version: str, fabric_loader_version: str) -> Dict:
    return await async_get_json(FABRIC_LOADER_VERSION_MANIFEST_URL.format(vanilla_core_version, fabric_loader_version))


@AsyncTTL(time_to_live=3600, maxsize=1)
async def get_forge_promotions_manifest() -> Dict[str, Any]:
    return await async_get_json(FORGE_PROMOTIONS_MANIFEST_URL)


@AsyncTTL(time_to_live=3600, maxsize=128)
async def get_forge_loader_version(mc_version: str) -> Dict[str, List]:
    return await async_get_json(FORGE_LOADER_VERSION_API_URL.format(mc_version))


@AsyncTTL(time_to_live=3600, maxsize=1)
async def get_forge_game_version_list() -> List[str]:
    manifest = await get_forge_promotions_manifest()
    result = []
    for entry in manifest.get("promos", {}):
        vid = entry.split("-")[0]
        if vid not in result:
            result.append(vid)
    result.reverse()
    return result


@AsyncTTL(time_to_live=3600, maxsize=128)
async def get_forge_loader_version_list(mc_version: str) -> List[str]:
    forge_game_list = await get_forge_game_version_list()
    versions = []
    if mc_version in forge_game_list:
        loader_list = await get_forge_loader_version(mc_version)
        versions = loader_list["result"]
        if not versions:
            manifest = await get_forge_promotions_manifest()
            promos = manifest.get("promos", {})
            for k in [f'{mc_version}-latest', f'{mc_version}-recommended']:
                if k in promos:
                    versions.append(promos.get(k))
    versions = list(set(versions))
    return versions


@AsyncTTL(time_to_live=3600, maxsize=512)
async def get_forge_installer_meta(mc_version: str, forge_version: str) -> Dict[str, Optional[str]]:
    artifact_path = f"net/minecraftforge/forge/{mc_version}-{forge_version}/"
    installer_name = f"forge-{mc_version}-{forge_version}-installer.jar"
    installer_url = f"{FORGE_MAVEN_REPO_URL}{artifact_path}{installer_name}"
    sha1: Optional[str] = None
    try:
        response = await async_client.get(installer_url + ".sha1")
        if response.status_code == 200:
            sha1 = response.text.strip()
    except httpx.RequestError:
        sha1 = None
    return {
        "installer_url": installer_url,
        "installer_sha1": sha1,
        "installer_name": installer_name,
    }


@AsyncTTL(time_to_live=3600, maxsize=1)
async def get_mcdr_plugins_catalogue(_r=None) -> Dict:
    return await async_get_json(MCDR_PLUGINS_CATALOGUE_URL)


@AsyncTTL(time_to_live=3600, maxsize=16384)
async def get_uuid_by_name(player_name: str) -> Optional[str]:
    url = MOJANG_PLAYER_PROFILE_URL.format(player_name)
    try:
        response = await async_get(url)
        if response.status_code == 200:
            data = response.json()
            return str(uuid.UUID(data.get("id")))
    except HTTPException:
        return None
    return None