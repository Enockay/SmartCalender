"""Light and dark themes that follow the computer's setting (UX review §4.6, Appendix A).

How it works
------------
The app's stylesheets are written for the light theme. In dark mode every
stylesheet passes through `to_dark()`, which rewrites colours according to
what they are used for:

* text colours (`color:`) that are dark become light;
* background colours that are light become dark (keeping their hue, so a
  pale green badge becomes a deep green one);
* borders that are light become subtle dark lines;
* colours that already suit a dark UI (the dark header, the sidebar, white
  text on green buttons) are left alone.

`install()` wraps QWidget.setStyleSheet so every widget, including inline
styles set from Python, is converted automatically, and the original light
stylesheet is remembered so the theme can be switched at runtime.
"""

from __future__ import annotations

import colorsys
import re
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QWidget

_RAW_PROP = "_smartcal_raw_qss"
_mode = "light"            # effective mode: "light" | "dark"
_preference = "dark"       # "system" | "light" | "dark" (dark is the default)
_installed = False
_orig_widget_set: Callable | None = None
_orig_app_set: Callable | None = None


class _Notifier(QObject):
    changed = Signal(str)


notifier = _Notifier()


# ── Colour maths ─────────────────────────────────────────────────────────────

def _hls(r: int, g: int, b: int) -> tuple[float, float, float]:
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)


def _rgb(h: float, l: float, s: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), s)
    return round(r * 255), round(g * 255), round(b * 255)


def _dark_rgb(r: int, g: int, b: int, role: str) -> tuple[int, int, int]:
    h, l, s = _hls(r, g, b)
    neutral = s < 0.25 or l > 0.93 or l < 0.06
    if role == "fg":
        if l >= 0.55:
            return r, g, b
        if neutral:
            # #111827 -> #F3F4F6, #6B7280 -> #9CA3AF
            return _rgb(0.6, 0.97 - l * 0.75, min(s, 0.12))
        return _rgb(h, 0.62 + (0.55 - l) * 0.45, min(s, 0.75))
    if role == "border":
        if l <= 0.5:
            return r, g, b
        if neutral:
            return _rgb(0.6, 0.12 + (1 - l) * 0.6, 0.12)
        return _rgb(h, 0.22 + (1 - l) * 0.3, min(s, 0.6))
    # background
    if l <= 0.5:
        return r, g, b
    if neutral:
        # #FFFFFF -> #111827-ish, #F3F4F6 -> #1F2937-ish
        return _rgb(0.61, 0.07 + (1 - l) * 1.1, 0.18)
    return _rgb(h, 0.10 + (1 - l) * 0.55, min(s, 0.55))


def color(hex_or_name: str, role: str = "bg") -> QColor:
    """Theme-aware QColor for Python painting code. role: "bg" | "fg" | "border"."""
    c = QColor(hex_or_name)
    if _mode != "dark" or not c.isValid():
        return c
    r, g, b = _dark_rgb(c.red(), c.green(), c.blue(), role)
    out = QColor(r, g, b)
    out.setAlpha(c.alpha())
    return out


def fg(hex_or_name: str) -> QColor:
    return color(hex_or_name, "fg")


def bg(hex_or_name: str) -> QColor:
    return color(hex_or_name, "bg")


# ── Stylesheet conversion ────────────────────────────────────────────────────

_COLOR = re.compile(
    r"#(?P<hex>[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b"
    r"|(?P<fn>rgba?)\(\s*(?P<r>\d+)\s*,\s*(?P<g>\d+)\s*,\s*(?P<b>\d+)\s*(?P<rest>(?:,\s*[\d.]+%?\s*)?)\)"
    r"|\b(?P<name>white|black)\b",
    re.I,
)
_DECL = re.compile(r"(?P<prop>[A-Za-z-]+)\s*:\s*(?P<val>[^;{}]+)")

_FG_PROPS = {"color", "selection-color", "alternate-color"}
_BORDER_PROPS = {
    "border", "border-color", "border-top", "border-bottom", "border-left", "border-right",
    "border-top-color", "border-bottom-color", "border-left-color", "border-right-color",
    "outline", "gridline-color",
}


def _role_for(prop: str) -> str | None:
    p = prop.lower()
    if p in _FG_PROPS:
        return "fg"
    if p in _BORDER_PROPS:
        return "border"
    if p.startswith("background") or p in ("selection-background-color", "alternate-background-color"):
        return "bg"
    return None


