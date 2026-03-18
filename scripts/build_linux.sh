#!/usr/bin/env bash
# =============================================================================
#  SmartCalender – Linux Build Script
#  Designed by Enock Mwems
#
#  Produces:
#    dist/linux/SmartCalender/          – standalone directory (run directly)
#    dist/linux/SmartCalender-x86_64.AppImage   – portable single-file image
#    dist/linux/smartcalender_1.0.0_amd64.deb  – Debian/Ubuntu package
#
#  Prerequisites:
#    pip install pyinstaller
#    sudo apt install libfuse2 binutils patchelf  (for AppImage)
#    sudo apt install fakeroot dpkg-deb            (for .deb package)
#
#  Usage:
#    chmod +x scripts/build_linux.sh
#    ./scripts/build_linux.sh
#
#  GPG signing (optional):
#    export GPG_KEY_ID="your-gpg-key-id"
#    ./scripts/build_linux.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_NAME="SmartCalender"
APP_NAME_LOWER="smartcalender"
VERSION="1.0.0"
AUTHOR="Enock Mwems"
DESCRIPTION="Smart Calender – Productivity calendar application"
ARCH="amd64"

GPG_KEY_ID="${GPG_KEY_ID:-}"    # optional: GPG key to sign the AppImage/deb

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$ROOT/dist/linux_build_$(date +%Y%m%d_%H%M%S)"
BUILD_DIR="$ROOT/build"

cd "$ROOT"

echo "============================================================"
echo "  Smart Calender – Linux Build"
echo "  Designed by $AUTHOR  |  v$VERSION"
echo "============================================================"

# ---------------------------------------------------------------------------
# 1. Clean
# ---------------------------------------------------------------------------
echo "[1/6] Cleaning previous build..."
rm -rf "$BUILD_DIR" 2>/dev/null || true
mkdir -p "$DIST_DIR"

# ---------------------------------------------------------------------------
# 2. Dependencies
# ---------------------------------------------------------------------------
echo "[2/6] Installing build dependencies..."
if ! command -v pyinstaller &>/dev/null; then
    pip install --quiet --upgrade pyinstaller
fi

# ---------------------------------------------------------------------------
# 3. PyInstaller build
# ---------------------------------------------------------------------------
echo "[3/6] Running PyInstaller..."
pyinstaller SmartCalender.spec \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR/work" \
    --noconfirm

APP_DIR="$DIST_DIR/$APP_NAME"
if [ ! -d "$APP_DIR" ]; then
    echo "ERROR: output directory not found at $APP_DIR"
    exit 1
fi
echo "  Built: $APP_DIR"

# ---------------------------------------------------------------------------
# 4. Create AppImage
#    Uses appimagetool (downloaded automatically if not present)
# ---------------------------------------------------------------------------
echo "[4/6] Creating AppImage..."

APPDIR_STAGING="$BUILD_DIR/AppDir"
mkdir -p "$APPDIR_STAGING/usr/bin"
mkdir -p "$APPDIR_STAGING/usr/share/applications"
mkdir -p "$APPDIR_STAGING/usr/share/icons/hicolor/256x256/apps"

# Copy the PyInstaller output into AppDir
cp -r "$APP_DIR"/. "$APPDIR_STAGING/usr/bin/"

# Desktop entry
cat > "$APPDIR_STAGING/usr/share/applications/$APP_NAME_LOWER.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Smart Calender
Comment=$DESCRIPTION
Exec=$APP_NAME
Icon=$APP_NAME_LOWER
Categories=Office;Productivity;
Keywords=calendar;schedule;reminder;task;
StartupNotify=true
DESKTOP

# Symlink for AppImage launcher
cp "$APPDIR_STAGING/usr/share/applications/$APP_NAME_LOWER.desktop" \
   "$APPDIR_STAGING/$APP_NAME_LOWER.desktop"

# Copy icon if available
if [ -f "$ROOT/assets/${APP_NAME}.png" ]; then
    cp "$ROOT/assets/${APP_NAME}.png" \
       "$APPDIR_STAGING/usr/share/icons/hicolor/256x256/apps/$APP_NAME_LOWER.png"
    cp "$ROOT/assets/${APP_NAME}.png" \
       "$APPDIR_STAGING/$APP_NAME_LOWER.png"
else
    echo "  Warning: no icon found at assets/${APP_NAME}.png – AppImage will have no icon"
    # Create a minimal 1×1 PNG placeholder so appimagetool doesn't fail
    touch "$APPDIR_STAGING/$APP_NAME_LOWER.png"
fi

# AppRun entrypoint
cat > "$APPDIR_STAGING/AppRun" <<'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "$HERE/usr/bin/SmartCalender" "$@"
APPRUN
chmod +x "$APPDIR_STAGING/AppRun"

