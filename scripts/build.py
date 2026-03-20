#!/usr/bin/env python3
"""
Smart Calender – Cross-Platform Build Helper
Designed by Enock Mwems

This script detects the current OS and delegates to the appropriate
platform-specific build script:
    macOS   → scripts/build_mac.sh
    Linux   → scripts/build_linux.sh
    Windows → scripts/build_windows.bat

It also verifies prerequisites and generates the entitlements.plist
needed for macOS code-signing.

Usage (from project root):
    python scripts/build.py
    python scripts/build.py --check   # only check prerequisites
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ROOT    = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ASSETS  = ROOT / "assets"
DIST    = ROOT / "dist"
VERSION = "1.0.0"
AUTHOR  = "Enock Mwems"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], *, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    print(f"  > {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, **kwargs)


def _banner(msg: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {msg}")
    print("=" * 60)


def _ok(msg: str)   -> None: print(f"  ✓  {msg}")
def _warn(msg: str) -> None: print(f"  ⚠  {msg}")
def _err(msg: str)  -> None: print(f"  ✗  {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Prerequisite check
# ---------------------------------------------------------------------------

def check_prerequisites() -> bool:
    _banner("Checking prerequisites")
    ok = True

    # Python version
    if sys.version_info < (3, 9):
        _err(f"Python 3.9+ required (found {platform.python_version()})")
        ok = False
    else:
        _ok(f"Python {platform.python_version()}")

    # PyInstaller
    if shutil.which("pyinstaller"):
        res = subprocess.run(["pyinstaller", "--version"], capture_output=True, text=True)
        _ok(f"PyInstaller {res.stdout.strip()}")
    else:
        _warn("PyInstaller not found – will be installed automatically during build")

    # Platform-specific
    system = platform.system()
    if system == "Darwin":
        if shutil.which("codesign"):
            _ok("codesign (Xcode CLT)")
        else:
            _warn("codesign not found – install Xcode Command Line Tools")
        if shutil.which("create-dmg"):
            _ok("create-dmg")
        else:
            _warn("create-dmg not found – falling back to hdiutil for DMG creation")
            _warn("  Install via: brew install create-dmg")
        if shutil.which("xcrun"):
            _ok("xcrun (notarization)")
        else:
            _warn("xcrun not found")

    elif system == "Linux":
        for tool, pkg in [("fakeroot", "fakeroot"), ("dpkg-deb", "dpkg-deb")]:
            if shutil.which(tool):
                _ok(tool)
            else:
                _warn(f"{tool} not found – install via: sudo apt install {pkg}")

    elif system == "Windows":
        if shutil.which("makensis"):
            _ok("makensis (NSIS)")
        else:
            _warn("makensis not found – installer won't be created")
            _warn("  Download NSIS from https://nsis.sourceforge.io/Download")
        if shutil.which("signtool"):
            _ok("signtool")
        else:
            _warn("signtool not found – code-signing won't be available")
            _warn("  Install Windows SDK to get signtool")

    return ok


# ---------------------------------------------------------------------------
# Asset generation
# ---------------------------------------------------------------------------

def generate_entitlements() -> None:
    """Generate assets/entitlements.plist for macOS code-signing."""
    ASSETS.mkdir(exist_ok=True)
    plist = ASSETS / "entitlements.plist"
    if plist.exists():
        _ok(f"entitlements.plist already exists at {plist}")
        return
    content = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Allow outbound network connections (weather / API features) -->
    <key>com.apple.security.network.client</key>
    <true/>
    <!-- Hardened runtime required for notarization -->
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <!-- Allow loading JIT-compiled code (Python interpreter) -->
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
</dict>
</plist>
"""
    plist.write_text(content, encoding="utf-8")
    _ok(f"Generated {plist}")


