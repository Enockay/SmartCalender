from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import sys

from app.ui.windows.main_window import MainWindow
from app.core.app_config import AppConfig
from app.core.logger import get_logger
from app.database.db_manager import DatabaseManager
from app.services.notification_service import NotificationService
from app.workers.reminder_worker import ReminderWorker
from app.services.settings_service import SettingsService


def main() -> int:
    AppConfig.load()
    logger = get_logger(__name__)

    app = QApplication(sys.argv)
    app.setApplicationName("SmartCalender Desktop")

    db = DatabaseManager()
    db.initialize()

    settings = SettingsService(db)

    window = MainWindow(settings=settings)
    window.show()

    notification_service = NotificationService(window, settings)
    if settings.get_notifications_enabled():
        ReminderWorker(notification_service, window)

    QTimer.singleShot(0, lambda: logger.info("Smart Calender  started"))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

