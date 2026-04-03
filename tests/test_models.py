"""Tests for src.models data classes."""

from __future__ import annotations

import logging

from src.models import AppConfig, Feed, FeedEntry


class TestFeed:
    def test_to_dict(self, sample_feed):
        d = sample_feed.to_dict()
        assert d["url"] == "https://example.com/feed.atom"
        assert d["name"] == "Example Feed"
        assert d["enabled"] is True
        assert d["sound_file"] is None
        assert d["last_poll_time"] is None

    def test_to_dict_no_plaintext_credentials(self):
        """to_dict must never include auth_user or auth_token."""
        feed = Feed(
            url="https://example.com/feed",
            name="Auth Feed",
            auth_user="admin",
            auth_token="secret",
        )
        d = feed.to_dict()
        assert "auth_user" not in d
        assert "auth_token" not in d
        assert d["has_auth"] is True

    def test_to_dict_has_auth_false_when_no_creds(self, sample_feed):
        """has_auth should be False when no credentials are set."""
        d = sample_feed.to_dict()
        assert d["has_auth"] is False

    def test_from_dict(self):
        data = {
            "url": "https://test.com/feed",
            "name": "Test",
            "enabled": False,
            "sound_file": "custom.wav",
        }
        feed = Feed.from_dict(data)
        assert feed.url == "https://test.com/feed"
        assert feed.name == "Test"
        assert feed.enabled is False
        assert feed.sound_file == "custom.wav"

    def test_from_dict_defaults(self):
        data = {"url": "https://test.com/feed", "name": "Test"}
        feed = Feed.from_dict(data)
        assert feed.enabled is True
        assert feed.sound_file is None

    def test_from_dict_legacy_plaintext_credentials(self):
        """from_dict should still read legacy auth_user/auth_token for migration."""
        data = {
            "url": "https://test.com/feed",
            "name": "Test",
            "auth_user": "admin",
            "auth_token": "secret",
        }
        feed = Feed.from_dict(data)
        assert feed.auth_user == "admin"
        assert feed.auth_token == "secret"

    def test_roundtrip(self, sample_feed):
        restored = Feed.from_dict(sample_feed.to_dict())
        assert restored.url == sample_feed.url
        assert restored.name == sample_feed.name
        assert restored.enabled == sample_feed.enabled


class TestFeedEntry:
    def test_to_dict(self, sample_entry):
        d = sample_entry.to_dict()
        assert d["entry_id"] == "entry-1"
        assert d["title"] == "Test Entry"
        assert d["seen"] is False

    def test_from_dict(self):
        data = {
            "feed_url": "https://example.com/feed",
            "title": "Entry",
            "link": "https://example.com/1",
            "published": "2024-01-01",
            "entry_id": "e1",
            "seen": True,
        }
        entry = FeedEntry.from_dict(data)
        assert entry.entry_id == "e1"
        assert entry.seen is True

    def test_roundtrip(self, sample_entry):
        restored = FeedEntry.from_dict(sample_entry.to_dict())
        assert restored.entry_id == sample_entry.entry_id
        assert restored.title == sample_entry.title


