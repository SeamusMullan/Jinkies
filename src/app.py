"""Application glue for Jinkies feed monitor.

Sets up the QApplication, system tray, and wires together all
components: FeedPoller, AudioPlayer, Notifier, and Dashboard.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

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
    """Get the path to the application icon.

    Returns:
        Path to the icon file.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # noqa: SLF001
    else:
        base = Path(__file__).resolve().parent.parent
    icon_path = base / "assets" / "icon.png"
    if icon_path.exists():
        return str(icon_path)
    return ""


def _try_lock(config_dir: Path) -> bool:
    """Attempt to create an advisory lock file for single-instance check.

    Args:
        config_dir: The config directory to place the lock file.

    Returns:
        True if lock was acquired (no other instance running).
    """
    lock_path = config_dir / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        # Check if the PID in the lock file is still running
        try:
            pid = int(lock_path.read_text().strip())
            # Check if process exists
            import os

            os.kill(pid, 0)
            return False  # noqa: TRY300
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass  # Stale lock file

    import os

    lock_path.write_text(str(os.getpid()))
    return True


def _release_lock(config_dir: Path) -> None:
    """Remove the advisory lock file.

    Args:
        config_dir: The config directory containing the lock file.
    """
    lock_path = config_dir / ".lock"
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
        self._state = load_state()
        self._seen_ids: set[str] = set(self._state.get("seen_ids", []))

        # Ensure default sounds exist
        ensure_default_sounds()

        # Set up system tray
        self._tray = QSystemTrayIcon()
        if icon_path:
            self._tray.setIcon(QIcon(icon_path))
        else:
            self._tray.setIcon(self.app.style().standardIcon(
                self.app.style().StandardPixmap.SP_ComputerIcon
            ))
        self._tray.setToolTip("Jinkies — Feed Monitor")
        self._setup_tray_menu()
        self._tray.show()
        self._tray.activated.connect(self._on_tray_activated)

        # Set up components
        self.audio = AudioPlayer(self.config.sound_map)
        self.notifier = Notifier(
            tray_icon=self._tray,
            style=self.config.notification_style,
        )

        self.dashboard = Dashboard()
        self.dashboard.update_feeds(self.config.feeds)
        self.dashboard.update_feed_names_mapping(self.config.feeds)

        # Connect dashboard signals
        self.dashboard.add_feed_requested.connect(self._on_add_feed)
        self.dashboard.remove_feed_requested.connect(self._on_remove_feed)
        self.dashboard.import_feeds_requested.connect(self._on_import_feeds)
        self.dashboard.settings_requested.connect(self._on_settings)
        self.dashboard.pause_requested.connect(self._on_pause_toggle)

        # Set up poller
        self.poller = FeedPoller(
            feeds=self.config.feeds,
            poll_interval=self.config.poll_interval_secs,
            seen_ids=self._seen_ids,
        )
        self.poller.new_entries_found.connect(self._on_new_entries)
        self.poller.feed_error.connect(self._on_feed_error)
        self.poller.poll_complete.connect(self._on_poll_complete)
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
        self.dashboard.add_entries(entries)
        self.audio.play("new_entry")

        count = len(entries)
        if count == 1:
            title = entries[0].title
            body = f"From: {entries[0].feed_url}"
        else:
            title = f"{count} new entries"
            body = f"From {len({e.feed_url for e in entries})} feed(s)"

        self.notifier.notify("Jinkies!", f"{title}\n{body}")

        # Update seen IDs
        for entry in entries:
            self._seen_ids.add(entry.entry_id)
        self._save_state()

    def _on_feed_error(self, url: str, error: str) -> None:
        """Handle a feed polling error.

        Args:
            url: The feed URL that failed.
            error: The error message.
        """
        self.dashboard.record_error()
        self.audio.play("error")
        self.notifier.notify("Jinkies — Error", f"Feed error: {url}\n{error}")

    def _on_poll_complete(self) -> None:
        """Handle completion of a polling cycle."""
        time_str = datetime.datetime.now(tz=datetime.UTC).strftime("%H:%M:%S UTC")
        self.dashboard.set_last_poll_time(time_str)

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

    def _on_remove_feed(self) -> None:
        """Remove the selected feed from the feed list."""
        selected = self.dashboard._feed_list.currentRow()
        if 0 <= selected < len(self.config.feeds):
            self.config.feeds.pop(selected)
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
        self._state["seen_ids"] = list(self._seen_ids)
        save_state(self._state)

    def _quit(self) -> None:
        """Shut down the application cleanly."""
        self.poller.requestInterruption()
        self.poller.resume()  # Unblock if paused
        self.poller.wait(5000)
        self._save_state()
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
