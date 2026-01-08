# backend/routers/mods.py

import asyncio
import json
import os
import shutil
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional, List, Dict, Any

from backend.core import crud, models
from backend.core.auth import require_role, get_current_user
from backend.core.constants import TEMP_PATH
from backend.core.utils import get_file_md5, get_file_sha256, get_size_bytes, get_file_sha1
from backend.core.database import get_db, SessionLocal
from backend.core.logger import logger
from backend.core.schemas import Role, ServerCoreConfig, ModDBCreate, ServerModsCount, TaskType, TaskStatus
from backend.core.dependencies import mod_manager, task_manager
from backend.services.permission_service import PermissionService, GroupAction

router = APIRouter(prefix="/api", tags=["Mods"])


def _mods_dir(server_path: str | Path) -> Path:
    p = Path(server_path) / 'server' / 'mods'
    p.mkdir(exist_ok=True, parents=True)
    return p


def _mods_dir_for_server(server: Any) -> Path:
    """根据服务器类型返回存储根目录。

    - Vanilla/Fabric/Forge：<server-path>/server/mods
    - Velocity：<server-path>/server/plugins
    """
    try:
        core = ServerCoreConfig.model_validate(json.loads(server.core_config))
        if core.server_type == 'velocity':
            p = Path(server.path) / 'server' / 'plugins'
        else:
            p = Path(server.path) / 'server' / 'mods'
    except Exception:
        # 解析失败兜底到 mods
        p = Path(server.path) / 'server' / 'mods'
    p.mkdir(exist_ok=True, parents=True)
    return p


def _check_server_admin_permission(db: Session, user: models.User, server_id: int) -> None:
    """检查用户是否有管理该服务器的权限（组 ADMIN 或平台管理员）"""
    if not PermissionService.can_manage_server(db, user, server_id, GroupAction.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限管理此服务器的模组"
        )


async def _try_fill_meta_from_modrinth_by_hash(file_path: Path) -> Dict[str, Any] | None:
    """通过 Modrinth 的文件哈希匹配接口补全元数据。
    参考: https://docs.modrinth.com/api/#tag/version/operation/getVersionFromHash
    """
    sha1 = get_file_sha1(file_path)
    url = f"https://api.modrinth.com/v2/version_file/{sha1}?algorithm=sha1"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        if r.status_code != 200:
            return None
        ver = r.json()
        # 获取项目信息
        project_id = ver.get('project_id')
        project = None
        if project_id:
            pr = await client.get(f"https://api.modrinth.com/v2/project/{project_id}")
            if pr.status_code == 200:
                project = pr.json()

        meta = {
            'source': 'modrinth',
            'modrinth_project_id': project_id,
            'modrinth_version_id': ver.get('id'),
            'id': (project or {}).get('slug') or project_id,
            'slug': (project or {}).get('slug'),
            'name': (project or {}).get('title') or (project or {}).get('name'),
            'description': (project or {}).get('description'),
            'authors': [a.get('name') for a in (project or {}).get('authors', []) if a.get('name')],
            'version': ver.get('version_number'),
            'game_versions': ver.get('game_versions', []),
            'loaders': ver.get('loaders', []),
            'downloads': (project or {}).get('downloads'),
            'follows': (project or {}).get('followers'),
            'project_page': (project or {}).get('project_type'),
        }
        return meta


def _build_mod_item(file_path: Path, enabled: bool, meta: Dict[str, Any] | None, hash_md5: Optional[str] = None,
                    hash_sha256: Optional[str] = None) -> Dict[str, Any]:
    return {
        'file_name': file_path.name,
        'path': str(file_path),
        'size': get_size_bytes(file_path),
        'enabled': enabled,
        'meta': meta or {},
        'hash_md5': hash_md5,
        'hash_sha256': hash_sha256,
        'read_meta_ok': bool(meta),
    }


