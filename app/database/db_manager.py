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

        self.db_path = full_path  # expose for backup/restore
        self._engine = create_engine(f"sqlite:///{full_path}", echo=False, future=True)
        self._session_factory = sessionmaker(bind=self._engine, class_=Session, expire_on_commit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(self._engine)
        self._ensure_meetings_schema()
        self._ensure_tasks_schema()
        self._ensure_reminders_schema()
        # ensure a default local user exists so meetings can attach to user_id=1
        with self.session() as session:
            existing = session.execute(select(User).limit(1)).scalar_one_or_none()
            if existing is None:
                user = User(email="local@schedora", name="Local User")
                session.add(user)
                session.commit()
        # Task tables are created automatically via Base.metadata.create_all

    def _ensure_meetings_schema(self) -> None:
        """Lightweight SQLite 'migration' to add new columns without wiping data."""
        with self._engine.begin() as conn:
            cols = conn.execute(text("PRAGMA table_info(meetings)")).fetchall()
            existing = {row[1] for row in cols}  # (cid, name, type, ...)
            if "color_gradient" not in existing:
                conn.execute(text("ALTER TABLE meetings ADD COLUMN color_gradient VARCHAR(64)"))

    def _ensure_tasks_schema(self) -> None:
        """Lightweight SQLite 'migration' to update tasks table schema."""
        with self._engine.begin() as conn:
            # Check if tasks table exists
            tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")).fetchall()
            if not tables:
                # Table doesn't exist, will be created by Base.metadata.create_all
                return
            
            # Get existing columns
            cols = conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
            existing = {row[1] for row in cols}  # (cid, name, type, ...)
            
            # Add task_date column if it doesn't exist
            if "task_date" not in existing:
                from datetime import datetime
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                # SQLite doesn't support NOT NULL with DEFAULT in ALTER TABLE, so add as nullable first
                conn.execute(text("ALTER TABLE tasks ADD COLUMN task_date DATETIME"))
                # Update all existing rows to have today's date
                conn.execute(text("UPDATE tasks SET task_date = :default_date WHERE task_date IS NULL"),
                           {"default_date": today})
            
            # Note: SQLite doesn't support DROP COLUMN directly, so we leave assignee column
            # in the database but ignore it in the code. It won't cause any issues.

    def _ensure_reminders_schema(self) -> None:
        """Migrate reminders table to the enhanced schema.

        The old table had meeting_id NOT NULL.  The new schema makes it
        nullable and adds many new columns.  Because SQLite cannot ALTER
        NULL constraints, we recreate the table if the new columns are
        missing.
        """
        with self._engine.begin() as conn:
            tables = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='reminders'"
            )).fetchall()
            if not tables:
                return  # will be created fresh by create_all

            cols = conn.execute(text("PRAGMA table_info(reminders)")).fetchall()
            col_map = {row[1]: row for row in cols}

            # Check if meeting_id is NOT NULL (notnull flag is index 3)
            meeting_col = col_map.get("meeting_id")
            meeting_is_notnull = meeting_col and meeting_col[3] == 1
            already_has_title = "title" in col_map

            if already_has_title and not meeting_is_notnull:
                return  # fully migrated

            if already_has_title and meeting_is_notnull:
                # Columns were added via ALTER but meeting_id is still NOT NULL
                # Need to recreate
                pass
            elif not already_has_title:
                # Old schema completely
                pass
            else:
                return

            # Recreate: rename old → create new → copy data → drop old
            old_cols = set(col_map.keys())
            conn.execute(text("ALTER TABLE reminders RENAME TO _reminders_old"))
            conn.execute(text("""
                CREATE TABLE reminders (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(255) DEFAULT 'Untitled Reminder',
                    description TEXT,
                    remind_at DATETIME NOT NULL,
                    category VARCHAR(50) DEFAULT 'Personal',
                    priority VARCHAR(20) DEFAULT 'Medium',
                    repeat_type VARCHAR(30) DEFAULT 'None',
                    repeat_custom VARCHAR(100),
                    notification_type VARCHAR(100) DEFAULT 'Desktop',
                    advance_minutes INTEGER DEFAULT 0,
                    status VARCHAR(30) DEFAULT 'active',
                    dismissed BOOLEAN DEFAULT 0,
                    snoozed_until DATETIME,
                    completed_at DATETIME,
                    meeting_id INTEGER REFERENCES meetings(id),
                    user_id INTEGER REFERENCES users(id),
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))
            # Copy all columns that exist in both old and new tables
            new_cols = {"id", "title", "description", "remind_at", "category",
                        "priority", "repeat_type", "repeat_custom",
                        "notification_type", "advance_minutes", "status",
                        "dismissed", "snoozed_until", "completed_at",
                        "meeting_id", "user_id", "created_at", "updated_at"}
            shared = sorted(old_cols & new_cols)
            cols_str = ", ".join(shared)
            conn.execute(text(
                f"INSERT INTO reminders ({cols_str}) SELECT {cols_str} FROM _reminders_old"
            ))
            conn.execute(text("DROP TABLE _reminders_old"))

    def session(self) -> Session:
        return self._session_factory()

