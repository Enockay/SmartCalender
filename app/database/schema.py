from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    subscription_tier = Column(String(50), default="free")
    is_active = Column(Boolean, default=True)


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    location = Column(String(255), nullable=True)
    # Stored as "linear:#RRGGBB:#RRGGBB" (start:end)
    color_gradient = Column(String(64), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False, default="Untitled Reminder")
    description = Column(Text, nullable=True)
    remind_at = Column(DateTime, nullable=False)
    category = Column(String(50), nullable=True, default="Personal")   # Work, Personal, Health, Meetings, Finance
    priority = Column(String(20), nullable=True, default="Medium")      # Low, Medium, High, Critical
    repeat_type = Column(String(30), nullable=True, default="None")     # None, Daily, Weekly, Monthly, Custom
    repeat_custom = Column(String(100), nullable=True)                  # e.g. "Mon,Wed,Fri"
    notification_type = Column(String(100), nullable=True, default="Desktop")  # Desktop, Sound, Desktop + Sound
    advance_minutes = Column(Integer, nullable=True, default=0)         # 0=at time, 5, 10, 30, 60, 1440
    status = Column(String(30), nullable=False, default="active")       # active, snoozed, completed, overdue
    dismissed = Column(Boolean, default=False)
    snoozed_until = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    meeting = relationship("Meeting")
    user = relationship("User")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    color = Column(String(20), nullable=True)


class AppSettings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(500), nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    deadline = Column(DateTime, nullable=True)
    task_date = Column(DateTime, nullable=False)  # Date this task belongs to
    priority = Column(String(50), nullable=True)  # Low, Medium, High
    status = Column(String(50), nullable=False, default="backlog")  # backlog, in_progress, completed
    progress = Column(Float, default=0.0)  # 0.0 to 100.0
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User")
    subtasks = relationship("Subtask", back_populates="task", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="task", cascade="all, delete-orphan")
    tags = relationship("Tag", back_populates="task", cascade="all, delete-orphan")


class Subtask(Base):
    __tablename__ = "subtasks"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    name = Column(String(255), nullable=False)
    completed = Column(Boolean, default=False)

    task = relationship("Task", back_populates="subtasks")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=True)  # document, image, link
    file_size = Column(Integer, nullable=True)  # in bytes

    task = relationship("Task", back_populates="attachments")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    tag_name = Column(String(100), nullable=False)

    task = relationship("Task", back_populates="tags")

