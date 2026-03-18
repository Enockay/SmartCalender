from __future__ import annotations

import os
import sys
from configparser import ConfigParser
from pathlib import Path


def get_base_dir() -> Path:
    """Return the base directory of the application.
    
    - In development: root of the source tree (3 levels above this file).
    - In a frozen PyInstaller bundle: the temporary extraction folder
      (sys._MEIPASS) where bundled read-only assets live.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[3]


def get_user_data_dir() -> Path:
    """Return a writable, platform-appropriate directory for user data.
    
    Created on first access.  Used for the SQLite database, logs, exports,
    backups, and cache so they are **never** stored inside the app bundle.
    
    - macOS   : ~/Library/Application Support/SmartCalender
    - Windows : %APPDATA%\\SmartCalender
    - Linux   : ~/.local/share/SmartCalender
    """
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support" / "SmartCalender"
        elif sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home())) / "SmartCalender"
        else:
            base = Path.home() / ".local" / "share" / "SmartCalender"
    else:
        # Development: keep everything inside the project root.
        base = Path(__file__).resolve().parents[3]
    base.mkdir(parents=True, exist_ok=True)
    return base


class AppConfig:
    _config: ConfigParser | None = None

    # config.ini is a *read-only* bundled asset → look in base_dir
    @classmethod
    def _config_path(cls) -> Path:
        return get_base_dir() / "config.ini"

    @classmethod
    def load(cls) -> None:
        parser = ConfigParser()
        p = cls._config_path()
        if p.exists():
            parser.read(p)
        cls._config = parser

    @classmethod
    def get(cls, section: str, option: str, fallback: str | None = None) -> str | None:
        if cls._config is None:
            cls.load()
        assert cls._config is not None
        if cls._config.has_option(section, option):
            return cls._config.get(section, option)
        return fallback

