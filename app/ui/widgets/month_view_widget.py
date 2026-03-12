from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QLinearGradient

from app.models.meeting import MeetingModel
from app.services.meeting_service import MeetingService


class MonthViewWidget(QWidget):
    daySelected = Signal(object)  # date for the clicked day

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MonthViewRoot")
        layout = QVBoxLayout(self)

        self._title = QLabel("Month View")
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._title.setProperty("viewTitle", True)

        self._table = QTableWidget(self)
        self._table.setObjectName("MonthGrid")
        self._table.setRowCount(6)   # Up to 6 weeks
        self._table.setColumnCount(7)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setVisible(True)
        # Make both columns and rows stretch so the month grid fills the view.
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.NoSelection)

        layout.addWidget(self._title)
        layout.addWidget(self._table)

        self._load_qss()

        self._service = MeetingService()
        self._month: date = date.today().replace(day=1)
        self._meetings: List[MeetingModel] = []

        # When the user clicks a cell, compute the calendar date and emit it.
        self._table.cellClicked.connect(self._on_cell_clicked)

    def _summarize_title(self, title: str, max_chars: int = 14) -> str:
        """Return a short summary of the meeting title for month cells."""
        title = title.strip()
        if len(title) <= max_chars:
            return title
        # Try to cut on a word boundary if possible.
        cutoff = title.rfind(" ", 0, max_chars)
        if cutoff == -1:
            cutoff = max_chars
        return title[:cutoff].rstrip() + "..."

    def set_date(self, d: date) -> None:
        """Fetch and render meetings for the month containing date d."""
        self._month = d.replace(day=1)
        next_month = (self._month.replace(day=28) + timedelta(days=4)).replace(day=1)
        self._title.setText(self._month.strftime("Month View – %B %Y"))

        self._meetings = self._service.list_meetings_between(
            datetime.combine(self._month, time.min),
            datetime.combine(next_month, time.min),
        )
        self._render()

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "month_view.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def _brush_for_gradient(self, raw: str | None) -> QBrush:
        if raw and isinstance(raw, str) and raw.startswith("linear:"):
            try:
                _, c1, c2 = raw.split(":")
                grad = QLinearGradient(0, 0, 1, 0)
                grad.setCoordinateMode(QLinearGradient.ObjectBoundingMode)
                grad.setColorAt(0.0, QColor(c1))
                grad.setColorAt(1.0, QColor(c2))
                return QBrush(grad)
            except Exception:
                return QBrush(QColor("#2563EB"))
        return QBrush(QColor(raw or "#2563EB"))

    def _render(self) -> None:
        # Header labels
        self._table.setHorizontalHeaderLabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])

        # Clear all cells
        for r in range(6):
            for c in range(7):
                item = self._table.item(r, c)
                if item is None:
                    item = QTableWidgetItem("")
                    self._table.setItem(r, c, item)
                item.setText("")
                item.setBackground(QBrush(QColor("#FFFFFF")))
                item.setForeground(QBrush(QColor("#0F172A")))
                # Top-right alignment for all day cells
                item.setTextAlignment(Qt.AlignRight | Qt.AlignTop)

        # Map day -> meetings
        by_day: Dict[int, List[MeetingModel]] = {}
        for m in self._meetings:
            day = m.start_time.day
            by_day.setdefault(day, []).append(m)

        first_weekday = (self._month.weekday() + 0) % 7  # Monday=0
        days_in_month = ((self._month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day

        day = 1
        row = 0
        col = first_weekday
        while day <= days_in_month and row < 6:
            item = self._table.item(row, col)
            meetings = by_day.get(day, [])
            if meetings:
                m = meetings[0]
                short_title = self._summarize_title(m.title)
                text = f"{day}\n{short_title}"
                if len(meetings) > 1:
                    text += f"\n+{len(meetings)-1} more"
                item.setText(text)
                item.setBackground(self._brush_for_gradient(getattr(m, "color_gradient", None)))
                item.setForeground(QBrush(QColor("#FFFFFF")))
            else:
                item.setText(str(day))
                item.setForeground(QBrush(QColor("#0F172A")))
                item.setBackground(QBrush(QColor("#F9FAFB")))

            col += 1
            if col >= 7:
                col = 0
                row += 1
            day += 1

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Emit the exact date for the clicked month cell."""
        first_weekday = (self._month.weekday() + 0) % 7  # Monday=0
        index = row * 7 + col - first_weekday
        if index < 0:
            return

        day = index + 1
        days_in_month = ((self._month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
        if day < 1 or day > days_in_month:
            return

        target = date(self._month.year, self._month.month, day)
        self.daySelected.emit(target)
