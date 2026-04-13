"""Tests for JinkiesApp: startup, teardown, signal handling, and single-instance logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.app import JinkiesApp, _get_icon_path
from src.models import AppConfig, Feed, FeedEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(icon_path="", state=None, config=None):
    """Return a JinkiesApp with all external dependencies mocked out.

    Args:
        icon_path: Value returned by the mocked _get_icon_path.
        state: State dict returned by mocked load_state.
        config: AppConfig returned by mocked load_config.
    """
    if state is None:
        state = {}
    if config is None:
        config = AppConfig(
            poll_interval_secs=60,
            feeds=[Feed(url="https://example.com/feed", name="Test Feed")],
            sound_map={"new_entry": "new_entry.wav", "error": "error.wav"},
        )

    patches = [
        patch("src.app.load_config", return_value=config),
        patch("src.app.load_state", return_value=state),
        patch("src.app.save_state"),
        patch("src.app.ensure_default_sounds"),
        patch("src.app.QApplication"),
        patch("src.app.QSystemTrayIcon"),
        patch("src.app.AudioPlayer"),
        patch("src.app.Notifier"),
        patch("src.app.Dashboard"),
        patch("src.app.FeedPoller"),
        patch("src.app._get_icon_path", return_value=icon_path),
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
# Startup / teardown
# ---------------------------------------------------------------------------

class TestJinkiesAppStartup:
    """JinkiesApp.__init__ and run() wiring tests."""

    def test_init_creates_components(self):
        """Construction wires all major components."""
        app, audio, notifier, dashboard = _make_app()
        assert app.audio is audio
        assert app.notifier is notifier
        assert app.dashboard is dashboard
        assert app.poller is not None

    def test_init_loads_config(self):
        """load_config is called during construction."""
        with (
            patch("src.app.load_config") as mock_load_config,
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
        ):
            mock_load_config.return_value = AppConfig()
            JinkiesApp()
            mock_load_config.assert_called_once()

    def test_init_starts_poller(self):
        """FeedPoller.start() is called during construction."""
        app, *_ = _make_app()
        app.poller.start.assert_called_once()

    def test_run_shows_dashboard_and_executes_app(self):
        """run() shows the dashboard and calls app.exec()."""
        app, _, _, dashboard = _make_app()
        app.app.exec.return_value = 0

        result = app.run()

        dashboard.show.assert_called_once()
        app.app.exec.assert_called_once()
        assert result == 0

    def test_run_returns_exec_exit_code(self):
        """run() forwards the exit code from QApplication.exec()."""
        app, *_ = _make_app()
        app.app.exec.return_value = 42

        assert app.run() == 42


class TestJinkiesAppQuit:
    """_quit() saves state and stops the poller cleanly."""

    def test_quit_saves_state(self):
        """_quit() persists state before stopping."""
        app, *_ = _make_app()
        with patch("src.app.save_state") as mock_save:
            app._quit()
        mock_save.assert_called()

    def test_quit_stops_poller(self):
        """_quit() requests poller interruption and waits."""
        app, *_ = _make_app()
        with patch("src.app.save_state"):
            app._quit()
        app.poller.requestInterruption.assert_called_once()
        app.poller.resume.assert_called_once()
        app.poller.wait.assert_called_once_with(5000)

    def test_quit_hides_tray_and_quits_app(self):
        """_quit() hides the tray icon and calls QApplication.quit()."""
        app, *_ = _make_app()
        with patch("src.app.save_state"):
            app._quit()
        app._tray.hide.assert_called_once()
        app.app.quit.assert_called_once()


# ---------------------------------------------------------------------------
# Window / tray
# ---------------------------------------------------------------------------

class TestToggleWindow:
    """_toggle_window() shows/hides the dashboard."""

    def test_hides_when_visible(self):
        """When the dashboard is visible, _toggle_window hides it."""
        app, _, _, dashboard = _make_app()
        dashboard.isVisible.return_value = True

        app._toggle_window()

        dashboard.hide.assert_called_once()
        dashboard.show.assert_not_called()

    def test_shows_when_hidden(self):
        """When the dashboard is hidden, _toggle_window shows and raises it."""
        app, _, _, dashboard = _make_app()
        dashboard.isVisible.return_value = False

        app._toggle_window()

        dashboard.show.assert_called()
        dashboard.raise_.assert_called_once()
        dashboard.activateWindow.assert_called_once()


class TestTrayActivation:
    """_on_tray_activated() toggles window on Trigger."""

    def test_trigger_toggles_window(self):
        """Trigger activation reason toggles the window."""
        from PySide6.QtWidgets import QSystemTrayIcon
        app, _, _, dashboard = _make_app()
        dashboard.isVisible.return_value = False

        app._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)

        dashboard.show.assert_called()

    def test_non_trigger_does_nothing(self):
        """Non-Trigger activation reason does not toggle the window."""
        from PySide6.QtWidgets import QSystemTrayIcon
        app, _, _, dashboard = _make_app()

        app._on_tray_activated(QSystemTrayIcon.ActivationReason.Context)

        dashboard.show.assert_not_called()
        dashboard.hide.assert_not_called()


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------

class TestOnNewEntries:
    """_on_new_entries() notifies and updates state."""

    def _make_entry(self, entry_id="entry-1", feed_url="https://example.com/feed"):
        return FeedEntry(
            feed_url=feed_url,
            title="New post",
            link="https://example.com/1",
            published="2024-01-01T00:00:00Z",
            entry_id=entry_id,
            seen=False,
        )

    def test_single_entry_notification_uses_title(self):
        """Single new entry uses its title in the notification."""
        app, audio, notifier, dashboard = _make_app()
        entry = self._make_entry()

        with patch("src.app.save_state"):
            app._on_new_entries([entry])

        audio.play.assert_called_once_with("new_entry")
        args = notifier.notify.call_args[0]
        assert "New post" in args[1]

    def test_multiple_entries_notification_uses_count(self):
        """Multiple new entries use the count in the notification."""
        app, audio, notifier, dashboard = _make_app()
        entries = [self._make_entry("e1"), self._make_entry("e2")]

        with patch("src.app.save_state"):
            app._on_new_entries(entries)

        audio.play.assert_called_once_with("new_entry")
        args = notifier.notify.call_args[0]
        assert "2" in args[1]

    def test_adds_entries_to_dashboard(self):
        """New entries are forwarded to the dashboard."""
        app, _, _, dashboard = _make_app()
        entry = self._make_entry()

        with patch("src.app.save_state"):
            app._on_new_entries([entry])

        dashboard.add_entries.assert_called_once_with([entry])

    def test_records_seen_ids(self):
        """New entry IDs are added to the seen-IDs set."""
        app, *_ = _make_app()
        entry = self._make_entry("unique-id-99")

        with patch("src.app.save_state"):
            app._on_new_entries([entry])

        assert "unique-id-99" in app._seen_ids

    def test_clears_errored_feed_state(self):
        """Receiving entries for a feed clears its error state."""
        app, audio, notifier, dashboard = _make_app()
        app._errored_feeds.add("https://example.com/feed")
        entry = self._make_entry()

        with patch("src.app.save_state"):
            app._on_new_entries([entry])

        assert "https://example.com/feed" not in app._errored_feeds
        dashboard.clear_feed_error.assert_called_with("https://example.com/feed")


class TestOnPollComplete:
    """_on_poll_complete() updates the last-poll display."""

    def test_sets_last_poll_time(self):
        """_on_poll_complete updates the dashboard last-poll timestamp."""
        app, _, _, dashboard = _make_app()

        app._on_poll_complete()

        dashboard.set_last_poll_time.assert_called_once()
        time_str = dashboard.set_last_poll_time.call_args[0][0]
        assert "UTC" in time_str


class TestOnPollTimeUpdated:
    """_on_poll_time_updated() updates the matching feed object."""

    def test_updates_matching_feed(self):
        """The feed whose URL matches gets its last_poll_time updated."""
        app, *_ = _make_app()
        url = "https://example.com/feed"
        timestamp = "2024-01-01T12:00:00+00:00"

        app._on_poll_time_updated(url, timestamp)

        feed = app.config.feeds[0]
        assert feed.last_poll_time == timestamp

    def test_ignores_unknown_url(self):
        """A URL that matches no feed leaves config unchanged."""
        app, *_ = _make_app()
        original = app.config.feeds[0].last_poll_time

        app._on_poll_time_updated("https://unknown.example.com/", "ts")

        assert app.config.feeds[0].last_poll_time == original


class TestOnFeedBackoffChanged:
    """_on_feed_backoff_changed() responds to backoff/recovery events."""

    def test_backoff_nonzero_marks_feed(self):
        """Non-zero backoff marks the feed with the retry delay."""
        app, _, _, dashboard = _make_app()

        app._on_feed_backoff_changed("https://example.com/feed", 30)

        dashboard.mark_feed_backoff.assert_called_once_with("https://example.com/feed", 30)

    def test_backoff_zero_clears_error(self):
        """Zero backoff (recovery) clears the feed error state."""
        app, _, _, dashboard = _make_app()
        app._errored_feeds.add("https://example.com/feed")

        app._on_feed_backoff_changed("https://example.com/feed", 0)

        assert "https://example.com/feed" not in app._errored_feeds
        dashboard.clear_feed_error.assert_called_once_with("https://example.com/feed")


class TestOnPauseToggle:
    """_on_pause_toggle() switches polling pause state."""

    def test_pause_when_running(self):
        """Toggling while running pauses the poller."""
        app, *_ = _make_app()
        app.poller.is_paused = False

        app._on_pause_toggle()

        app.poller.pause.assert_called_once()
        app.dashboard.set_paused.assert_called_once_with(True)
        assert "Resume" in app._tray_pause_action.text()

    def test_resume_when_paused(self):
        """Toggling while paused resumes the poller."""
        app, *_ = _make_app()
        app.poller.is_paused = True

        app._on_pause_toggle()

        app.poller.resume.assert_called_once()
        app.dashboard.set_paused.assert_called_once_with(False)
        assert "Pause" in app._tray_pause_action.text()


# ---------------------------------------------------------------------------
# Config / state
# ---------------------------------------------------------------------------

class TestApplyConfigChanges:
    """_apply_config_changes() propagates config to all components."""

    def test_saves_config(self):
        """Config is persisted to disk."""
        app, *_ = _make_app()
        with patch("src.app.save_config") as mock_save:
            app._apply_config_changes()
        mock_save.assert_called_once_with(app.config)

    def test_updates_dashboard(self):
        """Dashboard feeds and max_entries are refreshed."""
        app, _, _, dashboard = _make_app()
        with patch("src.app.save_config"):
            app._apply_config_changes()
        dashboard.update_feeds.assert_called()
        dashboard.update_feed_names_mapping.assert_called()

    def test_updates_poller(self):
        """Poller feeds and interval are refreshed."""
        app, *_ = _make_app()
        with patch("src.app.save_config"):
            app._apply_config_changes()
        app.poller.update_feeds.assert_called()
        app.poller.update_interval.assert_called_with(app.config.poll_interval_secs)

    def test_updates_audio_sound_map(self):
        """AudioPlayer sound_map attribute is updated."""
        app, audio, *_ = _make_app()
        app.config.sound_map = {"new_entry": "beep.wav"}
        with patch("src.app.save_config"):
            with patch("src.app.Notifier"):
                app._apply_config_changes()
        assert audio.sound_map == {"new_entry": "beep.wav"}


class TestSaveState:
    """_save_state() persists seen IDs and prunes stale ones."""

    def test_persists_seen_ids(self):
        """State is written to disk with current seen IDs."""
        app, *_ = _make_app()
        app._seen_ids.add("id-1")
        with patch("src.app.save_state") as mock_save:
            app._save_state()
        mock_save.assert_called_once()
        saved_state = mock_save.call_args[0][0]
        assert "id-1" in saved_state["seen_ids"]

    def test_prunes_stale_ids(self):
        """IDs older than max_age_days are removed."""
        import datetime
        app, *_ = _make_app()
        app.config.seen_ids_max_age_days = 1
        old_ts = (
            datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=10)
        ).isoformat()
        app._seen_ids.add("old-id")
        app._seen_ids_timestamps["old-id"] = old_ts

        with patch("src.app.save_state") as mock_save:
            app._save_state()

        saved = mock_save.call_args[0][0]["seen_ids"]
        assert "old-id" not in saved

    def test_drops_invalid_timestamp(self):
        """Entries with invalid timestamps are silently dropped."""
        app, *_ = _make_app()
        app._seen_ids.add("bad-ts-id")
        app._seen_ids_timestamps["bad-ts-id"] = "not-a-timestamp"

        with patch("src.app.save_state") as mock_save:
            app._save_state()

        saved = mock_save.call_args[0][0]["seen_ids"]
        assert "bad-ts-id" not in saved


# ---------------------------------------------------------------------------
# Dialog-driven handlers
# ---------------------------------------------------------------------------

class TestOnAddFeed:
    """_on_add_feed() shows FeedEditDialog and updates config on accept."""

    def test_accepted_adds_feed(self):
        """Accepted dialog appends a new feed to the config."""
        from PySide6.QtWidgets import QDialog
        app, *_ = _make_app()

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_dialog.url_edit.text.return_value = "https://new.example.com/feed"
        mock_dialog.name_edit.text.return_value = "New Feed"
        mock_dialog.auth_user_edit.text.return_value = ""
        mock_dialog.auth_token_edit.text.return_value = ""

        initial_count = len(app.config.feeds)
        with (
            patch("src.app.FeedEditDialog", return_value=mock_dialog),
            patch("src.app.save_config"),
        ):
            app._on_add_feed()

        assert len(app.config.feeds) == initial_count + 1
        assert app.config.feeds[-1].url == "https://new.example.com/feed"

    def test_rejected_does_not_add_feed(self):
        """Rejected dialog leaves config unchanged."""
        from PySide6.QtWidgets import QDialog
        app, *_ = _make_app()

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected

        initial_count = len(app.config.feeds)
        with patch("src.app.FeedEditDialog", return_value=mock_dialog):
            app._on_add_feed()

        assert len(app.config.feeds) == initial_count


class TestOnRemoveFeed:
    """_on_remove_feed() removes feeds from config when confirmed."""

    def test_confirmed_single_removal(self):
        """Confirming removal of a single feed removes it from config."""
        from PySide6.QtWidgets import QMessageBox
        app, *_ = _make_app()
        assert len(app.config.feeds) == 1

        with (
            patch(
                "src.app.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch("src.app.save_config"),
        ):
            app._on_remove_feed([0])

        assert len(app.config.feeds) == 0

    def test_cancelled_single_removal(self):
        """Cancelling the removal confirmation leaves config unchanged."""
        from PySide6.QtWidgets import QMessageBox
        app, *_ = _make_app()
        initial_count = len(app.config.feeds)

        with patch(
            "src.app.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            app._on_remove_feed([0])

        assert len(app.config.feeds) == initial_count

    def test_invalid_index_ignored(self):
        """Out-of-range indices are ignored without error."""
        app, *_ = _make_app()
        initial_count = len(app.config.feeds)

        app._on_remove_feed([999])

        assert len(app.config.feeds) == initial_count

    def test_multiple_removal_confirmation(self):
        """Removing multiple feeds at once uses plural dialog text."""
        from PySide6.QtWidgets import QMessageBox
        config = AppConfig(
            feeds=[
                Feed(url="https://a.com/feed", name="Feed A"),
                Feed(url="https://b.com/feed", name="Feed B"),
            ],
        )
        app, *_ = _make_app(config=config)

        with (
            patch(
                "src.app.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ) as mock_question,
            patch("src.app.save_config"),
        ):
            app._on_remove_feed([0, 1])

        assert len(app.config.feeds) == 0
        # Plural title expected
        title_arg = mock_question.call_args[0][1]
        assert "Feeds" in title_arg


class TestOnSettings:
    """_on_settings() shows SettingsDialog and applies on accept."""

    def test_accepted_applies_config(self):
        """Accepted settings dialog updates and saves config."""
        from PySide6.QtWidgets import QDialog
        app, *_ = _make_app()

        new_config = AppConfig(poll_interval_secs=120)
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_dialog.get_config.return_value = new_config

        with (
            patch("src.app.SettingsDialog", return_value=mock_dialog),
            patch("src.app.save_config"),
        ):
            app._on_settings()

        assert app.config.poll_interval_secs == 120

    def test_rejected_does_not_change_config(self):
        """Rejected settings dialog leaves config unchanged."""
        from PySide6.QtWidgets import QDialog
        app, *_ = _make_app()
        original_interval = app.config.poll_interval_secs

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected

        with patch("src.app.SettingsDialog", return_value=mock_dialog):
            app._on_settings()

        assert app.config.poll_interval_secs == original_interval


class TestOnImportFeeds:
    """_on_import_feeds() imports feeds from OPML or Atom/XML files."""

    def test_cancelled_file_dialog_does_nothing(self):
        """Empty path from file dialog (cancel) does nothing."""
        app, *_ = _make_app()
        initial_count = len(app.config.feeds)

        with patch("src.app.QFileDialog.getOpenFileName", return_value=("", "")):
            app._on_import_feeds()

        assert len(app.config.feeds) == initial_count

    def test_opml_import_adds_feeds(self):
        """Importing an OPML file adds the parsed feeds to config."""
        from PySide6.QtWidgets import QDialog
        app, *_ = _make_app()
        new_feed = Feed(url="https://imported.example.com/feed", name="Imported")

        mock_preview = MagicMock()
        mock_preview.exec.return_value = QDialog.DialogCode.Accepted
        mock_preview.get_feeds.return_value = [new_feed]

        with (
            patch("src.app.QFileDialog.getOpenFileName", return_value=("/tmp/feeds.opml", "")),
            patch("src.app.import_opml", return_value=[new_feed]),
            patch("src.app.ImportPreviewDialog", return_value=mock_preview),
            patch("src.app.save_config"),
        ):
            app._on_import_feeds()

        assert any(f.url == "https://imported.example.com/feed" for f in app.config.feeds)

    def test_import_error_shows_warning(self):
        """ValueError during import shows a warning dialog."""
        app, *_ = _make_app()

        with (
            patch("src.app.QFileDialog.getOpenFileName", return_value=("/tmp/bad.opml", "")),
            patch("src.app.import_opml", side_effect=ValueError("bad file")),
            patch("src.app.QMessageBox.warning") as mock_warning,
        ):
            app._on_import_feeds()

        mock_warning.assert_called_once()

    def test_preview_cancelled_adds_nothing(self):
        """If the user cancels the preview dialog, no feeds are added."""
        from PySide6.QtWidgets import QDialog
        app, *_ = _make_app()
        new_feed = Feed(url="https://imported.example.com/feed", name="Imported")
        initial_count = len(app.config.feeds)

        mock_preview = MagicMock()
        mock_preview.exec.return_value = QDialog.DialogCode.Rejected

        with (
            patch("src.app.QFileDialog.getOpenFileName", return_value=("/tmp/feeds.opml", "")),
            patch("src.app.import_opml", return_value=[new_feed]),
            patch("src.app.ImportPreviewDialog", return_value=mock_preview),
        ):
            app._on_import_feeds()

        assert len(app.config.feeds) == initial_count


# ---------------------------------------------------------------------------
# _get_icon_path
# ---------------------------------------------------------------------------

class TestGetIconPath:
    """_get_icon_path() returns the correct icon path or empty string."""

    def test_returns_empty_when_no_assets(self, tmp_path):
        """Returns '' when neither icon.ico nor icon.png exist."""
        import src.app as app_mod

        with patch.object(app_mod, "__file__", str(tmp_path / "src" / "app.py")):
            result = _get_icon_path()
        assert result == ""

    def test_returns_png_path_when_present(self, tmp_path):
        """Returns path to icon.png when it exists in the expected location."""
        import src.app as app_mod

        # Mirror the real directory layout expected by _get_icon_path:
        #   base = Path(__file__).resolve().parent.parent
        #   icon_path = base / "assets" / "icon.png"
        fake_src = tmp_path / "src"
        fake_src.mkdir()
        assets = tmp_path / "assets"
        assets.mkdir()
        png = assets / "icon.png"
        png.write_bytes(b"fake png data")

        with patch.object(app_mod, "__file__", str(fake_src / "app.py")):
            result = _get_icon_path()

        assert result == str(png)

    def test_returns_real_icon_when_assets_exist(self):
        """When the actual repo assets/icon.png exists, path is non-empty."""
        result = _get_icon_path()
        if result:
            assert Path(result).exists()
            assert result.endswith(".png") or result.endswith(".ico")


# ---------------------------------------------------------------------------
# Module-level run()
# ---------------------------------------------------------------------------

class TestModuleLevelRun:
    """The module-level run() function handles lock acquisition and app lifecycle."""

    def test_returns_1_when_already_running(self, tmp_path):
        """Returns exit code 1 when another instance holds the lock."""
        with (
            patch("src.config.get_config_dir", return_value=tmp_path),
            patch("src.app._try_lock", return_value=False),
        ):
            from src.app import run as app_run
            result = app_run()
        assert result == 1

    def test_runs_app_when_lock_acquired(self, tmp_path):
        """Starts JinkiesApp and returns its exit code when lock is acquired."""
        mock_app = MagicMock()
        mock_app.run.return_value = 0

        with (
            patch("src.config.get_config_dir", return_value=tmp_path),
            patch("src.app._try_lock", return_value=True),
            patch("src.app._release_lock") as mock_release,
            patch("src.app.JinkiesApp", return_value=mock_app),
        ):
            from src.app import run as app_run
            result = app_run()

        assert result == 0
        mock_app.run.assert_called_once()
        mock_release.assert_called_once_with(tmp_path)

    def test_releases_lock_on_exception(self, tmp_path):
        """_release_lock is called even if JinkiesApp raises."""
        with (
            patch("src.config.get_config_dir", return_value=tmp_path),
            patch("src.app._try_lock", return_value=True),
            patch("src.app._release_lock") as mock_release,
            patch("src.app.JinkiesApp", side_effect=RuntimeError("boom")),
        ):
            from src.app import run as app_run
            with pytest.raises(RuntimeError):
                app_run()

        mock_release.assert_called_once_with(tmp_path)

