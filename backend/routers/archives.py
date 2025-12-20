# backend/routers/archives.py

import uuid
import shutil
import os
from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path

from backend.core import crud, schemas
from backend.core.database import get_db
from backend.core.constants import ARCHIVE_STORAGE_PATH, TEMP_PATH
from backend.core.dependencies import task_manager, archive_manager
from backend.core.schemas import TaskType, Role
from backend.core.logger import logger
from backend.core.auth import require_role

router = APIRouter(
    prefix="/api",
    tags=["Archives"],
)


@router.get("/archives", response_model=List[schemas.Archive])
async def read_archives(_user=Depends(require_role(Role.HELPER))):
    return await archive_manager.list_archives()


@router.post("/archives/create/from-server", status_code=status.HTTP_202_ACCEPTED)
async def create_archive_from_server(
        server_id: int,
        db: Session = Depends(get_db),
        _user=Depends(require_role(Role.HELPER)),
):
    task = await archive_manager.start_create_archive_from_server_task(db, server_id)
    return {"task_id": task.id, "message": "已开始创建存档任务"}


@router.post("/archives/create/from-upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_archive(
        file: UploadFile,
        mc_version: Optional[str] = None,
        _user=Depends(require_role(Role.HELPER))
):
    if not any(file.filename.endswith(ext) for ext in ['.zip', '.tar', '.gz', '.7z', '.rar']):
        raise HTTPException(status_code=400, detail="不支持的文件格式。仅支持 zip, tar, tar.gz, 7z, rar。")
    archive_name = Path(file.filename).stem
    temp_file_path = TEMP_PATH / f"upload_{str(uuid.uuid4())}_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    task = await archive_manager.start_create_archive_from_upload_task(temp_file_path, archive_name, mc_version)
    return {"task_id": task.id, "message": "文件已上传，开始后台处理"}


@router.get("/archives/active-tasks", response_model=List[schemas.Task])
async def get_active_archive_tasks(_user=Depends(require_role(Role.HELPER))):
    """获取所有正在进行的存档任务的列表"""
    active_list = []
    # 遍历全局任务字典
    for task_id, status_obj in task_manager.get_tasks(TaskType.CREATE_ARCHIVE, TaskType.UPLOAD_ARCHIVE).items():
        # 将字典的键(task_id)和值(status_obj)组合成一个新的对象
        task_with_id = schemas.Task(
            id=task_id,
            status=status_obj.status,
            progress=status_obj.progress,
            message=status_obj.message,
            error=status_obj.error
        )
        active_list.append(task_with_id)
    return active_list


@router.get("/archives/download/{archive_id}")
async def download_archive(
        archive_id: int,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        _user=Depends(require_role(Role.ADMIN))
):
    """
    - 'SERVER' 类型，发送 .tar.gz 文件
    - 'UPLOADED' 类型，压缩目录为 .zip 文件并发送
    """
    db_archive = crud.get_archive_by_id(db, archive_id)
    if not db_archive:
        raise HTTPException(status_code=404, detail="存档不存在")
    archive_path = Path(db_archive.path)
    if not archive_path.exists():
        crud.delete_archive(db, archive_id)
        db.commit()
        raise HTTPException(status_code=404, detail="存档已被清除")
    if db_archive.type.value == 'SERVER':
        if not archive_path.is_file():
            raise HTTPException(status_code=409, detail="Database record is of type SERVER, but path is not a file.")
        return FileResponse(
            path=str(archive_path),
            filename=f"{db_archive.name}.tar.gz",
            media_type='application/gzip'
        )
    elif db_archive.type.value == 'UPLOADED':
        if not archive_path.is_dir():
            raise HTTPException(status_code=409,
                                detail="Database record is of type UPLOADED, but path is not a directory.")
        temp_dir = ARCHIVE_STORAGE_PATH / "temp_downloads"
        temp_dir.mkdir(exist_ok=True)

        zip_basename = temp_dir / f"{db_archive.name}_{uuid.uuid4().hex}"

        try:
            zip_path_str = shutil.make_archive(
                base_name=str(zip_basename),
                format='zip',
                root_dir=str(archive_path)
            )
            zip_path = Path(zip_path_str)
            background_tasks.add_task(os.remove, zip_path)
            return FileResponse(
                path=str(zip_path),
                filename=f"{db_archive.name}.zip",
                media_type='application/zip'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create archive zip file: {e}")

    else:
        raise HTTPException(status_code=400,
                            detail=f"Unknown archive type '{db_archive.type}', cannot process download.")


@router.delete("/archives/delete/{archive_id}", status_code=204)
def delete_archive(archive_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.HELPER))):
    db_archive = crud.delete_archive(db, archive_id)
    file_path = db_archive.path
    if os.path.exists(file_path):
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except OSError as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete archive file: {e}")

    db.commit()
    return


@router.post("/archives/batch-delete", status_code=204)
def batch_delete_archives(payload: schemas.BatchActionPayload, db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="No archive IDs provided")
    archives_to_delete = crud.delete_archives_by_ids(db, payload.ids)
    if not archives_to_delete:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    for db_archive in archives_to_delete:
        file_path = Path(db_archive.path)
        if file_path.exists():
            try:
                if file_path.is_file():
                    os.remove(file_path)
                elif file_path.is_dir():
                    shutil.rmtree(file_path)
            except OSError as e:
                logger.warning(f"删除存档文件 {file_path}（ID={db_archive.id}）失败：{e}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/archives/restore/{archive_id}/{server_id}", status_code=status.HTTP_202_ACCEPTED)
async def restore_archive_to_server(
        archive_id: int,
        server_id: int,
        _user=Depends(require_role(Role.HELPER))
):
    task = await archive_manager.start_restore_archive_task(archive_id, server_id)
    return {"task_id": task.id, "message": "已开始恢复存档任务"}
