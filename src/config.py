"""Platform-aware configuration persistence for Jinkies.

Handles loading and saving application config and state as JSON files,
using platform-appropriate directories.  On load, any legacy plaintext
credentials are migrated to the OS keyring.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.models import AppConfig

logger = logging.getLogger(__name__)


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
        try:
            x = json.load(f)
            return x
        except json.JSONDecodeError as e:
            logger.warning("Corrupted JSON file %s: %s — returning defaults", path, e)
            return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write data to a JSON file.

    Args:
        path: Path to the JSON file.
        data: Data to serialize as JSON.
    """
    _ensure_dir(path.parent)
    #with open(path, "w", encoding="utf-8") as f:
    #    json.dump(data, f, indent=2, ensure_ascii=False)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        os.unlink(tmp_path)
        raise


def _migrate_plaintext_credentials(config: AppConfig, config_dir: Path) -> bool:
    """Migrate any plaintext credentials to the OS keyring.

    If a feed still has ``auth_user`` / ``auth_token`` populated from a
    legacy config file, they are moved into the keyring and the config
    is re-saved without them.

    Args:
        config: The loaded AppConfig (may be mutated).
        config_dir: Config directory for re-saving.

    Returns:
        True if any credentials were migrated.
    """
    from src.credential_store import store_credentials

    migrated = False
    for feed in config.feeds:
        if feed.auth_user and feed.auth_token:
            try:
                store_credentials(feed.url, feed.auth_user, feed.auth_token)
                logger.info("Migrated credentials for %s to keyring", feed.url)
            except ValueError:
                logger.warning(
                    "Skipped credential migration for non-HTTPS feed: %s",
                    feed.url,
                )
            # Clear plaintext regardless so they are never re-saved
            feed.auth_user = None
            feed.auth_token = None
            migrated = True
    return migrated


def load_config(config_dir: Path | None = None) -> AppConfig:
    """Load application configuration from disk.

    On first load after upgrade, any plaintext credentials found in the
    config file are migrated to the OS keyring and the config is
    re-saved without them.

    Args:
        config_dir: Override config directory (for testing).

    Returns:
        The loaded AppConfig, or defaults if no config file exists.
    """
    config_dir = config_dir or get_config_dir()
    data = _read_json(config_dir / "config.json")
    if not data:
        return AppConfig()
    config = AppConfig.from_dict(data)

    # Migrate legacy plaintext credentials
    if _migrate_plaintext_credentials(config, config_dir):
        save_config(config, config_dir)

    return config


def save_config(config: AppConfig, config_dir: Path | None = None) -> None:
    """Save application configuration to disk.

    Args:
        config: The AppConfig to persist.
        config_dir: Override config directory (for testing).
    """
    config_dir = config_dir or get_config_dir()
    _write_json(config_dir / "config.json", config.to_dict())


def load_state(config_dir: Path | None = None, max_age_days: int = 30) -> dict[str, Any]:
    """Load application state (seen entry IDs, stats) from disk.

    Seen IDs older than ``max_age_days`` are pruned from the returned state.
    The ``seen_ids`` value in the returned dict is always a mapping of
    entry-id → ISO 8601 timestamp (when the entry was first seen).

    For backward compatibility, if the persisted ``seen_ids`` is a plain list
    of strings (written by an older version), each ID is treated as seen *now*
    for the purpose of future pruning so they are retained for another
    ``max_age_days`` days from this first upgrade.

    Args:
        config_dir: Override config directory (for testing).
        max_age_days: IDs seen more than this many days ago are discarded.

    Returns:
        State dictionary with 'seen_ids' dict (id → ISO timestamp) and
        optional stats.
    """
    config_dir = config_dir or get_config_dir()
    data = _read_json(config_dir / "state.json")
    raw_seen = data.get("seen_ids", {})

    if isinstance(raw_seen, list):
        # Backward compat: old format was a plain list; treat all as seen now.
        now_iso = datetime.now(UTC).isoformat()
        raw_seen = {entry_id: now_iso for entry_id in raw_seen}
    elif not isinstance(raw_seen, dict):
        # Unexpected type (e.g. null, string) — reset to empty and warn.
        logger.warning(
            "Unexpected type for seen_ids in state.json (%s); resetting to empty.",
            type(raw_seen).__name__,
        )
        raw_seen = {}

    # Prune stale entries
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    pruned: dict[str, str] = {}
    for entry_id, ts in raw_seen.items():
        try:
            seen_at = datetime.fromisoformat(ts)
            # Make timezone-aware if naive (treat naive as UTC)
            if seen_at.tzinfo is None:
                seen_at = seen_at.replace(tzinfo=UTC)
            if seen_at >= cutoff:
                pruned[entry_id] = ts
        except (ValueError, TypeError):
            pass  # Skip entries with invalid timestamps

    data["seen_ids"] = pruned
    return data


def save_state(state: dict[str, Any], config_dir: Path | None = None) -> None:
    """Save application state to disk.

    Args:
        state: State dictionary to persist.
        config_dir: Override config directory (for testing).
    """
    config_dir = config_dir or get_config_dir()
    _write_json(config_dir / "state.json", state)
