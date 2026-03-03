"""Tests for src.dashboard module."""

from __future__ import annotations

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
