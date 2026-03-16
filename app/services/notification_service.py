from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QSystemTrayIcon

from app.core.logger import get_logger
from app.services.settings_service import SettingsService
from app.ui.windows.reminder_popup import ReminderPopup


class NotificationService:
    def __init__(self, parent: QWidget, settings: SettingsService) -> None:
        self._parent = parent
        self._settings = settings
        self._logger = get_logger(__name__)

        # Keep a tray icon so the app can still integrate with the system tray,
        # but primary reminders will use our custom popup.
        self._tray = QSystemTrayIcon(self._parent)
        icon_path = Path(__file__).resolve().parents[2] / "home.png"
        self._tray.setIcon(QIcon(str(icon_path)))
        self._tray.setVisible(True)
        
        self._logger.info("NotificationService initialized")

    def show_reminder(self, title: str, body: str) -> bool:
        """Show a custom in-app reminder popup.

        Returns True if the user chose Snooze, False on Dismiss or auto-close.
        """
        notifications_enabled = self._settings.get_notifications_enabled()
        self._logger.info(f"show_reminder() called: title='{title}', notifications_enabled={notifications_enabled}")
        
        if not notifications_enabled:
            self._logger.warning("Notifications are disabled in settings - not showing reminder popup")
            return False

        self._logger.info(f"Showing reminder popup: '{title}'")
        try:
            result = ReminderPopup.exec_for(title=title, body=body, parent=self._parent)
            self._logger.info(f"Reminder popup closed: snooze={result.snooze}")
            return result.snooze
        except Exception as e:
            self._logger.error(f"Error showing reminder popup: {e}", exc_info=True)
            return False

