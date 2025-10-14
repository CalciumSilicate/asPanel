from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import asyncio
import psutil
import socket
import errno

from backend import schemas, models
from backend.core.config import CPU_PERCENT_INTERVAL
from backend.database import get_db
from backend.dependencies import mcdr_manager, task_manager
from backend.schemas import TaskStatus, TaskType, Role
from backend.auth import require_role

router = APIRouter(
    prefix="/api",
    tags=["System"],
)

cpu_percent_cache = 0.0


async def cpu_sampler():
    global cpu_percent_cache
    while True:
        cpu_percent_cache = psutil.cpu_percent(interval=None)
        await asyncio.sleep(CPU_PERCENT_INTERVAL)


@router.get("/system/stats")
async def get_system_stats(db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    servers = db.query(models.Server).all()
    results = await asyncio.gather(*[mcdr_manager.get_status(s.id, s.path) for s in servers])
    running_servers = sum(1 for st, _ in results if st == "running")
    return {"total_servers": len(servers), "running_servers": running_servers}


@router.get("/system/status")
async def get_system_status(_user=Depends(require_role(Role.USER))):
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return {
        "cpu_percent": cpu_percent_cache,
        "memory_percent": mem.percent,
        "memory_used": round(mem.used / (1024 ** 3), 2),
        "memory_total": round(mem.total / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
    }


@router.get("/system/task-progress/{task_id}", response_model=schemas.Task)
def get_download_progress(task_id: str, _user=Depends(require_role(Role.USER))):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务未找到")
    if task.status in [TaskStatus.SUCCESS, TaskStatus.FAILED]:
        task_manager.clear_finished_task(task_id, 0 if task.type == TaskType.DOWNLOAD else 5)
    return task


# @router.get("/system/tasks/", response_model=List[schemas.Task])
# async def get_active_archive_tasks(task_type: Optional[List[TaskType]] = Query(None)):
#     active_list = []
#     for task_id, status_obj in task_manager.get_tasks(*task_type).items():
#         task_with_id = schemas.Task(
#             id=task_id,
#             status=status_obj.status,
#             progress=status_obj.progress,
#             message=status_obj.message,
#             error=status_obj.error
#         )
#         active_list.append(task_with_id)
#     return active_list


@router.get("/utils/check-port", response_model=schemas.PortStatusResponse, tags=["Utilities"])
def check_port_availability(port: int, _user=Depends(require_role(Role.USER))):
    if not (1024 <= port <= 65535):
        raise HTTPException(400, "端口号必须在 1024-65535 之间")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return {"is_available": True}
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:
                return {"is_available": False}
            raise HTTPException(500, f"检查端口时发生错误: {e}")
