"""Platform-aware configuration persistence for Jinkies.

Handles loading and saving application config and state as JSON files,
using platform-appropriate directories.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from src.models import AppConfig


def get_config_dir() -> Path:
    """Get the platform-specific configuration directory.

    Returns:
        Path to the jinkies config directory.

    Raises:
        RuntimeError: If the platform is not supported.
    """
    if sys.platform == "linux":
        base = Path.home() / ".config"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        appdata = Path.home() / "AppData" / "Roaming"
        base = appdata
    else:
        msg = f"Unsupported platform: {sys.platform}"
        raise RuntimeError(msg)
    return base / "jinkies"


def _ensure_dir(path: Path) -> None:
    """Create directory if it doesn't exist.

    Args:
        path: Directory path to ensure exists.
    """
    path.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON file and return its contents.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON data, or empty dict if file doesn't exist.
    """
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write data to a JSON file.

    Args:
        path: Path to the JSON file.
        data: Data to serialize as JSON.
    """
    _ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_config(config_dir: Path | None = None) -> AppConfig:
    """Load application configuration from disk.

    Args:
        config_dir: Override config directory (for testing).

    Returns:
        The loaded AppConfig, or defaults if no config file exists.
    """
    config_dir = config_dir or get_config_dir()
    data = _read_json(config_dir / "config.json")
    if not data:
        return AppConfig()
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, config_dir: Path | None = None) -> None:
    """Save application configuration to disk.

    Args:
        config: The AppConfig to persist.
        config_dir: Override config directory (for testing).
    """
    config_dir = config_dir or get_config_dir()
    _write_json(config_dir / "config.json", config.to_dict())


def load_state(config_dir: Path | None = None) -> dict[str, Any]:
    """Load application state (seen entry IDs, stats) from disk.

    Args:
        config_dir: Override config directory (for testing).

    Returns:
        State dictionary with 'seen_ids' list and optional stats.
    """
    config_dir = config_dir or get_config_dir()
    data = _read_json(config_dir / "state.json")
    if "seen_ids" not in data:
        data["seen_ids"] = []
    return data


def save_state(state: dict[str, Any], config_dir: Path | None = None) -> None:
    """Save application state to disk.

    Args:
        state: State dictionary to persist.
        config_dir: Override config directory (for testing).
    """
    config_dir = config_dir or get_config_dir()
    _write_json(config_dir / "state.json", state)
