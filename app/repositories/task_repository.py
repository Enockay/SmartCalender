from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.schema import Task, Subtask, Attachment, Tag
from app.models.task import TaskModel, SubtaskModel, AttachmentModel, TagModel


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, model: TaskModel) -> TaskModel:
        entity = Task(
            name=model.name,
            description=model.description,
            deadline=model.deadline,
            task_date=model.task_date,
            priority=model.priority,
            status=model.status,
            progress=model.progress,
            user_id=model.user_id,
        )
        self._session.add(entity)
        self._session.flush()  # Flush to get the ID

        # Add subtasks
        for subtask in model.subtasks:
            subtask_entity = Subtask(
                task_id=entity.id,
                name=subtask.name,
                completed=subtask.completed,
            )
            self._session.add(subtask_entity)

        # Add attachments
        for attachment in model.attachments:
            attachment_entity = Attachment(
                task_id=entity.id,
                file_path=attachment.file_path,
                file_name=attachment.file_name,
                file_type=attachment.file_type,
                file_size=attachment.file_size,
            )
            self._session.add(attachment_entity)

        # Add tags
        for tag in model.tags:
            tag_entity = Tag(
                task_id=entity.id,
                tag_name=tag.tag_name,
            )
            self._session.add(tag_entity)

        self._session.commit()
        self._session.refresh(entity)
        model.id = entity.id
        return self._load_full_task(entity)

    def get(self, task_id: int) -> Optional[TaskModel]:
        entity = self._session.get(Task, task_id)
        if not entity:
            return None
        return self._load_full_task(entity)

    def list_all(self) -> Iterable[TaskModel]:
        for entity in self._session.query(Task).all():
            yield self._load_full_task(entity)

    def list_by_status(self, status: str) -> Iterable[TaskModel]:
        for entity in self._session.query(Task).filter(Task.status == status).all():
            yield self._load_full_task(entity)

    def list_by_date(self, task_date: date) -> Iterable[TaskModel]:
        """List all tasks for a specific date."""
        # Convert date to datetime for comparison (start of day)
        start_datetime = datetime.combine(task_date, datetime.min.time())
        end_datetime = datetime.combine(task_date, datetime.max.time())
        
        for entity in self._session.query(Task).filter(
            Task.task_date >= start_datetime,
            Task.task_date <= end_datetime
        ).all():
            yield self._load_full_task(entity)

    def update(self, model: TaskModel) -> Optional[TaskModel]:
        if model.id is None:
            return None
        entity = self._session.get(Task, model.id)
        if not entity:
            return None

        entity.name = model.name
        entity.description = model.description
        entity.deadline = model.deadline
        entity.task_date = model.task_date
        entity.priority = model.priority
        entity.status = model.status
        entity.progress = model.progress

        # Update subtasks
        self._session.query(Subtask).filter(Subtask.task_id == entity.id).delete()
        for subtask in model.subtasks:
            subtask_entity = Subtask(
                task_id=entity.id,
                name=subtask.name,
                completed=subtask.completed,
            )
            self._session.add(subtask_entity)

        # Update attachments
        self._session.query(Attachment).filter(Attachment.task_id == entity.id).delete()
        for attachment in model.attachments:
            attachment_entity = Attachment(
                task_id=entity.id,
                file_path=attachment.file_path,
                file_name=attachment.file_name,
                file_type=attachment.file_type,
                file_size=attachment.file_size,
            )
            self._session.add(attachment_entity)

        # Update tags
        self._session.query(Tag).filter(Tag.task_id == entity.id).delete()
        for tag in model.tags:
            tag_entity = Tag(
                task_id=entity.id,
                tag_name=tag.tag_name,
            )
            self._session.add(tag_entity)

        self._session.commit()
        self._session.refresh(entity)
        return self._load_full_task(entity)

    def delete(self, task_id: int) -> bool:
        entity = self._session.get(Task, task_id)
        if not entity:
            return False
        self._session.delete(entity)
        self._session.commit()
        return True

    def _load_full_task(self, entity: Task) -> TaskModel:
        """Load a task entity with all related data."""
        subtasks = [
            SubtaskModel(id=s.id, name=s.name, completed=s.completed)
            for s in entity.subtasks
        ]
        attachments = [
            AttachmentModel(
                id=a.id,
                file_path=a.file_path,
                file_name=a.file_name,
                file_type=a.file_type,
                file_size=a.file_size,
            )
            for a in entity.attachments
        ]
        tags = [
            TagModel(id=t.id, tag_name=t.tag_name)
            for t in entity.tags
        ]

        return TaskModel(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            deadline=entity.deadline,
            task_date=entity.task_date,
            priority=entity.priority,
            status=entity.status,
            progress=entity.progress,
            user_id=entity.user_id,
            subtasks=subtasks,
            attachments=attachments,
            tags=tags,
        )
