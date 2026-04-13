"""Application glue for Jinkies feed monitor.

Sets up the QApplication, system tray, and wires together all
components: FeedPoller, AudioPlayer, Notifier, and Dashboard.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import IO

if sys.platform == "win32":
    import msvcrt  # type: ignore[import-not-found]
else:
    import fcntl

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from src.audio import AudioPlayer, ensure_default_sounds
from src.config import load_config, load_state, save_config, save_state
from src.dashboard import Dashboard
from src.feed_import import import_local_feed, import_opml
from src.feed_poller import FeedPoller
from src.models import Feed, FeedEntry
from src.notifier import Notifier
from src.settings_dialog import FeedEditDialog, ImportPreviewDialog, SettingsDialog


def _get_icon_path() -> str:
    """Get the path to the application icon, using the platform-appropriate format.

    On Windows the system tray requires a ``.ico`` file for correct display;
    if one is present it is preferred over the generic PNG.  On all other
    platforms the PNG is used directly.

    Returns:
        Absolute path to the icon file, or an empty string if no icon is found.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # noqa: SLF001
    else:
        base = Path(__file__).resolve().parent.parent

    # Windows system tray renders .ico files more reliably than .png.
    if sys.platform == "win32":
        ico_path = base / "assets" / "icon.ico"
        if ico_path.exists():
            return str(ico_path)

    icon_path = base / "assets" / "icon.png"
    if icon_path.exists():
        return str(icon_path)
    return ""


# Module-level handle kept open for the lifetime of the process so the OS-level
# lock remains held.  The OS automatically releases it on exit (clean or crash),
# which eliminates the TOCTOU race present in the old PID-file approach.
_lock_fh: IO[str] | None = None


def _try_lock(config_dir: Path) -> bool:
    """Attempt to acquire an exclusive OS-level lock for single-instance enforcement.

    Uses ``fcntl.flock`` on POSIX or ``msvcrt.locking`` on Windows.  The lock is
    held for the lifetime of the process and is automatically released on exit,
    whether clean or due to a crash, eliminating the TOCTOU window in the old
    PID-file approach.

    Args:
        config_dir: The config directory to place the lock file.

    Returns:
        True if the lock was acquired (no other instance is running).
    """
    global _lock_fh  # noqa: PLW0603

    lock_path = config_dir / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        fh: IO[str] = lock_path.open("w")
    except OSError:
        return False

    try:
        if sys.platform == "win32":
            # msvcrt.locking requires at least one byte to exist in the file.
            # Write a space, flush it to disk, then seek back before locking.
            fh.write(" ")
            fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return False

    _lock_fh = fh  # Keep open; closing would release the lock
    return True


def _release_lock(config_dir: Path) -> None:
    """Release the OS-level advisory lock and remove the lock file.

    Args:
        config_dir: The config directory containing the lock file.
    """
    global _lock_fh  # noqa: PLW0603

    lock_path = config_dir / ".lock"
    if _lock_fh is not None:
        try:
            if sys.platform == "win32":
                _lock_fh.seek(0)
                msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_UNLCK, 1)
            _lock_fh.close()
        except OSError:
            pass
        _lock_fh = None
    lock_path.unlink(missing_ok=True)


