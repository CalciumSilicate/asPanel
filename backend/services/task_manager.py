# backend/services/task_manager.py

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Coroutine, Dict, Iterable, List, Optional, Tuple

from backend.core.logger import logger
from backend.core.schemas import Task, TaskStatus, TaskType


# =========================================
# 后台协程状态枚举
# =========================================
class CoroutineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CoroutineInfo:
    """后台协程信息"""
    name: str
    status: CoroutineStatus = CoroutineStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    task: Optional[asyncio.Task] = field(default=None, repr=False)


class TaskManager:
    """In-memory task tracker with optional Socket.IO broadcast.

    - Tasks are stored in-process (not persisted).
    - Callers may mutate returned Task objects directly (progress/status/message/etc).
    - A background broadcaster (polling diff) can emit task changes via Socket.IO.
    """

    def __init__(self, *, max_tasks: int = 300, broadcast_interval: float = 0.5):
        self._lock = threading.RLock()
        self.tasks: Dict[str, Task] = {}

        self._max_tasks = int(max_tasks)
        self._broadcast_interval = float(broadcast_interval)

        self._sio: Any = None
        self._broadcast_task: Optional[asyncio.Task] = None
        self._last_snapshot: Dict[str, Dict[str, Any]] = {}

        # 后台协程管理
        self._coroutines: Dict[str, CoroutineInfo] = {}
        self._coroutine_lock = asyncio.Lock()

    # -------------------------
    # Basic CRUD
    # -------------------------
    def create_task(
        self,
        _type: TaskType,
        *,
        name: Optional[str] = None,
        message: Optional[str] = None,
        total: Optional[int] = None,
    ) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            type=_type,
            name=name,
            message=message,
            status=TaskStatus.PENDING,
            progress=0.0,
            created_at=time.time(),
            total=total,
            done=0 if total is not None else None,
        )
        with self._lock:
            self.tasks[task_id] = task
            self._prune_locked()
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return None
            return self._derive_combined_task_locked(task_id, task)

    def get_tasks(self, *_types: Optional[TaskType]) -> Dict[str, Task]:
        with self._lock:
            if not _types or _types == (None,):
                return {tid: self._derive_combined_task_locked(tid, t) for tid, t in self.tasks.items()}

            types = {t for t in _types if t is not None}
            return {
                tid: self._derive_combined_task_locked(tid, t)
                for tid, t in self.tasks.items()
                if t.type in types
            }

    def list_tasks(self, *_types: Optional[TaskType]) -> List[Task]:
        items = list(self.get_tasks(*_types).values())
        items.sort(key=lambda t: float(t.created_at or 0), reverse=True)
        return items

    def clear_tasks(self, *, statuses: Iterable[TaskStatus]) -> int:
        status_set = set(statuses)
        with self._lock:
            to_delete = [tid for tid, t in self.tasks.items() if t.status in status_set]
            for tid in to_delete:
                self.tasks.pop(tid, None)
            return len(to_delete)

    def clear_task(self, task_id: str) -> bool:
        with self._lock:
            return self.tasks.pop(task_id, None) is not None

    # -------------------------
    # Cleanup policy
    # -------------------------
    def clear_finished_task(self, task_id: str, delay_seconds: int = 3600) -> None:
        """Schedule cleanup for a finished task.

        By default, only SUCCESS tasks are auto-removed (FAILED tasks stay for manual clearing).
        """

        def remove_task() -> None:
            try:
                with self._lock:
                    task = self.tasks.get(task_id)
                    if task is None:
                        return
                    if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                        return
                    # Keep failed tasks until user clears them.
                    if task.status == TaskStatus.FAILED:
                        return

                    self.tasks.pop(task_id, None)
            except Exception:
                logger.exception(f"清理任务失败: {task_id}")

        try:
            delay = max(0, int(delay_seconds))
        except Exception:
            delay = 3600

        timer = threading.Timer(delay, remove_task)
        timer.daemon = True
        timer.start()

    def _prune_locked(self) -> None:
        """Prune old tasks when exceeding max_tasks (prefer removing finished ones)."""
        if self._max_tasks <= 0:
            return
        if len(self.tasks) <= self._max_tasks:
            return

        tasks_sorted: List[Tuple[str, Task]] = sorted(
            self.tasks.items(), key=lambda kv: float((kv[1].created_at or 0))
        )

        def is_finished(t: Task) -> bool:
            return t.status in (TaskStatus.SUCCESS, TaskStatus.FAILED)

        # 1) Drop oldest finished tasks first
        for tid, t in tasks_sorted:
            if len(self.tasks) <= self._max_tasks:
                return
            if is_finished(t):
                self.tasks.pop(tid, None)

        # 2) If still too many, drop oldest (best-effort)
        for tid, _t in tasks_sorted:
            if len(self.tasks) <= self._max_tasks:
                return
            self.tasks.pop(tid, None)

    # -------------------------
    # Combined tasks
    # -------------------------
    def _derive_combined_task_locked(self, task_id: str, task: Task) -> Task:
        if task.type != TaskType.COMBINED:
            return task

        ids = list(task.ids or [])
        if not ids:
            return task

        children = [self.tasks.get(cid) for cid in ids]
        existing = [c for c in children if c is not None]
        if not existing:
            task.status = TaskStatus.FAILED
            task.error = task.error or "Combined task has no valid sub-tasks"
            task.progress = 0.0
            return task

        # progress: average over provided ids, missing treated as 0
        progress_values = [(c.progress or 0.0) if c is not None else 0.0 for c in children]
        task.progress = round(sum(progress_values) / max(len(progress_values), 1), 2)

        statuses = [c.status for c in existing]
        if any(s == TaskStatus.FAILED for s in statuses):
            task.status = TaskStatus.FAILED
        elif all(s == TaskStatus.SUCCESS for s in statuses) and len(existing) == len(ids):
            task.status = TaskStatus.SUCCESS
        elif any(s == TaskStatus.RUNNING for s in statuses):
            task.status = TaskStatus.RUNNING
        else:
            task.status = TaskStatus.PENDING
        return task

    # -------------------------
    # Socket.IO broadcasting (poll + diff)
    # -------------------------
    def attach_socketio(self, sio: Any) -> None:
        self._sio = sio

    def start_broadcaster(self) -> None:
        """Start background broadcaster (idempotent). Must be called within an event loop."""
        if self._sio is None:
            logger.warning("TaskManager: sio 未绑定，跳过任务广播启动")
            return
        if self._broadcast_task is not None and not self._broadcast_task.done():
            return
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def _broadcast_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._broadcast_interval)

                current = self._snapshot_public()
                if self._sio is None:
                    self._last_snapshot = current
                    continue

                # created / updated / finished
                for tid, cur in current.items():
                    prev = self._last_snapshot.get(tid)
                    if prev is None:
                        await self._emit_task_event("created", cur)
                        continue
                    if prev == cur:
                        continue

                    prev_status = prev.get("status")
                    cur_status = cur.get("status")
                    if prev_status != cur_status and cur_status in (TaskStatus.SUCCESS, TaskStatus.FAILED):
                        await self._emit_task_event("finished", cur)
                    else:
                        await self._emit_task_event("updated", cur)

                # deleted
                for tid in set(self._last_snapshot.keys()) - set(current.keys()):
                    await self._emit_task_event("deleted", {"id": tid})

                self._last_snapshot = current
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("TaskManager 广播循环异常")

    def _snapshot_public(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            out: Dict[str, Dict[str, Any]] = {}
            for tid, t in self.tasks.items():
                t2 = self._derive_combined_task_locked(tid, t)
                out[tid] = self._serialize_task_public(t2)
            return out

    @staticmethod
    def _serialize_task_public(task: Task) -> Dict[str, Any]:
        # Keep payload stable; avoid sending huge/complex objects.
        return {
            "id": task.id,
            "ids": list(task.ids or []) or None,
            "name": task.name,
            "status": task.status,
            "progress": round(float(task.progress or 0.0), 2),
            "message": task.message,
            "error": task.error,
            "type": task.type,
            "created_at": float(task.created_at or 0.0) or None,
            "total": task.total,
            "done": task.done,
        }

    async def _emit_task_event(self, action: str, task: Dict[str, Any]) -> None:
        try:
            await self._sio.emit("task_update", {"action": action, "task": task})
        except Exception:
            logger.exception(f"TaskManager emit 失败: action={action} task_id={task.get('id')}")

    # =========================================
    # 后台协程生命周期管理
    # =========================================
    async def register_coroutine(
        self,
        name: str,
        coro: Coroutine[Any, Any, Any],
        replace: bool = False
    ) -> asyncio.Task:
        """注册并启动一个后台协程"""
        async with self._coroutine_lock:
            # 检查是否已存在
            if name in self._coroutines:
                existing = self._coroutines[name]
                if existing.status == CoroutineStatus.RUNNING:
                    if not replace:
                        raise ValueError(f"协程 '{name}' 正在运行中")
                    await self.cancel_coroutine(name)

            # 创建任务
            task = asyncio.create_task(self._run_coroutine(name, coro))
            info = CoroutineInfo(
                name=name,
                status=CoroutineStatus.RUNNING,
                started_at=datetime.now(),
                task=task
            )
            self._coroutines[name] = info
            logger.debug(f"后台协程已注册: {name}")
            return task

    async def _run_coroutine(self, name: str, coro: Coroutine) -> Any:
        """包装协程执行，记录状态"""
        try:
            result = await coro
            async with self._coroutine_lock:
                if name in self._coroutines:
                    self._coroutines[name].status = CoroutineStatus.COMPLETED
                    self._coroutines[name].finished_at = datetime.now()
            logger.debug(f"后台协程完成: {name}")
            return result
        except asyncio.CancelledError:
            async with self._coroutine_lock:
                if name in self._coroutines:
                    self._coroutines[name].status = CoroutineStatus.CANCELLED
                    self._coroutines[name].finished_at = datetime.now()
            logger.debug(f"后台协程已取消: {name}")
            raise
        except Exception as e:
            async with self._coroutine_lock:
                if name in self._coroutines:
                    self._coroutines[name].status = CoroutineStatus.FAILED
                    self._coroutines[name].finished_at = datetime.now()
                    self._coroutines[name].error = str(e)
            logger.opt(exception=e).error(f"后台协程失败: {name}")
            raise

    async def cancel_coroutine(self, name: str) -> bool:
        """取消指定协程"""
        async with self._coroutine_lock:
            if name not in self._coroutines:
                return False

            info = self._coroutines[name]
            if info.task and not info.task.done():
                info.task.cancel()
                try:
                    await info.task
                except asyncio.CancelledError:
                    pass
            return True

    async def cancel_all_coroutines(self) -> None:
        """取消所有运行中的协程"""
        async with self._coroutine_lock:
            for name, info in self._coroutines.items():
                if info.task and not info.task.done():
                    info.task.cancel()

        # 等待所有协程完成
        tasks = [info.task for info in self._coroutines.values() if info.task]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("所有后台协程已取消")

    def get_coroutine_status(self, name: str) -> Optional[CoroutineInfo]:
        """获取协程状态"""
        return self._coroutines.get(name)

    def list_coroutines(self) -> Dict[str, CoroutineInfo]:
        """列出所有协程"""
        return dict(self._coroutines)

    def get_running_coroutine_count(self) -> int:
        """获取运行中的协程数量"""
        return sum(1 for c in self._coroutines.values() if c.status == CoroutineStatus.RUNNING)

