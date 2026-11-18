"""Small line icon set shared with the website (UX review §4.3: no emoji icons).

Paths are 24x24 strokes in the style of Tabler Icons (MIT licensed).
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS = {
    "today": '<path d="M12 3v2M12 19v2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M3 12h2M19 12h2M5.6 18.4L7 17M17 7l1.4-1.4"/><circle cx="12" cy="12" r="4"/>',
    "calendar": '<rect x="4" y="5" width="16" height="16" rx="2"/><path d="M16 3v4M8 3v4M4 11h16"/><path d="M8 15h2v2H8z"/>',
    "tasks": '<rect x="4" y="4" width="6" height="16" rx="1.5"/><rect x="14" y="4" width="6" height="10" rx="1.5"/>',
    "reminders": '<path d="M10 5a2 2 0 1 1 4 0a7 7 0 0 1 4 6v3a4 4 0 0 0 2 3H4a4 4 0 0 0 2-3v-3a7 7 0 0 1 4-6"/><path d="M9 17v1a3 3 0 0 0 6 0v-1"/>',
    "settings": '<path d="M10.3 4.3c.4-1.8 3-1.8 3.4 0a1.7 1.7 0 0 0 2.6 1.1c1.5-.9 3.3.8 2.4 2.4a1.7 1.7 0 0 0 1 2.5c1.8.4 1.8 3 0 3.4a1.7 1.7 0 0 0-1 2.6c.9 1.5-.9 3.3-2.4 2.4a1.7 1.7 0 0 0-2.6 1c-.4 1.8-3 1.8-3.4 0a1.7 1.7 0 0 0-2.6-1c-1.5.9-3.3-.9-2.4-2.4a1.7 1.7 0 0 0-1-2.6c-1.8-.4-1.8-3 0-3.4a1.7 1.7 0 0 0 1-2.5c-.9-1.6.9-3.3 2.4-2.4a1.7 1.7 0 0 0 2.6-1.1"/><circle cx="12" cy="12" r="3"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M12 17v.01M12 13.5a1.5 1.5 0 0 1 1-1.5a2.6 2.6 0 1 0-3-4"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="10" cy="10" r="7"/><path d="M21 21l-6-6"/>',
}


def svg(name: str, color: str = "#374151", stroke: float = 1.8) -> str:
    body = _PATHS.get(name, _PATHS["help"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )


def pixmap(name: str, size: int = 20, color: str = "#374151") -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg(name, color).encode("utf-8")))
    pm = QPixmap(QSize(size * 2, size * 2))  # 2x for crisp HiDPI rendering
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    pm.setDevicePixelRatio(2.0)
    return pm


def icon(name: str, color: str = "#374151", active_color: str | None = None, size: int = 20) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, size, color), QIcon.Normal, QIcon.Off)
    if active_color:
        ic.addPixmap(pixmap(name, size, active_color), QIcon.Selected, QIcon.Off)
        ic.addPixmap(pixmap(name, size, active_color), QIcon.Active, QIcon.Off)
    return ic
