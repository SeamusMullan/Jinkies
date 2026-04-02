"""Tests for JinkiesApp – startup, teardown, signal wiring, and event handlers.

Coverage targets:
- JinkiesApp.__init__ (component wiring, signal connections)
- _quit / run (shutdown and application lifecycle)
- _on_new_entries (single and multiple entry notification formatting)
- _on_poll_complete / _on_poll_time_updated
- _on_pause_toggle
- _toggle_window / _on_tray_activated
- _apply_config_changes
- _on_add_feed / _on_settings / _on_remove_feed / _on_import_feeds
- _get_icon_path
- Module-level run() entry point
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QDialog, QMessageBox, QSystemTrayIcon

from src.app import JinkiesApp, _get_icon_path
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


# ---------------------------------------------------------------------------
# Helpers shared by the new test classes below
# ---------------------------------------------------------------------------

def _make_entry(
    feed_url: str = "https://example.com/feed",
    title: str = "Test Entry",
    link: str = "https://example.com/1",
    entry_id: str = "entry-1",
) -> FeedEntry:
    """Return a minimal FeedEntry suitable for use in tests."""
    return FeedEntry(
        feed_url=feed_url,
        title=title,
        link=link,
        published="2024-01-01T00:00:00Z",
        entry_id=entry_id,
        seen=False,
    )


# ---------------------------------------------------------------------------
# Startup / initialisation
# ---------------------------------------------------------------------------


class TestJinkiesAppInit:
    """JinkiesApp.__init__ wires up all subsystems correctly."""

    def test_poller_starts_on_init(self, qtbot):
        """FeedPoller.start() is called during construction."""
        app, _, _, _ = _make_app()
        app.poller.start.assert_called_once()

    def test_all_poller_signals_connected(self, qtbot):
        """All four FeedPoller signals are connected to the right handlers."""
        app, _, _, _ = _make_app()
        app.poller.new_entries_found.connect.assert_called_once_with(app._on_new_entries)
        app.poller.feed_error.connect.assert_called_once_with(app._on_feed_error)
        app.poller.poll_complete.connect.assert_called_once_with(app._on_poll_complete)
        app.poller.poll_time_updated.connect.assert_called_once_with(
            app._on_poll_time_updated
        )

    def test_dashboard_signals_connected(self, qtbot):
        """Dashboard signals are wired to the corresponding handlers."""
        app, _, _, dashboard = _make_app()
        dashboard.add_feed_requested.connect.assert_called_once_with(app._on_add_feed)
        dashboard.remove_feed_requested.connect.assert_called_once_with(
            app._on_remove_feed
        )
        dashboard.import_feeds_requested.connect.assert_called_once_with(
            app._on_import_feeds
        )
        dashboard.settings_requested.connect.assert_called_once_with(app._on_settings)
        dashboard.pause_requested.connect.assert_called_once_with(app._on_pause_toggle)

    def test_seen_ids_loaded_from_persisted_state(self, qtbot):
        """_seen_ids is pre-populated with IDs stored in the state file."""
        mock_config = AppConfig(
            poll_interval_secs=60,
            feeds=[Feed(url="https://example.com/feed", name="Test Feed")],
            sound_map={"new_entry": "new_entry.wav", "error": "error.wav"},
        )
        patches = [
            patch("src.app.load_config", return_value=mock_config),
            patch("src.app.load_state", return_value={"seen_ids": ["id-1", "id-2"]}),
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
        try:
            app = JinkiesApp()
        finally:
            for p in patches:
                p.stop()

        assert app._seen_ids == {"id-1", "id-2"}

    def test_empty_state_gives_empty_seen_ids(self, qtbot):
        """When no state exists, _seen_ids starts as an empty set."""
        app, _, _, _ = _make_app()
        assert app._seen_ids == set()

    def test_errored_feeds_starts_empty(self, qtbot):
        """_errored_feeds is empty at startup."""
        app, _, _, _ = _make_app()
        assert app._errored_feeds == set()


# ---------------------------------------------------------------------------
# Shutdown / teardown
# ---------------------------------------------------------------------------


class TestJinkiesAppTeardown:
    """JinkiesApp._quit and run() cover the application lifecycle."""

    def test_quit_saves_state_before_stopping_poller(self, qtbot):
        """State is persisted before the poller is asked to stop."""
        app, _, _, _ = _make_app()
        call_order: list[str] = []

        with patch("src.app.save_state", side_effect=lambda *_: call_order.append("save")):
            app.poller.requestInterruption.side_effect = lambda: call_order.append(
                "interrupt"
            )
            app._quit()

        assert call_order.index("save") < call_order.index("interrupt")

    def test_quit_resumes_paused_poller(self, qtbot):
        """_quit unblocks a paused poller so it can exit promptly."""
        app, _, _, _ = _make_app()
        with patch("src.app.save_state"):
            app._quit()
        app.poller.resume.assert_called()

    def test_quit_waits_for_poller_thread(self, qtbot):
        """_quit waits up to 5 s for the poller thread to finish."""
        app, _, _, _ = _make_app()
        with patch("src.app.save_state"):
            app._quit()
        app.poller.wait.assert_called_once_with(5000)

    def test_quit_hides_tray_icon(self, qtbot):
        """The system tray icon is hidden on quit."""
        app, _, _, _ = _make_app()
        with patch("src.app.save_state"):
            app._quit()
        app._tray.hide.assert_called_once()

    def test_quit_calls_app_quit(self, qtbot):
        """QApplication.quit() is invoked to end the event loop."""
        app, _, _, _ = _make_app()
        with patch("src.app.save_state"):
            app._quit()
        app.app.quit.assert_called_once()

    def test_run_shows_dashboard_and_starts_loop(self, qtbot):
        """run() shows the dashboard then calls QApplication.exec()."""
        app, _, _, dashboard = _make_app()
        app.app.exec.return_value = 0
        result = app.run()
        dashboard.show.assert_called_once()
        app.app.exec.assert_called_once()
        assert result == 0


# ---------------------------------------------------------------------------
# _on_new_entries
# ---------------------------------------------------------------------------


class TestOnNewEntries:
    """_on_new_entries formats notifications and updates state correctly."""

    def test_single_entry_notification_uses_title_and_url(self, qtbot):
        """A single new entry notification shows the entry title and feed URL."""
        app, audio, notifier, dashboard = _make_app()
        entry = _make_entry(feed_url="https://example.com/feed", title="Hello World")
        with patch("src.app.save_state"):
            app._on_new_entries([entry])
        notifier.notify.assert_called_once()
        _, body_arg = notifier.notify.call_args[0][1].split("\n", 1)
        assert "Hello World" in notifier.notify.call_args[0][1]
        assert "https://example.com/feed" in body_arg

    def test_multiple_entries_notification_shows_count(self, qtbot):
        """Multiple new entries produces a summary count notification."""
        app, audio, notifier, dashboard = _make_app()
        entries = [
            _make_entry(feed_url="https://a.com/feed", entry_id="a-1"),
            _make_entry(feed_url="https://b.com/feed", entry_id="b-1"),
            _make_entry(feed_url="https://b.com/feed", entry_id="b-2"),
        ]
        with patch("src.app.save_state"):
            app._on_new_entries(entries)
        notifier.notify.assert_called_once()
        msg = notifier.notify.call_args[0][1]
        assert "3 new entries" in msg
        # Two distinct feed URLs
        assert "2 feed(s)" in msg

    def test_new_entries_plays_new_entry_sound(self, qtbot):
        """Audio plays the 'new_entry' event for every batch of new entries."""
        app, audio, notifier, dashboard = _make_app()
        with patch("src.app.save_state"):
            app._on_new_entries([_make_entry()])
        audio.play.assert_called_with("new_entry")

    def test_new_entries_forwarded_to_dashboard(self, qtbot):
        """Dashboard.add_entries() is called with the list of new entries."""
        app, _, _, dashboard = _make_app()
        entries = [_make_entry()]
        with patch("src.app.save_state"):
            app._on_new_entries(entries)
        dashboard.add_entries.assert_called_once_with(entries)

    def test_new_entries_stored_in_seen_ids(self, qtbot):
        """Entry IDs are persisted in _seen_ids after processing."""
        app, _, _, _ = _make_app()
        entry = _make_entry(entry_id="unique-xyz")
        with patch("src.app.save_state"):
            app._on_new_entries([entry])
        assert "unique-xyz" in app._seen_ids

    def test_new_entries_saves_state(self, qtbot):
        """save_state is called to persist seen IDs after new entries."""
        app, _, _, _ = _make_app()
        with patch("src.app.save_state") as mock_save:
            app._on_new_entries([_make_entry()])
        mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# _on_poll_complete / _on_poll_time_updated
# ---------------------------------------------------------------------------


class TestPollHandlers:
    """Tests for the poll-cycle update handlers."""

    def test_poll_complete_sets_last_poll_time(self, qtbot):
        """_on_poll_complete stamps the dashboard with the current UTC time."""
        app, _, _, dashboard = _make_app()
        app._on_poll_complete()
        dashboard.set_last_poll_time.assert_called_once()
        timestamp = dashboard.set_last_poll_time.call_args[0][0]
        assert "UTC" in timestamp

    def test_poll_time_updated_patches_matching_feed(self, qtbot):
        """_on_poll_time_updated sets last_poll_time on the matching feed."""
        app, _, _, _ = _make_app()
        app._on_poll_time_updated("https://example.com/feed", "2024-01-01T00:00:00Z")
        assert app.config.feeds[0].last_poll_time == "2024-01-01T00:00:00Z"

    def test_poll_time_updated_ignores_unknown_url(self, qtbot):
        """_on_poll_time_updated is a no-op for unrecognised URLs."""
        app, _, _, _ = _make_app()
        original_time = app.config.feeds[0].last_poll_time
        app._on_poll_time_updated("https://unknown.com/feed", "2024-01-01T00:00:00Z")
        assert app.config.feeds[0].last_poll_time == original_time


# ---------------------------------------------------------------------------
# _on_pause_toggle
# ---------------------------------------------------------------------------


class TestPauseToggle:
    """_on_pause_toggle switches the poller between running and paused."""

    def test_pause_when_running(self, qtbot):
        """Toggling while running pauses the poller and updates the UI."""
        app, _, _, dashboard = _make_app()
        app.poller.is_paused = False

        app._on_pause_toggle()

        app.poller.pause.assert_called_once()
        dashboard.set_paused.assert_called_once_with(True)
        assert app._tray_pause_action.text() == "Resume Polling"

    def test_resume_when_paused(self, qtbot):
        """Toggling while paused resumes the poller and updates the UI."""
        app, _, _, dashboard = _make_app()
        app.poller.is_paused = True

        app._on_pause_toggle()

        app.poller.resume.assert_called_once()
        dashboard.set_paused.assert_called_once_with(False)
        assert app._tray_pause_action.text() == "Pause Polling"


# ---------------------------------------------------------------------------
# _toggle_window / _on_tray_activated
# ---------------------------------------------------------------------------


class TestWindowToggle:
    """Tests for the dashboard show/hide logic."""

    def test_hides_dashboard_when_visible(self, qtbot):
        """_toggle_window hides the dashboard if it is currently visible."""
        app, _, _, dashboard = _make_app()
        dashboard.isVisible.return_value = True
        app._toggle_window()
        dashboard.hide.assert_called_once()
        dashboard.show.assert_not_called()

    def test_shows_dashboard_when_hidden(self, qtbot):
        """_toggle_window shows and raises the dashboard when it is hidden."""
        app, _, _, dashboard = _make_app()
        dashboard.isVisible.return_value = False
        app._toggle_window()
        dashboard.show.assert_called_once()
        dashboard.raise_.assert_called_once()
        dashboard.activateWindow.assert_called_once()

    def test_tray_trigger_toggles_window(self, qtbot):
        """A single-click (Trigger) on the tray icon toggles the window."""
        app, _, _, dashboard = _make_app()
        dashboard.isVisible.return_value = True
        app._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
        dashboard.hide.assert_called_once()

    def test_tray_other_reasons_do_nothing(self, qtbot):
        """Non-trigger tray activations leave the window state unchanged."""
        app, _, _, dashboard = _make_app()
        app._on_tray_activated(QSystemTrayIcon.ActivationReason.Context)
        dashboard.hide.assert_not_called()
        dashboard.show.assert_not_called()


# ---------------------------------------------------------------------------
# _apply_config_changes
# ---------------------------------------------------------------------------


class TestApplyConfigChanges:
    """_apply_config_changes propagates the new config to all subsystems."""

    def test_config_saved_to_disk(self, qtbot):
        """save_config is called with the current config."""
        app, _, _, _ = _make_app()
        with patch("src.app.save_config") as mock_save:
            app._apply_config_changes()
        mock_save.assert_called_once_with(app.config)

    def test_dashboard_updated(self, qtbot):
        """Dashboard feed list and name mapping are refreshed."""
        app, _, _, dashboard = _make_app()
        with patch("src.app.save_config"):
            app._apply_config_changes()
        dashboard.update_feeds.assert_called_with(app.config.feeds)
        dashboard.update_feed_names_mapping.assert_called_with(app.config.feeds)

    def test_poller_updated(self, qtbot):
        """Poller feed list and interval are updated."""
        app, _, _, _ = _make_app()
        with patch("src.app.save_config"):
            app._apply_config_changes()
        app.poller.update_feeds.assert_called_with(app.config.feeds)
        app.poller.update_interval.assert_called_with(app.config.poll_interval_secs)

    def test_audio_sound_map_updated(self, qtbot):
        """AudioPlayer.sound_map is synchronised with the new config."""
        app, audio, _, _ = _make_app()
        new_sound_map = {"new_entry": "beep.wav", "error": "boop.wav"}
        app.config.sound_map = new_sound_map
        with patch("src.app.save_config"):
            app._apply_config_changes()
        assert audio.sound_map == new_sound_map

    def test_notifier_recreated_with_new_style(self, qtbot):
        """A fresh Notifier is created when the notification style changes."""
        app, _, old_notifier, _ = _make_app()
        with patch("src.app.save_config"):
            app._apply_config_changes()
        # The notifier attribute must have been replaced
        assert app.notifier is not old_notifier


# ---------------------------------------------------------------------------
# _on_add_feed
# ---------------------------------------------------------------------------


class TestAddFeed:
    """Tests for the 'Add Feed' dialog handler."""

    def test_accepted_adds_feed_to_config(self, qtbot):
        """Accepting the dialog appends the new feed to config.feeds."""
        app, _, _, _ = _make_app()
        initial_count = len(app.config.feeds)

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_dialog.url_edit.text.return_value = "https://new.example.com/feed"
        mock_dialog.name_edit.text.return_value = "New Feed"
        mock_dialog.auth_user_edit.text.return_value = ""
        mock_dialog.auth_token_edit.text.return_value = ""

        with patch("src.app.FeedEditDialog", return_value=mock_dialog), \
             patch("src.app.save_config"):
            app._on_add_feed()

        assert len(app.config.feeds) == initial_count + 1
        assert app.config.feeds[-1].url == "https://new.example.com/feed"

    def test_rejected_leaves_config_unchanged(self, qtbot):
        """Cancelling the dialog does not modify config.feeds."""
        app, _, _, _ = _make_app()
        initial_count = len(app.config.feeds)

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected

        with patch("src.app.FeedEditDialog", return_value=mock_dialog):
            app._on_add_feed()

        assert len(app.config.feeds) == initial_count


# ---------------------------------------------------------------------------
# _on_settings
# ---------------------------------------------------------------------------


class TestSettings:
    """Tests for the Settings dialog handler."""

    def test_accepted_applies_new_config(self, qtbot):
        """Accepting the settings dialog replaces the current config."""
        app, _, _, _ = _make_app()
        new_config = AppConfig(
            poll_interval_secs=300,
            feeds=[Feed(url="https://new.com/feed", name="New")],
            sound_map={"new_entry": "ping.wav", "error": "alert.wav"},
        )
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_dialog.get_config.return_value = new_config

        with patch("src.app.SettingsDialog", return_value=mock_dialog), \
             patch("src.app.save_config"):
            app._on_settings()

        assert app.config is new_config

    def test_rejected_leaves_config_unchanged(self, qtbot):
        """Cancelling the settings dialog does not change the config."""
        app, _, _, _ = _make_app()
        original_config = app.config
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected

        with patch("src.app.SettingsDialog", return_value=mock_dialog):
            app._on_settings()

        assert app.config is original_config


# ---------------------------------------------------------------------------
# _on_remove_feed
# ---------------------------------------------------------------------------


class TestRemoveFeed:
    """Tests for the 'Remove Feed' handler."""

    def test_no_valid_indices_does_nothing(self, qtbot):
        """Passing indices out of range is silently ignored."""
        app, _, _, _ = _make_app()
        original_feeds = list(app.config.feeds)
        app._on_remove_feed([99])
        assert app.config.feeds == original_feeds

    def test_confirmed_removes_feed(self, qtbot):
        """Confirming the removal dialog deletes the feed at the given index."""
        app, _, _, _ = _make_app()
        original_count = len(app.config.feeds)

        with patch("src.app.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes), \
             patch("src.app.save_config"):
            app._on_remove_feed([0])

        assert len(app.config.feeds) == original_count - 1

    def test_rejected_does_not_remove_feed(self, qtbot):
        """Cancelling the confirmation dialog leaves config.feeds intact."""
        app, _, _, _ = _make_app()
        original_count = len(app.config.feeds)

        with patch("src.app.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.No):
            app._on_remove_feed([0])

        assert len(app.config.feeds) == original_count

    def test_multiple_indices_removes_all(self, qtbot):
        """All confirmed indices are removed in a single operation."""
        mock_config = AppConfig(
            poll_interval_secs=60,
            feeds=[
                Feed(url="https://a.com/feed", name="A"),
                Feed(url="https://b.com/feed", name="B"),
                Feed(url="https://c.com/feed", name="C"),
            ],
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
        try:
            app = JinkiesApp()
        finally:
            for p in patches:
                p.stop()

        with patch("src.app.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes), \
             patch("src.app.save_config"):
            app._on_remove_feed([0, 2])

        assert len(app.config.feeds) == 1
        assert app.config.feeds[0].url == "https://b.com/feed"


# ---------------------------------------------------------------------------
# _on_import_feeds
# ---------------------------------------------------------------------------


class TestImportFeeds:
    """Tests for the file-based feed import handler."""

    def test_no_file_selected_does_nothing(self, qtbot):
        """Cancelling the file dialog does not modify the feed list."""
        app, _, _, _ = _make_app()
        initial_count = len(app.config.feeds)

        with patch("src.app.QFileDialog.getOpenFileName", return_value=("", "")):
            app._on_import_feeds()

        assert len(app.config.feeds) == initial_count

    def test_opml_import_adds_feeds(self, qtbot):
        """Selecting an OPML file and confirming the preview adds the feeds."""
        app, _, _, _ = _make_app()
        new_feed = Feed(url="https://imported.com/feed", name="Imported")

        mock_preview = MagicMock()
        mock_preview.exec.return_value = QDialog.DialogCode.Accepted
        mock_preview.get_feeds.return_value = [new_feed]

        with patch("src.app.QFileDialog.getOpenFileName",
                   return_value=("/tmp/feeds.opml", "")), \
             patch("src.app.import_opml", return_value=[new_feed]), \
             patch("src.app.ImportPreviewDialog", return_value=mock_preview), \
             patch("src.app.save_config"):
            app._on_import_feeds()

        assert any(f.url == "https://imported.com/feed" for f in app.config.feeds)

    def test_xml_import_uses_local_feed_importer(self, qtbot):
        """Non-OPML files are processed by import_local_feed."""
        app, _, _, _ = _make_app()
        new_feed = Feed(url="https://local.com/feed", name="Local")

        mock_preview = MagicMock()
        mock_preview.exec.return_value = QDialog.DialogCode.Accepted
        mock_preview.get_feeds.return_value = [new_feed]

        with patch("src.app.QFileDialog.getOpenFileName",
                   return_value=("/tmp/feeds.xml", "")), \
             patch("src.app.import_local_feed", return_value=[new_feed]) as mock_local, \
             patch("src.app.ImportPreviewDialog", return_value=mock_preview), \
             patch("src.app.save_config"):
            app._on_import_feeds()

        mock_local.assert_called_once_with("/tmp/feeds.xml")

    def test_import_error_shows_warning(self, qtbot):
        """A ValueError from the importer is surfaced as a QMessageBox warning."""
        app, _, _, _ = _make_app()

        with patch("src.app.QFileDialog.getOpenFileName",
                   return_value=("/tmp/bad.opml", "")), \
             patch("src.app.import_opml", side_effect=ValueError("bad file")), \
             patch("src.app.QMessageBox.warning") as mock_warn:
            app._on_import_feeds()

        mock_warn.assert_called_once()

    def test_preview_cancelled_does_not_add_feeds(self, qtbot):
        """Cancelling the import preview dialog leaves the feed list unchanged."""
        app, _, _, _ = _make_app()
        initial_count = len(app.config.feeds)
        new_feed = Feed(url="https://preview.com/feed", name="Preview")

        mock_preview = MagicMock()
        mock_preview.exec.return_value = QDialog.DialogCode.Rejected

        with patch("src.app.QFileDialog.getOpenFileName",
                   return_value=("/tmp/feeds.opml", "")), \
             patch("src.app.import_opml", return_value=[new_feed]), \
             patch("src.app.ImportPreviewDialog", return_value=mock_preview):
            app._on_import_feeds()

        assert len(app.config.feeds) == initial_count


# ---------------------------------------------------------------------------
# Module-level run() entry point
# ---------------------------------------------------------------------------


class TestModuleLevelRun:
    """The module-level run() function enforces single-instance and orchestrates startup."""

    def test_returns_1_when_already_running(self):
        """Returns exit code 1 immediately if another instance holds the lock."""
        from src.app import run as app_run

        with patch("src.config.get_config_dir", return_value=Path("/tmp/jinkies_test")), \
             patch("src.app._try_lock", return_value=False):
            result = app_run()

        assert result == 1

    def test_creates_and_runs_app_when_lock_acquired(self):
        """Creates JinkiesApp and returns its exit code when the lock is free."""
        from src.app import run as app_run

        mock_app_instance = MagicMock()
        mock_app_instance.run.return_value = 0

        with patch("src.config.get_config_dir", return_value=Path("/tmp/jinkies_test")), \
             patch("src.app._try_lock", return_value=True), \
             patch("src.app._release_lock"), \
             patch("src.app.JinkiesApp", return_value=mock_app_instance):
            result = app_run()

        assert result == 0
        mock_app_instance.run.assert_called_once()

    def test_releases_lock_even_if_app_raises(self):
        """The lock is always released, even when JinkiesApp raises an exception."""
        from src.app import run as app_run

        with patch("src.config.get_config_dir", return_value=Path("/tmp/jinkies_test")), \
             patch("src.app._try_lock", return_value=True), \
             patch("src.app._release_lock") as mock_release, \
             patch("src.app.JinkiesApp", side_effect=RuntimeError("boom")):
            try:
                app_run()
            except RuntimeError:
                pass

        mock_release.assert_called_once()


# ---------------------------------------------------------------------------
# _get_icon_path
# ---------------------------------------------------------------------------


class TestGetIconPath:
    """_get_icon_path resolves the icon file relative to the project root."""

    def test_returns_empty_string_when_icon_missing(self, tmp_path):
        """Returns '' when the icon file does not exist at the expected location."""
        fake_meipass = str(tmp_path)
        # Simulate a frozen (PyInstaller) bundle with no icon
        original_frozen = getattr(sys, "frozen", False)
        sys.frozen = True
        sys._MEIPASS = fake_meipass  # noqa: SLF001
        try:
            result = _get_icon_path()
        finally:
            sys.frozen = original_frozen
            if hasattr(sys, "_MEIPASS"):
                del sys._MEIPASS

        assert result == ""

    def test_returns_path_string_when_icon_exists(self, tmp_path):
        """Returns the icon path string when the icon file is present."""
        assets = tmp_path / "assets"
        assets.mkdir()
        icon = assets / "icon.png"
        icon.write_bytes(b"PNG")

        fake_meipass = str(tmp_path)
        original_frozen = getattr(sys, "frozen", False)
        sys.frozen = True
        sys._MEIPASS = fake_meipass  # noqa: SLF001
        try:
            result = _get_icon_path()
        finally:
            sys.frozen = original_frozen
            if hasattr(sys, "_MEIPASS"):
                del sys._MEIPASS

        assert result == str(icon)

    def test_non_frozen_uses_project_root(self):
        """In a normal (non-frozen) run the icon path is derived from the source tree."""
        # sys.frozen is absent/False by default during tests
        result = _get_icon_path()
        # The repo ships assets/icon.png; either it's found or it isn't,
        # but the return value must always be a str.
        assert isinstance(result, str)
