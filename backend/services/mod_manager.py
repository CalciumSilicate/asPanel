# backend/services/mod_manager.py

import json
import os
import shutil
import httpx
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core import crud, models, schemas as _schemas
from backend.core.constants import TEMP_PATH
from backend.core.logger import logger
from backend.core.utils import (
    get_file_md5,
    get_file_sha256,
    get_file_sha1,
    get_size_bytes,
)
from backend.core.database import SessionLocal


class ModManager:
    """模组管理服务：承载 mods 相关的主要业务逻辑。

    目标：将 backend/routers/mods.py 中的大部分实现抽离到服务层，保持 API 不变，路由仅负责参数解析与鉴权。
    """

    # ---------- 路径与通用构件 ----------
    @staticmethod
    def mods_dir_for_server(server: Any) -> Path:
        """根据服务器核心类型决定模组所在目录（Velocity 使用 plugins）。"""
        try:
            from backend.core.schemas import ServerCoreConfig
            core = ServerCoreConfig.model_validate(json.loads(server.core_config))
            if core.server_type == 'velocity':
                p = Path(server.path) / 'server' / 'plugins'
            else:
                p = Path(server.path) / 'server' / 'mods'
        except Exception:
            p = Path(server.path) / 'server' / 'mods'
        p.mkdir(exist_ok=True, parents=True)
        return p

    @staticmethod
    def build_mod_item(file_path: Path, enabled: bool, meta: Dict[str, Any] | None,
                       hash_md5: Optional[str] = None, hash_sha256: Optional[str] = None) -> Dict[str, Any]:
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

    # ---------- Modrinth 元数据补全 ----------
    @staticmethod
    async def try_fill_meta_from_modrinth_by_hash(file_path: Path) -> Dict[str, Any] | None:
        """通过 Modrinth 的文件哈希匹配接口补全元数据。"""
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

    # ---------- 列表与概览 ----------
    async def list_server_mods(self, server: Any, db: Session, *, skip_enrich: bool = False) -> Dict[str, Any]:
        mods_dir = self.mods_dir_for_server(server)
        items: List[Dict[str, Any]] = []

        with os.scandir(mods_dir) as it:
            for entry in it:
                if entry.name.startswith('.'):
                    continue
                if not entry.is_file():
                    continue

                fp = Path(entry.path)
                enabled = not fp.name.endswith('.disabled')

                # 优先根据 path 命中 DB，避免不必要的哈希/外网查询
                db_mod = db.query(models.Mod).filter(models.Mod.path == str(fp.resolve())).first()
                meta: Dict[str, Any] | None = None

                if db_mod:
                    try:
                        meta = json.loads(db_mod.meta) if db_mod.meta else {}
                    except JSONDecodeError:
                        meta = {}

                    # 标记为 unknown 则不再补全，直接入结果并维护安装关系
                    if isinstance(meta, dict) and meta.get('unknown') is True:
                        try:
                            crud.add_server_to_mod(db, db_mod.id, server.id)
                        except Exception:
                            pass
                        items.append(self.build_mod_item(fp, enabled, {}))
                        continue

                    # 若为 modrinth 且缺少 slug，尽力补全并落 DB
                    if (not skip_enrich) and isinstance(meta, dict) and meta.get('source') == 'modrinth' and (
                            not meta.get('slug')):
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
                        crud.add_server_to_mod(db, db_mod.id, server.id)
                    except Exception:
                        pass

                    # 若 DB 中 meta 为空或缺少 id，尝试通过 Modrinth 进一步补全
                    if not skip_enrich and ((not meta) or (isinstance(meta, dict) and not meta.get('id'))):
                        try:
                            m2 = await self.try_fill_meta_from_modrinth_by_hash(fp)
                            if m2:
                                meta = m2
                                db_mod.meta = json.dumps(meta)
                                db.add(db_mod)
                                db.commit()
                        except Exception:
                            pass

                else:
                    # 首次见到该文件：可选补全 + 建库
                    if not skip_enrich:
                        try:
                            _ = get_file_md5(fp)  # 触发读取，异常时捕获
                            meta = await self.try_fill_meta_from_modrinth_by_hash(fp)
                        except Exception as e:
                            logger.warning(f"Modrinth hash lookup failed for {fp.name}: {e}")
                            meta = None

                    rec = _schemas.ModDBCreate(
                        file_name=fp.name,
                        path=str(fp),
                        size=fp.stat().st_size,
                        hash_md5=get_file_md5(fp),
                        hash_sha256=get_file_sha256(fp),
                        meta=meta if meta is not None else {'unknown': True},
                        url=None,
                    )
                    db_rec = crud.create_mod_record(db, rec)
                    crud.add_server_to_mod(db, db_rec.id, server.id)

                items.append(self.build_mod_item(fp, enabled, meta))

        return {'data': items}

    def overview(self, server: Any) -> Dict[str, Any]:
        mods_dir = self.mods_dir_for_server(server)
        from backend.core.schemas import ServerCoreConfig
        core = ServerCoreConfig.model_validate(json.loads(server.core_config))

        mods_count = len([f for f in os.listdir(mods_dir) if (mods_dir / f).is_file() and not f.startswith('.')])
        total_size = sum([(mods_dir / f).stat().st_size for f in os.listdir(mods_dir) if (mods_dir / f).is_file()], 0)

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

    def usage_total(self, db: Session) -> Dict[str, int]:
        servers = crud.get_all_servers(db)
        total = 0
        for s in servers:
            mods_dir = self.mods_dir_for_server(s)
            try:
                total += sum((mods_dir / f).stat().st_size for f in os.listdir(mods_dir) if (mods_dir / f).is_file())
            except Exception:
                pass
        return {'bytes': int(total)}

    # ---------- 文件操作 ----------
    def switch_mod(self, server: Any, file_name: str, enable: Optional[bool] = None) -> Dict[str, Any]:
        mods_dir = self.mods_dir_for_server(server)
        path = mods_dir / file_name
        if not path.exists():
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

    def delete_mod(self, server: Any, file_name: str, db: Session) -> None:
        mods_dir = self.mods_dir_for_server(server)
        path = mods_dir / file_name
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Mod file '{file_name}' not found")

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

    def get_download_path(self, server: Any, file_name: str) -> Path:
        mods_dir = self.mods_dir_for_server(server)
        requested_path = (mods_dir / file_name).resolve()
        if not requested_path.exists():
            raise HTTPException(status_code=404, detail='模组文件不存在')
        if not requested_path.is_file():
            raise HTTPException(status_code=400, detail='仅支持下载文件')
        return requested_path

    async def upload_mod(self, server: Any, file: UploadFile, db: Session) -> Dict[str, Any]:
        mods_dir = self.mods_dir_for_server(server)
        filename = ''.join(c for c in (file.filename or '') if c.isalnum() or c in '._-').strip() or 'mod.jar'
        temp_path = TEMP_PATH / f"upload_{os.urandom(6).hex()}_{filename}"
        target_path = mods_dir / filename

        try:
            content = await file.read()
            with open(temp_path, 'wb') as f:
                f.write(content)
            shutil.move(temp_path, target_path)

            meta = await self.try_fill_meta_from_modrinth_by_hash(target_path)
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
                crud.add_server_to_mod(db, existing.id, server.id)
            else:
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
                crud.add_server_to_mod(db, db_rec.id, server.id)
            return {'message': '上传成功', 'file_name': target_path.name}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'上传失败: {e}')
        finally:
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    # ---------- 远端 API 代理与版本变更 ----------
    async def search_modrinth(self, q: str, *, limit: int = 20, offset: int = 0,
                              game_version: Optional[str] = None, loader: Optional[str] = None,
                              project_type: Optional[str] = None):
        base = 'https://api.modrinth.com/v2/search'
        pt = (project_type or '').lower().strip() if project_type is not None else ''
        if not pt:
            pt = 'plugin' if (loader or '').lower().strip() == 'velocity' else 'mod'
        facets: List[List[str]] = [[f"project_type:{pt}"]]
        if loader and (loader or '').lower().strip() != 'velocity' and game_version:
            facets.append([f"versions:{game_version}"])
        if loader:
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

    async def modrinth_versions(self, project_id: str, *, game_version: Optional[str] = None,
                                loader: Optional[str] = None):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f'https://api.modrinth.com/v2/project/{project_id}/version')
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=r.text)
            versions = r.json()
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

    async def change_version(self, server: Any, *, file_name: str, source: str,
                              project_id: Optional[str], version_id: Optional[str], db: Session) -> Dict[str, Any]:
        mods_dir = self.mods_dir_for_server(server)
        old_path = mods_dir / file_name
        if not old_path.exists():
            raise HTTPException(status_code=404, detail='Old mod file not found')

        is_disabled = old_path.name.endswith('.disabled')

        if source == 'modrinth':
            if not project_id or not version_id:
                raise HTTPException(status_code=400, detail='project_id 和 version_id 为必填')
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                vr = await client.get(f'https://api.modrinth.com/v2/version/{version_id}')
                if vr.status_code != 200:
                    raise HTTPException(status_code=vr.status_code, detail=vr.text)
                ver = vr.json()
                from backend.core.schemas import ServerCoreConfig
                core = ServerCoreConfig.model_validate(json.loads(server.core_config))
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
                if ((not is_velocity) and core.core_version and core.core_version not in gv) or (
                        preferred_loader and preferred_loader not in ld):
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
                new_filename = file_info.get('filename') or f"{project_id}-{ver.get('version_number')}.jar"
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
                    if target.exists():
                        try:
                            os.remove(target)
                            try:
                                crud.delete_mod_by_path(db, str(target))
                            except Exception:
                                pass
                        except Exception:
                            pass
                    shutil.move(tmp, target)

                    try:
                        if old_path.exists():
                            os.remove(old_path)
                            try:
                                crud.delete_mod_by_path(db, str(old_path))
                            except Exception:
                                pass
                    except Exception:
                        pass

                    try:
                        old_md5 = get_file_md5(old_path) if old_path.exists() else None
                    except Exception:
                        old_md5 = None
                    if old_md5:
                        db_old = crud.get_mod_by_hash(db, hash_md5=old_md5)
                        if db_old:
                            crud.remove_server_from_mod(db, db_old.id, server.id)

                    # 获取项目 slug
                    project_slug = None
                    try:
                        pr = await client.get(f'https://api.modrinth.com/v2/project/{project_id}')
                        if pr.status_code == 200:
                            project_slug = (pr.json() or {}).get('slug')
                    except Exception:
                        project_slug = None

                    meta = {
                        'source': 'modrinth',
                        'modrinth_project_id': project_id,
                        'modrinth_version_id': ver.get('id'),
                        'id': project_id,
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
                        crud.add_server_to_mod(db, db_rec.id, server.id)

                    return {'message': '安装成功', 'file_name': target.name}
                finally:
                    if tmp.exists():
                        try:
                            os.remove(tmp)
                        except Exception:
                            pass

        raise HTTPException(status_code=400, detail='不支持的 source')

    # ---------- 后台任务 ----------
    async def check_updates_background(self, server_id: int):
        from backend.core.schemas import ServerCoreConfig
        async with httpx.AsyncClient(timeout=30) as client:
            with SessionLocal() as db:
                server = crud.get_server_by_id(db, server_id)
                if not server:
                    return
                core = ServerCoreConfig.model_validate(json.loads(server.core_config))
                preferred_loader = (
                    'forge' if core.server_type == 'forge' else (
                        'fabric' if core.is_fabric else (
                            'velocity' if core.server_type == 'velocity' else None
                        )
                    )
                )

                # 仅快速列举（跳过补全），减少开销
                mods = await self.list_server_mods(server, db=db, skip_enrich=True)  # type: ignore
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

