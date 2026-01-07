# backend/routers/plugins.py

import json
import os
import shutil
import time
import uuid
from fastapi import APIRouter, Depends, UploadFile, HTTPException, status, Response, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional, List

from backend.core.api import get_mcdr_plugins_catalogue
from backend.core import crud, schemas
from backend.core.auth import require_role
from backend.core.schemas import Role
from backend.core.constants import UPLOADED_PLUGINS_PATH
from backend.core.utils import get_file_md5, get_file_sha256
from backend.core.database import get_db, SessionLocal
from backend.core.dependencies import server_service, plugin_manager
from backend.core.logger import logger

router = APIRouter(
    prefix="/api",
    tags=["Plugins"],
)


@router.get("/plugins/mcdr/versions", response_model=schemas.PluginCatalogue)
async def get_mcdr_catalogue(do_refresh=False, _user=Depends(require_role(Role.HELPER))):
    """获取 MCDR 官方插件市场目录"""
    _r = time.time() if do_refresh else None
    catalogue_data = await get_mcdr_plugins_catalogue(_r)
    return schemas.PluginCatalogue.model_validate(catalogue_data)


@router.get("/plugins/server/{server_id}", response_model=schemas.ServerPlugins)
async def get_server_plugins(server_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.HELPER))):
    """获取指定服务器已安装的插件列表"""
    catalogue = await get_mcdr_catalogue()
    server_plugins = await server_service.get_server_plugins_info_by_id(server_id, db)
    for plugin in server_plugins.data:
        if plugin.meta.get("id") not in catalogue.plugins:
            # logger.info(f"查找{plugin.meta.get("id") or plugin.file_name}： {plugin.hash_md5}")
            db_plugin = crud.get_plugin_by_hash(db, plugin.hash_md5)
            if db_plugin is not None:
                crud.add_server_to_plugin(db, db_plugin.id, server_id)
    return server_plugins


@router.post(
    "/plugins/server/{server_id}/install/from-online",
    status_code=status.HTTP_202_ACCEPTED
)
async def install_plugin_from_online(
        server_id: int,
        plugin_id: str = Query(...),
        tag_name: str = Query("latest"),
        db: Session = Depends(get_db),
        _user=Depends(require_role(Role.HELPER))
):
    """
    从 MCDR 官方市场安装插件，返回任务 ID 供前端跟踪进度。
    """
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    catalogue = await get_mcdr_catalogue()
    if plugin_id not in catalogue.plugins:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found in catalogue.")
    
    task = plugin_manager.start_install_plugin_task(
        server_id=server.id,
        server_name=server.name,
        plugin_id=plugin_id,
        tag_name=tag_name,
        mcdr_plugins_catalogue=catalogue,
        get_server_by_id_func=crud.get_server_by_id,
        db_session_factory=SessionLocal
    )
    return {"message": f"Plugin installation for '{plugin_id}' has been started.", "task_id": task.id}


