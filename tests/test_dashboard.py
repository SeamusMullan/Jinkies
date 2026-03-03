"""Tests for src.dashboard module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

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
        """remove_feed_requested must carry the selected row index."""
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

        assert blocker.args == [1]

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

    def test_add_entries_evicts_oldest_when_limit_exceeded(self, qtbot):
        """Oldest entries must be evicted when max_entries is exceeded."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
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

    def test_add_entries_does_not_evict_when_under_limit(self, qtbot):
        """No eviction should happen while entries are within the limit."""
        dashboard = Dashboard()
        qtbot.addWidget(dashboard)
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
