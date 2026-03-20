from __future__ import annotations

from typing import Literal

from app.database.db_manager import DatabaseManager
from app.repositories.settings_repository import SettingsRepository


ThemeName = Literal["light", "dark"]
ViewName = Literal["day", "week", "month", "year"]


class SettingsService:
    THEME_KEY = "theme"
    DEFAULT_REMINDER_MINUTES_KEY = "default_reminder_minutes"
    DEFAULT_VIEW_KEY = "default_view"
    NOTIFICATIONS_ENABLED_KEY = "notifications_enabled"
    WEATHER_CITY_KEY = "weather_city"
    LANGUAGE_KEY = "language"
    DEFAULT_CATEGORY_KEY = "default_category"
    REMINDER_FREQUENCY_KEY = "reminder_frequency"
    # Notifications tab
    EMAIL_ALERTS_KEY = "email_alerts"
    SOUND_ALERTS_KEY = "sound_alerts"
    REMINDER_SOUND_KEY = "reminder_sound"  # Selected reminder sound name
    DEFAULT_REMINDER_SOUND = "alert-tone"
    QUIET_HOURS_START_KEY = "quiet_hours_start"
    QUIET_HOURS_END_KEY = "quiet_hours_end"
    # Backup tab
    AUTO_BACKUP_KEY = "auto_backup"
    BACKUP_SCHEDULE_KEY = "backup_schedule"

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or DatabaseManager()

    # --- helpers ----------------------------------------------------------

    def _get(self, key: str, default: str = "") -> str:
        session = self._db.session()
        try:
            repo = SettingsRepository(session)
            val = repo.get(key)
            return val if val is not None else default
        finally:
            session.close()

    def _set(self, key: str, value: str) -> None:
        session = self._db.session()
        try:
            repo = SettingsRepository(session)
            repo.set(key, value)
        finally:
            session.close()

    # --- Theme -----------------------------------------------------------

    def get_theme(self) -> ThemeName:
        val = self._get(self.THEME_KEY, "light")
        return val if val in ("light", "dark") else "light"

    def set_theme(self, theme: ThemeName) -> None:
        self._set(self.THEME_KEY, theme)

    # --- Default reminder minutes ---------------------------------------

    def get_default_reminder_minutes(self) -> int:
        try:
            return int(self._get(self.DEFAULT_REMINDER_MINUTES_KEY, "10"))
        except ValueError:
            return 10

    def set_default_reminder_minutes(self, minutes: int) -> None:
        self._set(self.DEFAULT_REMINDER_MINUTES_KEY, str(minutes))

    # --- Default calendar view ------------------------------------------

    def get_default_view(self) -> ViewName:
        val = self._get(self.DEFAULT_VIEW_KEY, "day")
        return val if val in ("day", "week", "month", "year") else "day"

    def set_default_view(self, view: ViewName) -> None:
        self._set(self.DEFAULT_VIEW_KEY, view)

    # --- Notifications on/off -------------------------------------------

    def get_notifications_enabled(self) -> bool:
        return self._get(self.NOTIFICATIONS_ENABLED_KEY, "true") != "false"

    def set_notifications_enabled(self, enabled: bool) -> None:
        self._set(self.NOTIFICATIONS_ENABLED_KEY, "true" if enabled else "false")

    # --- Weather city ----------------------------------------------------

    def get_weather_city(self) -> str:
        return self._get(self.WEATHER_CITY_KEY, "")

    def set_weather_city(self, city: str) -> None:
        self._set(self.WEATHER_CITY_KEY, city.strip())

    # --- Language ---------------------------------------------------------

    def get_language(self) -> str:
        return self._get(self.LANGUAGE_KEY, "English")

    def set_language(self, lang: str) -> None:
        self._set(self.LANGUAGE_KEY, lang)

    # --- Default category -------------------------------------------------

    def get_default_category(self) -> str:
        return self._get(self.DEFAULT_CATEGORY_KEY, "Work")

    def set_default_category(self, cat: str) -> None:
        self._set(self.DEFAULT_CATEGORY_KEY, cat)

    # --- Reminder frequency -----------------------------------------------

    def get_reminder_frequency(self) -> str:
        return self._get(self.REMINDER_FREQUENCY_KEY, "Daily")

    def set_reminder_frequency(self, freq: str) -> None:
        self._set(self.REMINDER_FREQUENCY_KEY, freq)

    # --- Email alerts -----------------------------------------------------

    def get_email_alerts(self) -> bool:
        return self._get(self.EMAIL_ALERTS_KEY, "false") == "true"

    def set_email_alerts(self, enabled: bool) -> None:
        self._set(self.EMAIL_ALERTS_KEY, "true" if enabled else "false")

    # --- Sound alerts -----------------------------------------------------

    def get_sound_alerts(self) -> bool:
        return self._get(self.SOUND_ALERTS_KEY, "true") != "false"

    def set_sound_alerts(self, enabled: bool) -> None:
        self._set(self.SOUND_ALERTS_KEY, "true" if enabled else "false")

    # --- Reminder sound ----------------------------------------------------

    def get_reminder_sound(self) -> str:
        """Get the selected reminder sound name.

        Fresh installs default to alert-tone.
        """
        return self._get(self.REMINDER_SOUND_KEY, self.DEFAULT_REMINDER_SOUND)

    def set_reminder_sound(self, sound_name: str) -> None:
        """Set the selected reminder sound name."""
        self._set(self.REMINDER_SOUND_KEY, sound_name)

    # --- Quiet hours ------------------------------------------------------

    def get_quiet_hours_start(self) -> str:
        return self._get(self.QUIET_HOURS_START_KEY, "22:00")

    def set_quiet_hours_start(self, t: str) -> None:
        self._set(self.QUIET_HOURS_START_KEY, t)

    def get_quiet_hours_end(self) -> str:
        return self._get(self.QUIET_HOURS_END_KEY, "07:00")

    def set_quiet_hours_end(self, t: str) -> None:
        self._set(self.QUIET_HOURS_END_KEY, t)

    # --- Auto backup ------------------------------------------------------

    def get_auto_backup(self) -> bool:
        return self._get(self.AUTO_BACKUP_KEY, "false") == "true"

    def set_auto_backup(self, enabled: bool) -> None:
        self._set(self.AUTO_BACKUP_KEY, "true" if enabled else "false")

    # --- Backup schedule --------------------------------------------------

    def get_backup_schedule(self) -> str:
        return self._get(self.BACKUP_SCHEDULE_KEY, "Weekly")

    def set_backup_schedule(self, sched: str) -> None:
        self._set(self.BACKUP_SCHEDULE_KEY, sched)
