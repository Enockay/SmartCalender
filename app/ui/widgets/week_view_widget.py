from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
 )

from app.models.meeting import MeetingModel
from app.services.meeting_service import MeetingService


class _WeekCellDelegate(QStyledItemDelegate):
    """Ensures programmatic background colors survive QSS styling."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        bg = index.data(Qt.BackgroundRole)
        if bg is not None:
            brush = bg if isinstance(bg, QBrush) else QBrush(bg)
            if brush.style() != Qt.NoBrush:
                painter.fillRect(option.rect, brush)
                option.state &= ~QStyle.State_Selected
        super().paint(painter, option, index)


class WeekViewWidget(QWidget):
    meetingActivated = Signal(object)  # MeetingModel
    daySelected = Signal(object)       # date
    timeSlotSelected = Signal(object)  # datetime for clicked slot

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("WeekViewRoot")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header bar (matches year view) ──
        header = QWidget(self)
        header.setObjectName("WeekHeader")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 8, 16, 8)
        h_lay.setSpacing(10)

        self._title = QLabel("Week View", header)
        self._title.setObjectName("WeekTitle")

        self._summary = QLabel("", header)
        self._summary.setObjectName("WeekSummary")

        h_lay.addWidget(self._title)
        h_lay.addStretch()
        h_lay.addWidget(self._summary)

        outer.addWidget(header)

        # ── Table ──
        self._table = QTableWidget(self)
        self._table.setObjectName("WeekGrid")
        self._table.setColumnCount(8)  # Time + 7 days
        self._table.setRowCount(24)    # 24 hours
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setVisible(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setMinimumHeight(32)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._table.setColumnWidth(0, 60)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.horizontalHeader().setObjectName("WeekGridHeader")
        self._table.setItemDelegate(_WeekCellDelegate(self._table))
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self._table.cellClicked.connect(self._on_cell_clicked)

        outer.addWidget(self._table, 1)

        self._load_qss()

        self._service = MeetingService()
        self._week_start: date = date.today()
        self._meetings: List[MeetingModel] = []
        self._focused_date: date | None = None
        self._build_grid()

    def set_date(self, d: date) -> None:
        """Set the reference date; widget fetches and renders the whole week."""
        self._week_start = d - timedelta(days=d.weekday())
        week_end = self._week_start + timedelta(days=7)
        self._title.setText(
            f"{self._week_start.strftime('%d %b')} – {(week_end - timedelta(days=1)).strftime('%d %b %Y')}"
        )
        self._meetings = self._service.list_meetings_between(
            datetime.combine(self._week_start, time.min),
            datetime.combine(week_end, time.min),
        )
        total = len(self._meetings)
        self._summary.setText(
            f"{total} meeting{'s' if total != 1 else ''}" if total else "No meetings"
        )
        self._render()

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "week_view.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def _build_grid(self) -> None:
        time_font = QFont("Segoe UI", 9)
        for r in range(24):
            t = time(hour=r, minute=0)
            time_item = QTableWidgetItem(t.strftime("%H:%M"))
            time_item.setTextAlignment(Qt.AlignCenter)
            time_item.setData(Qt.ForegroundRole, QBrush(QColor("#64748B")))
            time_item.setData(Qt.BackgroundRole, QBrush(QColor("#F8FAFC")))
            time_item.setFont(time_font)
            self._table.setItem(r, 0, time_item)
            self._table.setRowHeight(r, 40)
            for c in range(1, 8):
                self._table.setItem(r, c, QTableWidgetItem(""))

        self._update_headers()

    def _update_headers(self) -> None:
        today = date.today()
        labels = [""]
        for i in range(7):
            d = self._week_start + timedelta(days=i)
            label = d.strftime("%a %d")
            if d == today:
                label = f"● {label}"
            labels.append(label)
        self._table.setHorizontalHeaderLabels(labels)

        if self._focused_date is not None:
            try:
                day_idx = (self._focused_date - self._week_start).days
            except Exception:
                day_idx = -1
            if 0 <= day_idx < 7:
                item = self._table.horizontalHeaderItem(1 + day_idx)
                if item is not None:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)

    def _clear_spans_and_cells(self) -> None:
        self._table.clearSpans()
        self._table.clearSelection()
        today = date.today()
        for r in range(24):
            for c in range(1, 8):
                it = self._table.item(r, c)
                if it is None:
                    it = QTableWidgetItem("")
                    self._table.setItem(r, c, it)
                it.setText("")
                it.setData(Qt.UserRole, None)
                d = self._week_start + timedelta(days=c - 1)
                if d == today:
                    it.setData(Qt.BackgroundRole, QBrush(QColor("#EFF6FF")))
                else:
                    it.setData(Qt.BackgroundRole, QBrush(QColor("#FFFFFF")))
                it.setData(Qt.ForegroundRole, QBrush(QColor("#334155")))

    def focus_day(self, d: date) -> None:
        self._focused_date = d
        self._update_headers()

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
            end_hour = end.hour + (1 if end.minute or end.second else 0)
            end_row_excl = min(24, max(start_row + 1, end_hour))
            span_rows = max(1, end_row_excl - start_row)

            overlap = False
            for r in range(start_row, end_row_excl):
                cell = self._table.item(r, col)
                if cell is not None and cell.data(Qt.UserRole):
                    overlap = True
                    break
            if overlap:
                continue

            item = self._table.item(start_row, col)
            if span_rows > 1:
                self._table.setSpan(start_row, col, span_rows, 1)

            item.setText(m.title)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
            item.setData(Qt.ForegroundRole, QBrush(QColor("#FFFFFF")))
            item.setData(Qt.BackgroundRole, self._brush_for_gradient(getattr(m, "color_gradient", None)))
            font = QFont("Segoe UI", 10, QFont.Bold)
            item.setFont(font)
            for r in range(start_row, end_row_excl):
                cell = self._table.item(r, col)
                if cell is None:
                    cell = QTableWidgetItem("")
                    self._table.setItem(r, col, cell)
                cell.setData(Qt.UserRole, m if r == start_row else True)

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        if col == 0:
            return
        item = self._table.item(row, col)
        meeting = item.data(Qt.UserRole) if item else None
        if meeting:
            self.meetingActivated.emit(meeting)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if col == 0:
            return

        item = self._table.item(row, col)
        payload = item.data(Qt.UserRole) if item else None
        if isinstance(payload, MeetingModel):
            self.meetingActivated.emit(payload)
            return

        target_date = self._week_start + timedelta(days=col - 1)
        self.daySelected.emit(target_date)

        slot_time = time(hour=row, minute=0)
        slot_dt = datetime.combine(target_date, slot_time)
        self.timeSlotSelected.emit(slot_dt)
