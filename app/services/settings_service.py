from __future__ import annotations

from typing import Literal

from app.database.db_manager import DatabaseManager
from app.repositories.settings_repository import SettingsRepository


ThemeName = Literal["light"]
ViewName = Literal["day", "week", "month", "year"]


class SettingsService:
    THEME_KEY = "theme"
    DEFAULT_REMINDER_MINUTES_KEY = "default_reminder_minutes"
    DEFAULT_VIEW_KEY = "default_view"
    NOTIFICATIONS_ENABLED_KEY = "notifications_enabled"

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or DatabaseManager()

    # --- Theme -----------------------------------------------------------

    def get_theme(self) -> ThemeName:
        # Theme is fixed to "light" to match the SmartCalender mockup.
        return "light"

    def set_theme(self, theme: ThemeName) -> None:
        # Accept but ignore theme changes; kept for API compatibility.
        return

    # --- Default reminder minutes ---------------------------------------

    def get_default_reminder_minutes(self) -> int:
        session = self._db.session()
        try:
            repo = SettingsRepository(session)
            value = repo.get(self.DEFAULT_REMINDER_MINUTES_KEY)
        finally:
            session.close()
        try:
            return int(value) if value is not None else 10
        except ValueError:
            return 10

    def set_default_reminder_minutes(self, minutes: int) -> None:
        session = self._db.session()
        try:
            repo = SettingsRepository(session)
            repo.set(self.DEFAULT_REMINDER_MINUTES_KEY, str(minutes))
        finally:
            session.close()

    # --- Default calendar view ------------------------------------------

    def get_default_view(self) -> ViewName:
        # Always start in "day" view (todolist-style layout) on app launch.
        return "day"

    def set_default_view(self, view: ViewName) -> None:
        session = self._db.session()
        try:
            repo = SettingsRepository(session)
            repo.set(self.DEFAULT_VIEW_KEY, view)
        finally:
            session.close()

    # --- Notifications on/off -------------------------------------------

    def get_notifications_enabled(self) -> bool:
        session = self._db.session()
        try:
            repo = SettingsRepository(session)
            value = repo.get(self.NOTIFICATIONS_ENABLED_KEY)
            return value != "false"
        finally:
            session.close()

    def set_notifications_enabled(self, enabled: bool) -> None:
        session = self._db.session()
        try:
            repo = SettingsRepository(session)
            repo.set(self.NOTIFICATIONS_ENABLED_KEY, "true" if enabled else "false")
        finally:
            session.close()

