from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QTextCharFormat, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QCalendarWidget


class MiniCalendarWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MiniCalendarRoot")
        # Keep the mini calendar card at a fixed size so it
        # doesn't get stretched and lose its visual proportions.
        self.setFixedSize(230, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._calendar = QCalendarWidget(self)
        self._calendar.setObjectName("MiniCalendar")
        self._calendar.setGridVisible(False)
        # Use single-letter day names so they fit cleanly
        # in the compact mini calendar header.
        self._calendar.setHorizontalHeaderFormat(QCalendarWidget.SingleLetterDayNames)
        self._calendar.setFirstDayOfWeek(Qt.Sunday)
        self._calendar.setSelectedDate(QDate.currentDate())

        font = QFont("Avenir Next", 13)
        if not font.exactMatch():
            font = QFont("Helvetica Neue", 13)
        self._calendar.setFont(font)

        layout.addWidget(self._calendar)

        self._load_qss()
        self._configure_formats()

    @property
    def calendar(self) -> QCalendarWidget:
        return self._calendar

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "mini_calendar.qss"
        if qss_path.exists():
            style = qss_path.read_text(encoding="utf-8")
            self.setStyleSheet(style)

    def _configure_formats(self) -> None:
        # Header weekdays white
        header_format = QTextCharFormat()
        header_format.setForeground(QColor("#E5E7EB"))
        for weekday in (
            Qt.Monday,
            Qt.Tuesday,
            Qt.Wednesday,
            Qt.Thursday,
            Qt.Friday,
            Qt.Saturday,
            Qt.Sunday,
        ):
            self._calendar.setWeekdayTextFormat(weekday, header_format)

        self._calendar.currentPageChanged.connect(
            lambda _y, _m: self._update_day_formats()
        )
        self._calendar.selectionChanged.connect(self._update_day_formats)
        self._update_day_formats()

    def _update_day_formats(self) -> None:
        today = QDate.currentDate()
        year = self._calendar.yearShown()
        month = self._calendar.monthShown()

        normal = QTextCharFormat()
        normal.setForeground(QColor("#FFFFFF"))  # upcoming / today

        past = QTextCharFormat()
        past.setForeground(QColor("#9CA3AF"))  # already passed

        first_of_month = QDate(year, month, 1)
        fdow = self._calendar.firstDayOfWeek()
        first_day_of_week = fdow.value if hasattr(fdow, "value") else int(fdow)
        dow = first_of_month.dayOfWeek()
        offset = (dow - first_day_of_week) % 7
        start = first_of_month.addDays(-offset)

        for i in range(42):
            d = start.addDays(i)
            # All days from previous weeks / previous month,
            # and any day before "today", are shown in a greyish color.
            if d < today or d.month() != month:
                fmt = past
            else:
                fmt = normal
            self._calendar.setDateTextFormat(d, fmt)

