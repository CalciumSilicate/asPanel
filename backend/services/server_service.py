# backend/services/server_service.py

import json
import shutil
import asyncio
import time
import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List, Tuple, Optional

from backend.services.task_manager import TaskManager
from backend.core import crud, models, schemas
from backend.tools import server_parser
from backend.services.mcdr_manager import MCDRManager
from backend.services.plugin_manager import PluginManager
from backend.services.mod_manager import ModManager
from backend.core.database import get_db_context
from backend.core.constants import MCDR_ROOT_PATH
from backend.core.utils import get_size_mb, poll_copy_progress, copytree_resumable_throttled
from backend.core.schemas import ServerCoreConfig, Task, TaskStatus, TaskType
from backend.tools.server_parser import infer_server_type_and_analyze_core_config
from backend.core.logger import logger
from backend.services import player_manager


class ServerService:
    def __init__(self, mcdr_manager: MCDRManager, plugin_manager: PluginManager, mod_manager: ModManager, task_manager: TaskManager):
        self.mcdr_manager = mcdr_manager
        self.plugin_manager = plugin_manager
        self.mod_manager = mod_manager
        self.task_manager = task_manager

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

    async def get_servers_list(self, db: Session) -> List[schemas.ServerDetail]:
        """快速获取服务器列表（不计算目录大小、不统计 mods）。"""
        servers_from_db = crud.get_all_servers(db)
        if not servers_from_db:
            return []

        status_tasks = [self.get_status(server) for server in servers_from_db]
        plugins_count_tasks = [self.get_server_plugin_count(server) for server in servers_from_db]

        core_configs: List[ServerCoreConfig] = []
        fs_tasks = []
        for server in servers_from_db:
            try:
                if hasattr(ServerCoreConfig, "model_validate_json"):
                    core_config = ServerCoreConfig.model_validate_json(server.core_config)  # type: ignore[attr-defined]
                else:
                    core_config = ServerCoreConfig.model_validate(json.loads(server.core_config))
            except Exception:
                core_config = ServerCoreConfig()
            core_configs.append(core_config)
            fs_tasks.append(asyncio.to_thread(
                server_parser.get_server_details,
                server.path,
                core_config.server_type,
            ))

        statuses, plugins_counts, fs_details_list = await asyncio.gather(
            asyncio.gather(*status_tasks),
            asyncio.gather(*plugins_count_tasks),
            asyncio.gather(*fs_tasks),
        )

        server_details_list: List[schemas.ServerDetail] = []
        for i, server in enumerate(servers_from_db):
            status_res = statuses[i]
            plugins_count = plugins_counts[i]
            fs_details = fs_details_list[i] if isinstance(fs_details_list[i], dict) else {}
            server_detail = schemas.ServerDetail(
                name=server.name,
                id=server.id,
                path=server.path,
                creator_id=server.creator_id,
                core_config=core_configs[i],
                map=getattr(server, "map", None),
                status=status_res[0],
                return_code=status_res[1],
                size_mb=None,
                plugins_count=plugins_count,
                mods_count=None,
                **fs_details,
            )
            server_details_list.append(server_detail)
        return server_details_list

    async def get_servers_with_details(self, db: Session) -> List[schemas.ServerDetail]:
        servers_from_db = crud.get_all_servers(db)

        tasks = []
        status_result = []
        for server in servers_from_db:
            status = await self.get_status(server)
            status_result.append(status)
            if status[0] in ["stopped", "error"]:
                r_ = None
            else:
                r_ = time.time()
            size_task = asyncio.to_thread(get_size_mb, server.path, r_)
            plugins_count_task = self.get_server_plugin_count(server)
            mod_overview_task = asyncio.to_thread(self.mod_manager.overview, server)
            tasks.append(asyncio.gather(size_task, plugins_count_task, mod_overview_task))
        results = await asyncio.gather(*tasks)
        server_details_list = []
        for i, server in enumerate(servers_from_db):
            status_res = status_result[i]  # status_task 的结果
            size_mb = results[i][0]  # size_task 的结果
            plugins_count = results[i][1]  # plugins_count_task 的结果
            mod_amount = results[i][2].get("mods_amount")  # mod_overview_task 的结果

            core_config = ServerCoreConfig.model_validate(json.loads(server.core_config))
            fs_details = server_parser.get_server_details(server.path, server_type=core_config.server_type)
            server_detail = schemas.ServerDetail(
                name=server.name,
                id=server.id,
                path=server.path,
                creator_id=server.creator_id,
                core_config=core_config,
                map=getattr(server, "map", None),
                status=status_res[0],
                return_code=status_res[1],
                size_mb=size_mb,
                plugins_count=plugins_count,
                mods_count=mod_amount,
                **fs_details,
            )
            server_details_list.append(server_detail)
        return server_details_list

    async def get_servers_sizes(self, db: Session) -> List[schemas.ServerSize]:
        """获取所有服务器目录大小。

        - 默认使用 get_size_mb 的进程内缓存
        - 仅对运行中的服务器绕过缓存（更接近实时大小）
        """
        servers_from_db = crud.get_all_servers(db)
        if not servers_from_db:
            return []

        statuses = await asyncio.gather(*[self.get_status(server) for server in servers_from_db])

        async def _calc(server: models.Server, status: tuple[schemas.ServerStatus, int]) -> Optional[schemas.ServerSize]:
            try:
                is_running = status[0] == schemas.ServerStatus.RUNNING
                if is_running:
                    size_mb = await asyncio.to_thread(get_size_mb, server.path, time.time())
                else:
                    size_mb = await asyncio.to_thread(get_size_mb, server.path)
                return schemas.ServerSize(id=server.id, size_mb=size_mb)
            except Exception:
                return None

        results = await asyncio.gather(*[_calc(s, statuses[i]) for i, s in enumerate(servers_from_db)])
        return [r for r in results if r is not None]

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
            map=getattr(db_server, "map", None),
            status=status_res[0],
            return_code=status_res[1],
            size_mb=size_mb,
            plugins_count=(await self.get_server_plugin_count(db_server)),
            mods_count=self.mod_manager.overview(db_server).get("mods_amount"),
            **fs_details,
        )

    async def start_create_server_task(self, server_create: schemas.ServerCreate, creator_id: int) -> Task:
        # 轻量校验：名称重复 / 目标目录已存在（避免创建后立刻失败的任务）
        with get_db_context() as db:
            if crud.get_server_by_name(db, server_create.name):
                raise HTTPException(status_code=409, detail="A server with this name already exists.")
        safe_dirname = "".join(c if c.isalnum() or c in " _-" else "" for c in server_create.name).rstrip()
        if safe_dirname:
            target = MCDR_ROOT_PATH / safe_dirname
            if target.exists():
                raise HTTPException(status_code=409, detail=f"The directory '{target}' already exists.")

        task = self.task_manager.create_task(
            TaskType.CREATE_SERVER,
            name="创建服务器",
            message=f"服务器：{server_create.name}",
        )

        async def _runner():
            try:
                with get_db_context() as db:
                    await self.create_server(server_create, db, creator_id, task=task)
            except Exception as e:
                # create_server 内部会做回滚与清理；这里只做任务状态标记
                task.status = TaskStatus.FAILED
                task.error = str(getattr(e, "detail", e))
                task.message = f"服务器：{server_create.name}"
            finally:
                try:
                    self.task_manager.clear_finished_task(task.id)
                except Exception:
                    pass

        asyncio.create_task(_runner())
        return task

    async def create_server(
            self,
            server_create: schemas.ServerCreate,
            db: Session,
            creator_id: int,
            *,
            task: Optional[Task] = None,
    ) -> models.Server:
        if crud.get_server_by_name(db, server_create.name):
            raise HTTPException(status_code=409, detail="A server with this name already exists.")

        server_path = self._generate_server_path(server_create.name)
        if server_path.exists():
            raise HTTPException(status_code=409, detail=f"The directory '{server_path}' already exists.")

        if task:
            task.status = TaskStatus.RUNNING
            task.progress = 5
            task.message = f"服务器：{server_create.name} | 创建中..."

        internal_server_model = schemas.ServerCreateInternal(name=server_create.name, path=str(server_path),
                                                             creator_id=creator_id)
        db_server = crud.create_server(db, internal_server_model, creator_id=creator_id)

        try:
            if task:
                task.progress = 15
                task.message = f"服务器：{server_create.name} | 初始化目录..."
            server_path.mkdir(parents=True, exist_ok=True)
            if task:
                task.progress = 25
                task.message = f"服务器：{server_create.name} | 初始化 MCDR..."
            success, message = await self.mcdr_manager.initialize_server_files(db_server)
            if not success:
                crud.delete_server(db, db_server.id)
                await asyncio.to_thread(shutil.rmtree, server_path, ignore_errors=True)
                raise HTTPException(status_code=500, detail=f"Failed to initialize server files: {message}")
            if task:
                task.progress = 80
                task.message = f"服务器：{server_create.name} | 同步面板状态..."
            await self.mcdr_manager.notify_server_list_update(db_server, is_adding=True)
            # 玩家游玩时长映射：创建服务器后，为所有玩家添加 {server_name: 0}（当 world 存在时）
            try:
                server_name = Path(db_server.path).name
                player_manager.on_server_created(server_name, db_server.path)
            except Exception:
                pass
            # 将服务器添加到指定的服务器组
            if server_create.server_link_group_ids:
                try:
                    crud.add_server_to_groups(db, db_server.id, server_create.server_link_group_ids)
                except Exception:
                    pass
            if task:
                task.status = TaskStatus.SUCCESS
                task.progress = 100
                task.message = f"服务器：{server_create.name}"
        except Exception as e:
            crud.delete_server(db, db_server.id)
            await asyncio.to_thread(shutil.rmtree, server_path, ignore_errors=True)
            if task:
                task.status = TaskStatus.FAILED
                task.error = str(getattr(e, "detail", e))
                task.message = f"服务器：{server_create.name}"
            raise HTTPException(status_code=500, detail=f"An error occurred during server creation: {e}")

        return db_server

    async def start_delete_server_task(self, server_id: int) -> Task:
        # 校验：存在 + 不在运行中
        with get_db_context() as db:
            db_server = crud.get_server_by_id(db, server_id)
            if not db_server:
                raise HTTPException(status_code=404, detail="Server not found")
            server_name = db_server.name
            server_path_str = db_server.path

        st, _ = await self.mcdr_manager.get_status(server_id, server_path_str)
        if st == 'running':
            raise HTTPException(status_code=409, detail="Server is running. Please stop it before deletion.")

        task = self.task_manager.create_task(
            TaskType.DELETE_SERVER,
            name="删除服务器",
            message=f"服务器：{server_name}",
        )

        async def _runner():
            try:
                with get_db_context() as db:
                    await self.delete_server(server_id, db, task=task)
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(getattr(e, "detail", e))
                task.message = f"服务器：{server_name}"
            finally:
                try:
                    self.task_manager.clear_finished_task(task.id)
                except Exception:
                    pass

        asyncio.create_task(_runner())
        return task

    async def delete_server(self, server_id: int, db: Session, *, task: Optional[Task] = None):
        db_server = crud.get_server_by_id(db, server_id)
        if not db_server:
            # Server might already be deleted from DB but folder exists. Proceed gracefully.
            logger.warning(f"ID 为 {server_id} 的服务器在数据库中未找到，跳过数据库清理。")
        else:
            if task:
                task.status = TaskStatus.RUNNING
                task.progress = 5
                task.message = f"服务器：{db_server.name} | 删除中..."
            st, _ = await self.mcdr_manager.get_status(server_id, db_server.path)
            if st == 'running':
                raise HTTPException(status_code=409, detail="Server is running. Please stop it before deletion.")

        server = crud.get_server_by_id(db, server_id)
        if not server:
            logger.warning(f"删除时在数据库中未找到服务器 {server_id}，直接返回。")
            return

        server_path_str = server.path

        if task:
            task.progress = 20
            task.message = f"服务器：{server.name} | 清理数据库记录..."
        crud.delete_server(db, server_id)

        # 删除该服务器的 mods 数据库记录与关联
        try:
            crud.cleanup_mods_for_server_path(db, server_id, server_path_str)
        except Exception:
            pass
        # 额外清理：plugin 表中的 servers_installed 与 server_link_groups 的 server_ids
        try:
            crud.cleanup_plugins_for_server(db, server_id)
        except Exception:
            pass
        try:
            crud.cleanup_server_link_groups_for_server(db, server_id)
        except Exception:
            pass

        self.mcdr_manager.processes.pop(server_id, None)
        self.mcdr_manager.return_code.pop(server_id, None)
        self.mcdr_manager.java_pid.pop(server_id, None)
        self.mcdr_manager.log_tasks.pop(server_id, None)
        await self.mcdr_manager.notify_server_list_update(server_details=db_server, is_adding=False)

        try:
            server_path = Path(server_path_str)
            # 玩家游玩时长映射：删除服务器后，从所有玩家中移除该 server 键
            try:
                player_manager.on_server_deleted(server_path.name)
            except Exception:
                pass
            if server_path.is_dir():
                if task:
                    task.progress = 80
                    task.message = f"服务器：{server.name} | 删除文件..."
                await asyncio.to_thread(shutil.rmtree, server_path)
        except Exception as e:
            logger.warning(f"已删除服务器 {server_id} 的数据库记录，但删除目录 {server_path_str} 失败：{e}")
            if task:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.message = f"服务器：{server.name}"
            return

        if task:
            task.status = TaskStatus.SUCCESS
            task.progress = 100
            task.message = f"服务器：{server.name}"

    async def start_import_server_task(self, server_import: schemas.ServerImport, creator_id: int) -> Task:
        # 轻量校验：源路径有效 / 名称与目标目录冲突（避免创建后立刻失败的任务）
        source_path = Path(server_import.path).expanduser().resolve()
        if not source_path.is_dir():
            raise HTTPException(status_code=400, detail=f"提供的源路径 '{source_path}' 不是一个有效的目录。")
        if not (source_path / 'config.yml').is_file():
            raise HTTPException(status_code=400, detail=f"源路径 '{source_path}' 下未找到 'config.yml' 文件，请确保这是MCDR根目录。")
        is_copy = False
        with get_db_context() as db:
            if crud.get_server_by_name(db, server_import.name):
                raise HTTPException(status_code=409, detail=f"服务器名称 '{server_import.name}' 已存在。")
            try:
                # 若源路径正好是一个已存在服务器的 MCDR 根目录，则按“复制服务器”展示
                is_copy = db.query(models.Server).filter(models.Server.path == str(source_path)).first() is not None
            except Exception:
                is_copy = False
        safe_dirname = "".join(c if c.isalnum() or c in " _-" else "" for c in server_import.name).rstrip()
        if safe_dirname:
            target = MCDR_ROOT_PATH / safe_dirname
            if target.exists():
                raise HTTPException(status_code=409, detail=f"目标目录 '{target}' 已存在，无法导入。")

        task = self.task_manager.create_task(
            TaskType.IMPORT,
            name="复制服务器" if is_copy else "导入服务器",
            message=f"服务器：{server_import.name}",
        )

        async def _runner():
            try:
                with get_db_context() as db:
                    await self.import_server(server_import, db, creator_id, task)
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(getattr(e, "detail", e))
                task.message = f"服务器：{server_import.name}"
            finally:
                try:
                    self.task_manager.clear_finished_task(task.id)
                except Exception:
                    pass

        asyncio.create_task(_runner())
        return task

    async def import_server(self, server_import: schemas.ServerImport, db: Session, creator_id: int, task: Task) -> models.Server:

        progress_task = None
        try:
            task.status = TaskStatus.RUNNING
            task.progress = 1
            task.message = f"服务器：{server_import.name} | 准备导入..."

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
                                                                 creator_id=creator_id)
            db_server = crud.create_server(db, internal_server_model, creator_id=creator_id)

            try:
                task.progress = 5
                task.message = f"服务器：{server_import.name} | 复制文件中..."
                progress_task = asyncio.create_task(
                    poll_copy_progress(source_path, target_path, task, interval=2.0)
                )
                # 受限速且可断点续传复制，默认 128MB/s，可通过环境变量 ASP_IMPORT_BWLIMIT_MBPS 覆盖
                await asyncio.to_thread(copytree_resumable_throttled, source_path, target_path)
                await asyncio.to_thread(get_size_mb, target_path, time.time())
                task.progress = 100
                crud.update_server_core_config(db, db_server.id, infer_server_type_and_analyze_core_config(db_server))
                # 导入完成：根据是否存在 world，为所有玩家添加 {server_name: 0}
                try:
                    player_manager.on_server_created(Path(db_server.path).name, db_server.path)
                except Exception:
                    pass
                # 将服务器添加到指定的服务器组
                if server_import.server_link_group_ids:
                    try:
                        crud.add_server_to_groups(db, db_server.id, server_import.server_link_group_ids)
                    except Exception:
                        pass
                # 推送服务器列表更新（用于 ServerList 自动刷新）
                try:
                    await self.mcdr_manager.notify_server_list_update(db_server, is_adding=True)
                except Exception:
                    pass
                task.status = TaskStatus.SUCCESS
                task.message = f"服务器：{server_import.name}"
                return db_server
            except Exception as e:
                crud.delete_server(db, db_server.id)
                if target_path.exists():
                    await asyncio.to_thread(shutil.rmtree, target_path)
                raise HTTPException(status_code=500,
                                    detail=f"从 '{source_path}' 复制文件到 '{target_path}' 时发生错误: {e}")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise e
        finally:
            if progress_task:
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass

    async def get_server_plugins_info_by_id(self, server_id: int, db: Session) -> schemas.ServerPlugins:
        db_server = crud.get_server_by_id(db, server_id)
        if db_server is None:
            raise HTTPException(status_code=404, detail=f'未找到服务器')
        return self.plugin_manager.get_plugins_info(Path(db_server.path) / 'plugins')

    async def get_server_plugin_count(self, db_server: models.Server) -> Optional[int]:
        if db_server is None:
            raise HTTPException(status_code=404, detail=f'未找到服务器')
        return self.plugin_manager.get_plugins_count(Path(db_server.path) / 'plugins')
