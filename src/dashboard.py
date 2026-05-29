"""Main dashboard window for Jinkies feed monitor.

Displays a feed list, entry table, and stats bar. Provides toolbar
actions for managing feeds and controlling polling.
"""

from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDesktopServices, QKeyEvent, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

import qtawesome as qta

from src.config import get_config_dir
from src.models import FeedEntry
from src.notifier import jenkins_status

if TYPE_CHECKING:
    from src.models import Feed


class _RowColorDelegate(QStyledItemDelegate):
    """Paints row background from Qt.BackgroundRole, bypassing QSS overrides."""

    def initStyleOption(self, option: QStyleOptionViewItem, index: object) -> None:
        super().initStyleOption(option, index)
        bg = index.data(Qt.ItemDataRole.BackgroundRole)  # type: ignore[union-attr]
        if bg is not None:
            from PySide6.QtGui import QBrush
            brush = bg if isinstance(bg, QBrush) else QBrush(bg)
            if brush.color().isValid():
                option.backgroundBrush = brush  # type: ignore[attr-defined]


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
        page_size: Number of read entries shown per page.
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
    #: Emitted with the new ordered list of Feed objects after a drag-drop reorder.
    reorder_feeds_requested = Signal(list)
    #: Emitted with the total unread count each time the table is refreshed.
    unread_count_changed = Signal(int)
    #: Emitted when the user requests the feed health dashboard.
    health_requested = Signal()

    def __init__(self) -> None:
        """Initialize the dashboard window."""
        super().__init__()
        self.setWindowTitle("Jinkies — Feed Monitor")
        self.setMinimumSize(800, 500)
        self.entries: list[FeedEntry] = []
        self._feeds: list[Feed] = []
        self.max_entries: int = 10_000
        self.page_size: int = 100
        self._current_page: int = 0
        self._unread_collapsed: bool = False
        self._read_collapsed: bool = False
        self._unread_count: int = 0
        self._read_count: int = 0

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
        self._feed_groups: dict[str, list[Feed]] = {}

        self._active_table: QTableWidget | None = None

        self._setup_menubar()
        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()

        # Populate the table with any entries loaded from disk so they are
        # visible immediately on startup rather than waiting for the first poll.
        self._refresh_table()

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

    def _setup_menubar(self) -> None:
        """Create the menubar with File and View menus."""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        self._import_feeds_menu_action = file_menu.addAction("Import Feeds…")
        self._import_feeds_menu_action.setShortcut(QKeySequence("Ctrl+I"))
        self._import_feeds_menu_action.setToolTip("Import feeds from an OPML file")
        self._import_feeds_menu_action.triggered.connect(self.import_feeds_requested.emit)

        self._export_feeds_action = file_menu.addAction("Export Feeds…")
        self._export_feeds_action.setShortcut(QKeySequence("Ctrl+E"))
        self._export_feeds_action.setToolTip("Export current feeds as an OPML file")
        self._export_feeds_action.triggered.connect(self._on_export_feeds)

        view_menu = menubar.addMenu("&View")
        self._toggle_preview_action = view_menu.addAction("Toggle Preview Pane")
        self._toggle_preview_action.setCheckable(True)
        self._toggle_preview_action.setChecked(True)
        self._toggle_preview_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self._toggle_preview_action.setToolTip("Show or hide the entry preview pane")
        self._toggle_preview_action.toggled.connect(self._on_toggle_preview)

        view_menu.addSeparator()
        self._feed_health_action = view_menu.addAction("Feed Health…")
        self._feed_health_action.setShortcut(QKeySequence("Ctrl+Shift+H"))
        self._feed_health_action.setToolTip("Show per-feed health statistics")
        self._feed_health_action.triggered.connect(self.health_requested.emit)

    def _setup_toolbar(self) -> None:
        """Create the main toolbar with action buttons."""
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._add_feed_action = toolbar.addAction(
            qta.icon("fa6s.plus", color="#1a3a5c"), "Add Feed"
        )
        self._add_feed_action.setShortcut(QKeySequence.StandardKey.New)
        self._add_feed_action.setToolTip("Add a new RSS/Atom feed to monitor")
        self._add_feed_action.triggered.connect(self.add_feed_requested.emit)

        self._remove_feed_action = toolbar.addAction(
            qta.icon("fa6s.minus", color="#1a3a5c"), "Remove Feed"
        )
        self._remove_feed_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self._remove_feed_action.setToolTip("Remove the selected feed(s)")
        self._remove_feed_action.triggered.connect(self._on_remove_feed_clicked)

        self._import_feeds_action = toolbar.addAction(
            qta.icon("fa6s.file-import", color="#1a3a5c"), "Import Feeds"
        )
        self._import_feeds_action.setShortcut(QKeySequence("Ctrl+I"))
        self._import_feeds_action.setToolTip("Import feeds from an OPML file")
        self._import_feeds_action.triggered.connect(self.import_feeds_requested.emit)

        toolbar.addSeparator()

        self._settings_action = toolbar.addAction(
            qta.icon("fa6s.gear", color="#1a3a5c"), "Settings"
        )
        self._settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self._settings_action.setToolTip("Open application settings")
        self._settings_action.triggered.connect(self.settings_requested.emit)

        toolbar.addSeparator()

        self._pause_action = toolbar.addAction(
            qta.icon("fa6s.pause", color="#1a3a5c"), "Pause"
        )
        self._pause_action.setShortcut(QKeySequence("Ctrl+P"))
        self._pause_action.setToolTip("Pause or resume feed polling")
        self._pause_action.triggered.connect(self._on_pause_clicked)

        toolbar.addSeparator()

        self._mark_all_seen_action = toolbar.addAction(
            qta.icon("fa6s.check-double", color="#1a3a5c"), "Mark All Seen"
        )
        self._mark_all_seen_action.setToolTip("Mark all current entries as seen")
        self._mark_all_seen_action.triggered.connect(self._on_mark_all_seen_clicked)

    def _make_table(self) -> QTableWidget:
        """Create a standard entry table widget."""
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["★", "Title", "Feed", "Published", "Status"])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.resizeSection(0, 28)
        header.resizeSection(1, 400)
        header.resizeSection(2, 140)
        header.resizeSection(3, 120)
        header.resizeSection(4, 60)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(True)
        table.setItemDelegate(_RowColorDelegate(table))
        table.doubleClicked.connect(lambda idx, t=table: self._on_entry_double_click(idx, t))
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, t=table: self._on_entry_table_context_menu(pos, t)
        )
        return table

    def _setup_central(self) -> None:
        """Create the central widget with feed list, entry tables, and filter."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self._filter_combo = QComboBox()
        self._filter_combo.addItem("All Feeds")
        self._filter_combo.currentTextChanged.connect(self._on_feed_filter_changed)
        filter_layout.addWidget(self._filter_combo)

        filter_layout.addWidget(QLabel("Search:"))
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter entries…")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._refresh_table)
        filter_layout.addWidget(self._search_input)

        self._search_content_check = QCheckBox("Include content")
        self._search_content_check.setToolTip("Also search entry summaries/content when filtering")
        self._search_content_check.toggled.connect(self._refresh_table)
        filter_layout.addWidget(self._search_content_check)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Splitter: feed list | right pane
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._feed_list = QListWidget()
        self._feed_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._feed_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._feed_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._feed_list.model().rowsMoved.connect(self._on_feed_reordered)
        self._splitter.addWidget(self._feed_list)

        # Right pane: vertical splitter with (top) tables pane and (bottom) preview pane
        self._right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Tables pane: unread section then read section
        tables_pane = QWidget()
        right_layout = QVBoxLayout(tables_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._unread_header_btn = QPushButton("▼  Unread (0)")
        self._unread_header_btn.setProperty("sectionHeader", True)
        self._unread_header_btn.setFixedHeight(26)
        self._unread_header_btn.clicked.connect(self._toggle_unread)
        right_layout.addWidget(self._unread_header_btn)

        self._unread_table = self._make_table()
        right_layout.addWidget(self._unread_table, stretch=1)

        self._read_header_btn = QPushButton("▼  Read (0)")
        self._read_header_btn.setProperty("sectionHeader", True)
        self._read_header_btn.setFixedHeight(26)
        self._read_header_btn.clicked.connect(self._toggle_read)
        right_layout.addWidget(self._read_header_btn)

        self._read_table = self._make_table()
        right_layout.addWidget(self._read_table, stretch=2)

        self._right_splitter.addWidget(tables_pane)

        # Preview pane
        self._preview_pane = QTextEdit()
        self._preview_pane.setReadOnly(True)
        self._preview_pane.setPlaceholderText("Select an entry to preview")
        self._right_splitter.addWidget(self._preview_pane)
        self._right_splitter.setSizes([500, 200])

        # Connect selection signals to update preview
        self._unread_table.selectionModel().selectionChanged.connect(
            lambda: self._on_table_selection_changed(self._unread_table)
        )
        self._read_table.selectionModel().selectionChanged.connect(
            lambda: self._on_table_selection_changed(self._read_table)
        )

        # Track which table most recently received focus for keyboard navigation
        self._unread_table.installEventFilter(self)
        self._read_table.installEventFilter(self)

        # Tab focus order: feed list → unread table → read table
        self.setTabOrder(self._feed_list, self._unread_table)
        self.setTabOrder(self._unread_table, self._read_table)

        self._splitter.addWidget(self._right_splitter)
        self._splitter.setSizes([200, 600])
        layout.addWidget(self._splitter)

        # Pagination controls (for read table only)
        pagination_layout = QHBoxLayout()
        pagination_layout.addStretch()
        self._prev_page_btn = QPushButton("← Prev")
        self._prev_page_btn.clicked.connect(self._on_prev_page)
        pagination_layout.addWidget(self._prev_page_btn)
        self._page_label = QLabel("Page 1 of 1")
        pagination_layout.addWidget(self._page_label)
        self._next_page_btn = QPushButton("Next →")
        self._next_page_btn.clicked.connect(self._on_next_page)
        pagination_layout.addWidget(self._next_page_btn)
        pagination_layout.addStretch()
        self._pagination_widget = QWidget()
        self._pagination_widget.setLayout(pagination_layout)
        self._pagination_widget.setFixedHeight(36)
        self._pagination_widget.setVisible(False)
        layout.addWidget(self._pagination_widget)

    def _setup_statusbar(self) -> None:
        """Create the status bar with stats display."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._stats_label = QLabel("Ready")
        self._statusbar.addPermanentWidget(self._stats_label)

    def save_layout_state(self) -> dict:
        """Return splitter sizes and column widths for persistence."""
        header = self._unread_table.horizontalHeader()
        return {
            "splitter_sizes": self._splitter.sizes(),
            "right_splitter_sizes": self._right_splitter.sizes(),
            "preview_visible": self._preview_pane.isVisible(),
            "column_widths": [header.sectionSize(i) for i in range(self._unread_table.columnCount())],
            "unread_collapsed": self._unread_collapsed,
            "read_collapsed": self._read_collapsed,
        }

    def restore_layout_state(self, state: dict) -> None:
        """Apply previously saved splitter sizes and column widths."""
        sizes = state.get("splitter_sizes")
        if sizes and len(sizes) == 2:
            self._splitter.setSizes(sizes)
        right_sizes = state.get("right_splitter_sizes")
        if right_sizes and len(right_sizes) == 2:
            self._right_splitter.setSizes(right_sizes)
        preview_visible = state.get("preview_visible", True)
        self._preview_pane.setVisible(preview_visible)
        self._toggle_preview_action.setChecked(preview_visible)
        widths = state.get("column_widths")
        if widths:
            for table in (self._unread_table, self._read_table):
                header = table.horizontalHeader()
                if len(widths) == table.columnCount():
                    for i, w in enumerate(widths):
                        header.resizeSection(i, w)
        if state.get("unread_collapsed"):
            self._unread_collapsed = True
            self._unread_table.setVisible(False)
            self._update_section_header(
                self._unread_header_btn, "Unread", self._unread_count, True
            )
        if state.get("read_collapsed"):
            self._read_collapsed = True
            self._read_table.setVisible(False)
            self._update_section_header(
                self._read_header_btn, "Read", self._read_count, True
            )

    def _update_section_header(
        self, btn: QPushButton, label: str, count: int, collapsed: bool
    ) -> None:
        arrow = "▶" if collapsed else "▼"
        btn.setText(f"{arrow}  {label} ({count})")

    def _toggle_unread(self) -> None:
        self._unread_collapsed = not self._unread_collapsed
        self._unread_table.setVisible(not self._unread_collapsed)
        self._update_section_header(
            self._unread_header_btn, "Unread", self._unread_count, self._unread_collapsed
        )

    def _toggle_read(self) -> None:
        self._read_collapsed = not self._read_collapsed
        self._read_table.setVisible(not self._read_collapsed)
        self._update_section_header(
            self._read_header_btn, "Read", self._read_count, self._read_collapsed
        )

    def _on_table_selection_changed(self, table: QTableWidget) -> None:
        """Update the preview pane when the selection changes in a table."""
        selected = table.selectedItems()
        if not selected:
            return
        row = table.currentRow()
        entry = self._entry_at(table, row)
        self._update_preview(entry)

    def _update_preview(self, entry: object) -> None:
        """Populate the preview pane with the entry's summary, or clear it."""
        if entry is None:
            self._preview_pane.clear()
            return
        summary = getattr(entry, "summary", "") or ""
        if "<" in summary:
            self._preview_pane.setHtml(summary)
        else:
            self._preview_pane.setPlainText(summary)

    def _on_toggle_preview(self, checked: bool) -> None:
        """Show or hide the preview pane based on the menu action state."""
        self._preview_pane.setVisible(checked)

    def update_feeds(self, feeds: list[Feed]) -> None:
        """Refresh the feed list panel.

        Feeds are grouped by their :attr:`~src.models.Feed.group` field.
        Group headers are shown as bold, non-interactive items in the list.
        Feeds without a group appear at the bottom under no header (unless
        all feeds are ungrouped, in which case no header is shown at all).

        Args:
            feeds: Current list of Feed objects.
        """
        self._feeds = list(feeds)
        self._feed_list.clear()
        self._filter_combo.clear()
        self._filter_combo.addItem("All Feeds")
        self._filter_combo.addItem("⭐ Starred")

        # Build group → feed mapping (preserving insertion order).
        self._feed_groups = {}
        ungrouped: list[Feed] = []
        for feed in feeds:
            if feed.group:
                self._feed_groups.setdefault(feed.group, []).append(feed)
            else:
                ungrouped.append(feed)

        all_ungrouped = not self._feed_groups

        def _add_feed_item(feed: Feed, indent: bool) -> None:
            label = ("  " + feed.name) if indent else feed.name
            item = QListWidgetItem(label)
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

        # Add group-header items and their feeds to the filter combo.
        for group_name, group_feeds in self._feed_groups.items():
            # Group header — bold, not selectable
            header_item = QListWidgetItem(f"  {group_name}")
            font = header_item.font()
            font.setBold(True)
            header_item.setFont(font)
            header_item.setFlags(
                header_item.flags()
                & ~Qt.ItemFlag.ItemIsSelectable
                & ~Qt.ItemFlag.ItemIsEnabled
            )
            self._feed_list.addItem(header_item)
            # Group entry in filter combo
            self._filter_combo.addItem(f"\U0001f4c1 {group_name}")
            for feed in group_feeds:
                _add_feed_item(feed, indent=True)

        # Ungrouped feeds
        for feed in ungrouped:
            _add_feed_item(feed, indent=not all_ungrouped)

    def add_entries(self, new_entries: list[FeedEntry]) -> None:
        """Add new entries to the table and update stats.

        Only truly new entries are inserted; duplicates are silently ignored.
        Oldest entries are evicted when :attr:`max_entries` is exceeded.

        Args:
            new_entries: List of new FeedEntry objects to display.
        """
        existing_ids = {e.entry_id for e in self.entries}
        unique_new = [e for e in new_entries if e.entry_id not in existing_ids]
        if not unique_new:
            return

        total_after = len(self.entries) + len(unique_new)
        num_evicted = max(0, total_after - self.max_entries)
        evicted = self.entries[:num_evicted] if num_evicted > 0 else []  # noqa: F841

        self.entries.extend(unique_new)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

        self._entries_today += len(unique_new)
        self._refresh_table()
        self._update_stats()
        self._save_entries_store()

    def _apply_row_style(self, row: int, entry: FeedEntry, table: QTableWidget) -> str:
        """Apply Jenkins status color to a table row. Returns status text."""
        result = jenkins_status(entry.title)
        if result:
            kw, (r, g, b) = result
            alpha = 60 if entry.seen else 110
            bg = QColor(r, g, b, alpha)
            # Saturated foreground for the status cell so it reads clearly
            fg = QColor(r, g, b).darker(140)
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    item.setBackground(bg)
            status_item = table.item(row, 4)
            if status_item:
                status_item.setForeground(fg)
            return kw
        return "Seen" if entry.seen else "New"

    def _populate_table(self, table: QTableWidget, entries: list[FeedEntry]) -> None:
        """Fill *table* with *entries*, applying row styles."""
        table.setSortingEnabled(False)
        table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            # Column 0: star indicator
            star_item = QTableWidgetItem("★" if entry.starred else "☆")
            star_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if entry.starred:
                star_item.setForeground(QColor("#f5c518"))
            else:
                star_item.setForeground(QColor("#888888"))
            star_item.setFlags(star_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 0, star_item)
            # Columns 1-4: title, feed, published, status
            table.setItem(row, 1, QTableWidgetItem(entry.title))
            table.setItem(row, 2, QTableWidgetItem(self._feed_name_for(entry.feed_url)))
            table.setItem(row, 3, QTableWidgetItem(entry.published))
            table.setItem(row, 4, QTableWidgetItem(""))
            status = self._apply_row_style(row, entry, table)
            table.item(row, 4).setText(status)
        table.setSortingEnabled(True)

    def _get_display_entries(self) -> list[FeedEntry]:
        """Return entries filtered by the active feed filter and search text.

        Applies the feed combo filter first, then narrows further by the
        search input.  When "Include content" is checked the search also
        matches against each entry's :attr:`~src.models.FeedEntry.summary`.

        Returns:
            Filtered list of :class:`~src.models.FeedEntry` objects in their
            original (chronological) order.  The caller is responsible for
            reversing if newest-first display is required.
        """
        current_filter = self._filter_combo.currentText()
        filtered: list[FeedEntry] = self.entries
        _GROUP_PREFIX = "\U0001f4c1 "
        if current_filter == "⭐ Starred":
            filtered = [e for e in filtered if e.starred]
        elif current_filter.startswith(_GROUP_PREFIX):
            group_name = current_filter[len(_GROUP_PREFIX):]
            group_urls = {f.url for f in self._feed_groups.get(group_name, [])}
            filtered = [e for e in filtered if e.feed_url in group_urls]
        elif current_filter != "All Feeds":
            filtered = [
                e for e in filtered
                if self._feed_name_for(e.feed_url) == current_filter
            ]

        search = self._search_input.text().strip().lower()
        if search:
            include_content = self._search_content_check.isChecked()
            filtered = [
                e for e in filtered
                if search in e.title.lower()
                or (include_content and search in e.summary.lower())
            ]

        return filtered

    def _refresh_table(self) -> None:
        """Rebuild both entry tables from current entries, filter, and search."""
        filtered = self._get_display_entries()
        reversed_filtered = list(reversed(filtered))

        unread = [e for e in reversed_filtered if not e.seen]
        read_all = [e for e in reversed_filtered if e.seen]

        self._unread_count = len(unread)
        self._read_count = len(read_all)

        self._populate_table(self._unread_table, unread)
        self._update_section_header(
            self._unread_header_btn, "Unread", self._unread_count, self._unread_collapsed
        )

        # Paginate read table
        total_read = len(read_all)
        total_pages = max(1, -(-total_read // self.page_size))
        self._current_page = max(0, min(self._current_page, total_pages - 1))
        page_offset = self._current_page * self.page_size
        page_read = read_all[page_offset: page_offset + self.page_size]

        self._populate_table(self._read_table, page_read)
        self._update_section_header(
            self._read_header_btn, "Read", self._read_count, self._read_collapsed
        )

        show_pagination = total_read > self.page_size
        self._pagination_widget.setVisible(show_pagination)
        if show_pagination:
            self._page_label.setText(f"Page {self._current_page + 1} of {total_pages}")
            self._prev_page_btn.setEnabled(self._current_page > 0)
            self._next_page_btn.setEnabled(self._current_page < total_pages - 1)

        self.unread_count_changed.emit(self._unread_count)

    def _entry_at(self, table: QTableWidget, row: int) -> FeedEntry | None:
        """Return the FeedEntry corresponding to *row* in *table*."""
        filtered = self._get_display_entries()
        reversed_filtered = list(reversed(filtered))
        if table is self._unread_table:
            entries = [e for e in reversed_filtered if not e.seen]
            return entries[row] if 0 <= row < len(entries) else None
        else:
            entries = [e for e in reversed_filtered if e.seen]
            actual = self._current_page * self.page_size + row
            return entries[actual] if 0 <= actual < len(entries) else None

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

    def _on_feed_filter_changed(self, _text: str) -> None:
        """Reset the search input and re-filter the table when the feed selection changes.

        Clearing the search input when the feed selection changes satisfies the
        acceptance criterion "Filter state resets when feed selection changes".

        Args:
            _text: The newly selected feed name (unused directly).
        """
        self._search_input.blockSignals(True)
        self._search_input.clear()
        self._search_input.blockSignals(False)
        self._current_page = 0
        self._refresh_table()

    def _apply_filter(self, _text: str) -> None:
        """Re-filter the entry table when filter selection changes.

        Args:
            _text: The selected filter text (unused directly).
        """
        self._current_page = 0
        self._refresh_table()

    def _on_prev_page(self) -> None:
        """Navigate to the previous page of read entries."""
        if self._current_page > 0:
            self._current_page -= 1
            self._refresh_table()

    def _on_next_page(self) -> None:
        """Navigate to the next page of read entries."""
        self._current_page += 1
        self._refresh_table()

    def _toggle_star(self, table: QTableWidget, row: int) -> None:
        """Toggle the starred state of the entry at *row* in *table*.

        Args:
            table: The table widget containing the entry.
            row: The row index of the entry to toggle.
        """
        entry = self._entry_at(table, row)
        if entry is None:
            return
        entry.starred = not entry.starred
        star_item = table.item(row, 0)
        if star_item:
            star_item.setText("★" if entry.starred else "☆")
            if entry.starred:
                star_item.setForeground(QColor("#f5c518"))
            else:
                star_item.setForeground(QColor("#888888"))
        self._save_entries_store()

    def _on_entry_double_click(self, index: object, table: QTableWidget) -> None:
        """Open the entry link in the default browser on double-click.

        Double-clicking the star column (column 0) toggles the star instead of
        opening the link.  For all other columns the entry link is opened and the
        entry is marked as seen.

        Args:
            index: The model index of the double-clicked row.
            table: The table widget that was double-clicked.
        """
        row = index.row()  # type: ignore[union-attr]
        col = index.column()  # type: ignore[union-attr]
        if col == 0:
            self._toggle_star(table, row)
            return
        entry = self._entry_at(table, row)
        if entry and entry.link and (entry.link.startswith("http") or entry.link.startswith("https")):
            from PySide6.QtCore import QUrl

            QDesktopServices.openUrl(QUrl(entry.link))
            entry.seen = True
            self._save_entries_store()
            self._refresh_table()

    def _on_entry_table_context_menu(self, pos: QPoint, table: QTableWidget) -> None:
        """Show a right-click context menu for the entry table.

        Args:
            pos: The viewport-relative position of the right-click.
            table: The table widget that was right-clicked.
        """
        menu = QMenu(self)

        toggle_star_action = menu.addAction(
            qta.icon("fa6s.star", color="#f5c518"), "Toggle Star"
        )
        toggle_star_action.triggered.connect(
            lambda: self._toggle_star(table, table.currentRow())
        )

        menu.addSeparator()

        mark_selected_action = menu.addAction(
            qta.icon("fa6s.eye", color="#1a3a5c"), "Mark Selected as Seen"
        )
        mark_selected_action.triggered.connect(lambda: self._mark_selected_seen(table))

        menu.addSeparator()

        current_filter = self._filter_combo.currentText()
        if current_filter == "All Feeds":
            mark_all_label = "Mark All as Seen…"
        else:
            mark_all_label = f'Mark All in "{current_filter}" as Seen'
        mark_all_action = menu.addAction(
            qta.icon("fa6s.check-double", color="#1a3a5c"), mark_all_label
        )
        mark_all_action.triggered.connect(self._on_mark_all_seen_clicked)

        menu.exec(table.viewport().mapToGlobal(pos))

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

    def _mark_selected_seen(self, table: QTableWidget) -> None:
        """Mark the currently selected table rows as seen.

        Args:
            table: The table widget whose selection should be marked seen.
        """
        selected_rows = sorted({idx.row() for idx in table.selectedIndexes()})
        changed = False
        for row in selected_rows:
            entry = self._entry_at(table, row)
            if entry and not entry.seen:
                entry.seen = True
                changed = True

        if changed:
            self._save_entries_store()
            self._refresh_table()

    def _on_export_feeds(self) -> None:
        """Export the current feed list to an OPML file chosen by the user.

        Opens a save-file dialog, then writes an OPML 2.0 document containing
        all currently configured feeds.  A confirmation message is shown on
        success.
        """
        from src.feed_import import export_opml

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Feeds",
            "feeds.opml",
            "OPML Files (*.opml);;All Files (*)",
        )
        if not path:
            return
        try:
            export_opml(self._feeds, path)
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return
        count = len(self._feeds)
        QMessageBox.information(
            self,
            "Export Complete",
            f"Exported {count} feed{'s' if count != 1 else ''} to {path}",
        )

    def _on_remove_feed_clicked(self) -> None:
        """Emit remove_feed_requested with the indices of all selected feeds.

        Collects all selected rows from the feed list and emits
        :attr:`remove_feed_requested` with a sorted list of those indices so
        callers never need to access the private ``_feed_list`` widget directly.
        """
        indices = sorted({idx.row() for idx in self._feed_list.selectedIndexes()})
        if indices:
            self.remove_feed_requested.emit(indices)

    def _on_feed_reordered(self) -> None:
        """Called after a drag-drop reorder in the feed list.

        Rebuilds the ordered Feed list from the current QListWidget row order
        and emits :attr:`reorder_feeds_requested` so the app controller can
        persist the new order and update the poller.
        """
        url_to_feed = {f.url: f for f in self._feeds}
        ordered: list[Feed] = []
        for i in range(self._feed_list.count()):
            item = self._feed_list.item(i)
            if item:
                url = item.data(Qt.ItemDataRole.UserRole)
                feed = url_to_feed.get(url)
                if feed is not None:
                    ordered.append(feed)
        self.reorder_feeds_requested.emit(ordered)

    def _on_pause_clicked(self) -> None:
        """Toggle the pause state and emit the signal."""
        self._is_paused = not self._is_paused
        self._pause_action.setText("Resume" if self._is_paused else "Pause")
        icon_name = "fa6s.play" if self._is_paused else "fa6s.pause"
        self._pause_action.setIcon(qta.icon(icon_name, color="#1a3a5c"))
        self._update_stats()
        self.pause_requested.emit()

    def set_paused(self, paused: bool) -> None:
        """Update the UI to reflect pause state.

        Args:
            paused: Whether polling is paused.
        """
        self._is_paused = paused
        self._pause_action.setText("Resume" if paused else "Pause")
        icon_name = "fa6s.play" if paused else "fa6s.pause"
        self._pause_action.setIcon(qta.icon(icon_name, color="#1a3a5c"))
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

    # ------------------------------------------------------------------
    # Keyboard-first navigation helpers
    # ------------------------------------------------------------------

    def eventFilter(self, watched: object, event: object) -> bool:
        """Track which table last received focus for keyboard navigation."""
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Type.FocusIn:  # type: ignore[union-attr]
            if watched is self._unread_table:
                self._active_table = self._unread_table
            elif watched is self._read_table:
                self._active_table = self._read_table
        return super().eventFilter(watched, event)

    def _open_and_mark_seen(self, table: QTableWidget) -> None:
        """Open the selected entry link in browser and mark it as seen.

        Mirrors the double-click behaviour without requiring a QModelIndex.

        Args:
            table: The table whose current row should be acted on.
        """
        from PySide6.QtCore import QUrl

        row = table.currentRow()
        entry = self._entry_at(table, row)
        if entry and entry.link and (
            entry.link.startswith("http") or entry.link.startswith("https")
        ):
            QDesktopServices.openUrl(QUrl(entry.link))
            entry.seen = True
            self._save_entries_store()
            self._refresh_table()

    def _mark_entry_unseen(self, table: QTableWidget) -> None:
        """Mark the currently selected entry as unseen and refresh.

        Args:
            table: The table whose current row should be marked unseen.
        """
        row = table.currentRow()
        entry = self._entry_at(table, row)
        if entry and entry.seen:
            entry.seen = False
            self._save_entries_store()
            self._refresh_table()

    def _move_selection(self, table: QTableWidget, delta: int) -> None:
        """Move the table selection by *delta* rows (+1 down, -1 up).

        Args:
            table: The table to navigate.
            delta: Direction to move (+1 for down, -1 for up).
        """
        row_count = table.rowCount()
        if row_count == 0:
            return
        current = table.currentRow()
        new_row = max(0, min(row_count - 1, current + delta))
        table.setCurrentCell(new_row, table.currentColumn())

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        """Handle vim-style keyboard shortcuts for navigating feed entries.

        Shortcuts:
            J / Down  — move selection down in the active table
            K / Up    — move selection up in the active table
            Enter     — open selected entry in browser and mark as seen
            Space     — mark selected entry as seen and advance to next row
            U         — mark selected entry as unseen (move back to unread)
            S         — toggle star/bookmark on the selected entry
            /         — focus the search bar (only when search bar is not active)
        """
        key = event.key()
        search_has_focus = self._search_input.hasFocus()

        # Determine the target table: prefer the one with Qt keyboard focus,
        # falling back to _active_table, then _unread_table.
        if self._unread_table.hasFocus():
            target = self._unread_table
        elif self._read_table.hasFocus():
            target = self._read_table
        elif self._active_table is not None:
            target = self._active_table
        else:
            target = self._unread_table

        if key in (Qt.Key.Key_J, Qt.Key.Key_Down) and not search_has_focus:
            self._move_selection(target, +1)
            return
        if key in (Qt.Key.Key_K, Qt.Key.Key_Up) and not search_has_focus:
            self._move_selection(target, -1)
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not search_has_focus:
            self._open_and_mark_seen(target)
            return
        if key == Qt.Key.Key_Space and not search_has_focus:
            row = target.currentRow()
            entry = self._entry_at(target, row)
            if entry and not entry.seen:
                entry.seen = True
                self._save_entries_store()
                self._refresh_table()
            else:
                self._move_selection(target, +1)
            return
        if key == Qt.Key.Key_U and not search_has_focus:
            self._mark_entry_unseen(target)
            return
        if key == Qt.Key.Key_S and not search_has_focus:
            self._toggle_star(target, target.currentRow())
            return
        if key == Qt.Key.Key_Slash and not search_has_focus:
            self._search_input.setFocus()
            self._search_input.selectAll()
            return

        super().keyPressEvent(event)
