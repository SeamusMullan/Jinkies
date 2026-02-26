"""Main dashboard window for Jinkies feed monitor.

Displays a feed list, entry table, and stats bar. Provides toolbar
actions for managing feeds and controlling polling.
"""

from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.config import get_config_dir
from src.models import FeedEntry

if TYPE_CHECKING:
    from src.models import Feed


class Dashboard(QMainWindow):
    """Main application window showing feeds, entries, and stats.

    Signals:
        add_feed_requested: Emitted when the Add Feed button is clicked.
        remove_feed_requested: Emitted when the Remove Feed button is clicked.
        settings_requested: Emitted when the Settings button is clicked.
        pause_requested: Emitted when Pause/Resume is toggled.

    Attributes:
        entries: List of currently displayed FeedEntry objects.
    """

    add_feed_requested = Signal()
    remove_feed_requested = Signal()
    import_feeds_requested = Signal()
    settings_requested = Signal()
    pause_requested = Signal()

    def __init__(self) -> None:
        """Initialize the dashboard window."""
        super().__init__()
        self.setWindowTitle("Jinkies — Feed Monitor")
        self.setMinimumSize(800, 500)
        self.entries: list[FeedEntry] = []

        # Create store at default location if it doesnt exist
        self._entries_store_location = get_config_dir() / "store.json"
        if not self._entries_store_location.exists():
            self._entries_store_location.parent.mkdir(parents=True, exist_ok=True)
            f = open(self._entries_store_location, "w")
            f.write('{"entries": []}')
            f.close()

        self._update_entries_store()

        self._errors_today = 0
        self._entries_today = 0
        self._last_poll_time = ""
        self._is_paused = False

        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()

    def _update_entries_store(self) -> None:
        """Updates class entires using local store file."""
        with open(self._entries_store_location) as store:
            try:
                data = json.load(store)
            except Exception:
                data = {"entries": []}

            # Create a new FeedEntry from the json and append to self.entries
            # Since this happens in Dashboard constructor, we don't need any deduplation logic.
            for entry_data in data["entries"]:
                self.entries.append(FeedEntry.from_dict(entry_data))

    def _save_entries_store(self) -> None:
        """Updates the local store file with the class' entries list."""
        with open(self._entries_store_location, "w") as store:
            json.dump({"entries": [e.to_dict() for e in self.entries]}, store)

    def _setup_toolbar(self) -> None:
        """Create the main toolbar with action buttons."""
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._add_feed_action = toolbar.addAction("Add Feed")
        self._add_feed_action.triggered.connect(self.add_feed_requested.emit)

        self._remove_feed_action = toolbar.addAction("Remove Feed")
        self._remove_feed_action.triggered.connect(self.remove_feed_requested.emit)

        self._import_feeds_action = toolbar.addAction("Import Feeds")
        self._import_feeds_action.triggered.connect(self.import_feeds_requested.emit)

        toolbar.addSeparator()

        self._settings_action = toolbar.addAction("Settings")
        self._settings_action.triggered.connect(self.settings_requested.emit)

        toolbar.addSeparator()

        self._pause_action = toolbar.addAction("Pause")
        self._pause_action.triggered.connect(self._on_pause_clicked)

    def _setup_central(self) -> None:
        """Create the central widget with feed list, entry table, and filter."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self._filter_combo = QComboBox()
        self._filter_combo.addItem("All Feeds")
        self._filter_combo.currentTextChanged.connect(self._apply_filter)
        filter_layout.addWidget(self._filter_combo)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Splitter: feed list | entry table
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._feed_list = QListWidget()
        self._feed_list.setMaximumWidth(220)
        splitter.addWidget(self._feed_list)

        self._entry_table = QTableWidget(0, 4)
        self._entry_table.setHorizontalHeaderLabels(["Title", "Feed", "Published", "Status"])
        self._entry_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._entry_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._entry_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._entry_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._entry_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._entry_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._entry_table.setSortingEnabled(True)
        self._entry_table.doubleClicked.connect(self._on_entry_double_click)
        splitter.addWidget(self._entry_table)

        splitter.setSizes([200, 600])
        layout.addWidget(splitter)

    def _setup_statusbar(self) -> None:
        """Create the status bar with stats display."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._stats_label = QLabel("Ready")
        self._statusbar.addPermanentWidget(self._stats_label)

    def update_feeds(self, feeds: list[Feed]) -> None:
        """Refresh the feed list panel.

        Args:
            feeds: Current list of Feed objects.
        """
        self._feed_list.clear()
        self._filter_combo.clear()
        self._filter_combo.addItem("All Feeds")

        for feed in feeds:
            item = QListWidgetItem(feed.name)
            color = QColor(0, 180, 0) if feed.enabled else QColor(150, 150, 150)
            item.setForeground(color)
            self._feed_list.addItem(item)
            self._filter_combo.addItem(feed.name)

    def add_entries(self, new_entries: list[FeedEntry]) -> None:
        """Add new entries to the table and update stats.

        Args:
            new_entries: List of new FeedEntry objects to display.
        """
        self.entries.extend(new_entries)
        self._entries_today += len(new_entries)
        self._refresh_table()
        self._update_stats()
        self._save_entries_store()

    def _refresh_table(self) -> None:
        """Rebuild the entry table from current entries and filter."""
        current_filter = self._filter_combo.currentText()
        filtered = self.entries
        if current_filter != "All Feeds":
            filtered = [
                e for e in self.entries
                if self._feed_name_for(e.feed_url) == current_filter
            ]

        self._entry_table.setSortingEnabled(False)
        self._entry_table.setRowCount(len(filtered))
        for row, entry in enumerate(reversed(filtered)):
            self._entry_table.setItem(row, 0, QTableWidgetItem(entry.title))
            self._entry_table.setItem(
                row, 1, QTableWidgetItem(self._feed_name_for(entry.feed_url))
            )
            self._entry_table.setItem(row, 2, QTableWidgetItem(entry.published))
            status = "Seen" if entry.seen else "New"
            self._entry_table.setItem(row, 3, QTableWidgetItem(status))
        self._entry_table.setSortingEnabled(True)

    def _feed_name_for(self, url: str) -> str:
        """Look up a feed's display name by URL.

        Args:
            url: The feed URL.

        Returns:
            The feed name, or the URL if not found.
        """
        for i in range(self._feed_list.count()):
            item = self._feed_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == url:
                return item.text()
        return url

    def update_feed_names_mapping(self, feeds: list[Feed]) -> None:
        """Store feed URL-to-name mapping in list items' user data.

        Args:
            feeds: Current list of feeds.
        """
        for i, feed in enumerate(feeds):
            if i < self._feed_list.count():
                item = self._feed_list.item(i)
                if item:
                    item.setData(Qt.ItemDataRole.UserRole, feed.url)

    def record_error(self) -> None:
        """Increment the error counter and update stats display."""
        self._errors_today += 1
        self._update_stats()

    def set_last_poll_time(self, time_str: str) -> None:
        """Update the last poll time display.

        Args:
            time_str: Formatted time string.
        """
        self._last_poll_time = time_str
        self._update_stats()

    def _update_stats(self) -> None:
        """Refresh the status bar stats text."""
        parts = [
            f"Entries today: {self._entries_today}",
            f"Errors today: {self._errors_today}",
        ]
        if self._last_poll_time:
            parts.append(f"Last poll: {self._last_poll_time}")
        if self._is_paused:
            parts.append("PAUSED")
        self._stats_label.setText("  |  ".join(parts))

    def _apply_filter(self, _text: str) -> None:
        """Re-filter the entry table when filter selection changes.

        Args:
            _text: The selected filter text (unused directly).
        """
        self._refresh_table()

    def _on_entry_double_click(self, index: object) -> None:
        """Open the entry link in the default browser on double-click.

        Args:
            index: The model index of the double-clicked row.
        """
        row = index.row()  # type: ignore[union-attr]
        current_filter = self._filter_combo.currentText()
        filtered = self.entries
        if current_filter != "All Feeds":
            filtered = [
                e for e in self.entries
                if self._feed_name_for(e.feed_url) == current_filter
            ]

        reversed_filtered = list(reversed(filtered))
        if 0 <= row < len(reversed_filtered):
            entry = reversed_filtered[row]
            if entry.link:
                from PySide6.QtCore import QUrl

                QDesktopServices.openUrl(QUrl(entry.link))
                entry.seen = True
                self._save_entries_store()
                self._refresh_table()

    def _on_pause_clicked(self) -> None:
        """Toggle the pause state and emit the signal."""
        self._is_paused = not self._is_paused
        self._pause_action.setText("Resume" if self._is_paused else "Pause")
        self._update_stats()
        self.pause_requested.emit()

    def set_paused(self, paused: bool) -> None:
        """Update the UI to reflect pause state.

        Args:
            paused: Whether polling is paused.
        """
        self._is_paused = paused
        self._pause_action.setText("Resume" if paused else "Pause")
        self._update_stats()

    def reset_daily_stats(self) -> None:
        """Reset the daily entry and error counters."""
        self._entries_today = 0
        self._errors_today = 0
        self._update_stats()

    def get_last_poll_display(self) -> str:
        """Format the current time for display as last poll time.

        Returns:
            Formatted time string.
        """
        return datetime.datetime.now(tz=datetime.UTC).strftime("%H:%M:%S UTC")