@router.post("/plugins/upload", response_model=schemas.PluginDBRecord)
async def upload_plugin(file: UploadFile, db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    """上传插件到中央仓库"""
    storage_path, meta = await plugin_manager.save_uploaded_plugin(file)

    # 检查插件是否已存在 (基于hash)
    existing_plugin = crud.get_plugin_by_hash(db, hash_md5=get_file_md5(storage_path))
    if existing_plugin:
        return existing_plugin

    # 创建新的数据库记录
    plugin_create = schemas.PluginDBCreate(
        file_name=file.filename,
        path=str(storage_path),
        size=storage_path.stat().st_size,
        hash_md5=get_file_md5(storage_path),
        hash_sha256=get_file_sha256(storage_path),
        meta=meta
    )
    db_plugin = crud.create_plugin_record(db, plugin_create)
    return db_plugin


@router.get("/plugins/db", response_model=List[schemas.PluginDBRecord])
def get_db_plugins(db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    """获取中央仓库中的所有插件"""
    return crud.get_all_plugins(db)


@router.post("/plugins/server/{server_id}/install/from-db/{plugin_db_id}", status_code=status.HTTP_201_CREATED)
async def install_plugin_from_db(server_id: int, plugin_db_id: int, db: Session = Depends(get_db),
                                 _user=Depends(require_role(Role.HELPER))):
    """从中央仓库安装插件到服务器"""
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    plugin_record = crud.get_plugin_by_id(db, plugin_db_id)
    if not plugin_record:
        raise HTTPException(status_code=404, detail="Plugin not found in DB.")

    source_path = Path(plugin_record.path)
    if not source_path.exists():
        crud.delete_plugin_record(db, plugin_db_id)  # 文件丢失，清理脏数据
        raise HTTPException(status_code=404, detail="Plugin file is missing from storage. Record cleaned.")

    installed_path = plugin_manager.install_from_local_path(
        server_path=Path(server.path),
        source_path=source_path,
        file_name=plugin_record.file_name
    )

    # 关联服务器和插件
    crud.add_server_to_plugin(db, plugin_db_id, server_id)

    return {"message": "Plugin installed successfully from DB.", "path": str(installed_path)}


@router.post("/plugins/server/{server_id}/switch/{file_name}")
async def switch_server_plugin(server_id: int, file_name: str, enable: Optional[bool] = None,
                               db: Session = Depends(get_db), _user=Depends(require_role(Role.HELPER))):
    """启用/禁用服务器上的一个插件"""
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    new_path, new_status = plugin_manager.switch_plugin(
        server_path=Path(server.path),
        file_name=file_name,
        enable=enable
    )
    return {"message": "Plugin status changed.", "file_name": new_path.name, "enabled": new_status}


@router.delete("/plugins/server/{server_id}/{file_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server_plugin(server_id: int, file_name: str, db: Session = Depends(get_db),
                               _user=Depends(require_role(Role.HELPER))):
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    server_path = Path(server.path)
    plugin_path = server_path / "plugins" / file_name
    if not plugin_path.is_file():
        raise HTTPException(status_code=404, detail=f"Plugin file '{file_name}' not found on server")
    try:
        file_hash = get_file_md5(plugin_path)
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Could not read plugin file to calculate hash: {e}")
    db_plugin = crud.get_plugin_by_hash(db, hash_md5=file_hash)
    if db_plugin:
        crud.remove_server_from_plugin(db, plugin_id=db_plugin.id, server_id=server.id)
    try:
        plugin_manager.delete_plugin(Path(server.path), file_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plugin file from filesystem: {e}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/plugins/db/{plugin_db_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_db_plugin(plugin_db_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.HELPER))):
    """从中央仓库删除一个插件"""
    plugin_record = crud.get_plugin_by_id(db, plugin_db_id)
    if not plugin_record:
        raise HTTPException(status_code=404, detail="Plugin not found in DB.")

    # 检查插件是否仍被服务器使用
    if plugin_record.servers_installed and (js := json.loads(plugin_record.servers_installed)):
        flag = any(crud.get_server_by_id(db, sid) for sid in js)
        if flag:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Plugin is still installed on servers (IDs: {plugin_record.servers_installed}). Please uninstall it from them first."
            )

    # 删除物理文件
    file_path = Path(plugin_record.path)
    if file_path.exists():
        try:
            os.remove(file_path)
        except OSError as e:
            # 即使文件删除失败，也继续删除数据库记录，但要发出警告
            logger.warning(f"删除插件文件失败 {file_path}：{e}")

    # 删除数据库记录
    crud.delete_plugin_record(db, plugin_db_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/plugins/download/{server_id}/{file_name}")
async def download_plugin_file(
        server_id: int,
        file_name: str,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        _user=Depends(require_role(Role.HELPER))
):
    """
    下载服务器上指定名称的插件（文件或目录）。
    - 自动处理路径遍历安全问题。
    - 如果是目录，则动态压缩为 .zip 文件后提供下载。
    """
    db_server = crud.get_server_by_id(db, server_id)
    if not db_server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    # --- 安全性修复：防止路径遍历 ---
    # 1. 定义安全的根目录
    plugins_dir = Path(db_server.path) / "plugins"

    # 2. 解析请求的文件路径
    requested_path = plugins_dir.joinpath(file_name).resolve()
    # 3. 验证解析后的路径是否仍在安全的根目录内
    if not requested_path.is_relative_to(plugins_dir.resolve()):
        raise HTTPException(status_code=403, detail="禁止访问的路径")
    if not requested_path.exists():
        raise HTTPException(status_code=404, detail="插件文件或目录不存在")
    # --- 逻辑修正 ---
    if requested_path.is_file():
        # 为 .py 文件使用 text/plain，为其他所有文件使用通用的二进制流类型
        media_type = 'text/plain' if file_name.lower().endswith(".py") else 'application/octet-stream'
        return FileResponse(
            path=str(requested_path),
            filename=file_name,
            media_type=media_type
        )
    elif requested_path.is_dir():
        temp_dir = UPLOADED_PLUGINS_PATH / "temp_downloads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        # 创建一个唯一的临时文件名，避免冲突
        zip_basename = temp_dir / f"{file_name}_{uuid.uuid4().hex}"
        try:
            # 正确使用 shutil.make_archive 来压缩目录内容
            zip_path_str = shutil.make_archive(
                base_name=str(zip_basename),
                format='zip',
                root_dir=str(requested_path)  # 将要压缩的目录设为根目录
            )
            zip_path = Path(zip_path_str)

            # 使用后台任务在响应发送后删除临时 zip 文件
            background_tasks.add_task(os.remove, zip_path)
            return FileResponse(
                path=str(zip_path),
                filename=f"{file_name}.zip",  # 修正文件名
                media_type='application/zip'
            )
        except Exception as e:
            # 记录详细错误日志会更好
            # logger.error(f"Failed to create archive for {requested_path}: {e}")
            raise HTTPException(status_code=500, detail="创建插件压缩包失败")

    else:
        # 如果路径存在但既不是文件也不是目录（例如符号链接），也返回404
        raise HTTPException(status_code=404, detail="请求的路径类型不受支持")
