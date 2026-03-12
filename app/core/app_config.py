from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path


class AppConfig:
    _config: ConfigParser | None = None
    _path: Path = Path(__file__).resolve().parents[3] / "config.ini"

    @classmethod
    def load(cls) -> None:
        parser = ConfigParser()
        if cls._path.exists():
            parser.read(cls._path)
        cls._config = parser

    @classmethod
    def get(cls, section: str, option: str, fallback: str | None = None) -> str | None:
        if cls._config is None:
            cls.load()
        assert cls._config is not None
        if cls._config.has_option(section, option):
            return cls._config.get(section, option)
        return fallback

