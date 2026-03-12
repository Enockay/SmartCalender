from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.database.schema import AppSettings


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> Optional[str]:
        row = (
            self._session.query(AppSettings)
            .filter(AppSettings.key == key)
            .one_or_none()
        )
        return row.value if row else None

    def set(self, key: str, value: str) -> None:
        row = (
            self._session.query(AppSettings)
            .filter(AppSettings.key == key)
            .one_or_none()
        )
        if row is None:
            row = AppSettings(key=key, value=value)
            self._session.add(row)
        else:
            row.value = value
        self._session.commit()

