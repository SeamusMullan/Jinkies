"""Main dashboard window for Jinkies feed monitor.

Displays a feed list, entry table, and stats bar. Provides toolbar
actions for managing feeds and controlling polling.
"""

from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
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
    QMenu,
    QMessageBox,
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
        remove_feed_requested(list): Emitted with the list of zero-based indices
            of the feeds to remove when the Remove Feed button is clicked.
        settings_requested: Emitted when the Settings button is clicked.
        pause_requested: Emitted when Pause/Resume is toggled.

    Attributes:
        entries: List of currently displayed FeedEntry objects.
        max_entries: Maximum number of entries to keep; oldest are evicted when
            this limit is exceeded.
    """

    add_feed_requested = Signal()
    #: Emitted with a list of zero-based indices of the feeds to remove.
    remove_feed_requested = Signal(list)
    import_feeds_requested = Signal()
    settings_requested = Signal()
    pause_requested = Signal()
    #: Emitted when entries should be marked as seen.  The argument is either
    #: ``None`` (mark all feeds) or a feed *name* string (scope to one feed).
    mark_all_seen_requested = Signal(object)

    def __init__(self) -> None:
        """Initialize the dashboard window."""
        super().__init__()
        self.setWindowTitle("Jinkies — Feed Monitor")
        self.setMinimumSize(800, 500)
        self.entries: list[FeedEntry] = []
        self.max_entries: int = 10_000

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
        self._feed_errors: dict[str, str] = {}
        self._feed_backoff: dict[str, int] = {}  # url → backoff seconds

        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()

        # If one or more midnights passed while the app was closed, the stored
        # stats_date will be before today.  Reset now so the counters are always
        # accurate for the current calendar day, then kick off the timer for
        # subsequent midnight crossings during this session.
        if self._stats_date < datetime.date.today():
            self.reset_daily_stats()
        self._schedule_daily_reset()

    def _update_entries_store(self) -> None:
        """Updates class entries using local store file.

        Also loads the persisted stats_date so that missed-midnight resets
        (i.e. when the app was closed over midnight) can be detected on startup.
        Entries exceeding :attr:`max_entries` are trimmed (oldest first) after
        loading so the in-memory list always respects the configured limit.
        """
        with open(self._entries_store_location) as store:
            try:
                data = json.load(store)
            except Exception:
                data = {"entries": []}

            # Create a new FeedEntry from the json and append to self.entries
            # Since this happens in Dashboard constructor, we don't need any deduplation logic.
            for entry_data in data["entries"]:
                self.entries.append(FeedEntry.from_dict(entry_data))

            # Enforce the cap immediately so memory usage is bounded even when
            # the store was written with a larger limit or is externally edited.
            if len(self.entries) > self.max_entries:
                self.entries = self.entries[-self.max_entries:]

            # Restore the date the daily counters were last reset.  If absent
            # (e.g. first run after upgrade), default to "yesterday" so that the
            # startup check below will immediately trigger a reset and save today.
            raw_date = data.get("stats_date")
            try:
                self._stats_date: datetime.date = datetime.date.fromisoformat(raw_date)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                self._stats_date = datetime.date.today() - datetime.timedelta(days=1)

    def _save_entries_store(self) -> None:
        """Updates the local store file with the class' entries list and stats_date."""
        with open(self._entries_store_location, "w") as store:
            json.dump(
                {
                    "entries": [e.to_dict() for e in self.entries],
                    "stats_date": self._stats_date.isoformat(),
                },
                store,
            )

    def _setup_toolbar(self) -> None:
        """Create the main toolbar with action buttons."""
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._add_feed_action = toolbar.addAction("Add Feed")
        self._add_feed_action.setToolTip("Add a new RSS/Atom feed to monitor")
        self._add_feed_action.triggered.connect(self.add_feed_requested.emit)

        self._remove_feed_action = toolbar.addAction("Remove Feed")
        self._remove_feed_action.setToolTip("Remove the selected feed(s)")
        self._remove_feed_action.triggered.connect(self._on_remove_feed_clicked)

        self._import_feeds_action = toolbar.addAction("Import Feeds")
        self._import_feeds_action.setToolTip("Import feeds from an OPML file")
        self._import_feeds_action.triggered.connect(self.import_feeds_requested.emit)

        toolbar.addSeparator()

        self._settings_action = toolbar.addAction("Settings")
        self._settings_action.setToolTip("Open application settings")
        self._settings_action.triggered.connect(self.settings_requested.emit)

        toolbar.addSeparator()

        self._pause_action = toolbar.addAction("Pause")
        self._pause_action.setToolTip("Pause or resume feed polling")
        self._pause_action.triggered.connect(self._on_pause_clicked)

        toolbar.addSeparator()

        self._mark_all_seen_action = toolbar.addAction("Mark All Seen")
        self._mark_all_seen_action.setToolTip("Mark all current entries as seen")
        self._mark_all_seen_action.triggered.connect(self._on_mark_all_seen_clicked)

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
        self._feed_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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
        self._entry_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._entry_table.customContextMenuRequested.connect(self._on_entry_table_context_menu)
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
            item.setData(Qt.ItemDataRole.UserRole, feed.url)
            item.setData(Qt.ItemDataRole.UserRole + 1, feed.enabled)
            if feed.url in self._feed_errors:
                item.setForeground(QColor(200, 50, 50))
                item.setToolTip(f"Error: {self._feed_errors[feed.url]}")
            else:
                color = QColor(0, 180, 0) if feed.enabled else QColor(150, 150, 150)
                item.setForeground(color)
            self._feed_list.addItem(item)
            self._filter_combo.addItem(feed.name)

    def add_entries(self, new_entries: list[FeedEntry]) -> None:
        """Add new entries to the table and update stats.

        Oldest entries are evicted when :attr:`max_entries` is exceeded.

        Args:
            new_entries: List of new FeedEntry objects to display.
        """
        existing_ids = {e.entry_id for e in self.entries}
        unique_new = [e for e in new_entries if e.entry_id not in existing_ids]
        self.entries.extend(unique_new)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        self._entries_today += len(unique_new)
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

    def mark_feed_error(self, url: str, error: str) -> None:
        """Mark a feed as errored in the feed list and show a status bar message.

        Changes the feed list item to red and adds a tooltip with the error
        message.  A transient message is also shown in the status bar.

        Args:
            url: The feed URL that produced the error.
            error: The error message to display.
        """
        self._feed_errors[url] = error
        self._update_feed_item_state(url)
        self._statusbar.showMessage(f"Feed error: {error}", 8000)

    def mark_feed_backoff(self, url: str, backoff_secs: int) -> None:
        """Record that a feed is in backoff and update its list-item tooltip.

        The backoff delay is appended to the existing error tooltip so the
        user can see when the next retry is scheduled.

        Args:
            url: The feed URL that is in a backoff state.
            backoff_secs: Seconds until the next retry attempt.
        """
        self._feed_backoff[url] = backoff_secs
        self._update_feed_item_state(url)

    def clear_feed_error(self, url: str) -> None:
        """Remove the error and backoff state for a feed, restoring its normal appearance.

        Restores the feed list item to green and clears any error or backoff
        tooltip.

        Args:
            url: The feed URL whose error state should be cleared.
        """
        if url not in self._feed_errors and url not in self._feed_backoff:
            return
        self._feed_errors.pop(url, None)
        self._feed_backoff.pop(url, None)
        self._update_feed_item_state(url)

    def _update_feed_item_state(self, url: str) -> None:
        """Update the colour and tooltip of the feed list item for *url*.

        When the feed has an active error the item is coloured red.  If a
        backoff delay is also recorded the tooltip includes a human-readable
        "Retrying in ~N min" note so the user can see when the next attempt
        is scheduled.

        Args:
            url: The feed URL whose list item should be updated.
        """
        for i in range(self._feed_list.count()):
            item = self._feed_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == url:
                if url in self._feed_errors:
                    item.setForeground(QColor(200, 50, 50))
                    tooltip = f"Error: {self._feed_errors[url]}"
                    backoff = self._feed_backoff.get(url, 0)
                    if backoff:
                        mins = max(1, round(backoff / 60))
                        tooltip += f"\nRetrying in ~{mins} min (backoff)"
                    item.setToolTip(tooltip)
                else:
                    enabled = item.data(Qt.ItemDataRole.UserRole + 1)
                    color = QColor(0, 180, 0) if enabled else QColor(150, 150, 150)
                    item.setForeground(color)
                    item.setToolTip("")
                break

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

        Marks the entry as seen and immediately persists the updated state
        to disk, so the seen status survives application restarts even if
        the next periodic save has not yet occurred.

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
            if entry.link and (entry.link.startswith("http") or entry.link.startswith("https")):
                from PySide6.QtCore import QUrl

                QDesktopServices.openUrl(QUrl(entry.link))
                entry.seen = True
                self._save_entries_store()
                self._refresh_table()

    def _on_entry_table_context_menu(self, pos: QPoint) -> None:
        """Show a right-click context menu for the entry table.

        The menu provides two actions:

        * **Mark Selected as Seen** — marks only the currently highlighted rows.
        * **Mark All as Seen** — marks all entries in the current filter scope.
          When the scope is "All Feeds" the label is appended with "…" to signal
          that a confirmation dialog will follow.

        Args:
            pos: The viewport-relative position of the right-click.
        """
        menu = QMenu(self)

        mark_selected_action = menu.addAction("Mark Selected as Seen")
        mark_selected_action.triggered.connect(self._mark_selected_seen)

        menu.addSeparator()

        current_filter = self._filter_combo.currentText()
        if current_filter == "All Feeds":
            mark_all_label = "Mark All as Seen…"
        else:
            mark_all_label = f'Mark All in "{current_filter}" as Seen'
        mark_all_action = menu.addAction(mark_all_label)
        mark_all_action.triggered.connect(self._on_mark_all_seen_clicked)

        menu.exec(self._entry_table.viewport().mapToGlobal(pos))

    def _on_mark_all_seen_clicked(self) -> None:
        """Handle the "Mark All Seen" toolbar button and context-menu action.

        When the filter is set to "All Feeds" a confirmation dialog is shown
        first to prevent accidental bulk-marking.  When a specific feed is
        selected the action is applied immediately without a prompt.
        """
        current_filter = self._filter_combo.currentText()
        if current_filter == "All Feeds":
            reply = QMessageBox.question(
                self,
                "Mark All as Seen",
                "Mark all entries across all feeds as seen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._do_mark_all_seen(None)
        else:
            self._do_mark_all_seen(current_filter)

    def _do_mark_all_seen(self, feed_name: str | None) -> None:
        """Mark entries as seen, optionally scoped to a single feed.

        Args:
            feed_name: The display name of the feed whose entries should be
                marked as seen.  Pass ``None`` to mark entries across all feeds.
        """
        changed = False
        for entry in self.entries:
            in_scope = feed_name is None or self._feed_name_for(entry.feed_url) == feed_name
            if in_scope and not entry.seen:
                entry.seen = True
                changed = True

        if changed:
            self._save_entries_store()
            self._refresh_table()

    def _mark_selected_seen(self) -> None:
        """Mark the currently selected table rows as seen.

        Resolves which :class:`~src.models.FeedEntry` objects correspond to the
        selected row indices (accounting for the reversed display order and the
        active filter) and marks each unseen one as seen before persisting.
        """
        current_filter = self._filter_combo.currentText()
        filtered = self.entries
        if current_filter != "All Feeds":
            filtered = [
                e for e in self.entries
                if self._feed_name_for(e.feed_url) == current_filter
            ]

        reversed_filtered = list(reversed(filtered))
        selected_rows = sorted({idx.row() for idx in self._entry_table.selectedIndexes()})

        changed = False
        for row in selected_rows:
            if 0 <= row < len(reversed_filtered):
                entry = reversed_filtered[row]
                if not entry.seen:
                    entry.seen = True
                    changed = True

        if changed:
            self._save_entries_store()
            self._refresh_table()

    def _on_remove_feed_clicked(self) -> None:
        """Emit remove_feed_requested with the indices of all selected feeds.

        Collects all selected rows from the feed list and emits
        :attr:`remove_feed_requested` with a sorted list of those indices so
        callers never need to access the private ``_feed_list`` widget directly.
        """
        indices = sorted({idx.row() for idx in self._feed_list.selectedIndexes()})
        if indices:
            self.remove_feed_requested.emit(indices)

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
        """Reset the daily entry and error counters.

        Also records today's date in the store so that, on the next app launch,
        the startup check can detect any missed midnight resets.
        """
        self._entries_today = 0
        self._errors_today = 0
        self._stats_date = datetime.date.today()
        self._save_entries_store()
        self._update_stats()

    def _schedule_daily_reset(self) -> None:
        """Schedule reset_daily_stats to fire at the next local midnight.

        Calculates milliseconds until the next midnight by advancing from
        today's midnight to avoid DST-related off-by-one-hour issues.
        Uses a single-shot QTimer; once it fires, _on_daily_reset reschedules
        it so the counters are cleared every day at midnight.
        """
        now = datetime.datetime.now()
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_midnight = today_midnight + datetime.timedelta(days=1)
        ms_until_midnight = int((tomorrow_midnight - now).total_seconds() * 1000)
        # QTimer accepts at most 2^31-1 ms; clamp to ensure validity
        ms_until_midnight = max(0, min(ms_until_midnight, 2_147_483_647))
        self._daily_reset_timer = QTimer(self)
        self._daily_reset_timer.setSingleShot(True)
        self._daily_reset_timer.timeout.connect(self._on_daily_reset)
        self._daily_reset_timer.start(ms_until_midnight)

    def _on_daily_reset(self) -> None:
        """Reset daily stats and reschedule for the next midnight."""
        self.reset_daily_stats()
        self._schedule_daily_reset()

