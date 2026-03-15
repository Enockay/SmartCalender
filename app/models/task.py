from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class SubtaskModel:
    id: Optional[int]
    name: str
    completed: bool = False


@dataclass
class AttachmentModel:
    id: Optional[int]
    file_path: str
    file_name: str
    file_type: Optional[str] = None  # document, image, link
    file_size: Optional[int] = None  # in bytes


@dataclass
class TagModel:
    id: Optional[int]
    tag_name: str


@dataclass
class TaskModel:
    id: Optional[int]
    name: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    task_date: Optional[datetime] = None  # Date this task belongs to
    priority: Optional[str] = None  # Low, Medium, High
    status: str = "backlog"  # backlog, in_progress, completed
    progress: float = 0.0  # 0.0 to 100.0
    user_id: int = 1
    subtasks: List[SubtaskModel] = field(default_factory=list)
    attachments: List[AttachmentModel] = field(default_factory=list)
    tags: List[TagModel] = field(default_factory=list)
