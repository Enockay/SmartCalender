from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from app.services.reminder_service import ReminderService
from app.services.notification_service import NotificationService


class ReminderWorker(QObject):
    """Background worker that checks for due reminders every 30 seconds
    and fires notifications (popup + sound) accordingly."""

    def __init__(self, notification_service: NotificationService, parent=None) -> None:
        super().__init__(parent)
        self._reminders = ReminderService()
        self._notifications = notification_service

        self._timer = QTimer(self)
        self._timer.setInterval(30_000)  # every 30 seconds
        self._timer.timeout.connect(self.check_due)
        self._timer.start()

        # Do an immediate first check
        QTimer.singleShot(5_000, self.check_due)

    def check_due(self) -> None:
        """Query all due reminders and fire notifications."""
        now = datetime.now()

        # Mark any past-due active reminders as overdue first
        self._reminders.update_overdue()

        for info in self._reminders.get_due_reminders(now):
            # Build notification text
            remind_at = info.remind_at
            time_str = remind_at.strftime("%I:%M %p").lstrip("0")

            # If linked to a meeting, show meeting context
            if info.meeting_title:
                title = f"🔔 {info.meeting_title}"
                body = f"Reminder: {info.title}\nMeeting at {time_str}"
                if info.meeting_location:
                    body += f" • {info.meeting_location}"
            else:
                title = f"🔔 {info.title}"
                body = f"Scheduled for {time_str}"
                if info.description:
                    body += f"\n{info.description[:80]}"

            # Determine notification type
            notif_type = info.notification_type or "Desktop"

            if "Desktop" in notif_type:
                snooze = self._notifications.show_reminder(title, body)
                if snooze:
                    self._reminders.snooze(info.id, minutes=10)
                else:
                    self._reminders.dismiss(info.id)
            else:
                # No desktop popup, just dismiss
                self._reminders.dismiss(info.id)

            if "Sound" in notif_type:
                QApplication.beep()