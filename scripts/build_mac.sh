#!/usr/bin/env bash
# =============================================================================
#  SmartCalender – macOS Build & Sign Script
#  Designed by Enock Mwems
#
#  Produces:
#    dist/mac/SmartCalender.app   – signed macOS application bundle
#    dist/mac/SmartCalender.dmg   – disk image ready for distribution
#
#  Prerequisites:
#    pip install pyinstaller
#    Xcode Command Line Tools  (xcode-select --install)
#    create-dmg               (brew install create-dmg)
#
#  Code-signing prerequisites (optional but recommended for distribution):
#    A valid "Developer ID Application" certificate in your keychain.
#    Set SIGNING_IDENTITY below (or export it as an env var before running).
#
#  Usage:
#    chmod +x scripts/build_mac.sh
#    ./scripts/build_mac.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration – edit these values for your environment
# ---------------------------------------------------------------------------
APP_NAME="SmartCalender"
VERSION="1.0.0"
AUTHOR="Enock Mwems"
BUNDLE_ID="com.enockmwems.smartcalender"

# Set to your Developer ID (leave empty to skip signing)
# Example: "Developer ID Application: Enock Mwems (XXXXXXXXXX)"
SIGNING_IDENTITY="${SIGNING_IDENTITY:-}"

# Apple notarization credentials (only needed if distributing outside Mac App Store)
APPLE_ID="${APPLE_ID:-}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_APP_PASSWORD="${APPLE_APP_PASSWORD:-}"   # app-specific password

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$ROOT/dist/mac_build_$(date +%Y%m%d_%H%M%S)"
BUILD_DIR="$ROOT/build"

# ---------------------------------------------------------------------------
# 0. Move to project root
# ---------------------------------------------------------------------------
cd "$ROOT"
echo "============================================================"
echo "  Smart Calender – macOS Build"
echo "  Designed by $AUTHOR  |  v$VERSION"
echo "============================================================"

# ---------------------------------------------------------------------------
# 1. Clean previous build artefacts
# ---------------------------------------------------------------------------
echo "[1/7] Cleaning previous build..."
rm -rf "$BUILD_DIR" 2>/dev/null || true
mkdir -p "$DIST_DIR"

# ---------------------------------------------------------------------------
# 2. Install / upgrade build dependencies
# ---------------------------------------------------------------------------
echo "[2/7] Installing build dependencies..."
if ! command -v pyinstaller &>/dev/null; then
    pip install --quiet --upgrade pyinstaller
fi

# ---------------------------------------------------------------------------
# 3. Build with PyInstaller
# ---------------------------------------------------------------------------
echo "[3/7] Running PyInstaller..."
pyinstaller "$ROOT/SmartCalender.spec" \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR/work" \
    --noconfirm

APP_BUNDLE="$DIST_DIR/${APP_NAME}.app"
if [ ! -d "$APP_BUNDLE" ]; then
    echo "ERROR: .app bundle not found at $APP_BUNDLE"
    exit 1
fi
echo "  Built: $APP_BUNDLE"

# ---------------------------------------------------------------------------
# 4. Code-sign the .app bundle
# ---------------------------------------------------------------------------
if [ -n "$SIGNING_IDENTITY" ]; then
    echo "[4/7] Code-signing with identity: $SIGNING_IDENTITY"

    # Sign all nested frameworks / dylibs first, then the outer bundle
    find "$APP_BUNDLE" -name "*.dylib" -o -name "*.so" | while read -r lib; do
        codesign --force --verify --verbose=0 \
                 --sign "$SIGNING_IDENTITY" \
                 --options runtime \
                 "$lib" 2>/dev/null || true
    done

    codesign --deep \
             --force \
             --verify \
             --verbose=1 \
             --sign "$SIGNING_IDENTITY" \
             --options runtime \
             --entitlements "$ROOT/assets/entitlements.plist" \
             "$APP_BUNDLE"

    codesign --verify --deep --strict "$APP_BUNDLE"
    echo "  Code-signing: OK"
else
    echo "[4/7] Skipping code-signing (SIGNING_IDENTITY not set)"
    echo "  To sign, run:  export SIGNING_IDENTITY='Developer ID Application: Enock Mwems (TEAMID)'"
fi

# ---------------------------------------------------------------------------
# 5. Create DMG
# ---------------------------------------------------------------------------
echo "[5/7] Creating DMG..."

DMG_PATH="$DIST_DIR/${APP_NAME}-${VERSION}-macOS.dmg"

# Use create-dmg if available, otherwise fall back to hdiutil
if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "$APP_NAME" \
        --volicon "$ROOT/assets/SmartCalender.icns" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 175 190 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 425 190 \
        --no-internet-enable \
        "$DMG_PATH" \
        "$DIST_DIR/${APP_NAME}.app" 2>/dev/null || \
    echo "  create-dmg warning (non-fatal): continuing..."
else
    # Simple fallback with hdiutil
    STAGING="$BUILD_DIR/dmg_staging"
    mkdir -p "$STAGING"
    cp -R "$APP_BUNDLE" "$STAGING/"
    ln -sf /Applications "$STAGING/Applications"
    hdiutil create -volname "$APP_NAME" \
                   -srcfolder "$STAGING" \
                   -ov -format UDZO \
                   "$DMG_PATH"
    rm -rf "$STAGING"
fi

echo "  DMG: $DMG_PATH"

# ---------------------------------------------------------------------------
# 6. Sign the DMG (if signing identity is set)
# ---------------------------------------------------------------------------
if [ -n "$SIGNING_IDENTITY" ]; then
    echo "[6/7] Signing DMG..."
    codesign --force --sign "$SIGNING_IDENTITY" "$DMG_PATH"
    echo "  DMG signed: OK"

    # Notarize (optional – only if Apple credentials are set)
    if [ -n "$APPLE_ID" ] && [ -n "$APPLE_TEAM_ID" ] && [ -n "$APPLE_APP_PASSWORD" ]; then
        echo "  Submitting for notarization..."
        xcrun notarytool submit "$DMG_PATH" \
            --apple-id "$APPLE_ID" \
            --team-id "$APPLE_TEAM_ID" \
            --password "$APPLE_APP_PASSWORD" \
            --wait
        xcrun stapler staple "$DMG_PATH"
        echo "  Notarization: OK"
    else
        echo "  Skipping notarization (APPLE_ID / APPLE_TEAM_ID / APPLE_APP_PASSWORD not set)"
    fi
else
    echo "[6/7] Skipping DMG signing (SIGNING_IDENTITY not set)"
fi

# ---------------------------------------------------------------------------
# 7. Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  BUILD COMPLETE"
echo "  App    : $APP_BUNDLE"
echo "  DMG    : $DMG_PATH"
echo "  Author : $AUTHOR"
echo "  Version: $VERSION"
echo "============================================================"
