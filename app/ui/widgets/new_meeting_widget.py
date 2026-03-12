from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


class NewMeetingWidget(QWidget):
    """Compact professional header widget for the meeting dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NewMeetingWidgetRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 12)
        layout.setSpacing(4)

        self.title = QLabel("New Meeting", self)
        self.title.setObjectName("NewMeetingTitle")
        self.title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Shorter, clearer description for the dialog header
        self.subtitle = QLabel("Set your meeting details and reminder time.", self)
        self.subtitle.setObjectName("NewMeetingSubtitle")
        self.subtitle.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.separator = QFrame(self)
        self.separator.setObjectName("NewMeetingSeparator")
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setFixedHeight(1)

        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(4)
        layout.addWidget(self.separator)

        self._load_qss()

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "new_meeting_widget.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def sizeHint(self):
        return self.minimumSizeHint()