"""First-run onboarding: welcome tour flag and optional sample data (UX review §4.6).

Sample data is a realistic week with invented names. Every item created is
recorded so "Clear sample data" removes exactly those items and nothing else.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from app.core.logger import get_logger
from app.services.meeting_service import MeetingService
from app.services.reminder_service import ReminderService
from app.services.settings_service import SettingsService
from app.services.task_service import TaskService

ONBOARDED_KEY = "onboarding_completed"
SAMPLE_IDS_KEY = "sample_data_ids"


class OnboardingService:
    def __init__(self, settings: SettingsService | None = None) -> None:
        self._settings = settings or SettingsService()
        self._logger = get_logger(__name__)

    # ── Welcome tour ──────────────────────────────────────────────
    def needs_welcome(self) -> bool:
        return self._settings.get_value(ONBOARDED_KEY, "") != "1"

    def mark_welcomed(self) -> None:
        self._settings.set_value(ONBOARDED_KEY, "1")

    # ── Sample data ───────────────────────────────────────────────
    def _ids(self) -> dict:
        try:
            data = json.loads(self._settings.get_value(SAMPLE_IDS_KEY, "") or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def has_sample_data(self) -> bool:
        ids = self._ids()
        return any(ids.get(k) for k in ("meetings", "tasks", "reminders"))

    def load_sample_data(self) -> None:
        if self.has_sample_data():
            return
        meetings, tasks, reminders = MeetingService(), TaskService(), ReminderService()
        today = date.today()
        now = datetime.now()
        ids: dict[str, list[int]] = {"meetings": [], "tasks": [], "reminders": []}

        def at(day_offset: int, h: int, m: int = 0) -> datetime:
            return datetime.combine(today + timedelta(days=day_offset), time(h, m))

        sample_events = [
            ("Team stand-up", 0, 9, 30, 15, "Quick daily check-in."),
            ("Lunch with Ana", 0, 13, 0, 60, "Café on the corner."),
            ("Project review", 1, 11, 0, 60, "Review progress on the website redesign."),
            ("Team stand-up", 1, 9, 30, 15, "Quick daily check-in."),
            ("Dentist", 2, 16, 0, 45, "Check-up."),
            ("Call with Sam (supplier)", 3, 10, 0, 30, "Confirm delivery dates."),
            ("Yoga class", 4, 18, 0, 60, ""),
        ]
        for title, off, h, mi, dur, desc in sample_events:
            start = at(off, h, mi)
            if start < now:
                # Skip events whose time has already passed today, rather than
                # moving them (moving could clash with the next day's copy).
                continue
            try:
                mtg = meetings.create_meeting(
                    title=title,
                    start_time=start,
                    end_time=start + timedelta(minutes=dur),
                    description=desc or None,
                    reminder_minutes=10,
                )
                if mtg and mtg.id is not None:
                    ids["meetings"].append(mtg.id)
            except Exception as exc:
                self._logger.warning(f"sample meeting failed: {exc}")

        sample_tasks = [
            ("Draft quarterly plan", 0, "High", "in_progress", 50.0, ["Collect numbers", "Write summary", "Share with team"]),
            ("Book flights for the conference", 1, "Medium", "backlog", 0.0, []),
            ("Renew passport", 2, "Low", "backlog", 0.0, ["Fill in the form", "Take a photo"]),
            ("Send invoice to Northwind", 0, "High", "backlog", 0.0, []),
            ("Clean up inbox", 0, "Low", "completed", 100.0, []),
        ]
        for name, off, prio, status, progress, subtasks in sample_tasks:
            try:
                t = tasks.create_task(
                    name=name,
                    task_date=at(off, 9),
                    deadline=at(off, 17),
                    priority=prio,
                    status=status,
                    progress=progress,
                    subtasks=[{"name": s, "completed": False} for s in subtasks],
                )
                if t and t.id is not None:
                    ids["tasks"].append(t.id)
            except Exception as exc:
                self._logger.warning(f"sample task failed: {exc}")

        try:
            r = reminders.create_reminder(
                title="Pay the electricity bill",
                remind_at=at(1, 9),
                category="Bills",
                priority="Medium",
            )
            if r and getattr(r, "id", None) is not None:
                ids["reminders"].append(r.id)
        except Exception as exc:
            self._logger.warning(f"sample reminder failed: {exc}")

        self._settings.set_value(SAMPLE_IDS_KEY, json.dumps(ids))
        self._logger.info(
            f"Sample data loaded: {len(ids['meetings'])} events, {len(ids['tasks'])} tasks, "
            f"{len(ids['reminders'])} reminders"
        )

    def clear_sample_data(self) -> None:
        ids = self._ids()
        meetings, tasks, reminders = MeetingService(), TaskService(), ReminderService()
        for mid in ids.get("meetings", []):
            try:
                meetings.delete_meeting(mid)  # also removes the linked reminders
            except Exception:
                pass
        for tid in ids.get("tasks", []):
            try:
                tasks.delete_task(tid)
            except Exception:
                pass
        for rid in ids.get("reminders", []):
            try:
                reminders.delete_reminder(rid)
            except Exception:
                pass
        self._settings.set_value(SAMPLE_IDS_KEY, "{}")
        self._logger.info("Sample data cleared")
