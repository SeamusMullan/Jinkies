#!/usr/bin/env bash
set -euo pipefail

echo "==> Building Jinkies for Linux..."

uv run pyinstaller \
    --onefile \
    --name Jinkies \
    --add-data "sounds:sounds" \
    main.py

echo "==> Creating tarball..."
mkdir -p dist/jinkies-linux-x86_64

cp dist/Jinkies dist/jinkies-linux-x86_64/jinkies

# Bundle the application icon so the installer can place it on the system
if [ -f "assets/icon.png" ]; then
    cp assets/icon.png dist/jinkies-linux-x86_64/jinkies.png
fi

# Generate install script
cat > dist/jinkies-linux-x86_64/install.sh << 'INSTALL_EOF'
#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/usr/local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"
# Standard hicolor icon directory for per-user installation
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"

echo "Installing Jinkies..."
sudo cp jinkies "${INSTALL_DIR}/jinkies"
sudo chmod +x "${INSTALL_DIR}/jinkies"

# Install the application icon if it was bundled with the release
if [ -f "jinkies.png" ]; then
    mkdir -p "${ICON_DIR}"
    cp jinkies.png "${ICON_DIR}/jinkies.png"
fi

mkdir -p "${DESKTOP_DIR}"
cat > "${DESKTOP_DIR}/jinkies.desktop" << 'DESKTOP_EOF'
[Desktop Entry]
Name=Jinkies
Comment=Atom Feed Monitor
Exec=jinkies
Icon=jinkies
Type=Application
Categories=Network;Feed;
StartupWMClass=Jinkies
DESKTOP_EOF

echo "Jinkies installed successfully!"
echo "Run 'jinkies' to start."
INSTALL_EOF

chmod +x dist/jinkies-linux-x86_64/install.sh

cd dist && tar -czf jinkies-linux-x86_64.tar.gz jinkies-linux-x86_64/
echo "==> Done: dist/jinkies-linux-x86_64.tar.gz"
