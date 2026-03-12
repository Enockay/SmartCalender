from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class MeetingModel:
    id: Optional[int]
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    location: Optional[str]
    user_id: int
    # Stored as "linear:#RRGGBB:#RRGGBB" (start:end)
    color_gradient: Optional[str] = None

