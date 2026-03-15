from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QTextCharFormat, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QCalendarWidget, QLabel


class MiniCalendarWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MiniCalendarRoot")
        self.setFixedSize(224, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(0)

        self._calendar = QCalendarWidget(self)
        self._calendar.setObjectName("MiniCalendar")
        self._calendar.setGridVisible(False)
        self._calendar.setHorizontalHeaderFormat(QCalendarWidget.SingleLetterDayNames)
        self._calendar.setFirstDayOfWeek(Qt.Sunday)
        self._calendar.setSelectedDate(QDate.currentDate())
        self._calendar.setNavigationBarVisible(True)

        font = QFont("Segoe UI", 12)
        if not font.exactMatch():
            font = QFont("Helvetica Neue", 12)
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
        header_format = QTextCharFormat()
        header_format.setForeground(QColor("#94A3B8"))
        header_format.setFont(QFont("Helvetica Neue", 10, QFont.DemiBold))
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
        normal.setForeground(QColor("#E2E8F0"))

        past = QTextCharFormat()
        past.setForeground(QColor("#475569"))

        today_fmt = QTextCharFormat()
        today_fmt.setForeground(QColor("#FFFFFF"))
        today_fmt.setBackground(QColor("#3B82F6"))
        today_fmt.setFont(QFont("Helvetica Neue", 12, QFont.Bold))

        first_of_month = QDate(year, month, 1)
        fdow = self._calendar.firstDayOfWeek()
        first_day_of_week = fdow.value if hasattr(fdow, "value") else int(fdow)
        dow = first_of_month.dayOfWeek()
        offset = (dow - first_day_of_week) % 7
        start = first_of_month.addDays(-offset)

        for i in range(42):
            d = start.addDays(i)
            if d == today and d.month() == month:
                fmt = today_fmt
            elif d < today or d.month() != month:
                fmt = past
            else:
                fmt = normal
            self._calendar.setDateTextFormat(d, fmt)
