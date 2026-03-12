from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QLinearGradient
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
 )

from app.models.meeting import MeetingModel
from app.services.meeting_service import MeetingService


class WeekViewWidget(QWidget):
    meetingActivated = Signal(object)  # MeetingModel
    daySelected = Signal(object)       # date
    timeSlotSelected = Signal(object)  # datetime for clicked slot

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("WeekViewRoot")
        layout = QVBoxLayout(self)

        self._title = QLabel("Week View")
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._title.setProperty("viewTitle", True)

        self._table = QTableWidget(self)
        self._table.setObjectName("WeekGrid")
        self._table.setColumnCount(8)  # Time + 7 days
        self._table.setRowCount(24)    # 24 hours
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setVisible(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setMinimumHeight(34)
        self._table.setColumnWidth(0, 70)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Disable selection so that Qt's selection highlight does not
        # override the per-meeting background colors we set in _render().
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self._table.setFocusPolicy(Qt.NoFocus)
        # Give the horizontal header its own object name so QSS can override
        # generic header styles from other views.
        self._table.horizontalHeader().setObjectName("WeekHeader")
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self._table.cellClicked.connect(self._on_cell_clicked)

        layout.addWidget(self._title)
        layout.addWidget(self._table)

        self._load_qss()

        self._service = MeetingService()
        self._week_start: date = date.today()
        self._meetings: List[MeetingModel] = []
        self._build_grid()

    def set_date(self, d: date) -> None:
        """Set the reference date; widget fetches and renders the whole week."""
        # Monday as week start
        self._week_start = d - timedelta(days=d.weekday())
        week_end = self._week_start + timedelta(days=7)
        self._title.setText(
            f"Weekly View – {self._week_start.strftime('%d %b %Y')} to {(week_end - timedelta(days=1)).strftime('%d %b %Y')}"
        )
        self._meetings = self._service.list_meetings_between(
            datetime.combine(self._week_start, time.min),
            datetime.combine(week_end, time.min),
        )
        self._render()

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "week_view.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def _build_grid(self) -> None:
        # Initialize time column + empty cells
        for r in range(24):
            t = time(hour=r, minute=0)
            time_item = QTableWidgetItem(t.strftime("%H:%M"))
            time_item.setTextAlignment(Qt.AlignCenter)
            time_item.setForeground(QBrush(QColor("#64748B")))
            time_item.setBackground(QBrush(QColor("#F8FAFC")))
            self._table.setItem(r, 0, time_item)
            self._table.setRowHeight(r, 52)
            for c in range(1, 8):
                self._table.setItem(r, c, QTableWidgetItem(""))

        self._update_headers()

    def _update_headers(self) -> None:
        labels = ["Time"]
        for i in range(7):
            d = self._week_start + timedelta(days=i)
            labels.append(d.strftime("%a %d"))
        self._table.setHorizontalHeaderLabels(labels)

    def _clear_spans_and_cells(self) -> None:
        self._table.clearSpans()
        # Ensure any leftover selection highlight is removed so that
        # cell background colors (meeting gradients) remain visible.
        self._table.clearSelection()
        for r in range(24):
            for c in range(1, 8):
                it = self._table.item(r, c)
                if it is None:
                    it = QTableWidgetItem("")
                    self._table.setItem(r, c, it)
                it.setText("")
                it.setData(Qt.UserRole, None)
                it.setBackground(QBrush(QColor("#FFFFFF")))
                it.setForeground(QBrush(QColor("#334155")))

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
        self._update_headers()
        self._clear_spans_and_cells()

        for m in self._meetings:
            start = m.start_time
            end = m.end_time
            day_idx = (start.date() - self._week_start).days
            if day_idx < 0 or day_idx > 6:
                continue

            col = 1 + day_idx
            start_row = max(0, start.hour)
            # round up end hour if has minutes
            end_hour = end.hour + (1 if end.minute or end.second else 0)
            end_row_excl = min(24, max(start_row + 1, end_hour))
            span_rows = max(1, end_row_excl - start_row)

            item = self._table.item(start_row, col)
            # Skip if this slot already has a meeting rendered
            if item.data(Qt.UserRole):
                continue

            # Only create a span if it actually covers multiple rows; this
            # avoids Qt warnings about single-cell spans.
            if span_rows > 1:
                self._table.setSpan(start_row, col, span_rows, 1)

            item.setText(m.title)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
            item.setForeground(QBrush(QColor("#FFFFFF")))
            item.setBackground(self._brush_for_gradient(getattr(m, "color_gradient", None)))
            item.setData(Qt.UserRole, m)

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        if col == 0:
            return
        # If a meeting is stored in this cell, emit it; otherwise emit None and let caller create
        item = self._table.item(row, col)
        meeting = item.data(Qt.UserRole) if item else None
        if meeting:
            self.meetingActivated.emit(meeting)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Single-click navigates to the specific day and emits the exact slot."""
        if col == 0:
            return
        target_date = self._week_start + timedelta(days=col - 1)
        self.daySelected.emit(target_date)

        # Row index corresponds to the hour (0–23) in this simplified grid.
        slot_time = time(hour=row, minute=0)
        slot_dt = datetime.combine(target_date, slot_time)
        self.timeSlotSelected.emit(slot_dt)
