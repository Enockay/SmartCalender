from __future__ import annotations

from datetime import date, time
from pathlib import Path
from typing import List, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app.models.meeting import MeetingModel
from app.ui.widgets.todo_list_widget import TodoListWidget


class DayViewWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DayViewRoot")
        layout = QVBoxLayout(self)

        self._title = QLabel("Day View")
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._title.setProperty("viewTitle", True)

        self._todo_table = TodoListWidget(self)

        layout.addWidget(self._title)
        layout.addWidget(self._todo_table)

        self._load_qss()

    @property
    def list_widget(self):
        # Kept for compatibility with MainWindow._open_meeting_details;
        # this view no longer uses a QListWidget, so return None.
        return None

    def meeting_for_item(self, _item):
        # Day view is now table-based; double‑click behaviour
        # can be wired differently later if needed.
        return None

    def set_day(self, d: date, meetings: List[MeetingModel]) -> None:
        """Update only the title; events are set by MainWindow."""
        self._title.setText(f"Day View – {d.strftime('%a %d %b %Y')}")

    def set_events(self, events: Dict[time, object]) -> None:
        self._todo_table.set_events(events)

    @property
    def todo_table(self) -> TodoListWidget:
        return self._todo_table

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "day_view.qss"
        if qss_path.exists():
            # Merge with existing app styles
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))
