"""Tests for error-notification rate-limiting in JinkiesApp."""

from __future__ import annotations

from unittest.mock import patch

from src.app import JinkiesApp
from src.models import AppConfig, Feed, FeedEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Return a JinkiesApp with all external dependencies mocked out."""
    mock_config = AppConfig(
        poll_interval_secs=60,
        feeds=[Feed(url="https://example.com/feed", name="Test Feed")],
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
        entry = FeedEntry(
            feed_url="https://example.com/feed",
            title="New post",
            link="https://example.com/1",
            published="2024-01-01T00:00:00Z",
            entry_id="entry-1",
            seen=False,
        )
        app._on_new_entries([entry])

        dashboard.clear_feed_error.assert_called_once_with("https://example.com/feed")

        # Feed breaks again — should notify again
        audio.play.reset_mock()
        notifier.notify.reset_mock()
        app._on_feed_error("https://example.com/feed", "down again")

        audio.play.assert_called_once_with("error")
        notifier.notify.assert_called_once()
