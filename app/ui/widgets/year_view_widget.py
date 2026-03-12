from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QPushButton,
)

from app.models.meeting import MeetingModel
from app.services.meeting_service import MeetingService


class MonthCard(QFrame):
    def __init__(
        self,
        month_name: str,
        meeting_count: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("MonthCard")
        self.setProperty("active", meeting_count > 0)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        self._month_label = QLabel(month_name, self)
        self._month_label.setObjectName("MonthName")
        self._month_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._month_label.setWordWrap(True)

        self._badge_label = QLabel(self)
        self._badge_label.setObjectName("MeetingBadge")
        self._badge_label.setAlignment(Qt.AlignCenter)

        self._meta_label = QLabel(self)
        self._meta_label.setObjectName("MonthMeta")
        self._meta_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._meta_label.setWordWrap(True)

        if meeting_count > 0:
            self._badge_label.setText(
                f"{meeting_count} meeting{'s' if meeting_count != 1 else ''}"
            )
            self._badge_label.setVisible(True)
            self._meta_label.setText("Scheduled this month")
        else:
            self._badge_label.setVisible(False)
            self._meta_label.setText("No meetings yet")

        layout.addWidget(self._month_label)
        layout.addWidget(self._badge_label, 0, Qt.AlignLeft)
        layout.addWidget(self._meta_label)
        layout.addStretch()

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(15, 23, 42, 25))
        self.setGraphicsEffect(shadow)


class YearViewWidget(QWidget):
    monthSelected = Signal(object)  # date (first day of month)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("YearViewRoot")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header with year title and navigation controls
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._prev_button = QPushButton("◀", self)
        self._prev_button.setObjectName("YearNavButton")
        self._prev_button.setCursor(Qt.PointingHandCursor)

        self._title = QLabel("Year View", self)
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._title.setProperty("viewTitle", True)

        self._next_button = QPushButton("▶", self)
        self._next_button.setObjectName("YearNavButton")
        self._next_button.setCursor(Qt.PointingHandCursor)

        header_layout.addWidget(self._prev_button, 0, Qt.AlignVCenter)
        header_layout.addWidget(self._title, 0, Qt.AlignVCenter)
        header_layout.addStretch(1)
        header_layout.addWidget(self._next_button, 0, Qt.AlignVCenter)

        self._table = QTableWidget(self)
        self._table.setObjectName("YearGrid")
        self._table.setRowCount(3)
        self._table.setColumnCount(4)

        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setVisible(False)

        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setShowGrid(False)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._table.setContentsMargins(0, 0, 0, 0)

        # Slight spacing effect between tiles
        self._table.horizontalHeader().setDefaultSectionSize(220)
        self._table.verticalHeader().setDefaultSectionSize(180)

        self._table.cellClicked.connect(self._on_cell_clicked)

        layout.addLayout(header_layout)
        layout.addWidget(self._table, 1)

        self._load_qss()

        self._service = MeetingService()
        self._year: int = date.today().year
        self._meetings: List[MeetingModel] = []

        self._initialize_cells()

        # Connect navigation
        self._prev_button.clicked.connect(self._go_previous_year)
        self._next_button.clicked.connect(self._go_next_year)

        # Load current year by default
        self.set_date(date.today())

    def set_date(self, d: date) -> None:
        """Fetch and render meetings for the whole year containing d."""
        self._set_year(d.year)

    def _set_year(self, year: int) -> None:
        """Internal helper to change the active year and refresh data."""
        self._year = year
        self._title.setText(f"Year View – {self._year}")

        start = date(self._year, 1, 1)
        end = date(self._year + 1, 1, 1)

        self._meetings = self._service.list_meetings_between(
            datetime.combine(start, time.min),
            datetime.combine(end, time.min),
        )
        self._render()

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "year_view.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def _initialize_cells(self) -> None:
        """Create placeholder widgets so the grid is always populated."""
        month_names = [
            "January", "February", "March", "April",
            "May", "June", "July", "August",
            "September", "October", "November", "December",
        ]

        for month in range(1, 13):
            row = (month - 1) // 4
            col = (month - 1) % 4

            container = QWidget(self)
            container.setObjectName("MonthCellContainer")

            layout = QVBoxLayout(container)
            layout.setContentsMargins(6, 6, 6, 6)
            layout.setSpacing(0)

            card = MonthCard(month_names[month - 1], 0, container)
            layout.addWidget(card)

            container.setProperty("month", month)
            self._table.setCellWidget(row, col, container)

    def _render(self) -> None:
        by_month: Dict[int, List[MeetingModel]] = {}
        for meeting in self._meetings:
            month = meeting.start_time.month
            by_month.setdefault(month, []).append(meeting)

        month_names = [
            "January", "February", "March", "April",
            "May", "June", "July", "August",
            "September", "October", "November", "December",
        ]

        for month in range(1, 13):
            row = (month - 1) // 4
            col = (month - 1) % 4

            meetings = by_month.get(month, [])
            count = len(meetings)

            container = QWidget(self)
            container.setObjectName("MonthCellContainer")
            container.setProperty("month", month)

            layout = QVBoxLayout(container)
            layout.setContentsMargins(6, 6, 6, 6)
            layout.setSpacing(0)

            card = MonthCard(
                month_name=month_names[month - 1],
                meeting_count=count,
                parent=container,
            )
            layout.addWidget(card)

            old_widget = self._table.cellWidget(row, col)
            if old_widget is not None:
                old_widget.deleteLater()

            self._table.setCellWidget(row, col, container)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        month = row * 4 + col + 1
        target = date(self._year, month, 1)
        self.monthSelected.emit(target)

    def _go_previous_year(self) -> None:
        """Navigate to the previous year."""
        self._set_year(self._year - 1)

    def _go_next_year(self) -> None:
        """Navigate to the next year."""
        self._set_year(self._year + 1)