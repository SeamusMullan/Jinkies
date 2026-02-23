#!/usr/bin/env bash
# Setup a venv for the mgmt report scripts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ -d "$VENV_DIR" ]; then
    echo "venv already exists at $VENV_DIR"
else
    echo "Creating venv..."
    python3 -m venv "$VENV_DIR"
    echo "Installing dependencies..."
    "$VENV_DIR/bin/pip" install --quiet fpdf2 openpyxl
    echo "Done. venv created at $VENV_DIR"
fi

echo ""
echo "Usage:"
echo "  $VENV_DIR/bin/python $SCRIPT_DIR/gen_issues_pdf.py"
echo "  $VENV_DIR/bin/python $SCRIPT_DIR/gen_issues_xlsx.py"
