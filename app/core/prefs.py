"""Date and time preferences shared by every view (UX review §4.10).

week_start: 0 = Monday, 6 = Sunday, 5 = Saturday (Python weekday numbers).
clock: "24h" or "12h". Defaults follow the computer's locale.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QLocale, Qt

_cache: dict[str, str] = {}


def _settings():
    from app.services.settings_service import SettingsService
    return SettingsService()


def _locale_week_start() -> int:
    first = QLocale.system().firstDayOfWeek()  # Qt.DayOfWeek, Monday=1
    return (int(first.value if hasattr(first, "value") else first) - 1) % 7


def _locale_clock() -> str:
    fmt = QLocale.system().timeFormat(QLocale.ShortFormat)
    return "12h" if ("AP" in fmt.upper()) else "24h"


def reload() -> None:
    _cache.clear()


def week_start() -> int:
    if "week_start" not in _cache:
        _cache["week_start"] = _settings().get_value("week_start", "") or str(_locale_week_start())
    try:
        return int(_cache["week_start"]) % 7
    except ValueError:
        return 0


def clock() -> str:
    if "clock" not in _cache:
        _cache["clock"] = _settings().get_value("clock_format", "") or _locale_clock()
    return _cache["clock"] if _cache["clock"] in ("12h", "24h") else "24h"


def start_of_week(d: date) -> date:
    return d - timedelta(days=(d.weekday() - week_start()) % 7)


def week_offset(first_of_month: date) -> int:
    """Column of the first day of the month in a week-start-aware grid."""
    return (first_of_month.weekday() - week_start()) % 7


def weekday_labels(fmt: str = "%a") -> list[str]:
    base = date(2024, 1, 1)  # a Monday
    return [(base + timedelta(days=(week_start() + i) % 7)).strftime(fmt) for i in range(7)]


def qt_first_day() -> Qt.DayOfWeek:
    return [Qt.Monday, Qt.Tuesday, Qt.Wednesday, Qt.Thursday, Qt.Friday, Qt.Saturday, Qt.Sunday][week_start()]


def fmt_time(t: datetime | time) -> str:
    if clock() == "12h":
        return t.strftime("%I:%M %p").lstrip("0")
    return t.strftime("%H:%M")


def time_zone_name() -> str:
    """The computer's time zone, e.g. 'Africa/Nairobi (UTC+03:00)'. Events follow it."""
    from PySide6.QtCore import QTimeZone, QDateTime
    tz = QTimeZone.systemTimeZone()
    off = tz.offsetFromUtc(QDateTime.currentDateTime()) // 60
    sign = "+" if off >= 0 else "-"
    return f"{bytes(tz.id()).decode() or 'Local time'} (UTC{sign}{abs(off) // 60:02d}:{abs(off) % 60:02d})"
