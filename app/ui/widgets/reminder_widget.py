from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel, QComboBox


class ReminderWidget(QWidget):
    """Reminder row where the user can choose a system sound and reminder time."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReminderWidgetRoot")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(10)

        label = QLabel("Reminder sound", self)
        label.setObjectName("ReminderLabel")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._sound_combo = QComboBox(self)
        self._sound_combo.setObjectName("ReminderSoundCombo")
        # Placeholder list of system-like sounds; can be wired to actual
        # system sounds later.
        self._sound_combo.addItems(
            [
                "System Default",
                "Chime",
                "Ping",
                "Alert",
                "Soft Bell",
            ]
        )

        # Reminder time (how many minutes before the meeting)
        self._time_combo = QComboBox(self)
        self._time_combo.setObjectName("ReminderTimeCombo")
        self._time_combo.addItem("5 min before", 5)
        self._time_combo.addItem("10 min before", 10)
        self._time_combo.addItem("15 min before", 15)
        self._time_combo.addItem("30 min before", 30)
        self._time_combo.addItem("1 hour before", 60)
        self._time_combo.setCurrentIndex(1)  # default: 10 minutes

        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(self._sound_combo)
        layout.addWidget(self._time_combo)

        self._load_qss()

        # Whenever user changes the reminder sound, play a simple system beep
        # as feedback. This can be replaced with real sound files later.
        self._sound_combo.currentIndexChanged.connect(self._play_preview_sound)

    def selected_sound(self) -> str:
        return self._sound_combo.currentText()

    def reminder_minutes(self) -> int:
        """Return the selected reminder offset in minutes."""
        data = self._time_combo.currentData()
        try:
            return int(data)
        except (TypeError, ValueError):
            return 10

    def _play_preview_sound(self) -> None:
        # Use QApplication's static beep to avoid platform-specific issues
        QApplication.beep()

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "reminder_widget.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

