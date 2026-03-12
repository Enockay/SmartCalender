from __future__ import annotations

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox

from app.models.meeting import MeetingModel


class MeetingDetailsDialog(QDialog):
    def __init__(self, meeting: MeetingModel, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Meeting Details")

        layout = QVBoxLayout(self)

        when = f"{meeting.start_time.strftime('%A %d %B %Y %H:%M')} – {meeting.end_time.strftime('%H:%M')}"
        fields = [
            ("Title", meeting.title),
            ("When", when),
            ("Location", meeting.location or "-"),
            ("Description", getattr(meeting, "description", "") or "-"),
        ]

        for label, value in fields:
            layout.addWidget(QLabel(f"<b>{label}:</b> {value}"))

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)