from __future__ import annotations

import calendar
from datetime import date, datetime, time
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, QRect, QRectF, QSize
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models.meeting import MeetingModel
from app.services.meeting_service import MeetingService


# ────────────────────────────────────────────────────────
#  Mini‑calendar painted inside each month card
# ────────────────────────────────────────────────────────
class _MiniCalendar(QWidget):
    """Tiny calendar grid drawn with QPainter – no child widgets."""

    _DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"]

    def __init__(
        self,
        year: int,
        month: int,
        busy_days: set[int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._year = year
        self._month = month
        self._busy: set[int] = busy_days or set()
        self._today = date.today()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # noinspection PyMethodOverriding
    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(180, 120)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cell_w = w / 7
        cell_h = h / 7  # row 0 = header

        # ── Day‑of‑week header row ──
        header_font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(header_font)
        painter.setPen(QColor("#94A3B8"))
        for col, lbl in enumerate(self._DAY_LABELS):
            r = QRectF(col * cell_w, 0, cell_w, cell_h)
            painter.drawText(r, Qt.AlignCenter, lbl)

        # ── Day numbers ──
        day_font = QFont("Segoe UI", 8)
        painter.setFont(day_font)

        first_weekday, days_in = calendar.monthrange(self._year, self._month)
        row = 1
        col = first_weekday  # Monday = 0

        for day in range(1, days_in + 1):
            cx = col * cell_w + cell_w / 2
            cy = row * cell_h + cell_h / 2
            radius = min(cell_w, cell_h) * 0.38

            is_today = (
                self._year == self._today.year
                and self._month == self._today.month
                and day == self._today.day
            )
            is_busy = day in self._busy

            # Draw a filled dot behind busy / today days
            if is_today:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#2563EB"))
                painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
                painter.setPen(QColor("#FFFFFF"))
            elif is_busy:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#DBEAFE"))
                painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
                painter.setPen(QColor("#1E40AF"))
            else:
                painter.setPen(QColor("#475569"))

            painter.setFont(day_font)
            text_rect = QRectF(col * cell_w, row * cell_h, cell_w, cell_h)
            painter.drawText(text_rect, Qt.AlignCenter, str(day))

            col += 1
            if col >= 7:
                col = 0
                row += 1

        painter.end()


# ────────────────────────────────────────────────────────
#  Month card (one per month)
# ────────────────────────────────────────────────────────
class MonthCard(QFrame):
    clicked = Signal(int)  # month number 1–12

    def __init__(
        self,
        year: int,
        month: int,
        meetings: List[MeetingModel] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._month = month
        meetings = meetings or []

        is_current = date.today().year == year and date.today().month == month
        has_meetings = len(meetings) > 0

        self.setObjectName("YearMonthCard")
        self.setProperty("current", is_current)
        self.setProperty("active", has_meetings)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(4)

        # ── Top row: month name + badge ──
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        month_name = calendar.month_abbr[month].upper()
        name_label = QLabel(month_name, self)
        name_label.setObjectName("YearMonthName")
        top_row.addWidget(name_label)

        top_row.addStretch()

        if has_meetings:
            badge = QLabel(str(len(meetings)), self)
            badge.setObjectName("YearMeetingBadge")
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(24, 24)
            top_row.addWidget(badge)

        layout.addLayout(top_row)

        # ── Mini calendar ──
        busy_days = {m.start_time.day for m in meetings}
        mini_cal = _MiniCalendar(year, month, busy_days, self)
        layout.addWidget(mini_cal, 1)

        # ── Meeting summary (first 2 meetings) ──
        if meetings:
            sorted_meetings = sorted(meetings, key=lambda m: m.start_time)
            for m in sorted_meetings[:2]:
                line = QLabel(
                    f"• {m.start_time.strftime('%d')} {self._trunc(m.title, 20)}",
                    self,
                )
                line.setObjectName("YearMeetingLine")
                layout.addWidget(line)
            if len(meetings) > 2:
                more = QLabel(f"+{len(meetings) - 2} more", self)
                more.setObjectName("YearMeetingMore")
                layout.addWidget(more)

        # Subtle shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(15, 23, 42, 20))
        self.setGraphicsEffect(shadow)

    @staticmethod
    def _trunc(text: str, n: int) -> str:
        return text if len(text) <= n else text[: n - 1].rstrip() + "…"

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self._month)
        super().mousePressEvent(event)


# ────────────────────────────────────────────────────────
#  Year view
# ────────────────────────────────────────────────────────
class YearViewWidget(QWidget):
    monthSelected = Signal(object)  # date (first day of month)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("YearViewRoot")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)

        # ── Header bar ──
        header = QWidget(self)
        header.setObjectName("YearHeader")
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(16, 10, 16, 10)
        header_lay.setSpacing(12)

        self._prev_btn = QPushButton("‹", header)
        self._prev_btn.setObjectName("YearNavBtn")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.setCursor(Qt.PointingHandCursor)

        self._title = QLabel("2026", header)
        self._title.setObjectName("YearTitle")

        self._next_btn = QPushButton("›", header)
        self._next_btn.setObjectName("YearNavBtn")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.setCursor(Qt.PointingHandCursor)

        self._summary = QLabel("", header)
        self._summary.setObjectName("YearSummary")

        header_lay.addWidget(self._prev_btn)
        header_lay.addWidget(self._title)
        header_lay.addWidget(self._next_btn)
        header_lay.addStretch()
        header_lay.addWidget(self._summary)

        outer.addWidget(header)

        # ── Scrollable grid area ──
        scroll = QScrollArea(self)
        scroll.setObjectName("YearScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self._grid_widget = QWidget(scroll)
        self._grid_widget.setObjectName("YearGridArea")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(12, 8, 12, 12)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(10)

        scroll.setWidget(self._grid_widget)
        outer.addWidget(scroll, 1)

        # ── State ──
        self._service = MeetingService()
        self._year: int = date.today().year
        self._meetings: List[MeetingModel] = []
        self._cards: List[MonthCard] = []

        self._prev_btn.clicked.connect(lambda: self._set_year(self._year - 1))
        self._next_btn.clicked.connect(lambda: self._set_year(self._year + 1))

        self._load_qss()
        self.set_date(date.today())

    # ── Public API ──
    def set_date(self, d: date) -> None:
        self._set_year(d.year)

    # ── Internal ──
    def _set_year(self, year: int) -> None:
        self._year = year
        self._title.setText(str(self._year))

        start = date(self._year, 1, 1)
        end = date(self._year + 1, 1, 1)
        self._meetings = self._service.list_meetings_between(
            datetime.combine(start, time.min),
            datetime.combine(end, time.min),
        )

        total = len(self._meetings)
        self._summary.setText(
            f"{total} meeting{'s' if total != 1 else ''} this year"
            if total
            else "No meetings this year"
        )

        self._render()

    def _render(self) -> None:
        # Group meetings by month
        by_month: Dict[int, List[MeetingModel]] = {}
        for m in self._meetings:
            by_month.setdefault(m.start_time.month, []).append(m)

        # Clear old cards
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        for month in range(1, 13):
            row = (month - 1) // 4
            col = (month - 1) % 4
            meetings = by_month.get(month, [])
            card = MonthCard(self._year, month, meetings, self._grid_widget)
            card.clicked.connect(self._on_card_clicked)
            self._grid.addWidget(card, row, col)
            self._cards.append(card)

    def _on_card_clicked(self, month: int) -> None:
        target = date(self._year, month, 1)
        self.monthSelected.emit(target)

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "year_view.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))