def _convert_value(val: str, role: str) -> str:
    def repl(m: re.Match) -> str:
        if m.group("hex"):
            hx = m.group("hex")
            if len(hx) == 3:
                hx = "".join(c * 2 for c in hx)
            r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
            nr, ng, nb = _dark_rgb(r, g, b, role)
            return "#%02X%02X%02X" % (nr, ng, nb)
        if m.group("fn"):
            r, g, b = int(m.group("r")), int(m.group("g")), int(m.group("b"))
            nr, ng, nb = _dark_rgb(r, g, b, role)
            return f"{m.group('fn')}({nr}, {ng}, {nb}{m.group('rest') or ''})"
        name = m.group("name").lower()
        r, g, b = (255, 255, 255) if name == "white" else (0, 0, 0)
        nr, ng, nb = _dark_rgb(r, g, b, role)
        return "#%02X%02X%02X" % (nr, ng, nb)

    return _COLOR.sub(repl, val)


def to_dark(qss: str) -> str:
    if not qss:
        return qss

    def decl(m: re.Match) -> str:
        role = _role_for(m.group("prop"))
        if role is None:
            return m.group(0)
        return f"{m.group('prop')}: {_convert_value(m.group('val'), role)}"

    # Leave comments untouched
    parts = re.split(r"(/\*.*?\*/)", qss, flags=re.S)
    return "".join(p if p.startswith("/*") else _DECL.sub(decl, p) for p in parts)


def convert(qss: str) -> str:
    return to_dark(qss) if _mode == "dark" else qss


# ── Install / switch ─────────────────────────────────────────────────────────

def _patched_widget_set(self: QWidget, qss: str) -> None:
    self.setProperty(_RAW_PROP, qss)
    _orig_widget_set(self, convert(qss))


def _patched_app_set(self: QApplication, qss: str) -> None:
    self.setProperty(_RAW_PROP, qss)
    _orig_app_set(self, convert(qss))


def _system_is_dark() -> bool:
    app = QGuiApplication.instance()
    if app is None:
        return False
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    return app.palette().color(QPalette.Window).lightness() < 128


def _effective() -> str:
    if _preference in ("light", "dark"):
        return _preference
    return "dark" if _system_is_dark() else "light"


def _apply_palette() -> None:
    app = QApplication.instance()
    if app is None:
        return
    if _mode == "dark":
        p = QPalette()
        p.setColor(QPalette.Window, QColor("#111827"))
        p.setColor(QPalette.WindowText, QColor("#F3F4F6"))
        p.setColor(QPalette.Base, QColor("#0B0F14"))
        p.setColor(QPalette.AlternateBase, QColor("#1F2937"))
        p.setColor(QPalette.Text, QColor("#F3F4F6"))
        p.setColor(QPalette.Button, QColor("#1F2937"))
        p.setColor(QPalette.ButtonText, QColor("#F3F4F6"))
        p.setColor(QPalette.ToolTipBase, QColor("#1F2937"))
        p.setColor(QPalette.ToolTipText, QColor("#F3F4F6"))
        p.setColor(QPalette.PlaceholderText, QColor("#9CA3AF"))
        p.setColor(QPalette.Highlight, QColor("#10B981"))
        p.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
        p.setColor(QPalette.Link, QColor("#34D399"))
        app.setPalette(p)
    else:
        app.setPalette(app.style().standardPalette())


def mode() -> str:
    return _mode


def preference() -> str:
    return _preference


def _reapply_all() -> None:
    app = QApplication.instance()
    if app is None:
        return
    raw = app.property(_RAW_PROP)
    if isinstance(raw, str):
        _orig_app_set(app, convert(raw))
    for w in app.allWidgets():
        raw = w.property(_RAW_PROP)
        if isinstance(raw, str) and raw:
            _orig_widget_set(w, convert(raw))
    _apply_palette()


def set_preference(pref: str) -> None:
    """pref: "system" | "light" | "dark". Re-styles every open window."""
    global _preference, _mode
    _preference = pref if pref in ("system", "light", "dark") else "system"
    new_mode = _effective()
    if new_mode != _mode:
        _mode = new_mode
        _reapply_all()
        notifier.changed.emit(_mode)


def install(pref: str = "dark") -> None:
    """Call once, right after QApplication is created and before building windows."""
    global _installed, _orig_widget_set, _orig_app_set, _preference, _mode
    if not _installed:
        _orig_widget_set = QWidget.setStyleSheet
        _orig_app_set = QApplication.setStyleSheet
        QWidget.setStyleSheet = _patched_widget_set  # type: ignore[assignment]
        QApplication.setStyleSheet = _patched_app_set  # type: ignore[assignment]
        app = QGuiApplication.instance()
        if app is not None:
            try:
                app.styleHints().colorSchemeChanged.connect(lambda *_: set_preference(_preference))
            except Exception:
                pass
        _installed = True
    _preference = pref if pref in ("system", "light", "dark") else "system"
    _mode = _effective()
    _apply_palette()
