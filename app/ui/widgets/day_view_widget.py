from __future__ import annotations

from datetime import date, time
from pathlib import Path
from typing import List, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)

from app.models.meeting import MeetingModel
from app.ui.widgets.todo_list_widget import TodoListWidget


class DayViewWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DayViewRoot")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header bar (matches week / month / year header) ──
        header = QWidget(self)
        header.setObjectName("DayHeaderBar")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 8, 16, 8)
        h_lay.setSpacing(10)

        self._title = QLabel("Day View", header)
        self._title.setObjectName("DayTitle")

        self._summary = QLabel("", header)
        self._summary.setObjectName("DaySummary")

        h_lay.addWidget(self._title)
        h_lay.addStretch()
        h_lay.addWidget(self._summary)

        outer.addWidget(header)

        # ── Todo table ──
        self._todo_table = TodoListWidget(self)
        outer.addWidget(self._todo_table, 1)

        self._load_qss()

    @property
    def list_widget(self):
        return None

    def meeting_for_item(self, _item):
        return None

    def set_day(self, d: date, meetings: List[MeetingModel]) -> None:
        """Update the title; events are set by MainWindow."""
        self._title.setText(d.strftime("%A, %d %B %Y"))
        total = len(meetings)
        self._summary.setText(
            f"{total} event{'s' if total != 1 else ''}" if total else "No events"
        )

    def set_events(self, events: Dict[time, object]) -> None:
        self._todo_table.set_events(events)

    @property
    def todo_table(self) -> TodoListWidget:
        return self._todo_table

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "day_view.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))
