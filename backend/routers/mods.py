from __future__ import annotations

import json
import os
import shutil
from json import JSONDecodeError
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status, BackgroundTasks, Query
from pydantic import BaseModel
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend import crud, models
from backend.auth import require_role
from backend.core.config import TEMP_PATH
from backend.core.utils import get_file_md5, get_file_sha256, get_size_bytes, get_file_sha1
from backend.database import get_db, SessionLocal
from backend.logger import logger
from backend.schemas import Role

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
        from backend.schemas import ServerCoreConfig
        import json as _json
        core = ServerCoreConfig.model_validate(_json.loads(server.core_config))
        if core.server_type == 'velocity':
            p = Path(server.path) / 'server' / 'plugins'
        else:
            p = Path(server.path) / 'server' / 'mods'
    except Exception:
        # 解析失败兜底到 mods
        p = Path(server.path) / 'server' / 'mods'
    p.mkdir(exist_ok=True, parents=True)
    return p


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
        _user=Depends(require_role(Role.USER))
):
    """列出服务器 mods 目录下的模组，并尝试从本地数据库或 Modrinth 补全元信息。

    返回结构与 plugins 列表相似：{"data": [ ... ]}
    """
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')

    mods_dir = _mods_dir_for_server(server)
    items: List[Dict[str, Any]] = []
    # 使用 scandir 提升大目录性能
    entries = []
    with os.scandir(mods_dir) as it:
        for entry in it:
            if entry.name.startswith('.'):
                continue
            if not entry.is_file():
                continue
            entries.append(entry.name)
    for name in sorted(entries):
        fp = mods_dir / name
        enabled = not name.endswith('.disabled')

        # 先尝试根据 path 从 DB 中匹配（避免昂贵的哈希计算）
        db_mod = db.query(models.Mod).filter(models.Mod.path == str(fp.resolve())).first()
        md5 = None

        meta = None
        if db_mod:
            try:
                meta = json.loads(db_mod.meta) if db_mod.meta else {}
            except JSONDecodeError:
                meta = {}
            # 命中 unknown 标记时，快速返回空 meta，并不再尝试补全
            if isinstance(meta, dict) and meta.get('unknown') is True:
                try:
                    crud.add_server_to_mod(db, db_mod.id, server_id)
                except Exception:
                    pass
                items.append(_build_mod_item(fp, enabled, {}))
                continue
            # 若为 modrinth 且缺少 slug，尝试用 project_id/id 查询项目补全 slug
            if (not skip_enrich) and isinstance(meta, dict) and meta.get('source') == 'modrinth' and (not meta.get('slug')):
                pid = meta.get('modrinth_project_id') or meta.get('id')
                if pid:
                    try:
                        async with httpx.AsyncClient(timeout=20) as client:
                            pr = await client.get(f"https://api.modrinth.com/v2/project/{pid}")
                            if pr.status_code == 200:
                                meta['slug'] = (pr.json() or {}).get('slug')
                                db_mod.meta = json.dumps(meta)
                                db.add(db_mod)
                                db.commit()
                    except Exception:
                        pass
            # 记录服务器安装关系
            try:
                crud.add_server_to_mod(db, db_mod.id, server_id)
            except Exception:
                pass
            # 如果 DB 中没有有用的 meta，尝试通过 Modrinth 填充并更新 DB
            if not skip_enrich and ((not meta) or (isinstance(meta, dict) and not meta.get('id'))):
                try:
                    m2 = await _try_fill_meta_from_modrinth_by_hash(fp)
                    if m2:
                        meta = m2
                        db_mod.meta = json.dumps(meta)
                        db.add(db_mod)
                        db.commit()
                except Exception:
                    pass
        else:
            # 尝试 Modrinth 通过哈希补全一次
            if not skip_enrich:
                try:
                    # 仅在没有 DB 记录时才计算哈希并外网查询
                    md5 = get_file_md5(fp)
                    meta = await _try_fill_meta_from_modrinth_by_hash(fp)
                except Exception as e:
                    logger.warning(f"Modrinth hash lookup failed for {fp.name}: {e}")
                    meta = None
                # 将结果写入 DB：若 meta 为空，则以 unknown 占位，避免后续重复补全
                from backend import schemas as _schemas
                rec = _schemas.ModDBCreate(
                    file_name=fp.name,
                    path=str(fp),
                    size=fp.stat().st_size,
                    hash_md5=get_file_md5(fp) if meta is None else get_file_md5(fp),
                    hash_sha256=get_file_sha256(fp) if meta is None else get_file_sha256(fp),
                    meta=meta if meta is not None else {'unknown': True},
                    url=None,
                )
                db_rec = crud.create_mod_record(db, rec)
                crud.add_server_to_mod(db, db_rec.id, server_id)

        items.append(_build_mod_item(fp, enabled, meta))

    return {'data': items}


