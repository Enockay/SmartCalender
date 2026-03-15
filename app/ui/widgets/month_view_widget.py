from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont, QLinearGradient, QPainter

from app.models.meeting import MeetingModel
from app.services.meeting_service import MeetingService


class _MonthCellDelegate(QStyledItemDelegate):
    """Ensures programmatic background colors survive QSS styling."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        bg = index.data(Qt.BackgroundRole)
        if bg is not None:
            brush = bg if isinstance(bg, QBrush) else QBrush(bg)
            if brush.style() != Qt.NoBrush:
                painter.fillRect(option.rect, brush)
                option.state &= ~QStyle.State_Selected
        super().paint(painter, option, index)


class MonthViewWidget(QWidget):
    daySelected = Signal(object)  # date for the clicked day

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MonthViewRoot")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header bar ──
        header = QWidget(self)
        header.setObjectName("MonthHeaderBar")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 8, 16, 8)
        h_lay.setSpacing(10)

        self._title = QLabel("Month View", header)
        self._title.setObjectName("MonthTitle")

        self._summary = QLabel("", header)
        self._summary.setObjectName("MonthSummary")

        h_lay.addWidget(self._title)
        h_lay.addStretch()
        h_lay.addWidget(self._summary)

        outer.addWidget(header)

        # ── Table grid ──
        self._table = QTableWidget(self)
        self._table.setObjectName("MonthGrid")
        self._table.setRowCount(6)
        self._table.setColumnCount(7)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setVisible(True)
        self._table.horizontalHeader().setObjectName("MonthGridHeader")
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setFocusPolicy(Qt.NoFocus)

        # Custom delegate so that setBackground() colors are always painted
        # even when QSS styles ::item elements.
        self._table.setItemDelegate(_MonthCellDelegate(self._table))

        outer.addWidget(self._table, 1)

        self._load_qss()

        self._service = MeetingService()
        self._month: date = date.today().replace(day=1)
        self._meetings: List[MeetingModel] = []

        self._table.cellClicked.connect(self._on_cell_clicked)

    def _summarize_title(self, title: str, max_chars: int = 16) -> str:
        title = title.strip()
        if len(title) <= max_chars:
            return title
        cutoff = title.rfind(" ", 0, max_chars)
        if cutoff == -1:
            cutoff = max_chars
        return title[:cutoff].rstrip() + "…"

    def set_date(self, d: date) -> None:
        self._month = d.replace(day=1)
        next_month = (self._month.replace(day=28) + timedelta(days=4)).replace(day=1)
        self._title.setText(self._month.strftime("%B %Y"))

        self._meetings = self._service.list_meetings_between(
            datetime.combine(self._month, time.min),
            datetime.combine(next_month, time.min),
        )
        total = len(self._meetings)
        self._summary.setText(
            f"{total} meeting{'s' if total != 1 else ''}" if total else "No meetings"
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
        today = date.today()
        self._table.setHorizontalHeaderLabels(
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        )

        day_font = QFont("Segoe UI", 12, QFont.Bold)

        # Clear all cells
        for r in range(6):
            for c in range(7):
                item = self._table.item(r, c)
                if item is None:
                    item = QTableWidgetItem("")
                    self._table.setItem(r, c, item)
                item.setText("")
                item.setFont(day_font)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                item.setData(Qt.BackgroundRole, QBrush(QColor("#FFFFFF")))
                item.setData(Qt.ForegroundRole, QBrush(QColor("#0F172A")))

        # Map day -> meetings
        by_day: Dict[int, List[MeetingModel]] = {}
        for m in self._meetings:
            day = m.start_time.day
            by_day.setdefault(day, []).append(m)

        first_weekday = self._month.weekday()  # Monday=0
        days_in_month = (
            (self._month.replace(day=28) + timedelta(days=4)).replace(day=1)
            - timedelta(days=1)
        ).day

        day = 1
        row = 0
        col = first_weekday
        while day <= days_in_month and row < 6:
            item = self._table.item(row, col)
            meetings = by_day.get(day, [])
            current_date = date(self._month.year, self._month.month, day)
            is_today = current_date == today
            is_weekend = col >= 5

            if meetings:
                m = meetings[0]
                short_title = self._summarize_title(m.title)
                text = f" {day}\n {short_title}"
                if len(meetings) > 1:
                    text += f"\n +{len(meetings) - 1} more"
                item.setText(text)
                bg_brush = self._brush_for_gradient(
                    getattr(m, "color_gradient", None)
                )
                item.setData(Qt.BackgroundRole, bg_brush)
                item.setData(Qt.ForegroundRole, QBrush(QColor("#FFFFFF")))
            else:
                item.setText(f" {day}")
                if is_today:
                    item.setData(Qt.BackgroundRole, QBrush(QColor("#DBEAFE")))
                    item.setData(Qt.ForegroundRole, QBrush(QColor("#1D4ED8")))
                elif is_weekend:
                    item.setData(Qt.BackgroundRole, QBrush(QColor("#F8FAFC")))
                    item.setData(Qt.ForegroundRole, QBrush(QColor("#64748B")))
                else:
                    item.setData(Qt.BackgroundRole, QBrush(QColor("#FFFFFF")))
                    item.setData(Qt.ForegroundRole, QBrush(QColor("#0F172A")))

            col += 1
            if col >= 7:
                col = 0
                row += 1
            day += 1

        # Force the table to repaint so the delegate picks up new colors.
        self._table.viewport().update()

    def _on_cell_clicked(self, row: int, col: int) -> None:
        first_weekday = self._month.weekday()
        index = row * 7 + col - first_weekday
        if index < 0:
            return
        day = index + 1
        days_in_month = (
            (self._month.replace(day=28) + timedelta(days=4)).replace(day=1)
            - timedelta(days=1)
        ).day
        if day < 1 or day > days_in_month:
            return
        target = date(self._month.year, self._month.month, day)
        self.daySelected.emit(target)
