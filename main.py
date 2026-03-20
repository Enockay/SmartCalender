from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer, QSize
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
    app.setApplicationName("SmartCalender Desktop")

    # Use the same SVG as the dock/app + window icon.
    try:
        svg_path = get_base_dir() / "assets" / "logo.svg"
        renderer = QSvgRenderer(str(svg_path))
        icon = QIcon()
        if renderer.isValid():
            for s in (16, 32, 64, 128):
                pm = QPixmap(QSize(s, s))
                pm.fill(Qt.transparent)
                painter = QPainter(pm)
                renderer.render(painter)
                painter.end()
                icon.addPixmap(pm)
            app.setWindowIcon(icon)
    except Exception:
        # Non-fatal: if SVG rendering fails, fall back to default platform icon.
        pass

    db = DatabaseManager()
    db.initialize()

    settings = SettingsService(db)
    
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
        
        QTimer.singleShot(0, lambda: logger.info("Smart Calender started"))
    
    # Connect login success to show main window
    login_window._login_widget.loginSuccessful.connect(show_main_window)
    
    # Show login window
    _position_top_right(login_window)
    login_window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