@router.get('/mods/overview/{server_id}')
async def mods_overview(server_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    """提供 mods 目录的概览信息。"""
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    mods_dir = _mods_dir_for_server(server)

    # 读取 core_config
    import json as _json
    from backend.schemas import ServerCoreConfig
    core = ServerCoreConfig.model_validate(_json.loads(server.core_config))

    mods_count = len([f for f in os.listdir(mods_dir) if (mods_dir / f).is_file() and not f.startswith('.')])
    total_size = sum([(mods_dir / f).stat().st_size for f in os.listdir(mods_dir) if (mods_dir / f).is_file()], 0)

    # 计算加载器显示
    if core.server_type == 'forge':
        loader = 'forge'
    elif core.server_type == 'vanilla' and core.is_fabric:
        loader = 'fabric'
    elif core.server_type == 'vanilla' and not core.is_fabric:
        loader = '未安装'
    else:
        loader = core.server_type

    return {
        'storage_root': str(mods_dir),
        'mods_amount': mods_count,
        'total_size': total_size,
        'mc_version': core.core_version,
        'loader': loader,
        'loader_version': core.loader_version,
    }


@router.get('/mods/usage/total')
async def mods_usage_total(db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    """汇总所有服务器 mods 目录的总占用。"""
    servers = crud.get_all_servers(db)
    total = 0
    for s in servers:
        mods_dir = _mods_dir_for_server(s)
        try:
            total += sum((mods_dir / f).stat().st_size for f in os.listdir(mods_dir) if (mods_dir / f).is_file())
        except Exception:
            pass
    return {'bytes': int(total)}


@router.post('/mods/server/{server_id}/switch/{file_name}')
async def switch_mod(server_id: int, file_name: str, enable: Optional[bool] = None, db: Session = Depends(get_db),
                     _user=Depends(require_role(Role.ADMIN))):
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    mods_dir = _mods_dir_for_server(server)
    path = mods_dir / file_name
    if not path.exists():
        # 尝试规范化
        path = mods_dir / file_name.replace('.disabled', '')
        if not path.exists():
            path = mods_dir / (file_name + '.disabled')
            if not path.exists():
                raise HTTPException(status_code=404, detail=f"Mod file '{file_name}' not found.")

    is_enabled = not path.name.endswith('.disabled')
    if enable is None:
        enable = not is_enabled

    if enable and not is_enabled:
        target = path.with_name(path.name.removesuffix('.disabled'))
        path.rename(target)
        return {'file_name': target.name, 'enabled': True}
    elif not enable and is_enabled:
        target = path.with_name(path.name + '.disabled')
        path.rename(target)
        return {'file_name': target.name, 'enabled': False}
    return {'file_name': path.name, 'enabled': is_enabled}


@router.delete('/mods/server/{server_id}/{file_name}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_mod(server_id: int, file_name: str, db: Session = Depends(get_db),
                     _user=Depends(require_role(Role.ADMIN))):
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    mods_dir = _mods_dir_for_server(server)
    path = mods_dir / file_name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Mod file '{file_name}' not found")
    # 从 DB 关系中移除安装记录（如果存在）
    try:
        file_hash = get_file_md5(path)
        db_mod = crud.get_mod_by_hash(db, hash_md5=file_hash)
        if db_mod:
            crud.remove_server_from_mod(db, mod_id=db_mod.id, server_id=server.id)
    except Exception:
        pass

    try:
        os.remove(path)
        try:
            crud.delete_mod_by_path(db, str(path))
        except Exception:
            pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete mod file: {e}")
    return None


@router.get('/mods/download/{server_id}/{file_name}')
async def download_mod(server_id: int, file_name: str, db: Session = Depends(get_db),
                       _user=Depends(require_role(Role.USER))):
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    mods_dir = _mods_dir_for_server(server)
    requested_path = (mods_dir / file_name).resolve()
    if not requested_path.exists():
        raise HTTPException(status_code=404, detail='模组文件不存在')
    if not requested_path.is_file():
        raise HTTPException(status_code=400, detail='仅支持下载文件')
    return FileResponse(path=str(requested_path), filename=requested_path.name, media_type='application/octet-stream')


@router.post('/mods/upload/{server_id}')
async def upload_mod(server_id: int, file: UploadFile, db: Session = Depends(get_db),
                     _user=Depends(require_role(Role.ADMIN))):
    """上传本地模组到服务器 mods 目录，并写入元信息记录（若可识别）。"""
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    mods_dir = _mods_dir_for_server(server)

    # 安全化文件名
    filename = ''.join(c for c in file.filename or '' if c.isalnum() or c in '._-').strip() or 'mod.jar'
    temp_path = TEMP_PATH / f"upload_{os.urandom(6).hex()}_{filename}"
    target_path = mods_dir / filename

    try:
        content = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(content)
        shutil.move(temp_path, target_path)

        # 尝试Modrinth识别，记录到DB（若 path 存在则更新记录）
        meta = await _try_fill_meta_from_modrinth_by_hash(target_path)
        existing = crud.get_mod_by_path(db, str(target_path))
        md5 = get_file_md5(target_path)
        sha256 = get_file_sha256(target_path)
        if existing:
            crud.update_mod_record(db, existing,
                                   file_name=target_path.name,
                                   url=None,
                                   hash_md5=md5,
                                   hash_sha256=sha256,
                                   size=target_path.stat().st_size,
                                   meta=meta or {})
            crud.add_server_to_mod(db, existing.id, server_id)
        else:
            from backend import schemas as _schemas
            rec = _schemas.ModDBCreate(
                file_name=target_path.name,
                path=str(target_path),
                size=target_path.stat().st_size,
                hash_md5=md5,
                hash_sha256=sha256,
                meta=meta or {},
                url=None,
            )
            db_rec = crud.create_mod_record(db, rec)
            crud.add_server_to_mod(db, db_rec.id, server_id)
        return {'message': '上传成功', 'file_name': target_path.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'上传失败: {e}')
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except Exception:
                pass


class ModsCopyPayload(BaseModel):
    source_server_id: int
    target_server_id: int
    delete_target_before: bool = False


@router.post('/mods/copy')
async def copy_mods(
        payload: ModsCopyPayload,
        db: Session = Depends(get_db),
        _user=Depends(require_role(Role.ADMIN))
):
    """从一个服务器复制所有模组到另一个服务器。可选先清空目标。"""
    src = crud.get_server_by_id(db, payload.source_server_id)
    dst = crud.get_server_by_id(db, payload.target_server_id)
    if not src or not dst:
        raise HTTPException(status_code=404, detail='源或目标服务器不存在')

    # 类型匹配校验：不同类型（vanilla/fabric/forge/velocity）禁止互相复制
    try:
        import json as _json
        from backend.schemas import ServerCoreConfig
        sc = ServerCoreConfig.model_validate(_json.loads(src.core_config))
        dc = ServerCoreConfig.model_validate(_json.loads(dst.core_config))
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

    src_dir = _mods_dir_for_server(src)
    dst_dir = _mods_dir_for_server(dst)

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
        _user=Depends(require_role(Role.USER))
):
    """代理 Modrinth 搜索接口。简化版，仅支持 query + 可选版本/加载器过滤。"""
    base = 'https://api.modrinth.com/v2/search'
    # 根据参数/loader 推断项目类型：Velocity 走 plugin，其它默认 mod
    pt = (project_type or '').lower().strip() if project_type is not None else ''
    if not pt:
        pt = 'plugin' if (loader or '').lower().strip() == 'velocity' else 'mod'
    facets: List[List[str]] = [[f"project_type:{pt}"]]
    if loader and (loader or '').lower().strip() != 'velocity' and game_version:
        facets.append([f"versions:{game_version}"])
    if loader:
        # 在 modrinth 中，fabric/forge/velocity 等作为 categories 使用
        facets.append([f"categories:{loader}"])
    params = {
        'query': q,
        'limit': limit,
        'offset': offset,
        'facets': json.dumps(facets)
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(base, params=params)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


@router.get('/mods/modrinth/versions')
async def modrinth_versions(
        project_id: str,
        game_version: Optional[str] = None,
        loader: Optional[str] = None,
        _user=Depends(require_role(Role.USER))
):
    """代理 Modrinth 项目的版本列表，并可选过滤。"""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f'https://api.modrinth.com/v2/project/{project_id}/version')
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        versions = r.json()
        # 可选过滤
        if game_version or loader:
            filtered = []
            for v in versions:
                gv_ok = True if not game_version else (game_version in (v.get('game_versions') or []))
                ld_ok = True
                if loader:
                    ld_ok = loader in (v.get('loaders') or [])
                if gv_ok and ld_ok:
                    filtered.append(v)
            return filtered
        return versions


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
        _user=Depends(require_role(Role.ADMIN))
):
    server = crud.get_server_by_id(db, payload.server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    mods_dir = _mods_dir_for_server(server)
    old_path = mods_dir / payload.file_name
    if not old_path.exists():
        raise HTTPException(status_code=404, detail='Old mod file not found')

    # 保留启用/禁用状态
    is_disabled = old_path.name.endswith('.disabled')

    if payload.source == 'modrinth':
        if not payload.project_id or not payload.version_id:
            raise HTTPException(status_code=400, detail='project_id 和 version_id 为必填')
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            vr = await client.get(f'https://api.modrinth.com/v2/version/{payload.version_id}')
            if vr.status_code != 200:
                raise HTTPException(status_code=vr.status_code, detail=vr.text)
            ver = vr.json()
            # 校验兼容性
            from backend.schemas import ServerCoreConfig
            import json as _json
            core = ServerCoreConfig.model_validate(_json.loads(server.core_config))
            preferred_loader = (
            'forge' if core.server_type == 'forge' else (
                'fabric' if core.is_fabric else (
                    'velocity' if core.server_type == 'velocity' else None
                )
            )
        )
            gv = ver.get('game_versions') or []
            ld = ver.get('loaders') or []
            # Velocity 不校验 game_versions（核心版本是 Velocity 版本号，与 MC 版本不同）
            is_velocity = core.server_type == 'velocity'
            if ((not is_velocity) and core.core_version and core.core_version not in gv) or (preferred_loader and preferred_loader not in ld):
                raise HTTPException(status_code=409, detail='所选版本不兼容当前 MC 版本或加载器')
            files = ver.get('files') or []
            file_info = None
            for f in files:
                if (f.get('filename') or '').endswith('.jar'):
                    file_info = f
                    break
            if not file_info and files:
                file_info = files[0]
            if not file_info:
                raise HTTPException(status_code=400, detail='该版本没有可用的文件')

            download_url = file_info.get('url')
            new_filename = file_info.get('filename') or f"{payload.project_id}-{ver.get('version_number')}.jar"
            # 保留 .disabled 状态
            if is_disabled and not new_filename.endswith('.disabled'):
                new_filename = new_filename + '.disabled'
            tmp = TEMP_PATH / f"mod_{os.urandom(6).hex()}_{new_filename}"
            try:
                async with client.stream('GET', download_url) as resp:
                    resp.raise_for_status()
                    with open(tmp, 'wb') as out:
                        async for chunk in resp.aiter_bytes():
                            out.write(chunk)
                target = mods_dir / new_filename
                # 若目标存在则先删除，确保覆盖
                if target.exists():
                    try:
                        os.remove(target)
                        try:
                            crud.delete_mod_by_path(db, str(target))
                        except Exception:
                            pass
                    except Exception:
                        pass
                # 先保存新版本
                shutil.move(tmp, target)

                # 再删除老版本
                try:
                    if old_path.exists():
                        os.remove(old_path)
                        try:
                            crud.delete_mod_by_path(db, str(old_path))
                        except Exception:
                            pass
                except Exception:
                    pass

                # DB 记录迁移：旧记录移除安装，新文件入库并添加安装
                try:
                    old_md5 = get_file_md5(old_path) if old_path.exists() else None
                except Exception:
                    old_md5 = None
                if old_md5:
                    db_old = crud.get_mod_by_hash(db, hash_md5=old_md5)
                    if db_old:
                        crud.remove_server_from_mod(db, db_old.id, server.id)

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
                    'modrinth_version_id': payload.version_id,
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
                    crud.add_server_to_mod(db, existing.id, server.id)
                else:
                    from backend import schemas as _schemas
                    rec = _schemas.ModDBCreate(
                        file_name=target.name,
                        path=str(target),
                        size=target.stat().st_size,
                        hash_md5=md5,
                        hash_sha256=sha256,
                        meta=meta,
                        url=download_url,
                    )
                    db_new = crud.create_mod_record(db, rec)
                    crud.add_server_to_mod(db, db_new.id, server.id)

                return {'message': 'ok', 'file_name': target.name}
            finally:
                if tmp.exists():
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
    elif payload.source == 'curseforge':
        raise HTTPException(status_code=501, detail='Curseforge 更改版本暂未实现')
    else:
        raise HTTPException(status_code=400, detail='未知的来源')


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
        _user=Depends(require_role(Role.ADMIN))
):
    """从 Modrinth 安装某个项目的指定版本（或自动选择最新兼容版本）。"""
    # 兼容两种调用方式：JSON body 或 Query 参数
    if payload is None:
        if not server_id or not project_id:
            raise HTTPException(status_code=422, detail="server_id 和 project_id 不能为空")
        payload = ModrinthInstallPayload(server_id=server_id, project_id=project_id, version_id=version_id)

    server = crud.get_server_by_id(db, payload.server_id)
    if not server:
        raise HTTPException(status_code=404, detail='Server not found')
    import json as _json
    from backend.schemas import ServerCoreConfig
    core = ServerCoreConfig.model_validate(_json.loads(server.core_config))

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
                from backend import schemas as _schemas
                rec = _schemas.ModDBCreate(
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

            return {'message': '安装成功', 'file_name': target.name}
        finally:
            if tmp.exists():
                try:
                    os.remove(tmp)
                except Exception:
                    pass


async def _job_check_updates(server_id: int):
    from backend.schemas import ServerCoreConfig
    import json as _json
    async with httpx.AsyncClient(timeout=30) as client:
        with SessionLocal() as db:
            server = crud.get_server_by_id(db, server_id)
            if not server:
                return
            core = ServerCoreConfig.model_validate(_json.loads(server.core_config))
            preferred_loader = (
            'forge' if core.server_type == 'forge' else (
                'fabric' if core.is_fabric else (
                    'velocity' if core.server_type == 'velocity' else None
                )
            )
        )

            # 仅快速列举（跳过补全），减少开销
            mods = await list_server_mods(server_id, skip_enrich=True, db=db)  # type: ignore
            data = mods.get('data', [])

            for m in data:
                meta = m.get('meta') or {}
                if meta.get('source') != 'modrinth':
                    continue
                project_id = meta.get('modrinth_project_id') or meta.get('id')
                if not project_id:
                    continue
                r = await client.get(f'https://api.modrinth.com/v2/project/{project_id}/version')
                if r.status_code != 200:
                    continue
                versions = r.json() or []

                # 过滤匹配当前 MC 版本与加载器的版本，并按发布时间倒序择最新
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

                # 排序按 date_published 或者 id 顺序，优先 date_published
                def _sort_key(v):
                    return v.get('date_published') or v.get('version_number') or ''

                compat.sort(key=_sort_key, reverse=True)

                current_version = (meta.get('version') or '').strip()
                if compat:
                    latest_v = compat[0]
                    latest_number = latest_v.get('version_number')
                    latest_id = latest_v.get('id')
                    if latest_number and current_version and latest_number != current_version:
                        try:
                            file_hash = m.get('hash_md5') or get_file_md5(Path(m['path']))
                            db_mod = crud.get_mod_by_hash(db, hash_md5=file_hash) if file_hash else None
                            if db_mod:
                                mm = {}
                                try:
                                    mm = json.loads(db_mod.meta) if db_mod.meta else {}
                                except Exception:
                                    mm = {}
                                mm['modrinth_update_available'] = True
                                mm['modrinth_latest_version_number'] = latest_number
                                if latest_id:
                                    mm['modrinth_latest_version_id'] = latest_id
                                db_mod.meta = json.dumps(mm)
                                db.add(db_mod)
                                db.commit()
                        except Exception:
                            pass
                    else:
                        # 没有更新，清除标记
                        try:
                            file_hash = m.get('hash_md5') or get_file_md5(Path(m['path']))
                            db_mod = crud.get_mod_by_hash(db, hash_md5=file_hash) if file_hash else None
                            if db_mod:
                                mm = {}
                                try:
                                    mm = json.loads(db_mod.meta) if db_mod.meta else {}
                                except Exception:
                                    mm = {}
                                mm.pop('modrinth_update_available', None)
                                mm.pop('modrinth_latest_version_number', None)
                                mm.pop('modrinth_latest_version_id', None)
                                db_mod.meta = json.dumps(mm)
                                db.add(db_mod)
                                db.commit()
                        except Exception:
                            pass
                else:
                    # 不兼容：也清除更新标记
                    try:
                        file_hash = m.get('hash_md5') or get_file_md5(Path(m['path']))
                        db_mod = crud.get_mod_by_hash(db, hash_md5=file_hash) if file_hash else None
                        if db_mod:
                            mm = {}
                            try:
                                mm = json.loads(db_mod.meta) if db_mod.meta else {}
                            except Exception:
                                mm = {}
                            mm.pop('modrinth_update_available', None)
                            mm.pop('modrinth_latest_version_number', None)
                            mm.pop('modrinth_latest_version_id', None)
                            db_mod.meta = json.dumps(mm)
                            db.add(db_mod)
                            db.commit()
                    except Exception:
                        pass


@router.get('/mods/check-updates/{server_id}')
async def check_updates(server_id: int, background_tasks: BackgroundTasks, _user=Depends(require_role(Role.USER))):
    """将检查更新任务放入后台，立即返回提示前端稍后刷新。"""
    background_tasks.add_task(_job_check_updates, server_id)
    return {'status': 'accepted', 'message': '检查任务已开始，请稍后刷新'}