class TestAppConfig:
    def test_defaults(self):
        config = AppConfig()
        assert config.poll_interval_secs == 60
        assert config.feeds == []
        assert "new_entry" in config.sound_map

    def test_to_dict(self, sample_config):
        d = sample_config.to_dict()
        assert d["poll_interval_secs"] == 120
        assert len(d["feeds"]) == 1
        assert d["feeds"][0]["name"] == "Example Feed"

    def test_from_dict(self):
        data = {
            "poll_interval_secs": 90,
            "feeds": [{"url": "https://test.com", "name": "T"}],
            "sound_map": {"new_entry": "beep.wav"},
            "notification_style": "custom",
        }
        config = AppConfig.from_dict(data)
        assert config.poll_interval_secs == 90
        assert len(config.feeds) == 1
        assert config.notification_style == "custom"

    def test_from_dict_poll_interval_zero_clamped(self, caplog):
        """poll_interval_secs of 0 should be clamped to 1 with a warning."""
        with caplog.at_level(logging.WARNING, logger="src.models"):
            config = AppConfig.from_dict({"poll_interval_secs": 0})
        assert config.poll_interval_secs == 1
        assert "poll_interval_secs" in caplog.text

    def test_from_dict_poll_interval_negative_clamped(self, caplog):
        """Negative poll_interval_secs should be clamped to 1 with a warning."""
        with caplog.at_level(logging.WARNING, logger="src.models"):
            config = AppConfig.from_dict({"poll_interval_secs": -5})
        assert config.poll_interval_secs == 1
        assert "poll_interval_secs" in caplog.text

    def test_from_dict_invalid_notification_style_falls_back(self, caplog):
        """An unknown notification_style should fall back to 'native' with a warning."""
        with caplog.at_level(logging.WARNING, logger="src.models"):
            config = AppConfig.from_dict({"notification_style": "toast"})
        assert config.notification_style == "native"
        assert "notification_style" in caplog.text

    def test_from_dict_valid_notification_styles_accepted(self):
        """Both 'native' and 'custom' should be accepted without warnings."""
        for style in ("native", "custom"):
            config = AppConfig.from_dict({"notification_style": style})
            assert config.notification_style == style

    def test_roundtrip(self, sample_config):
        restored = AppConfig.from_dict(sample_config.to_dict())
        assert restored.poll_interval_secs == sample_config.poll_interval_secs
        assert len(restored.feeds) == len(sample_config.feeds)

    def test_default_max_entries(self):
        """AppConfig should default max_entries to 10,000."""
        config = AppConfig()
        assert config.max_entries == 10_000

    def test_to_dict_includes_max_entries(self):
        """to_dict should include max_entries."""
        config = AppConfig(max_entries=500)
        d = config.to_dict()
        assert d["max_entries"] == 500

    def test_from_dict_max_entries(self):
        """from_dict should read max_entries from the data."""
        config = AppConfig.from_dict({"max_entries": 250})
        assert config.max_entries == 250

    def test_from_dict_max_entries_default_when_absent(self):
        """from_dict should default max_entries to 10,000 when absent."""
        config = AppConfig.from_dict({})
        assert config.max_entries == 10_000

    def test_from_dict_max_entries_zero_clamped(self, caplog):
        """max_entries of 0 should be clamped to 1 with a warning."""
        with caplog.at_level(logging.WARNING, logger="src.models"):
            config = AppConfig.from_dict({"max_entries": 0})
        assert config.max_entries == 1
        assert "max_entries" in caplog.text

    def test_from_dict_max_entries_negative_clamped(self, caplog):
        """Negative max_entries should be clamped to 1 with a warning."""
        with caplog.at_level(logging.WARNING, logger="src.models"):
            config = AppConfig.from_dict({"max_entries": -100})
        assert config.max_entries == 1
        assert "max_entries" in caplog.text

    def test_default_seen_ids_max_age_days(self):
        """AppConfig should default seen_ids_max_age_days to 30."""
        config = AppConfig()
        assert config.seen_ids_max_age_days == 30

    def test_to_dict_includes_seen_ids_max_age_days(self):
        """to_dict should include seen_ids_max_age_days."""
        config = AppConfig(seen_ids_max_age_days=60)
        d = config.to_dict()
        assert d["seen_ids_max_age_days"] == 60

    def test_from_dict_seen_ids_max_age_days(self):
        """from_dict should read seen_ids_max_age_days from the data."""
        config = AppConfig.from_dict({"seen_ids_max_age_days": 90})
        assert config.seen_ids_max_age_days == 90

    def test_from_dict_seen_ids_max_age_days_default_when_absent(self):
        """from_dict should default seen_ids_max_age_days to 30 when absent."""
        config = AppConfig.from_dict({})
        assert config.seen_ids_max_age_days == 30

    def test_from_dict_seen_ids_max_age_days_zero_clamped(self, caplog):
        """seen_ids_max_age_days of 0 should be clamped to 1 with a warning."""
        with caplog.at_level(logging.WARNING, logger="src.models"):
            config = AppConfig.from_dict({"seen_ids_max_age_days": 0})
        assert config.seen_ids_max_age_days == 1
        assert "seen_ids_max_age_days" in caplog.text

    def test_from_dict_seen_ids_max_age_days_negative_clamped(self, caplog):
        """Negative seen_ids_max_age_days should be clamped to 1 with a warning."""
        with caplog.at_level(logging.WARNING, logger="src.models"):
            config = AppConfig.from_dict({"seen_ids_max_age_days": -5})
        assert config.seen_ids_max_age_days == 1
        assert "seen_ids_max_age_days" in caplog.text