@router.get('/mods/server/{server_id}')
async def list_server_mods(
        server_id: int,
        skip_enrich: bool = Query(False, description='跳过元数据补全与哈希计算以提升速度'),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """列出服务器 mods 目录下的模组，并尝试从本地数据库或 Modrinth 补全元信息。

    返回结构与 plugins 列表相似：{"data": [ ... ]}
    """
    _check_server_admin_permission(db, current_user, server_id)
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    return await mod_manager.list_server_mods(server, db=db, skip_enrich=skip_enrich)


@router.get('/mods/overview/{server_id}')
async def mods_overview(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """提供 mods 目录的概览信息。"""
    _check_server_admin_permission(db, current_user, server_id)
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    return mod_manager.overview(server)


@router.get('/mods/usage/total')
async def mods_usage_total(db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    """汇总所有服务器 mods 目录的总占用。"""
    return mod_manager.usage_total(db)


@router.get('/mods/servers', response_model=List[ServerModsCount])
async def list_servers_mods_counts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """汇总所有服务器的 mods 数量（不含模组列表与大小）。"""
    # 获取用户可访问的服务器
    if PermissionService.is_platform_admin(current_user):
        servers = crud.get_all_servers(db)
    else:
        accessible_ids = set(PermissionService.get_accessible_servers(db, current_user))
        servers = [s for s in crud.get_all_servers(db) if s.id in accessible_ids]
    
    if not servers:
        return []

    async def _count(server) -> Optional[ServerModsCount]:
        try:
            mods_count = await asyncio.to_thread(mod_manager.count_mods, server)
            return ServerModsCount(id=server.id, mods_count=int(mods_count))
        except Exception:
            return None

    results = await asyncio.gather(*[_count(s) for s in servers])
    return [r for r in results if r is not None]


@router.post('/mods/server/{server_id}/switch/{file_name}')
async def switch_mod(
    server_id: int,
    file_name: str,
    enable: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    _check_server_admin_permission(db, current_user, server_id)
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    return mod_manager.switch_mod(server, file_name, enable)


@router.delete('/mods/server/{server_id}/{file_name}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_mod(
    server_id: int,
    file_name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    _check_server_admin_permission(db, current_user, server_id)
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    mod_manager.delete_mod(server, file_name, db)
    return None


@router.get('/mods/download/{server_id}/{file_name}')
async def download_mod(
    server_id: int,
    file_name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    _check_server_admin_permission(db, current_user, server_id)
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    requested_path = mod_manager.get_download_path(server, file_name)
    return FileResponse(path=str(requested_path), filename=requested_path.name, media_type='application/octet-stream')


@router.post('/mods/upload/{server_id}')
async def upload_mod(
    server_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """上传本地模组到服务器 mods 目录，并写入元信息记录（若可识别）。"""
    _check_server_admin_permission(db, current_user, server_id)
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    return await mod_manager.upload_mod(server, file, db)


class ModsCopyPayload(BaseModel):
    source_server_id: int
    target_server_id: int
    delete_target_before: bool = False


@router.post('/mods/copy')
async def copy_mods(
        payload: ModsCopyPayload,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """从一个服务器复制所有模组到另一个服务器。可选先清空目标。"""
    # 需要对目标服务器有 ADMIN 权限
    _check_server_admin_permission(db, current_user, payload.target_server_id)
    src = crud.get_server_by_id(db, payload.source_server_id)
    dst = crud.get_server_by_id(db, payload.target_server_id)
    if not src or not dst:
        raise HTTPException(status_code=404, detail='源或目标服务器不存在')

    # 类型匹配校验：不同类型（vanilla/fabric/forge/velocity）禁止互相复制
    try:
        sc = ServerCoreConfig.model_validate(json.loads(src.core_config))
        dc = ServerCoreConfig.model_validate(json.loads(dst.core_config))
        def _norm(core: ServerCoreConfig) -> str:
            if core.server_type == 'velocity':
                return 'velocity'
            if core.server_type == 'forge':
                return 'forge'
            if core.server_type == 'vanilla' and core.is_fabric:
                return 'fabric'
            return 'vanilla'
        if _norm(sc) != _norm(dc):
            raise HTTPException(status_code=400, detail='不同类型的服务器禁止复制（vanilla/fabric/forge/velocity 需一致）')
    except HTTPException:
        raise
    except Exception:
        # 解析失败时为安全起见也禁止
        raise HTTPException(status_code=400, detail='无法解析服务器类型，禁止复制')

    src_dir = mod_manager.mods_dir_for_server(src)
    dst_dir = mod_manager.mods_dir_for_server(dst)

    if payload.delete_target_before:
        for f in os.listdir(dst_dir):
            p = dst_dir / f
            try:
                if p.is_file():
                    os.remove(p)
                    try:
                        crud.delete_mod_by_path(db, str(p))
                    except Exception:
                        pass
            except Exception:
                pass

    copied: List[str] = []
    for name in os.listdir(src_dir):
        sp = src_dir / name
        if not sp.is_file():
            continue
        dp = dst_dir / name
        try:
            shutil.copy2(sp, dp)
            copied.append(name)
        except Exception as e:
            logger.warning(f'复制模组 {name} 失败: {e}')

    return {'copied': copied}


@router.get('/mods/search/modrinth')
async def search_modrinth(
        q: str,
        limit: int = 20,
        offset: int = 0,
        game_version: Optional[str] = None,
        loader: Optional[str] = None,
        project_type: Optional[str] = None,
        _user=Depends(get_current_user)
):
    """代理 Modrinth 搜索接口。简化版，仅支持 query + 可选版本/加载器过滤。"""
    return await mod_manager.search_modrinth(q, limit=limit, offset=offset, game_version=game_version,
                                             loader=loader, project_type=project_type)


@router.get('/mods/modrinth/versions')
async def modrinth_versions(
        project_id: str,
        game_version: Optional[str] = None,
        loader: Optional[str] = None,
        _user=Depends(get_current_user)
):
    """代理 Modrinth 项目的版本列表，并可选过滤。"""
    return await mod_manager.modrinth_versions(project_id, game_version=game_version, loader=loader)


class ChangeVersionPayload(BaseModel):
    server_id: int
    file_name: str
    source: str  # 'modrinth' | 'curseforge'
    project_id: Optional[str] = None
    version_id: Optional[str] = None


@router.post('/mods/change-version')
async def change_version(
        payload: ChangeVersionPayload,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    _check_server_admin_permission(db, current_user, payload.server_id)
    server = crud.get_server_by_id(db, payload.server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    return await mod_manager.change_version(
        server,
        file_name=payload.file_name,
        source=payload.source,
        project_id=payload.project_id,
        version_id=payload.version_id,
        db=db,
    )


class ModrinthInstallPayload(BaseModel):
    server_id: int
    project_id: str
    version_id: Optional[str] = None


@router.post('/mods/install/modrinth')
async def install_from_modrinth(
        payload: Optional[ModrinthInstallPayload] = None,
        server_id: Optional[int] = Query(None),
        project_id: Optional[str] = Query(None),
        version_id: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """从 Modrinth 安装某个项目的指定版本（或自动选择最新兼容版本）。"""
    # 兼容两种调用方式：JSON body 或 Query 参数
    if payload is None:
        if not server_id or not project_id:
            raise HTTPException(status_code=422, detail="server_id 和 project_id 不能为空")
        payload = ModrinthInstallPayload(server_id=server_id, project_id=project_id, version_id=version_id)

    _check_server_admin_permission(db, current_user, payload.server_id)
    server = crud.get_server_by_id(db, payload.server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    core = ServerCoreConfig.model_validate(json.loads(server.core_config))

    # Create task for tracking
    task = task_manager.create_task(
        TaskType.INSTALL_MOD,
        name=f"安装模组 {payload.project_id}",
        message=f"正在从 Modrinth 下载模组..."
    )
    task.status = TaskStatus.RUNNING

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        version_id = payload.version_id
        if not version_id:
            # 拉取项目版本列表，选择与当前 MC 版本与加载器兼容的最新版本
            vr = await client.get(f'https://api.modrinth.com/v2/project/{payload.project_id}/version')
            if vr.status_code != 200:
                raise HTTPException(status_code=vr.status_code, detail=vr.text)
            versions = vr.json() or []
            preferred_loader = (
            'forge' if core.server_type == 'forge' else (
                'fabric' if core.is_fabric else (
                    'velocity' if core.server_type == 'velocity' else None
                )
            )
        )

            def is_compatible(v: Dict[str, Any]) -> bool:
                gv = v.get('game_versions') or []
                ld = v.get('loaders') or []
                is_velocity = core.server_type == 'velocity'
                if (not is_velocity) and core.core_version and core.core_version not in gv:
                    return False
                if preferred_loader and preferred_loader not in ld:
                    return False
                return True

            compat = [v for v in versions if is_compatible(v)]

            def _sort_key(v):
                return v.get('date_published') or v.get('version_number') or ''

            compat.sort(key=_sort_key, reverse=True)
            if compat:
                version_id = compat[0].get('id')
            else:
                raise HTTPException(status_code=409, detail='没有找到与当前 MC 版本与加载器兼容的版本')

        vr = await client.get(f'https://api.modrinth.com/v2/version/{version_id}')
        if vr.status_code != 200:
            raise HTTPException(status_code=vr.status_code, detail=vr.text)
        ver = vr.json()
        # 再次严格校验 loader 与版本
        preferred_loader = (
            'forge' if core.server_type == 'forge' else (
                'fabric' if core.is_fabric else (
                    'velocity' if core.server_type == 'velocity' else None
                )
            )
        )
        gv = ver.get('game_versions') or []
        ld = ver.get('loaders') or []
        is_velocity = core.server_type == 'velocity'
        if ((not is_velocity) and core.core_version and core.core_version not in gv) or (preferred_loader and preferred_loader not in ld):
            raise HTTPException(status_code=409, detail='所选版本不兼容当前 MC 版本或加载器')
        files = ver.get('files') or []
        # 选择第一个 .jar 文件
        file_info = None
        for f in files:
            url = f.get('url') or f.get('primary', False)
            if (f.get('filename') or '').endswith('.jar'):
                file_info = f
                break
        if not file_info and files:
            file_info = files[0]
        if not file_info:
            raise HTTPException(status_code=400, detail='该版本没有可用的文件')

        download_url = file_info.get('url')
        filename = file_info.get('filename') or f"{payload.project_id}-{ver.get('version_number')}.jar"

        # 下载并保存
        mods_dir = _mods_dir_for_server(server)
        tmp = TEMP_PATH / f"mod_{os.urandom(6).hex()}_{filename}"
        try:
            async with client.stream('GET', download_url) as resp:
                resp.raise_for_status()
                with open(tmp, 'wb') as out:
                    async for chunk in resp.aiter_bytes():
                        out.write(chunk)
            target = mods_dir / filename
            shutil.move(tmp, target)

            # 写入/更新 DB 记录（若 path 已存在则更新记录，避免 UNIQUE 约束冲突）
            # 获取项目信息以补全 slug
            project_slug = None
            try:
                pr = await client.get(f'https://api.modrinth.com/v2/project/{payload.project_id}')
                if pr.status_code == 200:
                    project_slug = (pr.json() or {}).get('slug')
            except Exception:
                project_slug = None

            meta = {
                'source': 'modrinth',
                'modrinth_project_id': payload.project_id,
                'modrinth_version_id': version_id,
                'id': payload.project_id,
                'slug': project_slug,
                'name': ver.get('name') or ver.get('version_number'),
                'version': ver.get('version_number'),
                'game_versions': ver.get('game_versions', []),
                'loaders': ver.get('loaders', []),
            }
            existing = crud.get_mod_by_path(db, str(target))
            md5 = get_file_md5(target)
            sha256 = get_file_sha256(target)
            if existing:
                crud.update_mod_record(db, existing,
                                       file_name=target.name,
                                       url=download_url,
                                       hash_md5=md5,
                                       hash_sha256=sha256,
                                       size=target.stat().st_size,
                                       meta=meta)
                crud.add_server_to_mod(db, existing.id, payload.server_id)
            else:
                rec = ModDBCreate(
                    file_name=target.name,
                    path=str(target),
                    size=target.stat().st_size,
                    hash_md5=md5,
                    hash_sha256=sha256,
                    meta=meta,
                    url=download_url,
                )
                db_rec = crud.create_mod_record(db, rec)
                crud.add_server_to_mod(db, db_rec.id, payload.server_id)

            task.status = TaskStatus.SUCCESS
            task.progress = 100
            task.message = f"模组 {target.name} 安装成功"
            return {'message': '安装成功', 'file_name': target.name, 'task_id': task.id}
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            if tmp.exists():
                try:
                    os.remove(tmp)
                except Exception:
                    pass


async def _job_check_updates(server_id: int):
    # 已迁移至 services.mod_manager.ModManager.check_updates_background
    return


@router.get('/mods/check-updates/{server_id}')
async def check_updates(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """启动检查模组更新任务，返回任务 ID 供前端跟踪进度。"""
    _check_server_admin_permission(db, current_user, server_id)
    from backend.core import crud
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='服务器不存在')
    
    task = mod_manager.start_check_updates_task(server_id, server.name)
    return {'status': 'accepted', 'message': '检查任务已开始', 'task_id': task.id}
