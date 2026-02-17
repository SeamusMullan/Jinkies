"""Jinkies — Atom feed monitor entry point.

Handles path resolution for both frozen (PyInstaller) and
development environments, then launches the application.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    """Launch the Jinkies application.

    Returns:
        The application exit code.
    """
    # Ensure the project root is on sys.path for imports
    if getattr(sys, "frozen", False):
        app_dir = Path(sys._MEIPASS)  # noqa: SLF001
    else:
        app_dir = Path(__file__).resolve().parent

    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    from src.app import run

    return run()


if __name__ == "__main__":
    sys.exit(main())