class JinkiesApp:
    """Main application controller.

    Wires together all components and manages the application lifecycle.

    Attributes:
        config: Current application configuration.
        dashboard: The main window.
        poller: The feed polling thread.
        audio: The audio player.
        notifier: The notification dispatcher.
    """

    def __init__(self) -> None:
        """Initialize the application and all components."""
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Jinkies")
        self.app.setQuitOnLastWindowClosed(False)

        icon_path = _get_icon_path()
        if icon_path:
            self.app.setWindowIcon(QIcon(icon_path))

        # Load config and state
        self.config = load_config()
        self._state = load_state(max_age_days=self.config.seen_ids_max_age_days)
        # seen_ids in state is now a dict {entry_id: iso_timestamp}
        seen_ids_dict: dict[str, str] = self._state.get("seen_ids", {})
        self._seen_ids: set[str] = set(seen_ids_dict.keys())
        self._seen_ids_timestamps: dict[str, str] = dict(seen_ids_dict)

        # Ensure default sounds exist
        ensure_default_sounds()

        # Set up system tray (guard against environments without a tray)
        self._tray = QSystemTrayIcon()
        if icon_path:
            self._tray.setIcon(QIcon(icon_path))
        else:
            self._tray.setIcon(self.app.style().standardIcon(
                self.app.style().StandardPixmap.SP_ComputerIcon
            ))
        self._tray.setToolTip("Jinkies — Feed Monitor")
        self._setup_tray_menu()

        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show()
            # On Windows, show a brief balloon on first launch so users know
            # they can click the tray icon to reopen the window.  The flag is
            # persisted in state.json so it is only shown once.
            if sys.platform == "win32" and not self._state.get("tray_tip_shown"):
                self._state["tray_tip_shown"] = True
                self._save_state()
                self._tray.showMessage(
                    "Jinkies",
                    "Jinkies is running in the system tray. "
                    "Click the icon to show or hide the window.",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )
        else:
            # Tray unavailable – ensure the window stays open so the app
            # remains accessible.
            self.app.setQuitOnLastWindowClosed(True)

        self._tray.activated.connect(self._on_tray_activated)

        # Set up components
        self.audio = AudioPlayer(self.config.sound_map)
        self.notifier = Notifier(
            tray_icon=self._tray,
            style=self.config.notification_style,
        )

        self.dashboard = Dashboard()
        self.dashboard.max_entries = self.config.max_entries
        self.dashboard.page_size = self.config.page_size
        self.dashboard.update_feeds(self.config.feeds)
        self.dashboard.update_feed_names_mapping(self.config.feeds)

        # Connect dashboard signals
        self.dashboard.add_feed_requested.connect(self._on_add_feed)
        self.dashboard.remove_feed_requested.connect(self._on_remove_feed)
        self.dashboard.import_feeds_requested.connect(self._on_import_feeds)
        self.dashboard.settings_requested.connect(self._on_settings)
        self.dashboard.pause_requested.connect(self._on_pause_toggle)

        # Track which feeds have already produced an error notification so that
        # repeated errors for the same broken feed are silenced after the first.
        # The entry is removed when the feed successfully delivers new entries,
        # allowing the next error to notify again.
        self._errored_feeds: set[str] = set()

        # Set up poller
        self.poller = FeedPoller(
            feeds=self.config.feeds,
            poll_interval=self.config.poll_interval_secs,
            seen_ids=self._seen_ids,
        )
        self.poller.new_entries_found.connect(self._on_new_entries)
        self.poller.feed_error.connect(self._on_feed_error)
        self.poller.poll_complete.connect(self._on_poll_complete)
        self.poller.poll_time_updated.connect(self._on_poll_time_updated)
        self.poller.feed_backoff_changed.connect(self._on_feed_backoff_changed)
        self.poller.start()

    def _setup_tray_menu(self) -> None:
        """Create the system tray context menu."""
        menu = QMenu()

        show_action = QAction("Show/Hide Window", menu)
        show_action.triggered.connect(self._toggle_window)
        menu.addAction(show_action)

        self._tray_pause_action = QAction("Pause Polling", menu)
        self._tray_pause_action.triggered.connect(self._on_pause_toggle)
        menu.addAction(self._tray_pause_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    def _toggle_window(self) -> None:
        """Toggle the dashboard window visibility."""
        if self.dashboard.isVisible():
            self.dashboard.hide()
        else:
            self.dashboard.show()
            self.dashboard.raise_()
            self.dashboard.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (click).

        Args:
            reason: The activation reason.
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def _on_new_entries(self, entries: list[FeedEntry]) -> None:
        """Handle new entries found by the poller.

        Args:
            entries: List of new FeedEntry objects.
        """
        # A successful delivery means the feed is healthy; clear any stored
        # error state so that a future error will notify again.
        for entry in entries:
            self._errored_feeds.discard(entry.feed_url)
            self.dashboard.clear_feed_error(entry.feed_url)

        self.dashboard.add_entries(entries)

        # Honour per-feed custom sound if configured.  All entries in a single
        # emission come from the same feed, so checking the first entry is
        # sufficient.
        feed_map = {f.url: f for f in self.config.feeds}
        if entries:
            feed = feed_map.get(entries[0].feed_url)
        else:
            feed = None
        sound_file = feed.sound_file if feed else None
        self.audio.play("new_entry", sound_file=sound_file)

        count = len(entries)
        if count == 1:
            title = entries[0].title
            body = f"From: {entries[0].feed_url}"
        else:
            title = f"{count} new entries"
            body = f"From {len({e.feed_url for e in entries})} feed(s)"

        self.notifier.notify("Jinkies!", f"{title}\n{body}")

        # Update seen IDs and record when each ID was first seen
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()
        for entry in entries:
            self._seen_ids.add(entry.entry_id)
            self._seen_ids_timestamps.setdefault(entry.entry_id, now_iso)
        self._save_state()

    def _on_feed_error(self, url: str, error: str) -> None:
        """Handle a feed polling error.

        Only the first error for each feed URL triggers a notification and
        sound; subsequent errors for the same URL are recorded in the
        dashboard but remain silent.  The error state is cleared when the
        feed next delivers new entries, so a later failure will notify again.

        Args:
            url: The feed URL that failed.
            error: The error message.
        """
        self.dashboard.record_error()
        self.dashboard.mark_feed_error(url, error)
        if url not in self._errored_feeds:
            self._errored_feeds.add(url)
            self.audio.play("error")
            self.notifier.notify("Jinkies — Error", f"Feed error: {url}\n{error}")

    def _on_poll_complete(self) -> None:
        """Handle completion of a polling cycle."""
        time_str = datetime.datetime.now(tz=datetime.UTC).strftime("%H:%M:%S UTC")
        self.dashboard.set_last_poll_time(time_str)

    def _on_poll_time_updated(self, url: str, timestamp: str) -> None:
        """Update the last-poll timestamp on the matching feed.

        This slot runs on the main thread, avoiding unsynchronized
        mutation of :attr:`Feed.last_poll_time` from the poller thread.

        Args:
            url: The feed URL that was polled.
            timestamp: ISO 8601 timestamp of the poll.
        """
        for feed in self.config.feeds:
            if feed.url == url:
                feed.last_poll_time = timestamp
                break

    def _on_feed_backoff_changed(self, url: str, backoff_secs: int) -> None:
        """Handle a change in a feed's exponential-backoff state.

        When *backoff_secs* is ``0`` the feed has recovered from a failure:
        any stored error state is cleared so that a future error can notify
        again.  When *backoff_secs* is non-zero the feed list tooltip is
        updated to show the scheduled retry delay.

        Args:
            url: The feed URL whose backoff state changed.
            backoff_secs: Seconds until the next retry, or ``0`` if the
                backoff has been cleared following a successful poll.
        """
        if backoff_secs == 0:
            self._errored_feeds.discard(url)
            self.dashboard.clear_feed_error(url)
        else:
            self.dashboard.mark_feed_backoff(url, backoff_secs)

    def _on_pause_toggle(self) -> None:
        """Toggle polling pause state."""
        if self.poller.is_paused:
            self.poller.resume()
            self.dashboard.set_paused(False)
            self._tray_pause_action.setText("Pause Polling")
        else:
            self.poller.pause()
            self.dashboard.set_paused(True)
            self._tray_pause_action.setText("Resume Polling")

    def _on_add_feed(self) -> None:
        """Show the add feed dialog."""
        dialog = FeedEditDialog(parent=self.dashboard)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            feed = Feed(
                url=dialog.url_edit.text(),
                name=dialog.name_edit.text(),
                auth_user=dialog.auth_user_edit.text() or None,
                auth_token=dialog.auth_token_edit.text() or None,
            )
            self.config.feeds.append(feed)
            self._apply_config_changes()

    def _on_import_feeds(self) -> None:
        """Show a file dialog to import feeds from OPML or Atom/XML files."""
        path, _ = QFileDialog.getOpenFileName(
            self.dashboard,
            "Import Feeds",
            "",
            "Feed Files (*.opml *.xml *.atom *.rss);;OPML Files (*.opml);;All Files (*)",
        )
        if not path:
            return

        try:
            if path.lower().endswith(".opml"):
                new_feeds = import_opml(path)
            else:
                new_feeds = import_local_feed(path)
        except ValueError as e:
            QMessageBox.warning(
                self.dashboard, "Import Error", str(e),
            )
            return

        if not new_feeds:
            return

        existing_urls = {f.url for f in self.config.feeds}
        preview = ImportPreviewDialog(
            new_feeds, existing_urls, parent=self.dashboard,
        )
        if preview.exec() != QDialog.DialogCode.Accepted:
            return

        added = preview.get_feeds()
        if not added:
            return

        self.config.feeds.extend(added)
        self._apply_config_changes()

    def _on_remove_feed(self, indices: list[int]) -> None:
        """Remove the feeds at *indices* from the config and refresh all components.

        Args:
            indices: Zero-based positions of the feeds to remove, as emitted by
                :attr:`Dashboard.remove_feed_requested`.
        """
        valid = [i for i in indices if 0 <= i < len(self.config.feeds)]
        if not valid:
            return

        if len(valid) == 1:
            feed = self.config.feeds[valid[0]]
            title = "Remove Feed"
            msg = f"Remove feed \"{feed.name}\"?"
        else:
            names = "\n".join(f"  \u2022 {self.config.feeds[i].name}" for i in valid)
            title = "Remove Feeds"
            msg = f"Remove {len(valid)} feeds?\n\n{names}"

        reply = QMessageBox.question(
            self.dashboard,
            title,
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for i in sorted(valid, reverse=True):
            self.config.feeds.pop(i)
        self._apply_config_changes()

    def _on_settings(self) -> None:
        """Show the settings dialog."""
        dialog = SettingsDialog(self.config, parent=self.dashboard)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = dialog.get_config()
            self._apply_config_changes()

    def _apply_config_changes(self) -> None:
        """Apply config changes to all components and save."""
        save_config(self.config)
        self.dashboard.max_entries = self.config.max_entries
        self.dashboard.page_size = self.config.page_size
        self.dashboard.update_feeds(self.config.feeds)
        self.dashboard.update_feed_names_mapping(self.config.feeds)
        self.poller.update_feeds(self.config.feeds)
        self.poller.update_interval(self.config.poll_interval_secs)
        self.audio.sound_map = self.config.sound_map
        self.notifier = Notifier(
            tray_icon=self._tray,
            style=self.config.notification_style,
        )

    def _save_state(self) -> None:
        """Persist the current state to disk."""
        # Ensure any IDs added via the poller without a timestamp get one now.
        # Iterate over a snapshot because the poller thread may add to
        # ``self._seen_ids`` concurrently.
        now = datetime.datetime.now(datetime.UTC)
        now_iso = now.isoformat()
        for entry_id in set(self._seen_ids):
            self._seen_ids_timestamps.setdefault(entry_id, now_iso)

        # Prune stale entries so memory and state.json don't grow without bound
        # during long-running sessions (not just on the next restart).
        cutoff = now - datetime.timedelta(days=self.config.seen_ids_max_age_days)
        pruned: dict[str, str] = {}
        for entry_id, ts in self._seen_ids_timestamps.items():
            try:
                seen_at = datetime.datetime.fromisoformat(ts)
                if seen_at.tzinfo is None:
                    seen_at = seen_at.replace(tzinfo=datetime.UTC)
                if seen_at >= cutoff:
                    pruned[entry_id] = ts
            except (ValueError, TypeError):
                pass  # Drop entries with invalid timestamps

        self._seen_ids_timestamps = pruned
        self._seen_ids.intersection_update(pruned)
        self._state["seen_ids"] = self._seen_ids_timestamps
        save_state(self._state)

    def _quit(self) -> None:
        """Shut down the application cleanly.

        State is persisted first so that it is always written, even if the
        poller thread does not stop within the wait timeout (e.g. it is
        blocked in a network request).  The poller is then asked to stop and
        the application exits after a short grace period.
        """
        self._save_state()
        self.poller.requestInterruption()
        self.poller.resume()  # Unblock if paused
        self.poller.wait(5000)
        self._tray.hide()
        self.app.quit()

    def run(self) -> int:
        """Show the dashboard and start the event loop.

        Returns:
            The application exit code.
        """
        self.dashboard.show()
        return self.app.exec()


def run() -> int:
    """Application entry point.

    Returns:
        The application exit code.
    """
    from src.config import get_config_dir

    config_dir = get_config_dir()
    if not _try_lock(config_dir):
        print("Jinkies is already running.")  # noqa: T201
        return 1

    try:
        app = JinkiesApp()
        return app.run()
    finally:
        _release_lock(config_dir)
