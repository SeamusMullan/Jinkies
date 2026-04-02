"""Tests for error-notification rate-limiting in JinkiesApp."""

from __future__ import annotations

from unittest.mock import patch

from src.app import JinkiesApp
from src.models import AppConfig, Feed, FeedEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(feeds=None):
    """Return a JinkiesApp with all external dependencies mocked out.

    Args:
        feeds: Optional list of Feed objects to include in the config.
            Defaults to a single feed with no custom sound.
    """
    if feeds is None:
        feeds = [Feed(url="https://example.com/feed", name="Test Feed")]

    mock_config = AppConfig(
        poll_interval_secs=60,
        feeds=feeds,
        sound_map={"new_entry": "new_entry.wav", "error": "error.wav"},
    )

    patches = [
        patch("src.app.load_config", return_value=mock_config),
        patch("src.app.load_state", return_value={}),
        patch("src.app.save_state"),
        patch("src.app.ensure_default_sounds"),
        patch("src.app.QApplication"),
        patch("src.app.QSystemTrayIcon"),
        patch("src.app.AudioPlayer"),
        patch("src.app.Notifier"),
        patch("src.app.Dashboard"),
        patch("src.app.FeedPoller"),
        patch("src.app._get_icon_path", return_value=""),
    ]

    for p in patches:
        p.start()

    app = JinkiesApp()

    # Stop patches after construction so they don't interfere with assertions
    for p in patches:
        p.stop()

    # Return both the app and the relevant mocks for assertions
    audio_mock = app.audio
    notifier_mock = app.notifier
    dashboard_mock = app.dashboard

    return app, audio_mock, notifier_mock, dashboard_mock


def _make_entry(feed_url="https://example.com/feed", entry_id="entry-1"):
    """Create a minimal FeedEntry for testing."""
    return FeedEntry(
        feed_url=feed_url,
        title="Test Entry",
        link=f"{feed_url}/1",
        published="2024-01-01T00:00:00Z",
        entry_id=entry_id,
        seen=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFeedErrorRateLimiting:
    """_on_feed_error should only notify on first error per feed URL."""

    def test_first_error_notifies(self, qtbot):
        app, audio, notifier, dashboard = _make_app()

        app._on_feed_error("https://example.com/feed", "connection refused")

        audio.play.assert_called_once_with("error")
        notifier.notify.assert_called_once()
        dashboard.record_error.assert_called_once()
        dashboard.mark_feed_error.assert_called_once_with(
            "https://example.com/feed", "connection refused"
        )

    def test_second_error_silent(self, qtbot):
        app, audio, notifier, dashboard = _make_app()

        app._on_feed_error("https://example.com/feed", "connection refused")
        audio.play.reset_mock()
        notifier.notify.reset_mock()
        dashboard.record_error.reset_mock()
        dashboard.mark_feed_error.reset_mock()

        app._on_feed_error("https://example.com/feed", "still down")

        audio.play.assert_not_called()
        notifier.notify.assert_not_called()
        # Dashboard counter and error marking should still be updated every time
        dashboard.record_error.assert_called_once()
        dashboard.mark_feed_error.assert_called_once_with(
            "https://example.com/feed", "still down"
        )

    def test_different_feeds_each_notify_once(self, qtbot):
        app, audio, notifier, dashboard = _make_app()

        app._on_feed_error("https://a.com/feed", "error A")
        app._on_feed_error("https://b.com/feed", "error B")

        assert audio.play.call_count == 2
        assert notifier.notify.call_count == 2

    def test_recovery_clears_error_state(self, qtbot):
        """After new entries arrive the next error should notify again."""
        app, audio, notifier, dashboard = _make_app()

        # First error — notifies
        app._on_feed_error("https://example.com/feed", "down")
        assert audio.play.call_count == 1

        # Feed recovers: new entry arrives
        entry = _make_entry()
        app._on_new_entries([entry])

        dashboard.clear_feed_error.assert_called_once_with("https://example.com/feed")

        # Feed breaks again — should notify again
        audio.play.reset_mock()
        notifier.notify.reset_mock()
        app._on_feed_error("https://example.com/feed", "down again")

        audio.play.assert_called_once_with("error")
        notifier.notify.assert_called_once()


class TestPerFeedSoundOverride:
    """Per-feed sound_file overrides should be used when set."""

    def test_new_entry_uses_default_when_no_override(self, qtbot):
        """play('new_entry') is called when the feed has no sound_file."""
        app, audio, notifier, dashboard = _make_app()

        app._on_new_entries([_make_entry()])

        audio.play.assert_called_once_with("new_entry")
        audio.play_file.assert_not_called()

    def test_new_entry_uses_feed_sound_file(self, qtbot):
        """play_file is called with the feed's sound_file when set."""
        feeds = [Feed(
            url="https://example.com/feed",
            name="Custom Sound Feed",
            sound_file="custom.wav",
        )]
        app, audio, notifier, dashboard = _make_app(feeds=feeds)

        app._on_new_entries([_make_entry()])

        audio.play_file.assert_called_once_with("custom.wav")
        audio.play.assert_not_called()

    def test_multi_feed_batch_uses_default_sound(self, qtbot):
        """When entries span multiple feeds, the global default is used."""
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A", sound_file="a.wav"),
            Feed(url="https://b.com/feed", name="Feed B", sound_file="b.wav"),
        ]
        app, audio, notifier, dashboard = _make_app(feeds=feeds)

        entries = [
            _make_entry(feed_url="https://a.com/feed", entry_id="entry-a"),
            _make_entry(feed_url="https://b.com/feed", entry_id="entry-b"),
        ]
        app._on_new_entries(entries)

        audio.play.assert_called_once_with("new_entry")
        audio.play_file.assert_not_called()

    def test_feed_error_uses_feed_sound_file(self, qtbot):
        """play_file is called with the feed's sound_file on an error."""
        feeds = [Feed(
            url="https://example.com/feed",
            name="Custom Sound Feed",
            sound_file="custom_error.wav",
        )]
        app, audio, notifier, dashboard = _make_app(feeds=feeds)

        app._on_feed_error("https://example.com/feed", "timeout")

        audio.play_file.assert_called_once_with("custom_error.wav")
        audio.play.assert_not_called()

    def test_feed_error_uses_default_when_no_override(self, qtbot):
        """play('error') is called when the feed has no sound_file."""
        app, audio, notifier, dashboard = _make_app()

        app._on_feed_error("https://example.com/feed", "timeout")

        audio.play.assert_called_once_with("error")
        audio.play_file.assert_not_called()

    def test_unknown_feed_url_uses_default_error_sound(self, qtbot):
        """play('error') is used when the erroring URL is not in the config."""
        app, audio, notifier, dashboard = _make_app()

        app._on_feed_error("https://unknown.com/feed", "timeout")

        audio.play.assert_called_once_with("error")
        audio.play_file.assert_not_called()

    def test_get_feed_by_url_returns_feed(self, qtbot):
        """_get_feed_by_url returns the correct Feed for a known URL."""
        app, *_ = _make_app()
        feed = app._get_feed_by_url("https://example.com/feed")
        assert feed is not None
        assert feed.url == "https://example.com/feed"

    def test_get_feed_by_url_returns_none_for_unknown(self, qtbot):
        """_get_feed_by_url returns None for an unknown URL."""
        app, *_ = _make_app()
        assert app._get_feed_by_url("https://not-configured.com/feed") is None
