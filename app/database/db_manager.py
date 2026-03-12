from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.app_config import AppConfig
from app.database.schema import Base, User


class DatabaseManager:
    def __init__(self) -> None:
        db_path = AppConfig.get("database", "path", "data/app.db")
        root = Path(__file__).resolve().parents[3]
        full_path = root / db_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_engine(f"sqlite:///{full_path}", echo=False, future=True)
        self._session_factory = sessionmaker(bind=self._engine, class_=Session, expire_on_commit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(self._engine)
        self._ensure_meetings_schema()
        # ensure a default local user exists so meetings can attach to user_id=1
        with self.session() as session:
            existing = session.execute(select(User).limit(1)).scalar_one_or_none()
            if existing is None:
                user = User(email="local@schedora", name="Local User")
                session.add(user)
                session.commit()

    def _ensure_meetings_schema(self) -> None:
        """Lightweight SQLite 'migration' to add new columns without wiping data."""
        with self._engine.begin() as conn:
            cols = conn.execute(text("PRAGMA table_info(meetings)")).fetchall()
            existing = {row[1] for row in cols}  # (cid, name, type, ...)
            if "color_gradient" not in existing:
                conn.execute(text("ALTER TABLE meetings ADD COLUMN color_gradient VARCHAR(64)"))

    def session(self) -> Session:
        return self._session_factory()

