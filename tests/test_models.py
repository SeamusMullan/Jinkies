"""Tests for src.models data classes."""

from __future__ import annotations

from src.models import AppConfig, Feed, FeedEntry


class TestFeed:
    def test_to_dict(self, sample_feed):
        d = sample_feed.to_dict()
        assert d["url"] == "https://example.com/feed.atom"
        assert d["name"] == "Example Feed"
        assert d["enabled"] is True
        assert d["sound_file"] is None
        assert d["last_poll_time"] is None

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

    def test_roundtrip(self, sample_config):
        restored = AppConfig.from_dict(sample_config.to_dict())
        assert restored.poll_interval_secs == sample_config.poll_interval_secs
        assert len(restored.feeds) == len(sample_config.feeds)
