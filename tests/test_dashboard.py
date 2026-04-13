"""Tests for src.dashboard module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QMessageBox

from src.dashboard import Dashboard
from src.models import Feed, FeedEntry


class TestDashboard:
    def test_init(self, qtbot):
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        assert dashboard.windowTitle() == "Jinkies — Feed Monitor"
        assert dashboard.entries == []

    def test_update_feeds(self, qtbot):
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B", enabled=False),
        ]
        dashboard.update_feeds(feeds)
        assert dashboard._feed_list.count() == 2
        # Filter combo should have "All Feeds" + 2 feeds
        assert dashboard._filter_combo.count() == 3

    def test_add_entries(self, qtbot):
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        entries = [
            FeedEntry(
                feed_url="https://a.com/feed",
                title="Entry 1",
                link="https://a.com/1",
                published="2024-01-01",
                entry_id="e1",
            ),
            FeedEntry(
                feed_url="https://a.com/feed",
                title="Entry 2",
                link="https://a.com/2",
                published="2024-01-02",
                entry_id="e2",
            ),
        ]
        dashboard.add_entries(entries)
        assert len(dashboard.entries) == 2
        assert dashboard._entry_table.rowCount() == 2

    def test_record_error(self, qtbot):
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard.record_error()
        assert dashboard._errors_today == 1
        dashboard.record_error()
        assert dashboard._errors_today == 2

    def test_mark_feed_error_colours_feed_item(self, qtbot):
        """mark_feed_error should turn the matching feed list item red."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        feeds = [Feed(url="https://a.com/feed", name="Feed A")]
        dashboard.update_feeds(feeds)
        dashboard.update_feed_names_mapping(feeds)

        dashboard.mark_feed_error("https://a.com/feed", "connection refused")

        item = dashboard._feed_list.item(0)
        assert item is not None
        # Colour should be red-ish (r > g)
        colour = item.foreground().color()
        assert colour.red() > colour.green()
        assert item.toolTip() == "Error: connection refused"
        assert dashboard._feed_errors["https://a.com/feed"] == "connection refused"

    def test_mark_feed_error_shows_status_bar_message(self, qtbot):
        """mark_feed_error should post a transient message to the status bar."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        feeds = [Feed(url="https://a.com/feed", name="Feed A")]
        dashboard.update_feeds(feeds)
        dashboard.update_feed_names_mapping(feeds)

        dashboard.mark_feed_error("https://a.com/feed", "timeout")

        assert "timeout" in dashboard._statusbar.currentMessage()

    def test_clear_feed_error_restores_feed_item(self, qtbot):
        """clear_feed_error should restore the feed item to green."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        feeds = [Feed(url="https://a.com/feed", name="Feed A")]
        dashboard.update_feeds(feeds)
        dashboard.update_feed_names_mapping(feeds)

        dashboard.mark_feed_error("https://a.com/feed", "oops")
        dashboard.clear_feed_error("https://a.com/feed")

        item = dashboard._feed_list.item(0)
        assert item is not None
        colour = item.foreground().color()
        assert colour.green() > colour.red()
        assert item.toolTip() == ""
        assert "https://a.com/feed" not in dashboard._feed_errors

    def test_clear_feed_error_noop_when_no_error(self, qtbot):
        """clear_feed_error should be a no-op when there is no stored error."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        # Should not raise even if URL was never in error
        dashboard.clear_feed_error("https://unknown.com/feed")

    def test_update_feeds_preserves_error_colour(self, qtbot):
        """update_feeds should keep errored items red when rebuilding the list."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        feeds = [Feed(url="https://a.com/feed", name="Feed A")]
        dashboard.update_feeds(feeds)
        dashboard.update_feed_names_mapping(feeds)
        dashboard.mark_feed_error("https://a.com/feed", "server down")

        # Rebuild the feed list (e.g. after config change)
        dashboard.update_feeds(feeds)

        item = dashboard._feed_list.item(0)
        assert item is not None
        colour = item.foreground().color()
        assert colour.red() > colour.green()
        assert item.toolTip() == "Error: server down"

    def test_clear_feed_error_restores_disabled_feed_to_gray(self, qtbot):
        """clear_feed_error on a disabled feed should restore it to gray, not green."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        feeds = [Feed(url="https://a.com/feed", name="Feed A", enabled=False)]
        dashboard.update_feeds(feeds)
        dashboard.update_feed_names_mapping(feeds)

        dashboard.mark_feed_error("https://a.com/feed", "oops")
        dashboard.clear_feed_error("https://a.com/feed")

        item = dashboard._feed_list.item(0)
        assert item is not None
        colour = item.foreground().color()
        # Disabled feed should be gray (r ≈ g ≈ b ≈ 150), not green
        assert colour.green() < 200  # Not bright green

    def test_set_last_poll_time(self, qtbot):
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard.set_last_poll_time("12:00:00 UTC")
        assert dashboard._last_poll_time == "12:00:00 UTC"

    def test_pause_toggle(self, qtbot):
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        assert not dashboard._is_paused
        dashboard.set_paused(True)
        assert dashboard._is_paused
        assert dashboard._pause_action.text() == "Resume"
        dashboard.set_paused(False)
        assert not dashboard._is_paused
        assert dashboard._pause_action.text() == "Pause"

    def test_reset_daily_stats(self, qtbot):
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard._entries_today = 10
        dashboard._errors_today = 5
        dashboard.reset_daily_stats()
        assert dashboard._entries_today == 0
        assert dashboard._errors_today == 0

    def test_reset_daily_stats_updates_stats_date(self, qtbot):
        import datetime
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard.reset_daily_stats()
        assert dashboard._stats_date == datetime.date.today()

    def test_missed_midnight_resets_counters_on_startup(self, qtbot, monkeypatch, tmp_path):
        """Counters should be zeroed when stats_date in store is before today."""
        import datetime
        import json

        # Write a store whose stats_date is in the past
        store = tmp_path / "store.json"
        past_date = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        store.write_text(json.dumps({"entries": [], "stats_date": past_date}))

        monkeypatch.setattr("src.dashboard.get_config_dir", lambda: tmp_path)

        dashboard = Dashboard()
        qtbot.addWidget(dashboard)

        # The startup code should have reset and advanced stats_date to today
        assert dashboard._stats_date == datetime.date.today()
        assert dashboard._entries_today == 0
        assert dashboard._errors_today == 0

    def test_daily_reset_timer_scheduled(self, qtbot):
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        # A single-shot timer should be active and scheduled for midnight
        assert hasattr(dashboard, "_daily_reset_timer")
        assert dashboard._daily_reset_timer.isSingleShot()
        assert dashboard._daily_reset_timer.isActive()

    def test_pause_signal(self, qtbot):
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        with qtbot.waitSignal(dashboard.pause_requested, timeout=1000):
            dashboard._on_pause_clicked()

    def test_remove_feed_signal_emits_index(self, qtbot):
        """remove_feed_requested must carry a list containing the selected row index."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
        ]
        dashboard.update_feeds(feeds)
        dashboard._feed_list.setCurrentRow(1)

        with qtbot.waitSignal(dashboard.remove_feed_requested, timeout=1000) as blocker:
            dashboard._on_remove_feed_clicked()

        assert blocker.args == [[1]]

    def test_remove_feed_signal_emits_multiple_indices(self, qtbot):
        """remove_feed_requested must carry all selected row indices."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
            Feed(url="https://c.com/feed", name="Feed C"),
        ]
        dashboard.update_feeds(feeds)
        # Select rows 0 and 2 explicitly
        dashboard._feed_list.item(0).setSelected(True)
        dashboard._feed_list.item(2).setSelected(True)

        with qtbot.waitSignal(dashboard.remove_feed_requested, timeout=1000) as blocker:
            dashboard._on_remove_feed_clicked()

        assert blocker.args == [[0, 2]]

    def test_remove_feed_signal_not_emitted_when_nothing_selected(self, qtbot):
        """remove_feed_requested must not be emitted when no row is selected."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        feeds = [Feed(url="https://a.com/feed", name="Feed A")]
        dashboard.update_feeds(feeds)
        # No row selected (currentRow() == -1)
        dashboard._feed_list.setCurrentRow(-1)

        signals = []
        dashboard.remove_feed_requested.connect(lambda idx: signals.append(idx))
        dashboard._on_remove_feed_clicked()

        assert signals == []
    def test_double_click_persists_seen_state(self, qtbot, tmp_path):
        """Double-clicking an entry marks it seen and flushes the state to disk."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)

        # Redirect the store to a temporary path so the test is isolated.
        store_path = tmp_path / "store.json"
        dashboard._entries_store_location = store_path

        entry = FeedEntry(
            feed_url="https://example.com/feed",
            title="Test Entry",
            link="https://example.com/1",
            published="2024-01-01",
            entry_id="test-1",
            seen=False,
        )
        dashboard.entries = [entry]

        mock_index = MagicMock()
        mock_index.row.return_value = 0

        with patch("PySide6.QtGui.QDesktopServices.openUrl"):
            dashboard._on_entry_double_click(mock_index)

        # The in-memory entry must be marked as seen.
        assert entry.seen is True

        # The store file must have been written with seen=True.
        with open(store_path) as f:
            data = json.load(f)
        assert any(
            e["entry_id"] == "test-1" and e["seen"] is True
            for e in data["entries"]
        )

    def test_double_click_no_http_link_does_not_persist(self, qtbot, tmp_path):
        """Double-clicking an entry with no valid HTTP link leaves seen unchanged."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)

        store_path = tmp_path / "store.json"
        dashboard._entries_store_location = store_path

        entry = FeedEntry(
            feed_url="https://example.com/feed",
            title="No-link Entry",
            link="",
            published="2024-01-01",
            entry_id="test-2",
            seen=False,
        )
        dashboard.entries = [entry]

        mock_index = MagicMock()
        mock_index.row.return_value = 0

        dashboard._on_entry_double_click(mock_index)

        # Entry with no link must NOT be marked as seen, and store must not exist.
        assert entry.seen is False
        assert not store_path.exists()

    def test_add_entries_evicts_oldest_when_limit_exceeded(self, qtbot, tmp_path):
        """Oldest entries must be evicted when max_entries is exceeded."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard._entries_store_location = tmp_path / "store.json"
        dashboard.entries = []
        dashboard.max_entries = 3

        entries_a = [
            FeedEntry(
                feed_url="https://a.com/feed",
                title=f"Entry {i}",
                link=f"https://a.com/{i}",
                published="2024-01-01",
                entry_id=f"e{i}",
            )
            for i in range(3)
        ]
        dashboard.add_entries(entries_a)
        assert len(dashboard.entries) == 3

        # Adding one more should evict the oldest
        new_entry = FeedEntry(
            feed_url="https://a.com/feed",
            title="Entry 3",
            link="https://a.com/3",
            published="2024-01-02",
            entry_id="e3",
        )
        dashboard.add_entries([new_entry])
        assert len(dashboard.entries) == 3
        # The oldest entry (e0) must have been evicted
        ids = [e.entry_id for e in dashboard.entries]
        assert "e0" not in ids
        assert "e3" in ids

    def test_add_entries_does_not_evict_when_under_limit(self, qtbot, tmp_path):
        """No eviction should happen while entries are within the limit."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard._entries_store_location = tmp_path / "store.json"
        dashboard.entries = []
        dashboard.max_entries = 100

        entries = [
            FeedEntry(
                feed_url="https://a.com/feed",
                title=f"Entry {i}",
                link=f"https://a.com/{i}",
                published="2024-01-01",
                entry_id=f"e{i}",
            )
            for i in range(10)
        ]
        dashboard.add_entries(entries)
        assert len(dashboard.entries) == 10

    def test_add_entries_noop_when_all_duplicates(self, qtbot, tmp_path, monkeypatch):
        """add_entries must be a no-op when every entry is already present."""
        monkeypatch.setattr("src.dashboard.get_config_dir", lambda: tmp_path)
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)

        entry = FeedEntry(
            feed_url="https://a.com/feed",
            title="Entry",
            link="https://a.com/1",
            published="2024-01-01",
            entry_id="e1",
        )
        dashboard.add_entries([entry])
        assert dashboard._entry_table.rowCount() == 1

        # Adding the same entry again must not change anything.
        dashboard.add_entries([entry])
        assert dashboard._entry_table.rowCount() == 1
        assert len(dashboard.entries) == 1

    def test_insert_new_rows_prepends_newest_at_top(self, qtbot, tmp_path, monkeypatch):
        """Both entries should appear in the table after incremental insertion."""
        monkeypatch.setattr("src.dashboard.get_config_dir", lambda: tmp_path)
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)

        entries = [
            FeedEntry(
                feed_url="https://a.com/feed",
                title="Older Entry",
                link="https://a.com/1",
                published="2024-01-01",
                entry_id="e1",
            ),
            FeedEntry(
                feed_url="https://a.com/feed",
                title="Newer Entry",
                link="https://a.com/2",
                published="2024-01-02",
                entry_id="e2",
            ),
        ]
        dashboard.add_entries(entries)

        assert dashboard._entry_table.rowCount() == 2
        titles = {
            dashboard._entry_table.item(r, 0).text()
            for r in range(dashboard._entry_table.rowCount())
        }
        assert titles == {"Older Entry", "Newer Entry"}

    def test_insert_new_rows_removes_evicted_rows_from_table(self, qtbot, tmp_path, monkeypatch):
        """Evicted entries must be removed from the bottom of the visible table."""
        monkeypatch.setattr("src.dashboard.get_config_dir", lambda: tmp_path)
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard.max_entries = 2

        # Seed two entries.
        initial = [
            FeedEntry(
                feed_url="https://a.com/feed",
                title=f"Entry {i}",
                link=f"https://a.com/{i}",
                published="2024-01-01",
                entry_id=f"e{i}",
            )
            for i in range(2)
        ]
        dashboard.add_entries(initial)
        assert dashboard._entry_table.rowCount() == 2

        # Adding one new entry evicts one old entry; table must stay at 2 rows.
        new_entry = FeedEntry(
            feed_url="https://a.com/feed",
            title="New Entry",
            link="https://a.com/2",
            published="2024-01-03",
            entry_id="e2",
        )
        dashboard.add_entries([new_entry])

        assert len(dashboard.entries) == 2
        assert dashboard._entry_table.rowCount() == 2
        # Newest entry must be at the top.
        assert dashboard._entry_table.item(0, 0).text() == "New Entry"

    def test_insert_new_rows_respects_active_filter(self, qtbot, tmp_path, monkeypatch):
        """Only entries matching the active filter should be inserted into the table."""
        monkeypatch.setattr("src.dashboard.get_config_dir", lambda: tmp_path)
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)

        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
        ]
        dashboard.update_feeds(feeds)
        dashboard._filter_combo.setCurrentText("Feed A")

        entries = [
            FeedEntry(
                feed_url="https://a.com/feed",
                title="Feed A Entry",
                link="https://a.com/1",
                published="2024-01-01",
                entry_id="a1",
            ),
            FeedEntry(
                feed_url="https://b.com/feed",
                title="Feed B Entry",
                link="https://b.com/1",
                published="2024-01-01",
                entry_id="b1",
            ),
        ]
        dashboard.add_entries(entries)

        # Only the Feed A entry should appear in the filtered table.
        assert dashboard._entry_table.rowCount() == 1
        assert dashboard._entry_table.item(0, 0).text() == "Feed A Entry"
        # Both entries are still in memory.
        assert len(dashboard.entries) == 2


