#!/usr/bin/env bash
# Build BLEPlot as a standalone macOS application bundle.
# Output: dist/BLEPlot.app  (drag to /Applications to install)
#
# Usage:
#   ./build.sh            # onedir bundle (faster startup, recommended)
#   ./build.sh --onefile  # single-file app (slower startup)
#
# Requirements:
#   pip install pyinstaller   (handled automatically below)
#
# macOS Bluetooth note:
#   The generated .app needs Bluetooth permission.
#   On first launch macOS will prompt; if it doesn't, grant access via
#   System Settings → Privacy & Security → Bluetooth.

set -e

VENV=".venv"
ENTRY="src/bleplot/main.py"
APP_NAME="BLEPlot"

if [ ! -d "$VENV" ]; then
    echo "ERROR: virtualenv '$VENV' not found. Run: python3 -m venv .venv && .venv/bin/pip install -e ." >&2
    exit 1
fi

echo "==> Installing / upgrading PyInstaller..."
"$VENV/bin/pip" install --quiet --upgrade pyinstaller

MODE="--onedir"
if [ "$1" = "--onefile" ]; then
    MODE="--onefile"
    echo "==> Mode: onefile (single executable)"
else
    echo "==> Mode: onedir (bundle directory)"
fi

echo "==> Building $APP_NAME for macOS..."
"$VENV/bin/pyinstaller" \
    --clean \
    --noconfirm \
    $MODE \
    --windowed \
    --name "$APP_NAME" \
    --collect-all dearpygui \
    --hidden-import bleak \
    --hidden-import bleak.backends.corebluetooth \
    --hidden-import bleak.backends.corebluetooth.scanner \
    --hidden-import bleak.backends.corebluetooth.client \
    --hidden-import bleak.backends.corebluetooth.CentralManagerDelegate \
    "$ENTRY"

echo ""
if [ "$MODE" = "--onefile" ]; then
    echo "==> Done: dist/$APP_NAME"
else
    echo "==> Done: dist/$APP_NAME.app"
    echo "    To install: cp -r dist/$APP_NAME.app /Applications/"
fi
