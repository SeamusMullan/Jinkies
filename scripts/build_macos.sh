#!/usr/bin/env bash
# build_macos.sh – Builds Jinkies for macOS and packages it into a DMG.
#
# PyInstaller is invoked with --onedir --windowed so that it produces a proper
# macOS .app bundle (dist/Jinkies.app) rather than a bare binary.  The .app
# bundle is then placed into a staging directory and wrapped in a UDZO-compressed
# DMG via hdiutil.
set -euo pipefail

echo "==> Building Jinkies for macOS..."

# Include the .icns icon when it is present.
ICON_FLAG=""
if [ -f "assets/icon.icns" ]; then
    ICON_FLAG="--icon=assets/icon.icns"
fi

# --onedir  : output a directory-based build (required for .app bundle creation)
# --windowed: suppress the terminal window and produce a .app bundle on macOS
uv run pyinstaller \
    --onedir \
    --windowed \
    --name Jinkies \
    ${ICON_FLAG} \
    --add-data "sounds:sounds" \
    main.py

echo "==> Creating DMG..."
if command -v hdiutil &> /dev/null; then
    # Verify that PyInstaller produced the expected .app bundle.
    # --onedir --windowed must always create dist/Jinkies.app on macOS; if it
    # is missing the build has gone wrong and we should fail loudly rather than
    # silently packaging a bare binary.
    if [ ! -d "dist/Jinkies.app" ]; then
        echo "==> ERROR: dist/Jinkies.app not found." >&2
        echo "    PyInstaller with --onedir --windowed should produce a .app bundle." >&2
        echo "    Check the PyInstaller output above for errors." >&2
        exit 1
    fi

    # Ensure all file handles from the build are released before creating the DMG.
    sync
    sleep 2

    mkdir -p dist/dmg_staging
    cp -r dist/Jinkies.app dist/dmg_staging/
    hdiutil create -volname "Jinkies" -srcfolder dist/dmg_staging -ov -format UDZO dist/Jinkies.dmg
    rm -rf dist/dmg_staging
    echo "==> Done: dist/Jinkies.dmg"
else
    echo "==> hdiutil not available, skipping DMG creation"
    echo "==> App bundle available at: dist/Jinkies.app"
fi
