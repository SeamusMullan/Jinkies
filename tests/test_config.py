"""Tests for src.config persistence functions."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import get_config_dir, load_config, load_state, save_config, save_state
from src.models import AppConfig


_FAKE_HOME = Path("/fake/home")


class TestGetConfigDir:
    """Tests for platform-specific path construction in get_config_dir."""

    @pytest.mark.parametrize(
        ("platform", "expected"),
        [
            ("linux", _FAKE_HOME / ".config" / "jinkies"),
            ("darwin", _FAKE_HOME / "Library" / "Application Support" / "jinkies"),
            ("win32", _FAKE_HOME / "AppData" / "Roaming" / "jinkies"),
        ],
    )
    def test_platform_specific_paths(self, platform, expected):
        """get_config_dir returns the correct path for each supported platform."""
        with patch("sys.platform", platform), patch("src.config.Path.home", return_value=_FAKE_HOME):
            result = get_config_dir()
        assert result == expected

    def test_unsupported_platform_raises(self):
        """get_config_dir raises RuntimeError for unsupported platforms."""
        with patch("sys.platform", "freebsd"), pytest.raises(RuntimeError, match="Unsupported platform"):
            get_config_dir()


class TestConfig:
    def test_corrupted_config_json_returns_defaults(self, tmp_config_dir, caplog):
        """Corrupted config.json should log a warning and return default AppConfig."""
        (tmp_config_dir / "config.json").write_text("{not valid json!!!", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="src.config"):
            config = load_config(tmp_config_dir)
        assert isinstance(config, AppConfig)
        assert config.feeds == []
        assert any("Corrupted" in m for m in caplog.messages)

    def test_load_config_missing_file(self, tmp_config_dir):
        config = load_config(tmp_config_dir)
        assert isinstance(config, AppConfig)
        assert config.poll_interval_secs == 60
        assert config.feeds == []

    def test_save_and_load_config(self, tmp_config_dir, sample_config):
        save_config(sample_config, tmp_config_dir)
        loaded = load_config(tmp_config_dir)
        assert loaded.poll_interval_secs == sample_config.poll_interval_secs
        assert len(loaded.feeds) == 1
        assert loaded.feeds[0].url == "https://example.com/feed.atom"

    def test_config_json_readable(self, tmp_config_dir, sample_config):
        save_config(sample_config, tmp_config_dir)
        with open(tmp_config_dir / "config.json") as f:
            data = json.load(f)
        assert data["poll_interval_secs"] == 120

    def test_save_creates_directory(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "dir"
        config = AppConfig()
        save_config(config, nested)
        assert (nested / "config.json").exists()

    def test_config_json_no_plaintext_credentials(self, tmp_config_dir, sample_config):
        """Saved config must never contain auth_user or auth_token."""
        save_config(sample_config, tmp_config_dir)
        with open(tmp_config_dir / "config.json") as f:
            data = json.load(f)
        feed_data = data["feeds"][0]
        assert "auth_user" not in feed_data
        assert "auth_token" not in feed_data
        assert "has_auth" in feed_data


class TestCredentialMigration:
    """Tests for migrating plaintext credentials to the keyring on load."""

    @patch("src.credential_store.store_credentials")
    def test_migrate_plaintext_to_keyring(self, mock_store, tmp_config_dir):
        """Legacy plaintext creds should be migrated to keyring on load."""
        legacy_data = {
            "poll_interval_secs": 60,
            "feeds": [
                {
                    "url": "https://example.com/feed",
                    "name": "Test Feed",
                    "auth_user": "admin",
                    "auth_token": "secret123",
                }
            ],
        }
        with open(tmp_config_dir / "config.json", "w") as f:
            json.dump(legacy_data, f)

        config = load_config(tmp_config_dir)

        # Credentials should have been stored in keyring
        mock_store.assert_called_once_with(
            "https://example.com/feed", "admin", "secret123",
        )

        # Feed object should no longer have plaintext creds
        assert config.feeds[0].auth_user is None
        assert config.feeds[0].auth_token is None

        # Config file should have been re-saved without plaintext creds
        with open(tmp_config_dir / "config.json") as f:
            saved = json.load(f)
        assert "auth_user" not in saved["feeds"][0]
        assert "auth_token" not in saved["feeds"][0]

    @patch("src.credential_store.store_credentials")
    def test_migrate_skips_http_feeds(self, mock_store, tmp_config_dir):
        """Plaintext creds for HTTP feeds should be cleared but not stored."""
        mock_store.side_effect = ValueError("non-HTTPS")
        legacy_data = {
            "poll_interval_secs": 60,
            "feeds": [
                {
                    "url": "http://insecure.example.com/feed",
                    "name": "Insecure Feed",
                    "auth_user": "admin",
                    "auth_token": "secret",
                }
            ],
        }
        with open(tmp_config_dir / "config.json", "w") as f:
            json.dump(legacy_data, f)

        config = load_config(tmp_config_dir)

        # Credentials should have been cleared even though migration failed
        assert config.feeds[0].auth_user is None
        assert config.feeds[0].auth_token is None

    def test_no_migration_needed(self, tmp_config_dir):
        """Config without plaintext creds should load without migration."""
        data = {
            "poll_interval_secs": 60,
            "feeds": [
                {
                    "url": "https://example.com/feed",
                    "name": "Test Feed",
                    "has_auth": True,
                }
            ],
        }
        with open(tmp_config_dir / "config.json", "w") as f:
            json.dump(data, f)

        config = load_config(tmp_config_dir)
        assert config.feeds[0].auth_user is None
        assert config.feeds[0].auth_token is None


class TestState:
    def test_corrupted_state_json_returns_defaults(self, tmp_config_dir, caplog):
        """Corrupted state.json should log a warning and return state with empty seen_ids."""
        (tmp_config_dir / "state.json").write_text("{not valid json!!!", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="src.config"):
            state = load_state(tmp_config_dir)
        assert "seen_ids" in state
        assert state["seen_ids"] == {}
        assert any("Corrupted" in m for m in caplog.messages)

    def test_load_state_missing_file(self, tmp_config_dir):
        state = load_state(tmp_config_dir)
        assert "seen_ids" in state
        assert state["seen_ids"] == {}

    def test_save_and_load_state_dict_format(self, tmp_config_dir):
        """Saving seen_ids as a dict (new format) round-trips correctly."""
        now_iso = datetime.now(UTC).isoformat()
        state = {"seen_ids": {"id1": now_iso, "id2": now_iso}}
        save_state(state, tmp_config_dir)
        loaded = load_state(tmp_config_dir)
        assert set(loaded["seen_ids"].keys()) == {"id1", "id2"}

    def test_load_state_backward_compat_list_format(self, tmp_config_dir):
        """Old list format is migrated to dict with current timestamps."""
        state = {"seen_ids": ["id1", "id2", "id3"]}
        save_state(state, tmp_config_dir)
        loaded = load_state(tmp_config_dir)
        assert isinstance(loaded["seen_ids"], dict)
        assert set(loaded["seen_ids"].keys()) == {"id1", "id2", "id3"}
        # All timestamps should be recent (within the last minute)
        cutoff = datetime.now(UTC) - timedelta(minutes=1)
        for ts in loaded["seen_ids"].values():
            assert datetime.fromisoformat(ts) >= cutoff

    def test_load_state_prunes_old_entries(self, tmp_config_dir):
        """Entries older than max_age_days are pruned on load."""
        old_ts = (datetime.now(UTC) - timedelta(days=40)).isoformat()
        recent_ts = datetime.now(UTC).isoformat()
        state = {"seen_ids": {"old-id": old_ts, "new-id": recent_ts}}
        save_state(state, tmp_config_dir)
        loaded = load_state(tmp_config_dir, max_age_days=30)
        assert "old-id" not in loaded["seen_ids"]
        assert "new-id" in loaded["seen_ids"]

    def test_load_state_keeps_entries_within_retention(self, tmp_config_dir):
        """Entries within max_age_days are retained on load."""
        recent_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        state = {"seen_ids": {"id1": recent_ts}}
        save_state(state, tmp_config_dir)
        loaded = load_state(tmp_config_dir, max_age_days=30)
        assert "id1" in loaded["seen_ids"]

    def test_load_state_entries_with_invalid_timestamps_skipped(self, tmp_config_dir):
        """Entries with unparseable timestamps are silently dropped."""
        good_ts = datetime.now(UTC).isoformat()
        state = {"seen_ids": {"bad-ts-id": "not-a-timestamp", "good-id": good_ts}}
        save_state(state, tmp_config_dir)
        loaded = load_state(tmp_config_dir)
        assert "bad-ts-id" not in loaded["seen_ids"]
        assert "good-id" in loaded["seen_ids"]

    def test_load_state_invalid_seen_ids_type_reset_to_empty(self, tmp_config_dir):
        """Unexpected seen_ids types (null, string, int) are reset to empty dict."""
        import json

        state_file = tmp_config_dir / "state.json"
        for bad_value in [None, "string", 42]:
            state_file.write_text(json.dumps({"seen_ids": bad_value}))
            loaded = load_state(tmp_config_dir)
            assert loaded["seen_ids"] == {}, f"Expected empty dict for seen_ids={bad_value!r}"

    def test_state_preserves_extra_fields(self, tmp_config_dir):
        now_iso = datetime.now(UTC).isoformat()
        state = {"seen_ids": {"id1": now_iso}, "errors_today": 5}
        save_state(state, tmp_config_dir)
        loaded = load_state(tmp_config_dir)
        assert loaded["errors_today"] == 5
