"""Shared fixtures for Jinkies tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.models import AppConfig, Feed, FeedEntry


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Provide a temporary config directory."""
    config_dir = tmp_path / "jinkies_config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def tmp_sounds_dir(tmp_path):
    """Provide a temporary sounds directory."""
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir()
    return sounds_dir


@pytest.fixture
def sample_feed():
    """Provide a sample Feed object."""
    return Feed(
        url="https://example.com/feed.atom",
        name="Example Feed",
        enabled=True,
    )


@pytest.fixture
def sample_entry():
    """Provide a sample FeedEntry object."""
    return FeedEntry(
        feed_url="https://example.com/feed.atom",
        title="Test Entry",
        link="https://example.com/entry/1",
        published="2024-01-01T00:00:00Z",
        entry_id="entry-1",
        seen=False,
    )


@pytest.fixture
def sample_config(sample_feed):
    """Provide a sample AppConfig."""
    return AppConfig(
        poll_interval_secs=120,
        feeds=[sample_feed],
        sound_map={"new_entry": "new_entry.wav", "error": "error.wav"},
    )


@pytest.fixture
def mock_feedparser_result():
    """Provide a mock feedparser result with sample entries."""
    entry1 = MagicMock()
    entry1.get = lambda key, default="": {
        "id": "entry-1",
        "title": "First Entry",
        "link": "https://example.com/1",
        "published": "2024-01-01T00:00:00Z",
    }.get(key, default)

    entry2 = MagicMock()
    entry2.get = lambda key, default="": {
        "id": "entry-2",
        "title": "Second Entry",
        "link": "https://example.com/2",
        "published": "2024-01-02T00:00:00Z",
    }.get(key, default)

    result = MagicMock()
    result.bozo = False
    result.entries = [entry1, entry2]
    return result