APPIMAGE_OUT="$DIST_DIR/${APP_NAME}-${VERSION}-x86_64.AppImage"

# Download appimagetool if not on PATH
if ! command -v appimagetool &>/dev/null; then
    APPIMAGETOOL="$BUILD_DIR/appimagetool"
    if [ ! -f "$APPIMAGETOOL" ]; then
        echo "  Downloading appimagetool..."
        curl -fsSL \
            "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
            -o "$APPIMAGETOOL"
        chmod +x "$APPIMAGETOOL"
    fi
else
    APPIMAGETOOL="appimagetool"
fi

ARCH=x86_64 "$APPIMAGETOOL" --no-appstream \
    "$APPDIR_STAGING" "$APPIMAGE_OUT" 2>&1 || \
echo "  appimagetool warning (non-fatal)"

echo "  AppImage: $APPIMAGE_OUT"

# ---------------------------------------------------------------------------
# 5. Create .deb package
# ---------------------------------------------------------------------------
echo "[5/6] Creating .deb package..."

DEB_ROOT="$BUILD_DIR/deb_pkg"
INSTALL_DIR="$DEB_ROOT/opt/$APP_NAME_LOWER"
mkdir -p "$INSTALL_DIR"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$DEB_ROOT/DEBIAN"

# Copy app files
cp -r "$APP_DIR"/. "$INSTALL_DIR/"

# Wrapper launcher script
mkdir -p "$DEB_ROOT/usr/local/bin"
cat > "$DEB_ROOT/usr/local/bin/$APP_NAME_LOWER" <<LAUNCHER
#!/bin/bash
exec /opt/$APP_NAME_LOWER/$APP_NAME "\$@"
LAUNCHER
chmod +x "$DEB_ROOT/usr/local/bin/$APP_NAME_LOWER"

# .desktop file
cat > "$DEB_ROOT/usr/share/applications/$APP_NAME_LOWER.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Smart Calender
Comment=$DESCRIPTION
Exec=/opt/$APP_NAME_LOWER/$APP_NAME
Icon=$APP_NAME_LOWER
Categories=Office;Productivity;
Keywords=calendar;schedule;reminder;task;
StartupNotify=true
DESKTOP

# Icon
if [ -f "$ROOT/assets/${APP_NAME}.png" ]; then
    cp "$ROOT/assets/${APP_NAME}.png" \
       "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps/$APP_NAME_LOWER.png"
fi

# Installed size (in KB)
INSTALLED_KB=$(du -sk "$INSTALL_DIR" | cut -f1)

# DEBIAN control file
cat > "$DEB_ROOT/DEBIAN/control" <<CONTROL
Package: $APP_NAME_LOWER
Version: $VERSION
Architecture: $ARCH
Maintainer: $AUTHOR <smartcalender@enockmwems.com>
Installed-Size: $INSTALLED_KB
Depends: libglib2.0-0, libgl1, libegl1
Section: misc
Priority: optional
Description: $DESCRIPTION
 Smart Calender is a productivity desktop application for managing
 events, tasks, reminders and meetings.
 .
 Designed by $AUTHOR.
CONTROL

# Post-install script
cat > "$DEB_ROOT/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
chmod +x /opt/smartcalender/SmartCalender
update-desktop-database -q /usr/share/applications || true
exit 0
POSTINST
chmod 0755 "$DEB_ROOT/DEBIAN/postinst"

DEB_OUT="$DIST_DIR/${APP_NAME_LOWER}_${VERSION}_${ARCH}.deb"
fakeroot dpkg-deb --build "$DEB_ROOT" "$DEB_OUT"
echo "  .deb: $DEB_OUT"

# ---------------------------------------------------------------------------
# 6. GPG sign artefacts
# ---------------------------------------------------------------------------
if [ -n "$GPG_KEY_ID" ]; then
    echo "[6/6] Signing artefacts with GPG key: $GPG_KEY_ID"
    for artifact in "$APPIMAGE_OUT" "$DEB_OUT"; do
        if [ -f "$artifact" ]; then
            gpg --batch --yes \
                --local-user "$GPG_KEY_ID" \
                --detach-sign --armor \
                "$artifact"
            echo "  Signed: ${artifact}.asc"
        fi
    done
else
    echo "[6/6] Skipping GPG signing (GPG_KEY_ID not set)"
    echo "  To sign, run:  export GPG_KEY_ID='your-key-id'"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  BUILD COMPLETE"
echo "  AppImage : $APPIMAGE_OUT"
echo "  .deb     : $DEB_OUT"
echo "  Author   : $AUTHOR"
echo "  Version  : $VERSION"
echo "============================================================"
