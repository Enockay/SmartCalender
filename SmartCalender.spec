# =============================================================================
#  SmartCalender – PyInstaller Spec File
#  Designed by Enock Mwems
#
#  Usage (run from project root):
#    pyinstaller SmartCalender.spec
#
#  Platform-specific builds are handled by:
#    scripts/build_mac.sh     → macOS  (produces .app + .dmg, signs it)
#    scripts/build_linux.sh   → Linux  (produces AppImage / .deb)
#    scripts/build_windows.bat → Windows (produces .exe installer via NSIS)
# =============================================================================

import sys
import os
from pathlib import Path

ROOT = Path(SPECPATH)          # project root (where this .spec lives)
APP_NAME    = "SmartCalender"
AUTHOR      = "Enock Mwema"
VERSION     = "1.0.0"
DESCRIPTION = "Smart Calender – Designed by Enock Mwema"
BUNDLE_ID   = "com.enockmwems.smartcalender"  # reverse-DNS, macOS only

# ---------------------------------------------------------------------------
# Detect platform
# ---------------------------------------------------------------------------
IS_MAC     = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")

# ---------------------------------------------------------------------------
# Icon paths  (put SmartCalender.icns / .ico / .png in assets/ folder)
# ---------------------------------------------------------------------------
ICON_MAC     = str(ROOT / "assets" / "SmartCalender.icns")
ICON_WIN     = str(ROOT / "assets" / "SmartCalender.ico")
ICON_LINUX   = str(ROOT / "assets" / "SmartCalender.png")

if IS_MAC:
    ICON = ICON_MAC if Path(ICON_MAC).exists() else None
elif IS_WINDOWS:
    ICON = ICON_WIN if Path(ICON_WIN).exists() else None
else:
    ICON = ICON_LINUX if Path(ICON_LINUX).exists() else None

# ---------------------------------------------------------------------------
# Data files to bundle (read-only assets only – NO database files!)
# Format: (source_glob_or_path, destination_folder_inside_bundle)
# ---------------------------------------------------------------------------
datas = [
    # QSS stylesheets
    (str(ROOT / "app" / "ui" / "resources" / "qss"),
     "app/ui/resources/qss"),

    # Icons / images / fonts used by the UI
    (str(ROOT / "app" / "ui" / "resources" / "icons"),
     "app/ui/resources/icons"),

    # Bundled notification sounds
    (str(ROOT / "app" / "resources" / "sounds"),
     "app/resources/sounds"),

    # App configuration (read-only defaults)
    (str(ROOT / "config.ini"), "."),

    # Bundled UI logo image
    (str(ROOT / "assets" / "image.png"), "assets"),
]

# Only add optional resource subdirs if they are present
_optional = [
    (ROOT / "app" / "ui" / "resources" / "fonts",  "app/ui/resources/fonts"),
    (ROOT / "app" / "ui" / "resources" / "images", "app/ui/resources/images"),
]
for src, dst in _optional:
    if src.exists() and any(src.iterdir()):
        datas.append((str(src), dst))

# ---------------------------------------------------------------------------
# Hidden imports that PyInstaller static-analysis misses
# ---------------------------------------------------------------------------
hidden_imports = [
    # PySide6
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtNetwork",
    # SQLAlchemy dialects / drivers
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "sqlalchemy.pool",
    "sqlalchemy.orm",
    # Standard library extras
    "configparser",
    "logging.handlers",
    "email.mime.text",
    "email.mime.multipart",
    # App packages
    "app.core",
    "app.database",
    "app.models",
    "app.services",
    "app.repositories",
    "app.controllers",
    "app.workers",
    "app.ui.windows",
    "app.ui.widgets",
    "app.ui.dialogs",
]

# ---------------------------------------------------------------------------
# Modules / packages to exclude (reduces bundle size)
# ---------------------------------------------------------------------------
excludes = [
    "tkinter",
    "matplotlib",
    "numpy",
    "pandas",
    "PIL",
    "cv2",
    "scipy",
    "PyQt5",
    "PyQt6",
    "wx",
    "gtk",
    "test",
    "unittest",
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ---------------------------------------------------------------------------
# EXE (single-folder mode – more reliable than --onefile across platforms)
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=IS_MAC,   # Needed for macOS open-with / file association
    target_arch=None,
    codesign_identity=None,  # macOS signing done post-build (see build_mac.sh)
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

# ---------------------------------------------------------------------------
# macOS .app bundle
# ---------------------------------------------------------------------------
if IS_MAC:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON,
        bundle_identifier=BUNDLE_ID,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": "Smart Calender",
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleVersion": VERSION,
            "CFBundleShortVersionString": VERSION,
            "CFBundleExecutable": APP_NAME,
            "NSHumanReadableCopyright": f"© 2024 {AUTHOR}. All rights reserved.",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.14",
            "NSMicrophoneUsageDescription": "Smart Calender may need microphone access.",
            "NSCalendarsUsageDescription":  "Smart Calender reads calendar data.",
            "LSApplicationCategoryType": "public.app-category.productivity",
            # Allow connecting to the internet for weather / API features
            "com.apple.security.network.client": True,
        },
    )
