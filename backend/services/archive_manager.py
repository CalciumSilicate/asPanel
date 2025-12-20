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
from backend.core.schemas import Server, Task, TaskStatus, TaskType, ArchiveCreate, ArchiveType, Archive
from backend.core.utils import to_local_dt
from backend.services.task_manager import TaskManager
from backend.tools import server_parser


class ArchiveManager:
    """处理与服务器存档相关的操作"""

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
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
