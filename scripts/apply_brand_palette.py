"""
Map the old navy / royal-blue / purple-pink accents to the Deskhab palette
shared with the website (UX review §4.3, Appendix A).

Safe to re-run: it only rewrites colours that are still in the old palette.
User-selectable event colours (meeting dialog, category colours) are not
touched because they live in Python data, not in these stylesheets.

    python scripts/apply_brand_palette.py
"""

from __future__ import annotations

import colorsys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QSS_DIR = ROOT / "app" / "ui" / "resources" / "qss"

HEX_MAP = {
    # royal blue accents -> Deskhab green
    "#2563EB": "#059669", "#3B82F6": "#10B981", "#1D4ED8": "#047857", "#1E40AF": "#065F46",
    "#60A5FA": "#34D399", "#93C5FD": "#6EE7B7", "#BFDBFE": "#A7F3D0", "#DBEAFE": "#D1FAE5",
    "#EFF6FF": "#ECFDF5", "#EEF2FF": "#ECFDF5", "#C7D2FE": "#A7F3D0", "#2D8CFF": "#10B981",
    "#1F6FF2": "#059669", "#4A6CF7": "#059669", "#5C6DFD": "#10B981", "#4C5DED": "#059669",
    "#4F46E5": "#059669", "#6366F1": "#10B981", "#F0F4FF": "#F3F4F6",
    # purple / pink banner -> cyan accent
    "#1E1B4B": "#0B0F14", "#3730A3": "#065F46", "#7C3AED": "#0E7490", "#8B5CF6": "#0891B2",
    "#EC4899": "#22D3EE", "#A855F7": "#22D3EE", "#1A1A3E": "#111827",
    # navy sidebar / panels -> night neutrals
    "#0D2147": "#0B0F14", "#102A5A": "#111827", "#0F2850": "#111827", "#132D5B": "#111827",
    "#1A3A6E": "#1F2937", "#142F5C": "#1F2937", "#1A3B75": "#1F2937", "#1E4384": "#374151",
}

RGBA_MAP = {
    (37, 99, 235): (5, 150, 105),
    (59, 130, 246): (16, 185, 129),
    (29, 78, 216): (4, 120, 87),
    (96, 165, 250): (52, 211, 153),
    (236, 72, 153): (34, 211, 238),
    (124, 58, 237): (14, 116, 144),
    (139, 92, 246): (8, 145, 178),
    (99, 102, 241): (16, 185, 129),
}

def _fallback(r: int, g: int, b: int) -> tuple[int, int, int] | None:
    """Any remaining saturated blue/violet is mapped onto the brand scale by lightness."""
    h, l, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if not (0.55 < h < 0.85 and sat > 0.4) or l > 0.95:
        return None
    for limit, hex_ in (
        (0.15, "#0B0F14"), (0.25, "#111827"), (0.38, "#065F46"), (0.55, "#059669"),
        (0.70, "#10B981"), (0.85, "#6EE7B7"), (0.95, "#D1FAE5"),
    ):
        if l < limit:
            return int(hex_[1:3], 16), int(hex_[3:5], 16), int(hex_[5:7], 16)
    return None


_hex = re.compile(r"#[0-9A-Fa-f]{6}\b")
_rgba = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


def convert(text: str) -> tuple[str, int]:
    count = 0

    def hx(m: re.Match) -> str:
        nonlocal count
        new = HEX_MAP.get(m.group(0).upper())
        if new:
            count += 1
            return new
        v = m.group(0)
        fb = _fallback(int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
        if fb:
            count += 1
            return "#%02X%02X%02X" % fb
        return v

    def rg(m: re.Match) -> str:
        nonlocal count
        key = tuple(int(g) for g in m.groups())
        new = RGBA_MAP.get(key) or _fallback(*key)
        if new:
            count += 1
            prefix = m.group(0)[: m.group(0).index("(") + 1]
            return f"{prefix}{new[0]}, {new[1]}, {new[2]}"
        return m.group(0)

    text = _hex.sub(hx, text)
    text = _rgba.sub(rg, text)
    return text, count


def main() -> None:
    total = 0
    for path in sorted(QSS_DIR.glob("*.qss")):
        src = path.read_text(encoding="utf-8")
        out, n = convert(src)
        if n:
            path.write_text(out, encoding="utf-8")
            print(f"{path.name}: {n} colours updated")
            total += n
    print(f"Total: {total}")


if __name__ == "__main__":
    main()
