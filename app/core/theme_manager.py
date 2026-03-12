from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QApplication


def _apply_qss(name: str) -> None:
    # theme_manager.py is in app/core/, so parents[1] is the app/ folder
    app_root = Path(__file__).resolve().parents[1]
    qss_path = app_root / "ui" / "resources" / "qss" / f"{name}_theme.qss"
    if not qss_path.exists():
        # Fallback: apply a very simple visual style so it's obvious something loaded
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet("QMainWindow { background-color: #123456; }")
        return
    with qss_path.open("r", encoding="utf-8") as f:
        style = f.read()
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(style)


def apply_light_theme() -> None:
    _apply_qss("light")


def apply_dark_theme() -> None:
    _apply_qss("dark")
