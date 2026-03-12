from __future__ import annotations

from datetime import timedelta, datetime
from calendar import monthrange

from PySide6.QtWidgets import QWidget

from app.services.meeting_service import MeetingService
from app.ui.dialogs.meeting_dialog import MeetingDialog


class MeetingController:
    def __init__(self, parent: QWidget, service: MeetingService | None = None) -> None:
        self._parent = parent
        self._service = service or MeetingService()
        self.on_meetings_changed = None

    def _generate_recurrence_starts(
        self, start: datetime, recurrence: str, occurrences: int = 10
    ) -> list[datetime]:
        """Expand a recurrence choice into concrete start datetimes.

        For now we keep this simple and generate a limited number of future
        instances so they appear in all calendar views without changing
        the database schema.
        """
        recurrence = (recurrence or "None").lower()
        starts = [start]

        if recurrence == "none":
            return starts

        if recurrence == "daily":
            delta = timedelta(days=1)
            for i in range(1, occurrences):
                starts.append(start + i * delta)
        elif recurrence == "weekly":
            delta = timedelta(weeks=1)
            for i in range(1, occurrences):
                starts.append(start + i * delta)
        elif recurrence == "monthly":
            for i in range(1, occurrences):
                # Add i months while clamping the day to the valid range
                month_index = start.month - 1 + i
                year = start.year + month_index // 12
                month = month_index % 12 + 1
                last_day = monthrange(year, month)[1]
                day = min(start.day, last_day)
                starts.append(
                    start.replace(year=year, month=month, day=day)
                )

        return starts

    def add_meeting(self) -> None:
        dialog = MeetingDialog(self._parent)
        if not dialog.exec():
            return
        data = dialog.get_data()
        if data is None:
            return
        (
            title,
            start,
            duration_minutes,
            category,
            recurrence,
            description,
            color_gradient,
            reminder_minutes,
        ) = data
        # Expand recurrence into multiple concrete meetings so they show up
        # across all calendar views.
        starts = self._generate_recurrence_starts(start, recurrence)
        for s in starts:
            end = s + timedelta(minutes=duration_minutes)
            self._service.create_meeting(
                title=title,
                start_time=s,
                end_time=end,
                description=description or None,
                color_gradient=color_gradient,
                reminder_minutes=reminder_minutes,
            )
        if self.on_meetings_changed:
            self.on_meetings_changed()

