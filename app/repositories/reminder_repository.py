from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from sqlalchemy.orm import Session

from app.database.schema import Reminder, Meeting


class ReminderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def due_reminders(self, now: datetime) -> List[Reminder]:
        return (
            self._session.query(Reminder)
            .filter(Reminder.remind_at <= now, Reminder.dismissed.is_(False))
            .all()
        )

    def mark_dismissed(self, reminder: Reminder) -> None:
        reminder.dismissed = True
        self._session.commit()

    def snooze(self, reminder: Reminder, minutes: int) -> None:
        from datetime import timedelta
        reminder.remind_at = reminder.remind_at + timedelta(minutes=minutes)
        self._session.commit()

    def get_meeting(self, reminder: Reminder) -> Meeting:
        return self._session.get(Meeting, reminder.meeting_id)

