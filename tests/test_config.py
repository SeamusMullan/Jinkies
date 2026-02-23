"""Tests for src.config persistence functions."""

from __future__ import annotations

import json
from unittest.mock import patch

from src.config import load_config, load_state, save_config, save_state
from src.models import AppConfig


class TestConfig:
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
    def test_load_state_missing_file(self, tmp_config_dir):
        state = load_state(tmp_config_dir)
        assert "seen_ids" in state
        assert state["seen_ids"] == []

    def test_save_and_load_state(self, tmp_config_dir):
        state = {"seen_ids": ["id1", "id2", "id3"]}
        save_state(state, tmp_config_dir)
        loaded = load_state(tmp_config_dir)
        assert loaded["seen_ids"] == ["id1", "id2", "id3"]

    def test_state_preserves_extra_fields(self, tmp_config_dir):
        state = {"seen_ids": ["id1"], "errors_today": 5}
        save_state(state, tmp_config_dir)
        loaded = load_state(tmp_config_dir)
        assert loaded["errors_today"] == 5
