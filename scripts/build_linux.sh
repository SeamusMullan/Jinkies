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

# Generate install script
cat > dist/jinkies-linux-x86_64/install.sh << 'INSTALL_EOF'
#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/usr/local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"

echo "Installing Jinkies..."
sudo cp jinkies "${INSTALL_DIR}/jinkies"
sudo chmod +x "${INSTALL_DIR}/jinkies"

mkdir -p "${DESKTOP_DIR}"
cat > "${DESKTOP_DIR}/jinkies.desktop" << 'DESKTOP_EOF'
[Desktop Entry]
Name=Jinkies
Comment=Atom Feed Monitor
Exec=jinkies
Type=Application
Categories=Network;Feed;
DESKTOP_EOF

echo "Jinkies installed successfully!"
echo "Run 'jinkies' to start."
INSTALL_EOF

chmod +x dist/jinkies-linux-x86_64/install.sh

cd dist && tar -czf jinkies-linux-x86_64.tar.gz jinkies-linux-x86_64/
echo "==> Done: dist/jinkies-linux-x86_64.tar.gz"
