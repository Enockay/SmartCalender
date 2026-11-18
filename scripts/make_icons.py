"""
Regenerate every app icon from assets/logo.svg (UX review §4.2: one logo everywhere).

    python scripts/make_icons.py

Writes assets/SmartCalender.png (1024 px), assets/image.png, assets/SmartCalender.ico
(16–256 px, PNG-compressed entries) and, on macOS, assets/SmartCalender.icns.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def render(renderer: QSvgRenderer, size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    renderer.render(p)
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def write_ico(renderer: QSvgRenderer, path: Path, sizes=(16, 24, 32, 48, 64, 128, 256)) -> None:
    blobs = [png_bytes(render(renderer, s)) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for s, blob in zip(sizes, blobs):
        dim = 0 if s >= 256 else s  # 0 means 256 in the ICO format
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    path.write_bytes(header + entries + b"".join(blobs))


def write_icns(png_1024: Path, path: Path) -> None:
    if sys.platform != "darwin" or not shutil.which("iconutil"):
        print("Skipping .icns (needs macOS iconutil)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "SmartCalender.iconset"
        iconset.mkdir()
        for s in (16, 32, 128, 256, 512):
            for scale, suffix in ((1, ""), (2, "@2x")):
                out = iconset / f"icon_{s}x{s}{suffix}.png"
                subprocess.run(
                    ["sips", "-z", str(s * scale), str(s * scale), str(png_1024), "--out", str(out)],
                    check=True, capture_output=True,
                )
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(path)], check=True)


def render_tile(renderer: QSvgRenderer, w: int, h: int, logo_ratio: float = 0.6) -> QImage:
    """Logo centred on a transparent tile, as the Microsoft Store expects."""
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    side = int(min(w, h) * logo_ratio)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    from PySide6.QtCore import QRectF
    renderer.render(p, QRectF((w - side) / 2, (h - side) / 2, side, side))
    p.end()
    return img


def write_msix_assets(renderer: QSvgRenderer) -> None:
    out = ASSETS / "msix"
    out.mkdir(exist_ok=True)
    tiles = {
        "StoreLogo.png": (50, 50, 1.0),
        "Square44x44Logo.png": (44, 44, 1.0),
        "Square44x44Logo.targetsize-256.png": (256, 256, 1.0),
        "Square71x71Logo.png": (71, 71, 0.7),
        "Square150x150Logo.png": (150, 150, 0.6),
        "Wide310x150Logo.png": (310, 150, 0.6),
        "Square310x310Logo.png": (310, 310, 0.6),
    }
    for name, (w, h, ratio) in tiles.items():
        render_tile(renderer, w, h, ratio).save(str(out / name))
        # scale-200 variants keep tiles sharp on high-DPI screens
        stem, ext = name.rsplit(".", 1)
        if "targetsize" not in stem:
            render_tile(renderer, w * 2, h * 2, ratio).save(str(out / f"{stem}.scale-200.{ext}"))


def main() -> None:
    app = QGuiApplication(sys.argv)  # noqa: F841
    renderer = QSvgRenderer(str(ASSETS / "logo.svg"))
    if not renderer.isValid():
        raise SystemExit("assets/logo.svg could not be rendered")
    big = render(renderer, 1024)
    big.save(str(ASSETS / "SmartCalender.png"))
    big.save(str(ASSETS / "image.png"))
    write_ico(renderer, ASSETS / "SmartCalender.ico")
    write_icns(ASSETS / "SmartCalender.png", ASSETS / "SmartCalender.icns")
    write_msix_assets(renderer)
    print("Icons written to", ASSETS)


if __name__ == "__main__":
    main()
