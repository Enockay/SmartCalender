from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)


@dataclass
class ReminderPopupResult:
    snooze: bool


class ReminderPopup(QDialog):
    """Small, focused reminder popup with Snooze / Dismiss actions."""

    def __init__(self, title: str, body: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reminder")
        self.setObjectName("ReminderPopupRoot")
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setModal(False)

        self._snooze = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Header area: icon + main text
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        icon_label = QLabel("⏰", self)
        icon_label.setObjectName("ReminderIcon")
        icon_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        title_label = QLabel("Reminder:", self)
        title_label.setObjectName("ReminderTitleLabel")

        message_label = QLabel(title, self)
        message_label.setObjectName("ReminderMainText")
        message_label.setWordWrap(True)

        subtitle_label = QLabel(body, self)
        subtitle_label.setObjectName("ReminderSubText")
        subtitle_label.setWordWrap(True)

        text_col.addWidget(title_label)
        text_col.addWidget(message_label)
        text_col.addWidget(subtitle_label)

        header_row.addWidget(icon_label)
        header_row.addLayout(text_col)

        layout.addLayout(header_row)

        # Buttons row
        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 8, 0, 0)
        buttons_row.setSpacing(10)
        buttons_row.addStretch(1)

        snooze_btn = QPushButton("Snooze", self)
        snooze_btn.setObjectName("ReminderSnoozeButton")
        snooze_btn.clicked.connect(self._on_snooze_clicked)

        dismiss_btn = QPushButton("Dismiss", self)
        dismiss_btn.setObjectName("ReminderDismissButton")
        dismiss_btn.clicked.connect(self._on_dismiss_clicked)

        buttons_row.addWidget(snooze_btn)
        buttons_row.addWidget(dismiss_btn)

        layout.addLayout(buttons_row)

        # No auto-close timer - popup stays visible until user snoozes or dismisses
        # This ensures notifications persist until user interaction

        # Apply styles and lock a fixed window size similar to the reference UI.
        self._apply_qss()
        # Fixed size so the user cannot resize the popup.
        self.setFixedSize(360, 170)
        self._move_to_top_right()

    def _move_to_top_right(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        x = available.right() - frame.width() - 20
        y = available.top() + 40
        self.move(x, y)

    def _apply_qss(self) -> None:
        """Load QSS from the shared resources folder."""
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "reminder_popup.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def _on_snooze_clicked(self) -> None:
        self._snooze = True
        self.accept()

    def _on_dismiss_clicked(self) -> None:
        self._snooze = False
        self.accept()

    @staticmethod
    def exec_for(title: str, body: str, parent: QWidget | None = None) -> ReminderPopupResult:
        dlg = ReminderPopup(title, body, parent)
        dlg.exec()
        return ReminderPopupResult(snooze=dlg._snooze)

