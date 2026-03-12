from __future__ import annotations

from datetime import date
from typing import Callable, List

from app.models.meeting import MeetingModel
from app.services.calendar_service import CalendarService


class CalendarController:
    def __init__(self, service: CalendarService | None = None) -> None:
        self._service = service or CalendarService()
        self.on_day_meetings_changed: Callable[[date, List[MeetingModel]], None] | None = None

    def load_day(self, d: date) -> None:
        meetings = self._service.meetings_for_day(d)
        if self.on_day_meetings_changed:
            self.on_day_meetings_changed(d, meetings)

