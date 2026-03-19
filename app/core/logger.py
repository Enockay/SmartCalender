from __future__ import annotations

import sys
from pathlib import Path
from loguru import logger
from app.core.app_config import get_user_data_dir


def _configure() -> None:
    logger.remove()

    # In frozen/windowed builds (notably Windows with console=False),
    # sys.stderr/sys.stdout can be None. Fall back to a file sink.
    stream = sys.stderr or sys.stdout
    if stream is not None:
        logger.add(stream, level="INFO", backtrace=True, diagnose=False)

    log_dir: Path = get_user_data_dir() / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_dir / "smartcalender.log"),
        level="INFO",
        rotation="5 MB",
        retention="14 days",
        backtrace=True,
        diagnose=False,
        encoding="utf-8",
    )


_configure()


def get_logger(name: str = "schedora") -> "logger.__class__":
    return logger.bind(name=name)

