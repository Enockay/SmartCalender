from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database.schema import Reminder


class ReminderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Create ────────────────────────────────────────────────
    def create(self, reminder: Reminder) -> Reminder:
        self._session.add(reminder)
        self._session.commit()
        self._session.refresh(reminder)
        return reminder

    # ── Read ──────────────────────────────────────────────────
    def get_by_id(self, reminder_id: int) -> Optional[Reminder]:
        return self._session.get(Reminder, reminder_id)

    def get_all(self) -> List[Reminder]:
        return (
            self._session.query(Reminder)
            .order_by(Reminder.remind_at.asc())
            .all()
        )

    def get_active(self) -> List[Reminder]:
        return (
            self._session.query(Reminder)
            .filter(Reminder.status == "active")
            .order_by(Reminder.remind_at.asc())
            .all()
        )

    def get_by_status(self, status: str) -> List[Reminder]:
        return (
            self._session.query(Reminder)
            .filter(Reminder.status == status)
            .order_by(Reminder.remind_at.asc())
            .all()
        )

    def get_today(self) -> List[Reminder]:
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = today_start + timedelta(days=1)
        return (
            self._session.query(Reminder)
            .filter(
                Reminder.remind_at >= today_start,
                Reminder.remind_at < today_end,
            )
            .order_by(Reminder.remind_at.asc())
            .all()
        )

    def get_upcoming(self, days: int = 7) -> List[Reminder]:
        now = datetime.now()
        future = now + timedelta(days=days)
        return (
            self._session.query(Reminder)
            .filter(
                Reminder.remind_at >= now,
                Reminder.remind_at <= future,
                Reminder.status.in_(["active", "snoozed"]),
            )
            .order_by(Reminder.remind_at.asc())
            .all()
        )

    def get_overdue(self) -> List[Reminder]:
        now = datetime.now()
        return (
            self._session.query(Reminder)
            .filter(
                Reminder.remind_at < now,
                Reminder.status.in_(["active", "snoozed"]),
                Reminder.dismissed.is_(False),
            )
            .order_by(Reminder.remind_at.asc())
            .all()
        )

    def get_completed(self) -> List[Reminder]:
        return (
            self._session.query(Reminder)
            .filter(Reminder.status == "completed")
            .order_by(Reminder.completed_at.desc())
            .all()
        )

    def due_reminders(self, now: datetime) -> List[Reminder]:
        """Reminders that should fire right now."""
        return (
            self._session.query(Reminder)
            .filter(
                Reminder.remind_at <= now,
                Reminder.dismissed.is_(False),
                Reminder.status.in_(["active", "snoozed"]),
            )
            .all()
        )

    def search(self, query: str) -> List[Reminder]:
        pattern = f"%{query}%"
        return (
            self._session.query(Reminder)
            .filter(
                or_(
                    Reminder.title.ilike(pattern),
                    Reminder.description.ilike(pattern),
                    Reminder.category.ilike(pattern),
                )
            )
            .order_by(Reminder.remind_at.asc())
            .all()
        )

    def get_by_category(self, category: str) -> List[Reminder]:
        return (
            self._session.query(Reminder)
            .filter(Reminder.category == category)
            .order_by(Reminder.remind_at.asc())
            .all()
        )

    def count_by_status(self) -> dict[str, int]:
        """Return counts: {active, snoozed, completed, overdue, today, total}."""
        all_reminders = self.get_all()
        now = datetime.now()
        counts = {"active": 0, "snoozed": 0, "completed": 0, "overdue": 0, "today": 0, "total": len(all_reminders)}
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = today_start + timedelta(days=1)
        for r in all_reminders:
            if r.status == "completed":
                counts["completed"] += 1
            elif r.status == "snoozed":
                counts["snoozed"] += 1
            elif r.remind_at < now and r.status == "active" and not r.dismissed:
                counts["overdue"] += 1
            else:
                counts["active"] += 1
            if today_start <= r.remind_at < today_end:
                counts["today"] += 1
        return counts

    # ── Update ────────────────────────────────────────────────
    def update(self, reminder: Reminder) -> Reminder:
        self._session.commit()
        self._session.refresh(reminder)
        return reminder

    def mark_completed(self, reminder: Reminder) -> None:
        reminder.status = "completed"
        reminder.completed_at = datetime.now()
        reminder.dismissed = True
        self._session.commit()

    def mark_dismissed(self, reminder: Reminder) -> None:
        reminder.dismissed = True
        self._session.commit()

    def snooze(self, reminder: Reminder, minutes: int) -> None:
        reminder.remind_at = datetime.now() + timedelta(minutes=minutes)
        reminder.status = "snoozed"
        reminder.snoozed_until = reminder.remind_at
        self._session.commit()

    def mark_overdue(self, reminder: Reminder) -> None:
        reminder.status = "overdue"
        self._session.commit()

    # ── Delete ────────────────────────────────────────────────
    def delete(self, reminder: Reminder) -> None:
        self._session.delete(reminder)
        self._session.commit()

    def delete_by_id(self, reminder_id: int) -> bool:
        reminder = self.get_by_id(reminder_id)
        if reminder:
            self._session.delete(reminder)
            self._session.commit()
            return True
        return False