def ensure_assets_dir() -> None:
    """Create assets/ directory with placeholder files if needed."""
    ASSETS.mkdir(exist_ok=True)

    # Placeholder LICENSE.txt
    lic = ROOT / "LICENSE.txt"
    if not lic.exists():
        lic.write_text(
            f"Smart Calender\nDesigned by {AUTHOR}\n"
            f"Copyright (c) 2024 {AUTHOR}. All rights reserved.\n",
            encoding="utf-8",
        )
        _ok(f"Created placeholder {lic}")

    image_png = ASSETS / "image.png"
    if not image_png.exists():
        _warn(f"Missing {image_png} (base icon source)")
    else:
        _ok(f"Found {image_png.name}")
        smart_png = ASSETS / "SmartCalender.png"
        if not smart_png.exists():
            shutil.copy2(image_png, smart_png)
            _ok(f"Created {smart_png.name} from image.png")
        else:
            _ok(f"Found {smart_png.name}")

        # On macOS, create SmartCalender.icns from assets/image.png if absent.
        # This is the icon format used by app bundles and installers.
        smart_icns = ASSETS / "SmartCalender.icns"
        if platform.system() == "Darwin" and not smart_icns.exists():
            _generate_macos_icns_from_png(image_png, smart_icns)

    # Windows still needs a .ico for best installer/taskbar icon behavior.
    win_ico = ASSETS / "SmartCalender.ico"
    if win_ico.exists():
        _ok(f"Found {win_ico.name}")
    else:
        _warn(f"Missing {win_ico} (Windows icon)")

    mac_icns = ASSETS / "SmartCalender.icns"
    if mac_icns.exists():
        _ok(f"Found {mac_icns.name}")
    else:
        _warn(f"Missing {mac_icns} (macOS icon)")


def _generate_macos_icns_from_png(src_png: Path, out_icns: Path) -> None:
    """Generate .icns from a PNG using native macOS tools (sips + iconutil)."""
    if not shutil.which("sips") or not shutil.which("iconutil"):
        _warn("sips/iconutil not found; cannot auto-generate SmartCalender.icns")
        return

    tmp_root = ROOT / "build" / "icongen"
    iconset = tmp_root / "SmartCalender.iconset"
    shutil.rmtree(iconset, ignore_errors=True)
    iconset.mkdir(parents=True, exist_ok=True)

    # iconutil expects this fixed set of iconset filenames/sizes.
    size_map = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }

    try:
        for name, size in size_map.items():
            out_png = iconset / name
            subprocess.run(
                ["sips", "-z", str(size), str(size), str(src_png), "--out", str(out_png)],
                check=True,
                capture_output=True,
                text=True,
            )

        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(out_icns)],
            check=True,
            capture_output=True,
            text=True,
        )
        _ok(f"Generated {out_icns.name} from image.png")
    except subprocess.CalledProcessError as exc:
        _warn(f"Could not generate {out_icns.name}: {exc}")


# ---------------------------------------------------------------------------
# Build dispatch
# ---------------------------------------------------------------------------

def build() -> int:
    system = platform.system()
    _banner(f"Starting build for {system}  |  Smart Calender v{VERSION}")
    _banner(f"Designed by {AUTHOR}")

    ensure_assets_dir()
    if system == "Darwin":
        generate_entitlements()

    dist_platform = {"Darwin": "mac", "Linux": "linux", "Windows": "windows"}.get(system, system.lower())
    (DIST / dist_platform).mkdir(parents=True, exist_ok=True)

    if system == "Darwin":
        script = SCRIPTS / "build_mac.sh"
        os.chmod(script, 0o755)
        ret = subprocess.call(["bash", str(script)])

    elif system == "Linux":
        script = SCRIPTS / "build_linux.sh"
        os.chmod(script, 0o755)
        ret = subprocess.call(["bash", str(script)])

    elif system == "Windows":
        script = SCRIPTS / "build_windows.bat"
        ret = subprocess.call([str(script)], shell=True)

    else:
        _err(f"Unsupported platform: {system}")
        return 1

    if ret == 0:
        _banner(f"Build finished successfully  →  dist/{dist_platform}/")
        print(f"\n  Designed by {AUTHOR}\n")
    else:
        _err(f"Build script exited with code {ret}")

    return ret


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Smart Calender build helper – Designed by {AUTHOR}"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check prerequisites, do not build",
    )
    args = parser.parse_args()

    if args.check:
        check_prerequisites()
        return 0

    check_prerequisites()
    return build()


if __name__ == "__main__":
    raise SystemExit(main())
