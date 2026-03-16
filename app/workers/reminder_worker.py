from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from app.core.logger import get_logger
from app.services.reminder_service import ReminderService
from app.services.notification_service import NotificationService
from app.services.sound_service import SoundService


class ReminderWorker(QObject):
    """Background worker that checks for due reminders every 30 seconds
    and fires notifications (popup + sound) accordingly."""

    def __init__(self, notification_service: NotificationService, parent=None) -> None:
        super().__init__(parent)
        self._logger = get_logger(__name__)
        self._reminders = ReminderService()
        self._notifications = notification_service
        self._sound_service = SoundService()

        self._timer = QTimer(self)
        self._timer.setInterval(30_000)  # every 30 seconds
        self._timer.timeout.connect(self.check_due)
        self._timer.start()

        self._logger.info("ReminderWorker started - checking every 30 seconds")
        self._logger.info(f"Timer interval: {self._timer.interval()}ms, isActive: {self._timer.isActive()}")

        # Do an immediate first check after 5 seconds
        self._logger.info("Scheduling first check in 5 seconds...")
        def first_check():
            self._logger.info("First check timer fired - calling check_due()")
            self.check_due()
        QTimer.singleShot(5_000, first_check)

    def check_due(self) -> None:
        """Query all due reminders and fire notifications."""
        now = datetime.now()
        self._logger.info(f"ReminderWorker.check_due() called at {now.strftime('%Y-%m-%d %H:%M:%S')}")

        # Mark any past-due active reminders as overdue first
        overdue_count = self._reminders.update_overdue()
        if overdue_count > 0:
            self._logger.info(f"Marked {overdue_count} reminders as overdue")

        # Get all due reminders
        due_reminders = self._reminders.get_due_reminders(now)
        self._logger.info(f"Found {len(due_reminders)} due reminder(s) at {now.strftime('%H:%M:%S')}")

        if not due_reminders:
            self._logger.info("No due reminders found - check completed")
            return

        for info in due_reminders:
            self._logger.info(f"Processing due reminder: ID={info.id}, Title='{info.title}', remind_at={info.remind_at.strftime('%Y-%m-%d %H:%M:%S')}")
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
            self._logger.info(f"Reminder {info.id} notification type: {notif_type}")

            # Play sound FIRST (3 times) before showing popup
            if "Sound" in notif_type:
                self._logger.info(f"Playing sound for reminder {info.id}")
                try:
                    # Get selected sound from settings
                    from app.services.settings_service import SettingsService
                    settings = SettingsService()
                    selected_sound = settings.get_reminder_sound()
                    
                    # Remove emoji prefix if present (from custom sounds)
                    sound_name = selected_sound.replace("🎵 ", "")
                    
                    self._sound_service.play_sound(sound_name, repeat=3)
                    self._logger.info(f"Playing sound '{sound_name}' for reminder {info.id} (3 times)")
                    self._logger.info(f"Sound played successfully for reminder {info.id}")
                except Exception as e:
                    self._logger.error(f"Error playing sound for reminder {info.id}: {e}")

            # Show desktop popup - stays visible until user snoozes or dismisses
            if "Desktop" in notif_type:
                self._logger.info(f"Showing desktop notification for reminder {info.id}: {title}")
                try:
                    # Popup will stay visible until user clicks Snooze or Dismiss (no auto-close)
                    snooze = self._notifications.show_reminder(title, body)
                    if snooze:
                        self._logger.info(f"User snoozed reminder {info.id} for 10 minutes")
                        self._reminders.snooze(info.id, minutes=10)
                    else:
                        self._logger.info(f"User dismissed reminder {info.id}")
                        self._reminders.dismiss(info.id)
                except Exception as e:
                    self._logger.error(f"Error showing notification for reminder {info.id}: {e}", exc_info=True)
            else:
                # No desktop popup, just dismiss
                self._logger.info(f"Dismissing reminder {info.id} (no desktop notification)")
                self._reminders.dismiss(info.id)
        
        self._logger.info(f"Check completed - processed {len(due_reminders)} due reminder(s) at {now.strftime('%H:%M:%S')}")