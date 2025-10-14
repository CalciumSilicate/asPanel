from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import uuid
import shutil
from typing import List
from pathlib import Path
import os

from backend import crud, schemas
from backend.database import get_db
from backend.core.config import ARCHIVE_STORAGE_PATH
from backend.dependencies import task_manager
from backend.schemas import TaskType, TaskStatus, Role
from backend.tasks.background import \
    background_create_archive, background_restore_archive, background_process_upload
from backend.logger import logger
from backend.auth import require_role

router = APIRouter(
    prefix="/api",
    tags=["Archives"],
)


@router.get("/archives", response_model=List[schemas.Archive])
def read_archives(db: Session = Depends(get_db), _user=Depends(require_role(Role.HELPER))):
    db_archives = crud.get_archives(db)
    response_archives = [schemas.Archive.model_validate(archive) for archive in db_archives]
    return response_archives


@router.post("/archives/create/from-server", status_code=status.HTTP_202_ACCEPTED)
async def create_archive_from_server(
        server_id: int,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        _user=Depends(require_role(Role.ADMIN)),
):
    db_server = crud.get_server_by_id(db, server_id)
    if not db_server:
        raise HTTPException(status_code=404, detail="服务器未找到")
    task = task_manager.create_task(TaskType.CREATE_ARCHIVE)
    background_tasks.add_task(background_create_archive, db, server_id, task)
    return {"task_id": task.id, "message": "已开始创建存档任务"}


@router.post("/archives/create/from-upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_archive(
        mc_version: str,
        file: UploadFile,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        _user=Depends(require_role(Role.HELPER))
):
    if not any(file.filename.endswith(ext) for ext in ['.zip', '.tar', '.gz', '.7z', '.rar']):
        raise HTTPException(status_code=400, detail="不支持的文件格式。仅支持 zip, tar, tar.gz, 7z, rar。")
    archive_name = Path(file.filename).stem  # 使用文件名（不含扩展名）作为存档名

    # 先将上传的文件保存到临时位置
    task = task_manager.create_task(TaskType.UPLOAD_ARCHIVE)
    temp_file_path = ARCHIVE_STORAGE_PATH / f"upload_{task.id}_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    background_tasks.add_task(background_process_upload, db, temp_file_path, archive_name, mc_version, task)
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


@router.post("/archives/restore/{archive_id}", status_code=status.HTTP_202_ACCEPTED)
async def restore_archive_to_server(
        archive_id: int,
        payload: schemas.RestorePayload,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        _user=Depends(require_role(Role.HELPER))
):
    if not crud.get_archive_by_id(db, archive_id):
        raise HTTPException(status_code=404, detail="源存档未找到。")
    if not crud.get_server_by_id(db, payload.target_server_id):
        raise HTTPException(status_code=404, detail="目标服务器未找到。")
    task = task_manager.create_task(TaskType.RESTORE_ARCHIVE)
    background_tasks.add_task(background_restore_archive, db, archive_id, payload.target_server_id, task)
    return {"task_id": task.id, "message": "已开始恢复存档任务"}
