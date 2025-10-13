# core/api.py
from typing import Dict, Any, List
from cache import AsyncTTL
from fastapi.exceptions import HTTPException
from backend.core.config import MINECRAFT_VERSION_MANIFEST_URL, VELOCITY_VERSION_MANIFEST_URL, \
    VELOCITY_BUILD_MANIFEST_URL, FABRIC_GAME_VERSION_LIST_MANIFEST_URL, FABRIC_LOADER_VERSION_LIST_MANIFEST_URL, \
    FABRIC_LOADER_VERSION_MANIFEST_URL, MCDR_PLUGINS_CATALOGUE_URL
import httpx

async_client = httpx.AsyncClient(timeout=10)


async def async_get(url: str):
    try:
        response = await async_client.get(url)
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch {url}: {e}")


@AsyncTTL(time_to_live=3600, maxsize=1)
async def get_minecraft_versions_raw() -> Dict:
    return await async_get(MINECRAFT_VERSION_MANIFEST_URL)


@AsyncTTL(time_to_live=3600, maxsize=1)
async def get_velocity_versions_raw() -> Dict:
    return await async_get(VELOCITY_VERSION_MANIFEST_URL)


@AsyncTTL(time_to_live=3600, maxsize=128)
async def get_minecraft_version_detail(version_url: str) -> Dict[str, Any]:
    return await async_get(version_url)


@AsyncTTL(time_to_live=3600, maxsize=128)
async def get_minecraft_version_detail_by_version_id(version_id: str) -> Dict[str, Any] | None:
    manifest = await get_minecraft_versions_raw()
    for version in manifest.get("versions"):
        if version.get("id") == version_id:
            return await get_minecraft_version_detail(version.get("url"))
    return None


@AsyncTTL(time_to_live=3600, maxsize=128)
async def get_velocity_version_detail(version: str, build: str) -> Dict[str, Any]:
    _ = await async_get(VELOCITY_BUILD_MANIFEST_URL.format(version))
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
    return list(x['version'] for x in (await async_get(FABRIC_GAME_VERSION_LIST_MANIFEST_URL)))


@AsyncTTL(time_to_live=3600, maxsize=128)
async def get_fabric_loader_version_list(vanilla_core_version: str) -> List:
    return list(x['loader']['version'] for x in
                (await async_get(FABRIC_LOADER_VERSION_LIST_MANIFEST_URL.format(vanilla_core_version))))


@AsyncTTL(time_to_live=3600, maxsize=1024)
async def get_fabric_version_meta(vanilla_core_version: str, fabric_loader_version: str) -> Dict:
    return await async_get(FABRIC_LOADER_VERSION_MANIFEST_URL.format(vanilla_core_version, fabric_loader_version))


@AsyncTTL(time_to_live=3600, maxsize=1)
async def get_mcdr_plugins_catalogue() -> Dict:
    return await async_get(MCDR_PLUGINS_CATALOGUE_URL)
