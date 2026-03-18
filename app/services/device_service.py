from __future__ import annotations

import platform
import uuid
from typing import Optional

from app.database.db_manager import DatabaseManager
from app.repositories.settings_repository import SettingsRepository


DEVICE_ID_KEY = "device_id"


class DeviceService:
    """Manages a stable device_id for this installation and calls device-binding APIs."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or DatabaseManager()

    def get_or_create_device_id(self) -> str:
        """Return a stable device_id stored in AppSettings, generating one if missing."""
        session = self._db.session()
        try:
            repo = SettingsRepository(session)
            existing = repo.get(DEVICE_ID_KEY)
            if existing:
                return existing
            new_id = str(uuid.uuid4())
            repo.set(DEVICE_ID_KEY, new_id)
            return new_id
        finally:
            session.close()

    def get_device_name(self) -> str:
        """Best-effort device name for server display."""
        try:
            return platform.node() or "Desktop"
        except Exception:
            return "Desktop"

