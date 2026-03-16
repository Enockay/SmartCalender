from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Iterable, List

from app.database.db_manager import DatabaseManager
from app.models.meeting import MeetingModel
from app.repositories.meeting_repository import MeetingRepository
from app.services.reminder_service import ReminderService


class MeetingService:
    """Application-facing API for meeting CRUD."""

    def __init__(self, db: DatabaseManager | None = None, settings_service=None) -> None:
        self._db = db or DatabaseManager()
        self._settings_service = settings_service

    # --- CRUD operations -------------------------------------------------

    def create_meeting(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime | None = None,
        description: str | None = None,
        location: str | None = None,
        color_gradient: str | None = None,
        user_id: int = 1,
        reminder_minutes: int | None = None,
    ) -> MeetingModel:
        if end_time is None:
            end_time = start_time + timedelta(hours=1)
        model = MeetingModel(
            id=None,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            location=location,
            color_gradient=color_gradient,
            user_id=user_id,
        )
        session = self._db.session()
        try:
            repo = MeetingRepository(session)
            created = repo.create(model)

            # Automatically create a reminder using either the per-meeting
            # setting, the global default, or a hard-coded fallback.
            if reminder_minutes is not None:
                minutes_before = reminder_minutes
            else:
                # If a settings service is provided, prefer its default;
                # otherwise fall back to 10 minutes before.
                if self._settings_service is not None:
                    minutes_before = self._settings_service.get_default_reminder_minutes()
                else:
                    minutes_before = 10

            ReminderService(self._db).create_for_meeting(
                created,
                minutes_before=minutes_before,
            )

            return created
        finally:
            session.close()

    def get_meeting(self, meeting_id: int) -> Optional[MeetingModel]:
        session = self._db.session()
        try:
            repo = MeetingRepository(session)
            return repo.get(meeting_id)
        finally:
            session.close()

    def update_meeting(self, model: MeetingModel) -> Optional[MeetingModel]:
        session = self._db.session()
        try:
            repo = MeetingRepository(session)
            updated = repo.update(model)
            # Update linked reminders when meeting is updated
            if updated:
                reminder_service = ReminderService(self._db)
                reminder_service.update_for_meeting(updated)
            return updated
        finally:
            session.close()

    def delete_meeting(self, meeting_id: int) -> bool:
        session = self._db.session()
        try:
            # Delete linked reminders first
            reminder_service = ReminderService(self._db)
            reminder_service.delete_for_meeting(meeting_id)
            # Then delete the meeting
            repo = MeetingRepository(session)
            return repo.delete(meeting_id)
        finally:
            session.close()

    def list_meetings_between(
        self, start: datetime, end: datetime
    ) -> List[MeetingModel]:
        session = self._db.session()
        try:
            repo = MeetingRepository(session)
            return [
                m
                for m in repo.list_all()
                if start <= m.start_time < end
            ]
        finally:
            session.close()

