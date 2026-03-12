from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List

from app.models.meeting import MeetingModel
from app.services.meeting_service import MeetingService


class CalendarService:
    def __init__(self, meeting_service: MeetingService | None = None) -> None:
        self._meetings = meeting_service or MeetingService()

    def meetings_for_day(self, d: date) -> List[MeetingModel]:
        start = datetime(d.year, d.month, d.day)
        end = start + timedelta(days=1)
        return self._meetings.list_meetings_between(start, end)

