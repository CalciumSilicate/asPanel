# backend/services/archive_manager.py
import asyncio
import os
import shutil
import tarfile
import uuid
import time
import zipfile
from pathlib import Path
from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.core import crud
from backend.core.constants import ARCHIVE_STORAGE_PATH
from backend.core.database import get_db_context
from backend.core.schemas import Server, Task, TaskStatus, TaskType, ArchiveCreate, ArchiveType, Archive, ServerStatus
from backend.core.utils import to_local_dt
from backend.services.task_manager import TaskManager
from backend.services.mcdr_manager import MCDRManager
from backend.tools import server_parser


class ArchiveManager:
    """处理与服务器存档相关的操作"""

    def __init__(self, task_manager: TaskManager, mcdr_manager: MCDRManager):
        self.task_manager = task_manager
        self.mcdr_manager = mcdr_manager
        self.storage_path = Path(ARCHIVE_STORAGE_PATH)
        self.storage_path.mkdir(exist_ok=True)

    @staticmethod
    def _pack_world(
            source_root: Path,
            archive_path: Path,
            world_name: str,
            task: Task,
    ):
        files = [p for p in source_root.rglob("*") if p.is_file()]
        total_bytes = sum(p.stat().st_size for p in files) or 1
        done_bytes = 0

        last_update_t = 0.0
        last_progress = task.progress

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(source_root, arcname=world_name, recursive=False)

            for i, p in enumerate(files, start=1):
                arcname = str(Path(world_name) / p.relative_to(source_root))
                tar.add(p, arcname=arcname, recursive=False)

                done_bytes += p.stat().st_size
                progress = int(done_bytes * 98 / total_bytes)
                if progress > 98:
                    progress = 98

                now = time.monotonic()
                if progress != last_progress and (now - last_update_t) >= 0.5:
                    task.progress = progress
                    task.message = f"正在打包... {task.progress}%（{i}/{len(files)}）"
                    last_progress = progress
                    last_update_t = now

    @staticmethod
    def _create_archive_record(archive_schema: ArchiveCreate):
        with get_db_context() as db:
            try:
                crud.create_archive(db, archive_schema)
                db.commit()
            finally:
                db.close()

    @staticmethod
    def _process_uploaded_archive(
            storage_path: Path,
            file_path: Path,
            archive_name: str,
            task: Task,
    ) -> Path:
        final_world_path = storage_path / f"{archive_name}_{uuid.uuid4().hex[:8]}"
        temp_extract_dir = storage_path / f"temp_extract_{uuid.uuid4().hex[:8]}"
        temp_extract_dir.mkdir(parents=True, exist_ok=False)

        try:
            task.progress = 5
            task.message = "正在解压上传的存档..."

            # ① 解压失败：400
            try:
                shutil.unpack_archive(file_path, temp_extract_dir)
            except (shutil.ReadError, zipfile.BadZipFile, tarfile.TarError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"上传的文件不是有效的压缩包或格式不支持：{e}",
                )

            task.progress = 35
            task.message = "正在检测世界目录..."

            found_world_dir: Optional[Path] = None
            if (temp_extract_dir / "level.dat").is_file():
                found_world_dir = temp_extract_dir
            else:
                for item in temp_extract_dir.iterdir():
                    if item.is_dir() and (item / "level.dat").is_file():
                        found_world_dir = item
                        break

            # ② 内容不符合：422
            if not found_world_dir:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="上传的存档中未找到有效的世界文件夹（缺少 level.dat）。",
                )

            task.progress = 70
            task.message = "正在整理存档文件..."

            # ③ 移动失败：500（通常是权限/磁盘/占用）
            try:
                shutil.move(str(found_world_dir), str(final_world_path))
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"移动世界文件夹失败：{e}",
                )

            task.progress = 85
            task.message = "正在清理临时文件..."
            return final_world_path

        finally:
            # 清理上传文件 & 临时解压目录（不影响主异常）
            try:
                if file_path.exists():
                    os.remove(file_path)
            except Exception:
                pass

            try:
                if temp_extract_dir.exists():
                    shutil.rmtree(temp_extract_dir, ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    def _restore_archive(
            db_archive,
            db_server,
            task: Task,
    ) -> str:
        """
        纯同步：做所有阻塞的文件系统操作（备份 / copy / unpack / move / 清理临时目录等）
        返回 world_name 供外层组装消息
        """
        temp_unpack_dir: Path | None = None

        server_name = getattr(db_server, "name", str(getattr(db_server, "id", "")))
        archive_name = getattr(db_archive, "name", str(getattr(db_archive, "id", "")))

        target_server_path = Path(db_server.path)
        target_mc_server_dir = target_server_path / "server"
        target_mc_server_dir.mkdir(parents=True, exist_ok=True)

        # 1) 解析 server.properties 获取 world_name
        task.progress = 15
        task.message = f"正在读取服务器配置（{server_name}）..."

        properties_path = target_mc_server_dir / "server.properties"
        world_name = "world"
        if properties_path.exists():
            properties = server_parser.parse_properties(str(properties_path))
            world_name = properties.get("level-name", "world")

        target_world_path = target_mc_server_dir / world_name

        # 2) 备份现有世界（滚动备份：world_backup_last）
        task.progress = 30
        task.message = f"正在备份当前世界 '{world_name}'..."

        if target_world_path.exists() and target_world_path.is_dir():
            backup_name = f"{world_name}_backup_last"
            backup_path = target_world_path.with_name(backup_name)

            if backup_path.exists():
                task.message = f"正在删除旧的备份 '{backup_name}'..."
                shutil.rmtree(backup_path)

            task.message = f"正在将当前世界备份为 '{backup_name}'..."
            shutil.move(str(target_world_path), str(backup_path))
        else:
            if target_world_path.exists():
                # 存在但不是目录，清掉避免后续 copytree/move 冲突
                try:
                    target_world_path.unlink()
                except Exception:
                    # 如果是奇怪的非文件/非目录，交给后续操作报错也行
                    pass

        # 3) 恢复存档
        task.progress = 60
        task.message = f"正在恢复存档 '{archive_name}' 到世界 '{world_name}'..."

        source_archive_path = Path(db_archive.path)

        try:
            if db_archive.type.value == ArchiveType.UPLOADED.value:
                # UPLOADED：db_archive.path 是一个世界目录
                if target_world_path.exists():
                    shutil.rmtree(target_world_path, ignore_errors=True)
                task.message = f"正在复制上传的存档到 '{world_name}'..."
                shutil.copytree(str(source_archive_path), str(target_world_path))

            elif db_archive.type.value == ArchiveType.SERVER.value:
                # SERVER：db_archive.path 是 tar.gz
                task.message = "正在解压服务器存档..."
                temp_unpack_dir = target_mc_server_dir / f"temp_unpack_{task.id}"
                temp_unpack_dir.mkdir(parents=True, exist_ok=False)

                shutil.unpack_archive(str(source_archive_path), str(temp_unpack_dir))

                task.message = "正在查找世界数据..."
                unpacked_world_path = None
                for item in temp_unpack_dir.iterdir():
                    if item.is_dir() and (item / "level.dat").is_file():
                        unpacked_world_path = item
                        break

                if not unpacked_world_path:
                    raise FileNotFoundError("在解压的存档中未能找到有效的世界文件夹 (缺少 level.dat)。")

                if target_world_path.exists():
                    shutil.rmtree(target_world_path, ignore_errors=True)

                task.message = f"正在恢复世界到 '{world_name}'..."
                shutil.move(str(unpacked_world_path), str(target_world_path))

            else:
                raise HTTPException(
                    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                    detail=f"不支持的存档类型：{getattr(db_archive.type, 'value', db_archive.type)}",
                )

            task.progress = 90
            task.message = "文件恢复完成，正在收尾..."

        finally:
            # 清理临时解压目录（无论成功失败都清）
            if temp_unpack_dir and temp_unpack_dir.exists():
                shutil.rmtree(temp_unpack_dir, ignore_errors=True)

        return world_name

    async def start_create_archive_from_server_task(self, db: Session, server_id: int) -> Task:
        db_server = crud.get_server_by_id(db, server_id)
        if not db_server:
            raise HTTPException(status_code=404, detail="源服务器不存在")

        server = Server.model_validate(db_server)
        server_path = Path(db_server.path)

        if server.core_config.server_type in ['forge', 'vanilla', 'beta18']:
            properties_path = server_path / "server" / "server.properties"

            if not properties_path.is_file():
                raise HTTPException(status_code=404,
                                    detail=f"服务器 '{db_server.name}' 尚未配置或启动，找不到 server.properties 文件。")
        else:
            raise HTTPException(status_code=405, detail=f"该服务器类型'{server.core_config.server_type}'不支持此操作")

        properties_dict = server_parser.parse_properties(str(properties_path))
        world_name = properties_dict.get('level-name', 'world')
        source_world_path = server_path / "server" / world_name
        if not source_world_path.is_dir():
            raise HTTPException(status_code=404,
                                detail=f"服务器 '{db_server.name}' 的世界文件夹 '{source_world_path.name}' 不存在。")

        archive_name = f"{db_server.name}_{world_name}"

        task = self.task_manager.create_task(
            TaskType.CREATE_ARCHIVE,
            name=f"创建服务器归档：{db_server.name}",
            message=f"排队中"
        )

        async def _runner():
            task.progress = 0
            task.status = TaskStatus.RUNNING
            task.message = f"正在打包服务器 '{db_server.name}' 的世界 '{world_name}'..."

            archive_filename = f"{task.id}.tar.gz"
            archive_path = self.storage_path / archive_filename

            try:
                await asyncio.to_thread(
                    self._pack_world,
                    source_world_path,
                    archive_path,
                    world_name,
                    task,
                )

                task.progress = 98
                task.message = "正在写入数据库..."

                archive_schema = ArchiveCreate(
                    name=archive_name,
                    type=ArchiveType.SERVER,
                    source_server_id=server_id,
                    filename=archive_path.name,
                    path=str(archive_path),
                )

                await asyncio.to_thread(self._create_archive_record, archive_schema)

                task.status = TaskStatus.SUCCESS
                task.progress = 100
                task.message = f"服务器 '{db_server.name}' 的世界 '{world_name}' 存档创建成功"

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(getattr(e, "detail", e))
                task.message = f"服务器：{db_server.name}"
            finally:
                try:
                    self.task_manager.clear_finished_task(task.id)
                except Exception:
                    pass

        asyncio.create_task(_runner())
        return task

    async def start_create_archive_from_upload_task(
            self,
            file_path: Path,
            archive_name: str,
            mc_version: Optional[str],
    ) -> Task:
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="上传的存档不存在")

        task = self.task_manager.create_task(
            TaskType.UPLOAD_ARCHIVE,
            name=f"上传存档：{archive_name}",
            message=f"存档名：{archive_name}",
        )

        async def _runner():
            task.status = TaskStatus.RUNNING
            task.progress = 0
            task.message = "排队中"

            final_world_path: Optional[Path] = None
            try:
                final_world_path = await asyncio.to_thread(
                    self._process_uploaded_archive,
                    self.storage_path,
                    file_path,
                    archive_name,
                    task,
                )

                task.progress = 98
                task.message = "正在写入数据库..."

                archive_schema = ArchiveCreate(
                    name=archive_name,
                    type=ArchiveType.UPLOADED,
                    mc_version=mc_version,
                    filename=final_world_path.name,
                    path=str(final_world_path),
                )

                await asyncio.to_thread(self._create_archive_record, archive_schema)

                task.progress = 100
                task.status = TaskStatus.SUCCESS
                task.message = "上传存档创建成功"

            except HTTPException as e:
                task.status = TaskStatus.FAILED
                task.error = e.detail
                task.message = "上传存档失败"
                # 失败清理最终目录（如果已经创建）
                if final_world_path:
                    try:
                        shutil.rmtree(final_world_path, ignore_errors=True)
                    except Exception:
                        pass

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.message = "上传存档失败"
                if final_world_path:
                    try:
                        shutil.rmtree(final_world_path, ignore_errors=True)
                    except Exception:
                        pass

            finally:
                self.task_manager.clear_finished_task(task.id)

        asyncio.create_task(_runner())
        return task

    @staticmethod
    async def list_archives() -> List[Archive]:
        with get_db_context() as db:
            db_archives = crud.get_archives(db)
            response_archives = []
            for archive in db_archives:
                out = Archive.model_validate(archive)
                try:
                    if getattr(archive, 'created_at', None):
                        out = out.model_copy(update={"created_at": to_local_dt(archive.created_at)})
                except Exception:
                    continue
                response_archives.append(out)
            return response_archives

    async def start_restore_archive_task(self, archive_id: int, target_server_id: int) -> Task:
        # 先创建 Task，符合你其它 start_xxx_task 的行为
        task = self.task_manager.create_task(
            TaskType.RESTORE_ARCHIVE,  # 如果你有专门的 RESTORE 类型，可以换成 TaskType.RESTORE_ARCHIVE
            name=f"恢复存档：{archive_id} -> 服务器：{target_server_id}",
            message="排队中",
        )

        async def _runner():
            task.status = TaskStatus.RUNNING
            task.progress = 0
            task.message = "排队中"

            try:
                # 读取 DB（这里很轻量，保持同步即可；你也可以改成 to_thread）
                with get_db_context() as db:
                    db_archive = crud.get_archive_by_id(db, archive_id)
                    if not db_archive:
                        raise HTTPException(status_code=404, detail="存档不存在")

                    db_server = crud.get_server_by_id(db, target_server_id)
                    if not db_server:
                        raise HTTPException(status_code=404, detail="目标服务器不存在")
                task.name = f"恢复存档：{db_archive.name} → 服务器：{db_server.name}"
                # 停服（必须 await，保持在事件循环里）
                server_name = getattr(db_server, "name", str(target_server_id))
                task.progress = 5
                task.message = f"正在检查服务器 '{server_name}' 状态..."

                status_tuple = await self.mcdr_manager.get_status(
                    server_id=db_server.id,
                    server_path=db_server.path,
                )
                if status_tuple and status_tuple[0] == ServerStatus.RUNNING:
                    task.message = f"正在停止服务器 '{server_name}'..."
                    await self.mcdr_manager.stop(db_server)
                    task.message = f"服务器 '{server_name}' 已停止，准备恢复存档..."

                # 关键：阻塞文件操作进线程
                task.progress = 10
                task.message = "准备恢复存档..."

                world_name = await asyncio.to_thread(
                    self._restore_archive,
                    db_archive,
                    db_server,
                    task,
                )

                # 恢复成功后启动服务器
                task.progress = 95
                task.message = "正在启动服务器..."
                await self.mcdr_manager.start(db_server)

                task.status = TaskStatus.SUCCESS
                task.progress = 100
                task.message = f"存档 '{db_archive.name}' 已成功恢复到服务器 '{db_server.name}'（世界：{world_name}）！"

            except HTTPException as e:
                task.status = TaskStatus.FAILED
                task.error = e.detail
                task.message = "恢复存档失败"

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.message = "恢复存档失败"

            finally:
                try:
                    self.task_manager.clear_finished_task(task.id)
                except Exception:
                    pass

        asyncio.create_task(_runner())
        return task
