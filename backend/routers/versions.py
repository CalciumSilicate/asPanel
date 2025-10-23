# backend/routers/versions.py

from fastapi import APIRouter, Depends
from cachetools import TTLCache

from backend.core.api import get_minecraft_versions_raw, get_velocity_versions_raw, get_fabric_game_version_list, \
    get_fabric_loader_version_list, get_forge_game_version_list, get_forge_loader_version_list
from backend.core import schemas
from backend.core.auth import require_role
from backend.core.schemas import Role

router = APIRouter(
    prefix="/api",
    tags=["Versions"],
)
velocity_version_cache = TTLCache(maxsize=1, ttl=3600)


@router.get("/velocity/versions", response_model=schemas.PaperVersionManifest, tags=["Velocity"])
async def get_velocity_versions(_user=Depends(require_role(Role.ADMIN))):
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
async def get_minecraft_versions(_user=Depends(require_role(Role.USER))):
    _ = await get_minecraft_versions_raw()
    return schemas.MinecraftVersionManifest(**_)


@router.get("/fabric/game-versions", response_model=schemas.FabricGameVersionManifest)
async def get_fabric_games(_user=Depends(require_role(Role.USER))):
    _ = await get_fabric_game_version_list()
    return schemas.FabricGameVersionManifest(versions=_)


@router.get("/fabric/loader-versions", response_model=schemas.FabricLoaderVersionManifest)
async def get_fabric_versions(version_id: str, _user=Depends(require_role(Role.USER))):
    _ = await get_fabric_loader_version_list(version_id)
    return schemas.FabricLoaderVersionManifest(versions=_)


@router.get("/forge/game-versions", response_model=schemas.ForgeGameVersionManifest)
async def get_forge_games(_user=Depends(require_role(Role.USER))):
    _ = await get_forge_game_version_list()
    return schemas.ForgeGameVersionManifest(versions=_)


@router.get("/forge/loader-versions", response_model=schemas.ForgeLoaderVersionManifest)
async def get_forge_versions(version_id: str, _user=Depends(require_role(Role.USER))):
    _ = await get_forge_loader_version_list(version_id)
    return schemas.ForgeLoaderVersionManifest(versions=_)
