from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, QTimer

from app.services.reminder_service import ReminderService
from app.services.notification_service import NotificationService


class ReminderWorker(QObject):
    def __init__(self, notification_service: NotificationService, parent=None) -> None:
        super().__init__(parent)
        self._reminders = ReminderService()
        self._notifications = notification_service

        self._timer = QTimer(self)
        self._timer.setInterval(60_000)  # every minute
        self._timer.timeout.connect(self.check_due)
        self._timer.start()

    def check_due(self) -> None:
        now = datetime.utcnow()
        for info in self._reminders.get_due_reminders(now):
            # How many whole minutes remain until the meeting starts?
            minutes_until = int((info.start_time - now).total_seconds() // 60)
            if minutes_until > 0:
                title = f"{info.title} in {minutes_until} minute{'s' if minutes_until != 1 else ''}."
            else:
                title = f"{info.title} starting now."

            # Friendlier body text similar to the reference design.
            body = f"Don't forget your {info.start_time.strftime('%I:%M %p').lstrip('0')} meeting."
            snooze = self._notifications.show_reminder(title, body)
            if snooze:
                self._reminders.snooze(info.id, minutes=10)
            else:
                self._reminders.dismiss(info.id)

