from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QSystemTrayIcon

from app.services.settings_service import SettingsService
from app.ui.windows.reminder_popup import ReminderPopup


class NotificationService:
    def __init__(self, parent: QWidget, settings: SettingsService) -> None:
        self._parent = parent
        self._settings = settings

        # Keep a tray icon so the app can still integrate with the system tray,
        # but primary reminders will use our custom popup.
        self._tray = QSystemTrayIcon(self._parent)
        icon_path = Path(__file__).resolve().parents[2] / "home.png"
        self._tray.setIcon(QIcon(str(icon_path)))
        self._tray.setVisible(True)

    def show_reminder(self, title: str, body: str) -> bool:
        """Show a custom in-app reminder popup.

        Returns True if the user chose Snooze, False on Dismiss or auto-close.
        """
        if not self._settings.get_notifications_enabled():
            return False

        result = ReminderPopup.exec_for(title=title, body=body, parent=self._parent)
        return result.snooze

