#!/usr/bin/env bash
set -euo pipefail

echo "==> Building Jinkies for macOS..."

ICON_FLAG=""
if [ -f "assets/icon.icns" ]; then
    ICON_FLAG="--icon=assets/icon.icns"
fi

uv run pyinstaller \
    --onedir \
    --windowed \
    --name Jinkies \
    ${ICON_FLAG} \
    --add-data "sounds:sounds" \
    main.py

echo "==> Creating DMG..."
if command -v hdiutil &> /dev/null; then
    # Ensure all file handles from the build are released
    sync
    sleep 2

    mkdir -p dist/dmg_staging
    cp -r dist/Jinkies.app dist/dmg_staging/ 2>/dev/null || cp -r dist/Jinkies dist/dmg_staging/
    hdiutil create -volname "Jinkies" -srcfolder dist/dmg_staging -ov -format UDZO dist/Jinkies.dmg
    rm -rf dist/dmg_staging
    echo "==> Done: dist/Jinkies.dmg"
else
    echo "==> hdiutil not available, skipping DMG creation"
    echo "==> Binary available at: dist/Jinkies"
fi
