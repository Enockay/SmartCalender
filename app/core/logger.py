from __future__ import annotations

import sys
from loguru import logger


def _configure() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", backtrace=True, diagnose=False)


_configure()


def get_logger(name: str = "schedora") -> "logger.__class__":
    return logger.bind(name=name)

