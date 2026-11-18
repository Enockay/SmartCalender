from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QWidget, QSystemTrayIcon, QMenu, QApplication

from app.core.logger import get_logger
from app.services.settings_service import SettingsService
from app.ui.windows.reminder_popup import ReminderPopup


class NotificationService:
    def __init__(self, parent: QWidget, settings: SettingsService) -> None:
        self._parent = parent
        self._settings = settings
        self._logger = get_logger(__name__)

        # Tray / menu-bar icon (review §4.6): keeps SmartCalender one click away
        # and lets reminders keep working after the window is closed.
        self._tray = QSystemTrayIcon(self._parent)
        app_icon = QApplication.windowIcon()
        if app_icon.isNull():
            from app.core.app_config import get_base_dir
            app_icon = QIcon(str(get_base_dir() / "assets" / "SmartCalender.png"))
        self._tray.setIcon(app_icon)
        self._tray.setToolTip("SmartCalender")
        self._tray.setContextMenu(self._build_menu())
        self._tray.activated.connect(self._on_activated)
        self._tray.setVisible(True)
        
        self._logger.info("NotificationService initialized")

    # ── Tray menu ─────────────────────────────────────────────────
    def _build_menu(self) -> QMenu:
        menu = QMenu(self._parent)
        win = self._parent

        def add(text: str, fn) -> None:
            act = QAction(text, menu)
            act.triggered.connect(fn)
            menu.addAction(act)

        add("Open SmartCalender", self.show_window)
        add("Quick add…", lambda: (self.show_window(), getattr(win, "_focus_quick_add", lambda: None)()))
        add("Today", lambda: (self.show_window(), getattr(win, "_set_view", lambda *_: None)(0)))
        add("Calendar", lambda: (self.show_window(), win._set_view(win._calendar_view)) if hasattr(win, "_calendar_view") else self.show_window())
        menu.addSeparator()
        add("Quit SmartCalender", self.quit_app)
        return menu

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    def show_window(self) -> None:
        win = self._parent
        win.showNormal()
        win.raise_()
        win.activateWindow()

    def quit_app(self) -> None:
        setattr(self._parent, "_really_quit", True)
        QApplication.quit()

    @property
    def tray_available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable() and self._tray.isVisible()

    def show_tray_message(self, title: str, body: str) -> None:
        if self.tray_available:
            self._tray.showMessage(title, body, QSystemTrayIcon.Information, 6000)

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

