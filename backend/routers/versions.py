from fastapi import APIRouter

from cachetools import TTLCache
from backend.core.api import get_minecraft_versions_raw, get_velocity_versions_raw, get_fabric_game_version_list, \
    get_fabric_loader_version_list
from backend import schemas

router = APIRouter(
    prefix="/api",
    tags=["Versions"],
)
velocity_version_cache = TTLCache(maxsize=1, ttl=3600)


@router.get("/velocity/versions", response_model=schemas.PaperVersionManifest, tags=["Velocity"])
async def get_velocity_versions():
    _ = await get_velocity_versions_raw()
    result = {
        "project": {
            "id": "velocity",
            "name": "Velocity"
        },
        "versions": []
    }
    for version in _["versions"]:
        result["versions"].extend(list(f"{version['version']['id']}#{b}" for b in version["builds"]))
    return schemas.PaperVersionManifest(
        **result
    )


@router.get("/minecraft/versions", response_model=schemas.MinecraftVersionManifest)
async def get_minecraft_versions():
    _ = await get_minecraft_versions_raw()
    return schemas.MinecraftVersionManifest(**_)


@router.get("/fabric/game-versions", response_model=schemas.FabricGameVersionManifest)
async def get_fabric_games():
    _ = await get_fabric_game_version_list()
    return schemas.FabricGameVersionManifest(versions=_)


@router.get("/fabric/loader-versions", response_model=schemas.FabricLoaderVersionManifest)
async def get_fabric_versions(version_id: str):
    _ = await get_fabric_loader_version_list(version_id)
    return schemas.FabricLoaderVersionManifest(versions=_)
