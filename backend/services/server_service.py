# services/server_service.py
import json
import shutil
import asyncio
import uuid
from pathlib import Path
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException

from .task_manager import TaskManager
from .. import crud, models, schemas
from backend import server_parser
from backend.services.mcdr_manager import MCDRManager
from backend.services.plugin_manager import PluginManager
from ..core.config import MCDR_ROOT_PATH
from ..core.utils import get_size_mb, poll_copy_progress, copytree_resumable_throttled
from ..schemas import ServerCoreConfig, Task, TaskStatus
from ..server_parser import infer_server_type_and_analyze_core_config
from backend.logger import logger


class ServerService:
    def __init__(self, mcdr_manager: MCDRManager, plugin_manager: PluginManager):
        self.mcdr_manager = mcdr_manager
        self.plugin_manager = plugin_manager

    @staticmethod
    def _generate_server_path(server_name: str) -> Path:
        """根据服务器名称生成服务器路径"""
        safe_dirname = "".join(c if c.isalnum() or c in " _-" else "" for c in server_name).rstrip()
        if safe_dirname:
            return MCDR_ROOT_PATH / safe_dirname
        else:
            return MCDR_ROOT_PATH / str(uuid.uuid4())

    async def get_status(self, db_server: models.Server) -> Tuple[schemas.ServerStatus, int]:
        return await self.mcdr_manager.get_status(db_server.id, db_server.path)

    async def get_servers_with_details(self, db: Session) -> List[schemas.ServerDetail]:
        servers_from_db = crud.get_all_servers(db)

        tasks = []
        for server in servers_from_db:
            status_task = self.get_status(server)
            size_task = asyncio.to_thread(get_size_mb, server.path)
            tasks.append(asyncio.gather(status_task, size_task))
        results = await asyncio.gather(*tasks)
        server_details_list = []
        for i, server in enumerate(servers_from_db):
            status_res = results[i][0]  # status_task 的结果
            size_mb = results[i][1]  # size_task 的结果

            core_config = ServerCoreConfig.model_validate(json.loads(server.core_config))
            fs_details = server_parser.get_server_details(server.path, server_type=core_config.server_type)
            server_detail = schemas.ServerDetail(
                name=server.name,
                id=server.id,
                path=server.path,
                creator_id=server.creator_id,
                core_config=core_config,
                status=status_res[0],
                return_code=status_res[1],
                size_mb=size_mb,
                **fs_details,
            )
            server_details_list.append(server_detail)
        return server_details_list

    async def get_server_details_by_id(self, server_id: int, db: Session) -> schemas.ServerDetail:
        server = crud.get_server_by_id(db, server_id)
        return await self.get_server_details(server)

    async def get_server_details(self, db_server: models.Server):
        if not db_server:
            raise HTTPException(status_code=404, detail="Server not found")
        (status_res, size_mb) = await asyncio.gather(
            self.get_status(db_server),
            asyncio.to_thread(get_size_mb, db_server.path)
        )
        core_config = ServerCoreConfig.model_validate(json.loads(db_server.core_config))
        fs_details = server_parser.get_server_details(db_server.path, server_type=core_config.server_type)

        return schemas.ServerDetail(
            name=db_server.name,
            id=db_server.id,
            path=db_server.path,
            creator_id=db_server.creator_id,
            core_config=core_config,
            status=status_res[0],
            return_code=status_res[1],
            size_mb=size_mb,
            **fs_details,
        )

    async def create_server(self, server_create: schemas.ServerCreate, db: Session, user: models.User) -> models.Server:
        if crud.get_server_by_name(db, server_create.name):
            raise HTTPException(status_code=409, detail="A server with this name already exists.")

        server_path = self._generate_server_path(server_create.name)
        if server_path.exists():
            raise HTTPException(status_code=409, detail=f"The directory '{server_path}' already exists.")

        internal_server_model = schemas.ServerCreateInternal(name=server_create.name, path=str(server_path),
                                                             creator_id=user.id)
        db_server = crud.create_server(db, internal_server_model, creator_id=user.id)

        try:
            server_path.mkdir(parents=True, exist_ok=True)
            success, message = await self.mcdr_manager.initialize_server_files(db_server)
            if not success:
                crud.delete_server(db, db_server.id)
                shutil.rmtree(server_path, ignore_errors=True)
                raise HTTPException(status_code=500, detail=f"Failed to initialize server files: {message}")
            await self.mcdr_manager.notify_server_list_update(db_server, is_adding=True)
        except Exception as e:
            crud.delete_server(db, db_server.id)
            shutil.rmtree(server_path, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"An error occurred during server creation: {e}")

        return db_server

    async def delete_server(self, server_id: int, db: Session):
        db_server = crud.get_server_by_id(db, server_id)
        if not db_server:
            # Server might already be deleted from DB but folder exists. Proceed gracefully.
            logger.warning(f"ID 为 {server_id} 的服务器在数据库中未找到，跳过数据库清理。")
        else:
            st, _ = await self.mcdr_manager.get_status(server_id, db_server.path)
            if st == 'running':
                raise HTTPException(status_code=409, detail="Server is running. Please stop it before deletion.")

        server = crud.get_server_by_id(db, server_id)
        if not server:
            logger.warning(f"删除时在数据库中未找到服务器 {server_id}，直接返回。")
            return

        server_path_str = server.path

        crud.delete_server(db, server_id)
        self.mcdr_manager.processes.pop(server_id, None)
        self.mcdr_manager.return_code.pop(server_id, None)
        self.mcdr_manager.java_pid.pop(server_id, None)
        self.mcdr_manager.log_tasks.pop(server_id, None)
        await self.mcdr_manager.notify_server_list_update(server_details=db_server, is_adding=False)

        try:
            server_path = Path(server_path_str)
            if server_path.is_dir():
                shutil.rmtree(server_path)
        except Exception as e:
            logger.warning(f"已删除服务器 {server_id} 的数据库记录，但删除目录 {server_path_str} 失败：{e}")

    async def import_server(self, server_import: schemas.ServerImport, db: Session, user: models.User, task: Task,
                            task_manager: TaskManager) -> models.Server:

        progress_task = None
        try:
            source_path = Path(server_import.path).expanduser().resolve()
            if not source_path.is_dir():
                raise HTTPException(status_code=400, detail=f"提供的源路径 '{source_path}' 不是一个有效的目录。")
            if not (source_path / 'config.yml').is_file():
                raise HTTPException(status_code=400,
                                    detail=f"源路径 '{source_path}' 下未找到 'config.yml' 文件，请确保这是MCDR根目录。")

            if crud.get_server_by_name(db, server_import.name):
                raise HTTPException(status_code=409, detail=f"服务器名称 '{server_import.name}' 已存在。")
            target_path = self._generate_server_path(server_import.name)
            if target_path.exists():
                raise HTTPException(status_code=409,
                                    detail=f"目标目录 '{target_path}' 已存在，无法导入。")

            internal_server_model = schemas.ServerCreateInternal(name=server_import.name, path=str(target_path),
                                                                 creator_id=user.id)
            db_server = crud.create_server(db, internal_server_model, creator_id=user.id)

            try:
                progress_task = asyncio.create_task(
                    poll_copy_progress(source_path, target_path, task, interval=2.0)
                )
                # 受限速且可断点续传复制，默认 128MB/s，可通过环境变量 ASP_IMPORT_BWLIMIT_MBPS 覆盖
                await asyncio.to_thread(copytree_resumable_throttled, source_path, target_path)
                task.progress = 100
                crud.update_server_core_config(db, db_server.id, infer_server_type_and_analyze_core_config(db_server))
                return db_server
            except Exception as e:
                crud.delete_server(db, db_server.id)
                if target_path.exists():
                    shutil.rmtree(target_path)
                raise HTTPException(status_code=500,
                                    detail=f"从 '{source_path}' 复制文件到 '{target_path}' 时发生错误: {e}")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise e
        finally:
            task_manager.clear_finished_task(task.id)
            if progress_task:
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass

    async def get_server_plugins_info_by_id(self, server_id: int, db: Session) -> schemas.ServerPlugins:
        server = crud.get_server_by_id(db, server_id)
        if server is None:
            raise HTTPException(status_code=404, detail=f'未找到服务器')
        return self.plugin_manager.get_plugins_info(Path(server.path) / 'plugins')
