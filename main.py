from PySide6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QComboBox,
    QTabBar,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, QTimer, QSize, QObject, QEvent
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
import sys

from app.ui.windows.main_window import MainWindow
from app.ui.windows.login_window import LoginWindow
from app.core.app_config import AppConfig, get_base_dir
from app.core.logger import get_logger
from app.database.db_manager import DatabaseManager
from app.services.notification_service import NotificationService
from app.workers.reminder_worker import ReminderWorker
from app.services.settings_service import SettingsService
from app.models.auth_response import AuthResponse


class _PointerCursorFilter(QObject):
    """Give every clickable control the pointing-hand cursor (UX review W4, §4.6).

    Applied app-wide when each widget is first polished, so new controls inherit
    it without anyone having to remember setCursor().
    """

    _CLICKABLE = (QAbstractButton, QComboBox, QTabBar)

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() == QEvent.Polish:
            if isinstance(obj, self._CLICKABLE):
                obj.setCursor(Qt.PointingHandCursor)
            elif isinstance(obj, QAbstractItemView) and obj.objectName() in ("NavList",):
                obj.viewport().setCursor(Qt.PointingHandCursor)
        return False


def _position_top_right(window) -> None:
    """Place a window at the top-right of the active screen before show()."""
    screen = window.screen() or QApplication.primaryScreen()
    if not screen:
        return
    available = screen.availableGeometry()
    # Use current widget size so we can place before show and avoid left→right jump.
    width = window.width()
    x = available.right() - width
    y = available.top()
    window.move(x, y)


def main() -> int:
    AppConfig.load()
    logger = get_logger(__name__)

    app = QApplication(sys.argv)
    app.setApplicationName("SmartCalender")
    _cursor_filter = _PointerCursorFilter(app)
    app.installEventFilter(_cursor_filter)

    # Use packaged assets for dock/app + window icon.
    try:
        icon = QIcon()
        base_dir = get_base_dir()
        svg_path = base_dir / "assets" / "logo.svg"
        renderer = QSvgRenderer(str(svg_path))
        if renderer.isValid():
            for s in (16, 32, 64, 128):
                pm = QPixmap(QSize(s, s))
                pm.fill(Qt.transparent)
                painter = QPainter(pm)
                renderer.render(painter)
                painter.end()
                icon.addPixmap(pm)
        else:
            for raster_icon in (
                base_dir / "assets" / "SmartCalender.png",
                base_dir / "assets" / "image.png",
            ):
                if raster_icon.exists():
                    icon = QIcon(str(raster_icon))
                    break
        if not icon.isNull():
            app.setWindowIcon(icon)
    except Exception:
        # Non-fatal: if SVG rendering fails, fall back to default platform icon.
        pass

    db = DatabaseManager()
    db.initialize()

    settings = SettingsService(db)

    # Light / dark theme following the computer unless the user picked one (review §4.6)
    from app.core import theme
    theme.install(settings.get_theme())
    
    # Show login window first
    login_window = LoginWindow()
    
    # Create main window but don't show it yet
    main_window = None
    
    def show_main_window(auth_response: AuthResponse):
        """Show main window after successful login."""
        nonlocal main_window
        login_window.close()
        
        main_window = MainWindow(settings=settings)
        _position_top_right(main_window)
        main_window.show()
        
        notification_service = NotificationService(main_window, settings)
        main_window.attach_notification_service(notification_service)
        # From now on the tray keeps the app alive when the window is closed;
        # "Quit SmartCalender" in the tray menu (or Cmd/Ctrl+Q) quits for real.
        app.setQuitOnLastWindowClosed(not notification_service.tray_available)
        # Always start the reminder worker – it checks notification settings internally
        ReminderWorker(notification_service, main_window)
        
        # Check for missed reminders when app starts
        from app.services.reminder_service import ReminderService
        from app.services.system_notification_service import SystemNotificationService
        reminder_service = ReminderService()
        sys_notif = SystemNotificationService()
        missed_count = sys_notif.check_missed_reminders(reminder_service)
        if missed_count > 0:
            logger.info(f"Found {missed_count} reminder(s) that were due while app was closed")
        
        QTimer.singleShot(0, lambda: logger.info("SmartCalender started"))
    
    # Connect login success to show main window
    login_window._login_widget.loginSuccessful.connect(show_main_window)
    
    # Show login window
    _position_top_right(login_window)
    login_window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

