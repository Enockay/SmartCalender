from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List

from app.database.db_manager import DatabaseManager
from app.models.task import TaskModel
from app.repositories.task_repository import TaskRepository


class TaskService:
    """Application-facing API for task CRUD operations."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or DatabaseManager()

    def create_task(
        self,
        name: str,
        task_date: datetime,
        description: str | None = None,
        deadline: datetime | None = None,
        priority: str | None = None,
        status: str = "backlog",
        progress: float = 0.0,
        user_id: int = 1,
        subtasks: List[dict] | None = None,
        attachments: List[dict] | None = None,
        tags: List[str] | None = None,
    ) -> TaskModel:
        """Create a new task."""
        from app.models.task import SubtaskModel, AttachmentModel, TagModel

        subtask_models = []
        if subtasks:
            for st in subtasks:
                subtask_models.append(
                    SubtaskModel(id=None, name=st.get("name", ""), completed=st.get("completed", False))
                )

        attachment_models = []
        if attachments:
            for att in attachments:
                attachment_models.append(
                    AttachmentModel(
                        id=None,
                        file_path=att.get("file_path", ""),
                        file_name=att.get("file_name", ""),
                        file_type=att.get("file_type"),
                        file_size=att.get("file_size"),
                    )
                )

        tag_models = []
        if tags:
            for tag_name in tags:
                tag_models.append(TagModel(id=None, tag_name=tag_name))

        # Calculate progress from subtasks if available, otherwise use provided progress
        calculated_progress = progress
        if subtasks and len(subtasks) > 0:
            total = len(subtasks)
            completed = sum(1 for st in subtasks if st.get("completed", False))
            if total > 0:
                calculated_progress = (completed / total * 100.0)
                # Cap progress based on status
                if status == "completed":
                    calculated_progress = 100.0
                elif status == "in_progress":
                    calculated_progress = min(calculated_progress, 50.0)
                else:  # backlog
                    calculated_progress = min(calculated_progress, 0.0)

        model = TaskModel(
            id=None,
            name=name,
            description=description,
            deadline=deadline,
            task_date=task_date,
            priority=priority,
            status=status,
            progress=calculated_progress,
            user_id=user_id,
            subtasks=subtask_models,
            attachments=attachment_models,
            tags=tag_models,
        )

        session = self._db.session()
        try:
            repo = TaskRepository(session)
            return repo.create(model)
        finally:
            session.close()

    def get_task(self, task_id: int) -> Optional[TaskModel]:
        """Get a task by ID."""
        session = self._db.session()
        try:
            repo = TaskRepository(session)
            return repo.get(task_id)
        finally:
            session.close()

    def list_all_tasks(self) -> List[TaskModel]:
        """List all tasks."""
        session = self._db.session()
        try:
            repo = TaskRepository(session)
            return list(repo.list_all())
        finally:
            session.close()

    def list_tasks_by_status(self, status: str) -> List[TaskModel]:
        """List tasks by status."""
        session = self._db.session()
        try:
            repo = TaskRepository(session)
            return list(repo.list_by_status(status))
        finally:
            session.close()

    def list_tasks_by_date(self, task_date: date) -> List[TaskModel]:
        """List tasks for a specific date."""
        session = self._db.session()
        try:
            repo = TaskRepository(session)
            return list(repo.list_by_date(task_date))
        finally:
            session.close()

    def update_task(self, task: TaskModel) -> Optional[TaskModel]:
        """Update an existing task."""
        session = self._db.session()
        try:
            repo = TaskRepository(session)
            return repo.update(task)
        finally:
            session.close()

    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        session = self._db.session()
        try:
            repo = TaskRepository(session)
            return repo.delete(task_id)
        finally:
            session.close()

    def update_task_status(self, task_id: int, status: str) -> Optional[TaskModel]:
        """Update task status."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.status = status
        return self.update_task(task)

    def update_task_progress(self, task_id: int, progress: float) -> Optional[TaskModel]:
        """Update task progress."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.progress = max(0.0, min(100.0, progress))
        return self.update_task(task)