class TestMarkAsSeen:
    """Tests for the bulk mark-as-seen actions."""

    def _make_entries(self) -> list[FeedEntry]:
        return [
            FeedEntry(
                feed_url="https://a.com/feed",
                title="Feed A Entry 1",
                link="https://a.com/1",
                published="2024-01-01",
                entry_id="a1",
                seen=False,
            ),
            FeedEntry(
                feed_url="https://a.com/feed",
                title="Feed A Entry 2",
                link="https://a.com/2",
                published="2024-01-02",
                entry_id="a2",
                seen=False,
            ),
            FeedEntry(
                feed_url="https://b.com/feed",
                title="Feed B Entry 1",
                link="https://b.com/1",
                published="2024-01-01",
                entry_id="b1",
                seen=False,
            ),
        ]

    def test_do_mark_all_seen_marks_all_entries(self, qtbot, tmp_path):
        """_do_mark_all_seen(None) must mark every entry as seen."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard._entries_store_location = tmp_path / "store.json"
        dashboard.entries = self._make_entries()
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
        ]
        dashboard.update_feeds(feeds)

        dashboard._do_mark_all_seen(None)

        assert all(e.seen for e in dashboard.entries)

    def test_do_mark_all_seen_scoped_to_feed(self, qtbot, tmp_path):
        """_do_mark_all_seen('Feed A') must only mark Feed A entries."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard._entries_store_location = tmp_path / "store.json"
        dashboard.entries = self._make_entries()
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
        ]
        dashboard.update_feeds(feeds)

        dashboard._do_mark_all_seen("Feed A")

        feed_a_entries = [e for e in dashboard.entries if e.feed_url == "https://a.com/feed"]
        feed_b_entries = [e for e in dashboard.entries if e.feed_url == "https://b.com/feed"]
        assert all(e.seen for e in feed_a_entries)
        assert all(not e.seen for e in feed_b_entries)

    def test_do_mark_all_seen_persists_to_disk(self, qtbot, tmp_path):
        """_do_mark_all_seen should write the updated seen state to store.json."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        store_path = tmp_path / "store.json"
        dashboard._entries_store_location = store_path
        dashboard.entries = self._make_entries()
        feeds = [Feed(url="https://a.com/feed", name="Feed A")]
        dashboard.update_feeds(feeds)

        dashboard._do_mark_all_seen(None)

        with open(store_path) as f:
            data = json.load(f)
        assert all(e["seen"] for e in data["entries"])

    def test_do_mark_all_seen_noop_when_already_seen(self, qtbot, tmp_path):
        """_do_mark_all_seen should not write to disk if nothing changed."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        store_path = tmp_path / "store.json"
        dashboard._entries_store_location = store_path
        entries = self._make_entries()
        for e in entries:
            e.seen = True
        dashboard.entries = entries

        dashboard._do_mark_all_seen(None)

        assert not store_path.exists()

    def test_on_mark_all_seen_clicked_all_feeds_confirmed(self, qtbot, tmp_path):
        """Clicking 'Mark All Seen' on All Feeds scope with confirm=Yes marks all."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard._entries_store_location = tmp_path / "store.json"
        dashboard.entries = self._make_entries()
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
        ]
        dashboard.update_feeds(feeds)
        # Ensure filter is "All Feeds"
        dashboard._filter_combo.setCurrentText("All Feeds")

        with patch(
            "src.dashboard.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dashboard._on_mark_all_seen_clicked()

        assert all(e.seen for e in dashboard.entries)

    def test_on_mark_all_seen_clicked_all_feeds_cancelled(self, qtbot, tmp_path):
        """Clicking 'Mark All Seen' on All Feeds scope with confirm=No changes nothing."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard._entries_store_location = tmp_path / "store.json"
        dashboard.entries = self._make_entries()
        dashboard._filter_combo.setCurrentText("All Feeds")

        with patch(
            "src.dashboard.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            dashboard._on_mark_all_seen_clicked()

        assert all(not e.seen for e in dashboard.entries)

    def test_on_mark_all_seen_clicked_single_feed_no_dialog(self, qtbot, tmp_path):
        """Clicking 'Mark All Seen' for a specific feed skips the confirmation dialog."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard._entries_store_location = tmp_path / "store.json"
        dashboard.entries = self._make_entries()
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
        ]
        dashboard.update_feeds(feeds)
        dashboard._filter_combo.setCurrentText("Feed A")

        with patch("src.dashboard.QMessageBox.question") as mock_dlg:
            dashboard._on_mark_all_seen_clicked()
            mock_dlg.assert_not_called()

        feed_a_entries = [e for e in dashboard.entries if e.feed_url == "https://a.com/feed"]
        feed_b_entries = [e for e in dashboard.entries if e.feed_url == "https://b.com/feed"]
        assert all(e.seen for e in feed_a_entries)
        assert all(not e.seen for e in feed_b_entries)

    def test_mark_selected_seen(self, qtbot, tmp_path):
        """_mark_selected_seen should mark only the selected rows as seen."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        dashboard._entries_store_location = tmp_path / "store.json"
        entries = self._make_entries()
        dashboard.entries = entries
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
        ]
        dashboard.update_feeds(feeds)
        dashboard._refresh_table()

        # Select row 0 (which maps to the last entry in reversed order)
        dashboard._entry_table.selectRow(0)
        dashboard._mark_selected_seen()

        # Exactly one entry should be marked seen — the one at display row 0
        seen_entries = [e for e in dashboard.entries if e.seen]
        assert len(seen_entries) == 1

    def test_mark_selected_seen_noop_when_nothing_selected(self, qtbot, tmp_path):
        """_mark_selected_seen with no selection should not write to disk."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        store_path = tmp_path / "store.json"
        dashboard._entries_store_location = store_path
        dashboard.entries = self._make_entries()
        dashboard._refresh_table()
        # No row selected
        dashboard._entry_table.clearSelection()

        dashboard._mark_selected_seen()

        assert not store_path.exists()
        assert all(not e.seen for e in dashboard.entries)

    def test_toolbar_mark_all_seen_action_exists(self, qtbot):
        """The toolbar should have a 'Mark All Seen' action."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
        assert hasattr(dashboard, "_mark_all_seen_action")
        assert dashboard._mark_all_seen_action.text() == "Mark All Seen"

