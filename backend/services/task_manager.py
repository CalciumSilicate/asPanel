# backend/services/task_manager.py

import threading
import uuid
from typing import Dict, Optional

from backend.core.schemas import Task, TaskType, TaskStatus
from backend.core.logger import logger


class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}

    def create_task(self, _type: TaskType) -> Task:
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = Task(status=TaskStatus.PENDING, type=_type, id=task_id)
        return self.tasks[task_id]

    def get_task(self, task_id: str) -> Task | None:
        _: Task = self.tasks.get(task_id, None)
        if _.type == TaskType.COMBINED:
            _.progress = self._calculate_combined_task(*(self.get_task(task_id) for task_id in _.ids))
            if all(self.get_task(task_id).status == TaskStatus.SUCCESS for task_id in _.ids):
                _.status = TaskStatus.SUCCESS
                self.clear_finished_task(_.id)
        return _

    @staticmethod
    def _calculate_combined_task(*tasks: Task) -> float:
        return round(sum(x.progress for x in tasks) / len(tasks), 2)

    def get_tasks(self, *_type: Optional[TaskType]) -> Dict[str, Task]:
        if _type is None:
            return self.tasks
        _ = {}
        for task_id in self.tasks:
            if self.get_task(task_id).type in _type:
                _[task_id] = self.tasks.get(task_id)
        return _

    def clear_finished_task(self, task_id: str, delay_seconds: int = 60):
        def remove_task():
            if task_id in self.tasks and self.tasks[task_id].status not in [
                TaskStatus.PENDING, TaskStatus.RUNNING
            ]:
                task = self.tasks[task_id]
                if task.error:
                    logger.error(f"任务 {task_id} 出错：{task.error}")
                del self.tasks[task_id]
                logger.info(f"已清理完成的归档任务：{task_id}")

        timer = threading.Timer(delay_seconds, remove_task)
        timer.start()
