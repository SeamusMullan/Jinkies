"""Feed health dashboard dialog for Jinkies.

Shows per-feed poll statistics in a non-modal dialog so it can remain
open while the app continues running.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from src.feed_poller import FeedPoller


class FeedHealthDialog(QDialog):
    """Non-modal dialog showing per-feed health statistics.

    Displays a table with one row per polled feed.  A "Refresh" button
    re-fetches the current stats from the poller and updates the table.

    Args:
        poller: The running :class:`~src.feed_poller.FeedPoller` instance.
        parent: Optional parent widget.
    """

    _COLUMNS = [
        "Feed name",
        "URL",
        "Polls",
        "Success rate %",
        "Entries today",
        "Avg latency ms",
        "Last error",
        "Last poll",
    ]

    def __init__(self, poller: FeedPoller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Feed Health Dashboard")
        self.setMinimumSize(900, 400)
        self._poller = poller

        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(self._COLUMNS)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.resizeSection(0, 160)
        header.resizeSection(1, 200)
        header.resizeSection(2, 60)
        header.resizeSection(3, 110)
        header.resizeSection(4, 100)
        header.resizeSection(5, 110)
        header.resizeSection(6, 160)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSortingEnabled(True)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._populate)
        btn_row.addWidget(self._refresh_btn)
        layout.addLayout(btn_row)

        self._populate()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _feed_name_for(self, url: str) -> str:
        """Resolve a feed URL to a display name via the poller's feed list.

        Falls back to returning the URL itself when no matching feed is found.

        Args:
            url: The feed URL to look up.

        Returns:
            The feed's display name, or *url* if not found.
        """
        for feed in self._poller.feeds:
            if feed.url == url:
                return feed.name
        return url

    def _populate(self) -> None:
        """Fetch fresh stats from the poller and rebuild the table rows."""
        stats_map = self._poller.get_stats()

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(stats_map))

        for row, (url, stats) in enumerate(stats_map.items()):
            feed_name = self._feed_name_for(url)

            if stats.total_polls > 0:
                success_pct = (stats.successful_polls / stats.total_polls) * 100
                success_str = f"{success_pct:.1f}"
            else:
                success_str = "—"

            latency_str = (
                f"{stats.last_poll_latency_ms:.0f}"
                if stats.successful_polls > 0
                else "—"
            )

            cells = [
                feed_name,
                url,
                str(stats.total_polls),
                success_str,
                str(stats.entries_today),
                latency_str,
                stats.last_error,
                stats.last_poll_time,
            ]

            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, col, item)

        self._table.setSortingEnabled(True)
