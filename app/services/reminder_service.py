from __future__ import annotations

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

from app.database.db_manager import DatabaseManager
from app.database.schema import Reminder


@dataclass
class DueReminder:
    id: int
    title: str
    start_time: datetime


class ReminderService:
    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or DatabaseManager()

    def get_due_reminders(self, now: datetime | None = None) -> List[DueReminder]:
        if now is None:
            now = datetime.utcnow()
        session = self._db.session()
        try:
            q = (
                session.query(Reminder)
                .filter(Reminder.remind_at <= now, Reminder.dismissed.is_(False))
            )
            results: List[DueReminder] = []
            for r in q.all():
                meeting = r.meeting
                title = meeting.title if meeting else "Upcoming meeting"
                start = meeting.start_time if meeting else now
                results.append(DueReminder(id=r.id, title=title, start_time=start))
            return results
        finally:
            session.close()

    def dismiss(self, reminder_id: int) -> None:
        session = self._db.session()
        try:
            r = session.get(Reminder, reminder_id)
            if r:
                r.dismissed = True
                session.commit()
        finally:
            session.close()

    def snooze(self, reminder_id: int, minutes: int = 10) -> None:
        session = self._db.session()
        try:
            r = session.get(Reminder, reminder_id)
            if r:
                r.remind_at = r.remind_at + timedelta(minutes=minutes)
                session.commit()
        finally:
            session.close()

    def create_for_meeting(self, meeting, minutes_before: int = 10) -> None:
        """Create a reminder some minutes before the meeting start."""
        remind_at = meeting.start_time - timedelta(minutes=minutes_before)
        session = self._db.session()
        try:
            reminder = Reminder(
                meeting_id=meeting.id,
                remind_at=remind_at,
                dismissed=False,
            )
            session.add(reminder)
            session.commit()
        finally:
            session.close()

