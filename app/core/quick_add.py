"""Plain-language quick add (UX review §4.6).

Turns text such as

    lunch with Ana Friday 1pm
    remind me to pay rent on the 1st every month
    call the bank tomorrow
    team sync every monday 9:30

into an event, a task or a reminder. The rules are deliberately simple and
predictable; anything the parser cannot place becomes a task for today.
"""

from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_WD = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))


@dataclass
class QuickAddResult:
    kind: str                 # "event" | "task" | "reminder"
    title: str
    day: date
    at: time | None = None    # None for an all-day task
    repeat: str = "None"      # None | Daily | Weekly | Monthly
    duration_minutes: int = 60

    @property
    def start(self) -> datetime:
        return datetime.combine(self.day, self.at or time(9, 0))

    def describe(self) -> str:
        """Short human summary, e.g. 'Event · Fri 21 Nov, 13:00'."""
        label = {"event": "Event", "task": "Task", "reminder": "Reminder"}[self.kind]
        when = self.day.strftime("%a %d %b")
        if self.at:
            when += f", {self.at.strftime('%H:%M')}"
        rep = f" · repeats {self.repeat.lower()}" if self.repeat != "None" else ""
        return f"{label} · {when}{rep}"


def _next_weekday(today: date, wd: int, force_next: bool = False) -> date:
    ahead = (wd - today.weekday()) % 7
    if ahead == 0 and force_next:
        ahead = 7
    return today + timedelta(days=ahead)


def _clamp_day(y: int, m: int, d: int) -> date:
    return date(y, m, min(d, monthrange(y, m)[1]))


def parse(text: str, now: datetime | None = None) -> QuickAddResult | None:
    now = now or datetime.now()
    today = now.date()
    raw = " ".join((text or "").split())
    if not raw:
        return None
    s = " " + raw + " "
    low = s.lower()

    def cut(m: re.Match) -> None:
        nonlocal s, low
        s = s[: m.start()] + " " + s[m.end():]
        low = s.lower()

    kind = None
    m = re.match(r"\s(remind me to|remind me|reminder:?)\s", low)
    if m:
        kind = "reminder"
        cut(m)
    else:
        m = re.match(r"\s(todo:?|task:?|to do:?)\s", low)
        if m:
            kind = "task"
            cut(m)

    # ── Recurrence ──
    repeat = "None"
    weekday_from_repeat = None
    m = re.search(rf"\s(every\s+({_WD})s?)\s", low)
    if m:
        repeat = "Weekly"
        weekday_from_repeat = WEEKDAYS[m.group(2)]
        cut(m)
    else:
        for pat, rep in (
            (r"\s(every\s*day|daily|each day)\s", "Daily"),
            (r"\s(every\s*week|weekly|each week)\s", "Weekly"),
            (r"\s(every\s*month|monthly|each month)\s", "Monthly"),
        ):
            m = re.search(pat, low)
            if m:
                repeat = rep
                cut(m)
                break

    # ── Time ──
    at: time | None = None
    m = re.search(r"\s(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s", low)
    if m:
        h = int(m.group(1)) % 12 + (12 if m.group(3) == "pm" else 0)
        mi = int(m.group(2) or 0)
        if h < 24 and mi < 60:
            at = time(h, mi)
            cut(m)
    if at is None:
        m = re.search(r"\s(?:at\s+)?([01]?\d|2[0-3])[:h.]([0-5]\d)\s", low)
        if m:
            at = time(int(m.group(1)), int(m.group(2)))
            cut(m)
    if at is None:
        m = re.search(r"\sat\s+(\d{1,2})\s", low)
        if m and 0 <= int(m.group(1)) <= 23:
            h = int(m.group(1))
            # "at 3" during the working day most likely means 15:00
            at = time(h + 12 if 1 <= h <= 7 else h, 0)
            cut(m)
    if at is None:
        for word, t in (("noon", time(12)), ("midday", time(12)), ("midnight", time(0)),
                        ("this morning", time(9)), ("in the morning", time(9)), ("morning", time(9)),
                        ("this afternoon", time(14)), ("afternoon", time(14)),
                        ("this evening", time(18)), ("evening", time(18))):
            m = re.search(rf"\s(?:at\s+|in the\s+)?{word}\s", low)
            if m:
                at = t
                cut(m)
                break

    # ── Date ──
    day: date | None = None
    m = re.search(r"\s(in\s+(\d+)\s+(minute|min|hour|hr|day|week)s?)\s", low)
    if m:
        n, unit = int(m.group(2)), m.group(3)
        if unit in ("minute", "min", "hour", "hr"):
            dt = now + (timedelta(minutes=n) if unit in ("minute", "min") else timedelta(hours=n))
            day, at = dt.date(), time(dt.hour, dt.minute)
        else:
            day = today + timedelta(days=n * (7 if unit == "week" else 1))
        cut(m)
    if day is None:
        m = re.search(r"\s(?:on\s+|by\s+)?(today|tonight|tomorrow|tmrw|tmr)\s", low)
        if m:
            word = m.group(1)
            day = today + timedelta(days=0 if word in ("today", "tonight") else 1)
            if word == "tonight" and at is None:
                at = time(20, 0)
            cut(m)
    if day is None:
        m = re.search(rf"\s(?:on\s+|by\s+)?(next\s+)?({_WD})\s", low)
        if m:
            wd = WEEKDAYS[m.group(2)]
            if m.group(1):
                # "next friday" = that weekday in next week (weeks start Monday)
                day = today - timedelta(days=today.weekday()) + timedelta(days=7 + wd)
            else:
                day = _next_weekday(today, wd)
            cut(m)
    if day is None:
        m = re.search(rf"\s(?:on\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MON})\s", low) or re.search(
            rf"\s(?:on\s+)?({_MON})\s+(\d{{1,2}})(?:st|nd|rd|th)?\s", low
        )
        if m:
            a, b = m.group(1), m.group(2)
            d_num, mon = (int(a), MONTHS[b]) if a.isdigit() else (int(b), MONTHS[a])
            if 1 <= d_num <= 31:
                cand = _clamp_day(today.year, mon, d_num)
                if cand < today:
                    cand = _clamp_day(today.year + 1, mon, d_num)
                day = cand
                cut(m)
    if day is None:
        m = re.search(r"\s(?:on\s+)?(?:the\s+)?(\d{1,2})(st|nd|rd|th)\s", low)
        if m and 1 <= int(m.group(1)) <= 31:
            d_num = int(m.group(1))
            cand = _clamp_day(today.year, today.month, d_num)
            if cand < today:
                y, mo = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
                cand = _clamp_day(y, mo, d_num)
            day = cand
            cut(m)
    if day is None:
        m = re.search(r"\s(\d{4})-(\d{2})-(\d{2})\s", low)
        if m:
            try:
                day = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                cut(m)
            except ValueError:
                pass
    if day is None and weekday_from_repeat is not None:
        day = _next_weekday(today, weekday_from_repeat)
    if day is None:
        day = today
        # A time that has already passed today most likely means tomorrow.
        if at is not None and datetime.combine(day, at) < now - timedelta(minutes=1) and kind != "task":
            day = today + timedelta(days=1)

    title = " ".join(s.split())
    title = re.sub(r"\s+(at|on|by|for|every|in)$", "", title, flags=re.I).strip(" ,.-")
    if not title:
        return None
    title = title[0].upper() + title[1:]

    if kind is None:
        kind = "event" if at is not None else "task"
    return QuickAddResult(kind=kind, title=title, day=day, at=at, repeat=repeat)
