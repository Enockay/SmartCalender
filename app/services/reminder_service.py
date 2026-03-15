from __future__ import annotations

from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from app.database.db_manager import DatabaseManager
from app.database.schema import Reminder, Meeting
from app.repositories.reminder_repository import ReminderRepository


CATEGORIES = ["Work", "Personal", "Health", "Meetings", "Finance", "Bills"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
REPEAT_TYPES = ["None", "Daily", "Weekly", "Monthly", "Custom"]
NOTIFICATION_TYPES = ["Desktop", "Sound", "Desktop + Sound"]
ADVANCE_OPTIONS = [
    (0, "At time"),
    (5, "5 minutes before"),
    (10, "10 minutes before"),
    (30, "30 minutes before"),
    (60, "1 hour before"),
    (1440, "1 day before"),
]
SNOOZE_OPTIONS = [
    (5, "5 minutes"),
    (10, "10 minutes"),
    (30, "30 minutes"),
    (60, "1 hour"),
]


@dataclass
class ReminderData:
    id: int = 0
    title: str = ""
    description: str = ""
    remind_at: datetime = field(default_factory=datetime.now)
    category: str = "Personal"
    priority: str = "Medium"
    repeat_type: str = "None"
    repeat_custom: str = ""
    notification_type: str = "Desktop"
    advance_minutes: int = 0
    status: str = "active"
    meeting_id: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    # Meeting-linked fields
    meeting_title: Optional[str] = None
    meeting_start: Optional[datetime] = None
    meeting_end: Optional[datetime] = None
    meeting_location: Optional[str] = None
    meeting_color: Optional[str] = None


class ReminderService:
    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or DatabaseManager()

    # -- Helpers ---------------------------------------------------------------
    def _to_data(self, r: Reminder) -> ReminderData:
        # Eagerly resolve the meeting relationship if present
        meeting = r.meeting if r.meeting_id else None
        return ReminderData(
            id=r.id,
            title=r.title or "Untitled",
            description=r.description or "",
            remind_at=r.remind_at,
            category=r.category or "Personal",
            priority=r.priority or "Medium",
            repeat_type=r.repeat_type or "None",
            repeat_custom=r.repeat_custom or "",
            notification_type=r.notification_type or "Desktop",
            advance_minutes=r.advance_minutes or 0,
            status=r.status or "active",
            meeting_id=r.meeting_id,
            created_at=r.created_at,
            completed_at=r.completed_at,
            snoozed_until=r.snoozed_until,
            meeting_title=meeting.title if meeting else None,
            meeting_start=meeting.start_time if meeting else None,
            meeting_end=meeting.end_time if meeting else None,
            meeting_location=meeting.location if meeting else None,
            meeting_color=meeting.color_gradient if meeting else None,
        )

    # -- CRUD ------------------------------------------------------------------
    def create_reminder(
        self,
        title: str,
        remind_at: datetime,
        description: str = "",
        category: str = "Personal",
        priority: str = "Medium",
        repeat_type: str = "None",
        repeat_custom: str = "",
        notification_type: str = "Desktop",
        advance_minutes: int = 0,
        meeting_id: Optional[int] = None,
    ) -> ReminderData:
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            reminder = Reminder(
                title=title,
                description=description,
                remind_at=remind_at,
                category=category,
                priority=priority,
                repeat_type=repeat_type,
                repeat_custom=repeat_custom,
                notification_type=notification_type,
                advance_minutes=advance_minutes,
                status="active",
                meeting_id=meeting_id,
                user_id=1,
            )
            repo.create(reminder)
            return self._to_data(reminder)
        finally:
            session.close()

    def update_reminder(
        self,
        reminder_id: int,
        title: str,
        remind_at: datetime,
        description: str = "",
        category: str = "Personal",
        priority: str = "Medium",
        repeat_type: str = "None",
        repeat_custom: str = "",
        notification_type: str = "Desktop",
        advance_minutes: int = 0,
    ) -> Optional[ReminderData]:
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            r = repo.get_by_id(reminder_id)
            if not r:
                return None
            r.title = title
            r.description = description
            r.remind_at = remind_at
            r.category = category
            r.priority = priority
            r.repeat_type = repeat_type
            r.repeat_custom = repeat_custom
            r.notification_type = notification_type
            r.advance_minutes = advance_minutes
            repo.update(r)
            return self._to_data(r)
        finally:
            session.close()

    def delete_reminder(self, reminder_id: int) -> bool:
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            return repo.delete_by_id(reminder_id)
        finally:
            session.close()

    # -- Queries ---------------------------------------------------------------
    def get_all(self) -> List[ReminderData]:
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            return [self._to_data(r) for r in repo.get_all()]
        finally:
            session.close()

    def get_by_filter(self, filter_name: str) -> List[ReminderData]:
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            if filter_name == "today":
                items = repo.get_today()
            elif filter_name == "upcoming":
                items = repo.get_upcoming()
            elif filter_name == "completed":
                items = repo.get_completed()
            elif filter_name == "overdue":
                items = repo.get_overdue()
            elif filter_name == "active":
                items = repo.get_active()
            else:
                items = repo.get_all()
            return [self._to_data(r) for r in items]
        finally:
            session.close()

    def search(self, query: str) -> List[ReminderData]:
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            return [self._to_data(r) for r in repo.search(query)]
        finally:
            session.close()

    def get_counts(self) -> dict[str, int]:
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            return repo.count_by_status()
        finally:
            session.close()

    def get_reminder_dates(self) -> Dict[date, List[str]]:
        """Return a dict mapping dates to list of category colors for calendar dots."""
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            all_r = repo.get_all()
            result: Dict[date, List[str]] = {}
            for r in all_r:
                d = r.remind_at.date()
                cat = r.category or "Personal"
                if d not in result:
                    result[d] = []
                result[d].append(cat)
            return result
        finally:
            session.close()

    # -- Actions ---------------------------------------------------------------
    def mark_completed(self, reminder_id: int) -> bool:
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            r = repo.get_by_id(reminder_id)
            if not r:
                return False
            repo.mark_completed(r)
            # Handle repeat: create next occurrence
            self._handle_repeat(r, session)
            return True
        finally:
            session.close()

    def snooze(self, reminder_id: int, minutes: int = 10) -> bool:
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            r = repo.get_by_id(reminder_id)
            if not r:
                return False
            repo.snooze(r, minutes)
            return True
        finally:
            session.close()

    def dismiss(self, reminder_id: int) -> None:
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            r = repo.get_by_id(reminder_id)
            if r:
                repo.mark_dismissed(r)
        finally:
            session.close()

    def get_due_reminders(self, now: datetime | None = None) -> List[ReminderData]:
        if now is None:
            now = datetime.now()
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            return [self._to_data(r) for r in repo.due_reminders(now)]
        finally:
            session.close()

    def update_overdue(self) -> int:
        """Mark any past-due active reminders as overdue. Returns count."""
        now = datetime.now()
        session = self._db.session()
        try:
            repo = ReminderRepository(session)
            overdue = repo.get_overdue()
            count = 0
            for r in overdue:
                if r.status != "overdue":
                    repo.mark_overdue(r)
                    count += 1
            return count
        finally:
            session.close()

    # -- Repeat ----------------------------------------------------------------
    def _handle_repeat(self, reminder: Reminder, session) -> None:
        """If reminder has a repeat, create the next occurrence."""
        if not reminder.repeat_type or reminder.repeat_type == "None":
            return
        next_at = self._calc_next_occurrence(reminder.remind_at, reminder.repeat_type, reminder.repeat_custom)
        if next_at:
            repo = ReminderRepository(session)
            new_r = Reminder(
                title=reminder.title,
                description=reminder.description,
                remind_at=next_at,
                category=reminder.category,
                priority=reminder.priority,
                repeat_type=reminder.repeat_type,
                repeat_custom=reminder.repeat_custom,
                notification_type=reminder.notification_type,
                advance_minutes=reminder.advance_minutes,
                status="active",
                user_id=reminder.user_id,
                meeting_id=reminder.meeting_id,
            )
            repo.create(new_r)

    @staticmethod
    def _calc_next_occurrence(current: datetime, repeat_type: str, custom: str) -> Optional[datetime]:
        if repeat_type == "Daily":
            return current + timedelta(days=1)
        elif repeat_type == "Weekly":
            return current + timedelta(weeks=1)
        elif repeat_type == "Monthly":
            month = current.month + 1
            year = current.year
            if month > 12:
                month = 1
                year += 1
            day = min(current.day, 28)
            return current.replace(year=year, month=month, day=day)
        elif repeat_type == "Custom" and custom:
            day_map = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
            target_days = [day_map[d.strip()] for d in custom.split(",") if d.strip() in day_map]
            if not target_days:
                return None
            today_wd = current.weekday()
            for delta in range(1, 8):
                if (today_wd + delta) % 7 in target_days:
                    return current + timedelta(days=delta)
        return None

    def create_for_meeting(self, meeting, minutes_before: int = 10) -> None:
        """Legacy: create a reminder from a meeting."""
        remind_at = meeting.start_time - timedelta(minutes=minutes_before)
        self.create_reminder(
            title=f"Meeting: {meeting.title}",
            remind_at=remind_at,
            category="Meetings",
            notification_type="Desktop + Sound",
            advance_minutes=minutes_before,
            meeting_id=meeting.id,
        )
