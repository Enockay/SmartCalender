from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtWidgets import QWidget

from app.models.task import TaskModel
from app.services.task_service import TaskService


class TaskController:
    """Controller for task management UI interactions."""

    def __init__(self, parent: QWidget, service: TaskService | None = None) -> None:
        self._parent = parent
        self._service = service or TaskService()
        self.on_tasks_changed: Callable[[], None] | None = None

    def create_task(self, task_data: dict) -> Optional[TaskModel]:
        """Create a new task."""
        task = self._service.create_task(**task_data)
        if task and self.on_tasks_changed:
            self.on_tasks_changed()
        return task

    def update_task(self, task: TaskModel) -> Optional[TaskModel]:
        """Update an existing task."""
        updated = self._service.update_task(task)
        if updated and self.on_tasks_changed:
            self.on_tasks_changed()
        return updated

    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        result = self._service.delete_task(task_id)
        if result and self.on_tasks_changed:
            self.on_tasks_changed()
        return result

    def get_all_tasks(self) -> List[TaskModel]:
        """Get all tasks."""
        return self._service.list_all_tasks()

    def get_tasks_by_status(self, status: str) -> List[TaskModel]:
        """Get tasks by status."""
        return self._service.list_tasks_by_status(status)

    def update_task_status(self, task_id: int, status: str) -> Optional[TaskModel]:
        """Update task status (for drag and drop)."""
        updated = self._service.update_task_status(task_id, status)
        if updated and self.on_tasks_changed:
            self.on_tasks_changed()
        return updated

    def update_task_progress(self, task_id: int, progress: float) -> Optional[TaskModel]:
        """Update task progress."""
        updated = self._service.update_task_progress(task_id, progress)
        if updated and self.on_tasks_changed:
            self.on_tasks_changed()
        return updated
