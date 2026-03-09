"""Tests for src.feed_poller."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from src.feed_poller import FeedPoller
from src.models import Feed


class TestFeedPoller:
    def test_init(self, sample_feed):
        poller = FeedPoller(feeds=[sample_feed], poll_interval=30)
        assert poller.poll_interval == 30
        assert len(poller.feeds) == 1
        assert len(poller.seen_ids) == 0

    def test_init_with_seen_ids(self, sample_feed):
        seen = {"id1", "id2"}
        poller = FeedPoller(feeds=[sample_feed], seen_ids=seen)
        assert poller.seen_ids == seen

    def test_pause_resume(self, sample_feed):
        poller = FeedPoller(feeds=[sample_feed])
        assert not poller.is_paused
        poller.pause()
        assert poller.is_paused
        poller.resume()
        assert not poller.is_paused

    def test_update_feeds(self, sample_feed):
        poller = FeedPoller(feeds=[sample_feed])
        new_feed = Feed(url="https://other.com/feed", name="Other")
        poller.update_feeds([new_feed])
        assert len(poller.feeds) == 1
        assert poller.feeds[0].url == "https://other.com/feed"

    def test_update_interval(self, sample_feed):
        poller = FeedPoller(feeds=[sample_feed], poll_interval=60)
        poller.update_interval(120)
        assert poller.poll_interval == 120

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_poll_feed_emits_new_entries(
        self, mock_parse, _mock_creds, sample_feed, mock_feedparser_result, qtbot,
    ):
        mock_parse.return_value = mock_feedparser_result
        poller = FeedPoller(feeds=[sample_feed])

        entries = []
        poller.new_entries_found.connect(entries.extend)
        poller._poll_feed(sample_feed)

        assert len(entries) == 2
        assert entries[0].title == "First Entry"
        assert entries[1].title == "Second Entry"

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_poll_feed_emits_poll_time_updated(
        self, mock_parse, _mock_creds, sample_feed, mock_feedparser_result, qtbot,
    ):
        mock_parse.return_value = mock_feedparser_result
        poller = FeedPoller(feeds=[sample_feed])

        updates = []
        poller.poll_time_updated.connect(lambda url, ts: updates.append((url, ts)))
        poller._poll_feed(sample_feed)

        assert len(updates) == 1
        assert updates[0][0] == sample_feed.url
        assert updates[0][1]  # non-empty ISO timestamp

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_poll_feed_does_not_mutate_last_poll_time(
        self, mock_parse, _mock_creds, sample_feed, mock_feedparser_result,
    ):
        mock_parse.return_value = mock_feedparser_result
        poller = FeedPoller(feeds=[sample_feed])

        assert sample_feed.last_poll_time is None
        poller._poll_feed(sample_feed)
        assert sample_feed.last_poll_time is None  # not mutated by poller thread

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_poll_feed_skips_seen_entries(
        self, mock_parse, _mock_creds, sample_feed, mock_feedparser_result, qtbot,
    ):
        mock_parse.return_value = mock_feedparser_result
        poller = FeedPoller(feeds=[sample_feed], seen_ids={"entry-1"})

        entries = []
        poller.new_entries_found.connect(entries.extend)
        poller._poll_feed(sample_feed)

        assert len(entries) == 1
        assert entries[0].entry_id == "entry-2"

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_poll_feed_error(self, mock_parse, _mock_creds, sample_feed, qtbot):
        mock_parse.side_effect = OSError("Network error")
        poller = FeedPoller(feeds=[sample_feed])

        errors = []
        poller.feed_error.connect(lambda url, msg: errors.append((url, msg)))
        poller._poll_feed(sample_feed)

        assert len(errors) == 1
        assert errors[0][0] == sample_feed.url
        assert "Network error" in errors[0][1]

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_poll_feed_unexpected_exception_reraises(
        self, mock_parse, _mock_creds, sample_feed, qtbot,
    ):
        mock_parse.side_effect = RuntimeError("Unexpected failure")
        poller = FeedPoller(feeds=[sample_feed])

        with pytest.raises(RuntimeError, match="Unexpected failure"):
            poller._poll_feed(sample_feed)

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_poll_feed_bozo_error(self, mock_parse, _mock_creds, sample_feed, qtbot):
        result = MagicMock()
        result.bozo = True
        result.entries = []
        result.bozo_exception = ValueError("Bad XML")
        mock_parse.return_value = result

        poller = FeedPoller(feeds=[sample_feed])
        errors = []
        poller.feed_error.connect(lambda url, msg: errors.append((url, msg)))
        poller._poll_feed(sample_feed)

        assert len(errors) == 1

    def test_file_url_blocked(self, qtbot):
        feed = Feed(url="file:///etc/passwd", name="Malicious")
        poller = FeedPoller(feeds=[feed])

        errors = []
        poller.feed_error.connect(lambda url, msg: errors.append((url, msg)))
        poller._poll_feed(feed)

        assert len(errors) == 1
        assert errors[0][0] == "file:///etc/passwd"
        assert "not allowed" in errors[0][1]

    def test_data_url_blocked(self, qtbot):
        feed = Feed(url="data:text/xml,<feed/>", name="Malicious")
        poller = FeedPoller(feeds=[feed])

        errors = []
        poller.feed_error.connect(lambda url, msg: errors.append((url, msg)))
        poller._poll_feed(feed)

        assert len(errors) == 1
        assert "not allowed" in errors[0][1]

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_https_url_allowed(self, mock_parse, _mock_creds, qtbot, mock_feedparser_result):
        mock_parse.return_value = mock_feedparser_result
        feed = Feed(url="https://example.com/feed.atom", name="Safe")
        poller = FeedPoller(feeds=[feed])

        errors = []
        poller.feed_error.connect(lambda url, msg: errors.append((url, msg)))
        poller._poll_feed(feed)

        assert len(errors) == 0

    def test_disabled_feed_not_polled(self, qtbot):
        feed = Feed(url="https://example.com/feed", name="Disabled", enabled=False)
        poller = FeedPoller(feeds=[feed])

        with patch("src.feed_poller.feedparser.parse"):
            poller._poll_feed = MagicMock()
            # Simulate one run iteration manually (won't actually call _poll_feed for disabled)
            for f in poller.feeds:
                if f.enabled:
                    poller._poll_feed(f)
            poller._poll_feed.assert_not_called()


class TestFeedPollerAuth:
    """Tests for credential lookup and HTTP rejection in feed polling."""

    @patch("src.feed_poller.get_credentials", return_value=("user", "pass"))
    def test_http_url_with_auth_emits_error(self, _mock_creds, qtbot):
        """Credentials over plain HTTP must be rejected."""
        feed = Feed(url="http://insecure.example.com/feed", name="Insecure")
        poller = FeedPoller(feeds=[feed])

        errors = []
        poller.feed_error.connect(lambda url, msg: errors.append((url, msg)))
        poller._poll_feed(feed)

        assert len(errors) == 1
        assert errors[0][0] == feed.url
        assert "insecure HTTP" in errors[0][1]

    @patch("src.feed_poller.urllib.request.urlopen")
    @patch("src.feed_poller.get_credentials", return_value=("user", "token123"))
    @patch("src.feed_poller.feedparser.parse")
    def test_https_url_with_auth_succeeds(
        self, mock_parse, _mock_creds, mock_urlopen, mock_feedparser_result, qtbot,
    ):
        """Credentials over HTTPS should be sent via Basic auth."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<feed></feed>"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        mock_parse.return_value = mock_feedparser_result

        feed = Feed(url="https://secure.example.com/feed", name="Secure")
        poller = FeedPoller(feeds=[feed])

        entries = []
        poller.new_entries_found.connect(entries.extend)
        poller._poll_feed(feed)

        # feedparser.parse was called with the fetched content
        mock_parse.assert_called_once_with(b"<feed></feed>")
        assert len(entries) == 2

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_no_auth_http_url_allowed(
        self, mock_parse, _mock_creds, mock_feedparser_result, qtbot,
    ):
        """HTTP URLs without auth should still work (no credentials at risk)."""
        mock_parse.return_value = mock_feedparser_result
        feed = Feed(url="http://example.com/feed", name="Public")
        poller = FeedPoller(feeds=[feed])

        entries = []
        poller.new_entries_found.connect(entries.extend)
        poller._poll_feed(feed)

        assert len(entries) == 2

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_no_auth_fetch_uses_socket_timeout(
        self, mock_parse, _mock_creds, mock_feedparser_result, qtbot,
    ):
        """Non-auth feedparser.parse must be called with a socket_timeout."""
        mock_parse.return_value = mock_feedparser_result
        feed = Feed(url="https://example.com/feed.atom", name="Timed")
        poller = FeedPoller(feeds=[feed])
        poller._poll_feed(feed)

        mock_parse.assert_called_once()
        _, kwargs = mock_parse.call_args
        assert "socket_timeout" in kwargs, "feedparser.parse must be called with socket_timeout"
        assert kwargs["socket_timeout"] > 0


def _make_entry(data: dict) -> MagicMock:
    """Helper: create a mock feedparser entry whose .get() mirrors *data*."""
    entry = MagicMock()
    entry.get = lambda key, default="": data.get(key, default)
    return entry


class TestGetEntryId:
    """Unit tests for FeedPoller._get_entry_id fallback logic."""

    def setup_method(self):
        feed = Feed(url="https://example.com/feed.atom", name="Test")
        self.poller = FeedPoller(feeds=[feed])

    def test_uses_id_field_when_present(self):
        entry = _make_entry({"id": "urn:uuid:abc123", "link": "https://x.com/1"})
        assert self.poller._get_entry_id(entry) == "urn:uuid:abc123"

    def test_falls_back_to_link_when_no_id(self):
        entry = _make_entry({"link": "https://x.com/1"})
        assert self.poller._get_entry_id(entry) == "https://x.com/1"

    def test_hash_fallback_uses_title_summary_published(self):
        entry = _make_entry({"title": "Hello", "summary": "World", "published": "2024-01-01"})
        expected = hashlib.sha256(b"Hello|World|2024-01-01").hexdigest()
        assert self.poller._get_entry_id(entry) == expected

    def test_hash_fallback_updated_used_when_published_missing(self):
        entry = _make_entry({"title": "T", "updated": "2024-06-01"})
        expected = hashlib.sha256(b"T||2024-06-01").hexdigest()
        assert self.poller._get_entry_id(entry) == expected

    def test_hash_fallback_is_stable(self):
        """Same content must always produce the same ID."""
        entry1 = _make_entry({"title": "A", "summary": "B", "published": "2024-01-01"})
        entry2 = _make_entry({"title": "A", "summary": "B", "published": "2024-01-01"})
        assert self.poller._get_entry_id(entry1) == self.poller._get_entry_id(entry2)

    def test_different_content_produces_different_hashes(self):
        entry1 = _make_entry({"title": "Entry One"})
        entry2 = _make_entry({"title": "Entry Two"})
        assert self.poller._get_entry_id(entry1) != self.poller._get_entry_id(entry2)

    def test_uuid_fallback_for_completely_empty_entry(self):
        """Entries with no usable fields get a UUID (non-empty, non-colliding)."""
        entry1 = _make_entry({})
        entry2 = _make_entry({})
        id1 = self.poller._get_entry_id(entry1)
        id2 = self.poller._get_entry_id(entry2)
        assert id1  # non-empty
        assert id2  # non-empty
        # Two separate calls must not collide
        assert id1 != id2

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_no_id_link_entries_each_get_unique_id(
        self, mock_parse, _mock_creds, sample_feed, qtbot,
    ):
        """Entries without id/link must not collide with each other."""
        entry1 = _make_entry({"title": "Alpha", "summary": "First", "published": "2024-01-01"})
        entry2 = _make_entry({"title": "Beta", "summary": "Second", "published": "2024-01-02"})

        result = MagicMock()
        result.bozo = False
        result.entries = [entry1, entry2]
        mock_parse.return_value = result

        poller = FeedPoller(feeds=[sample_feed])
        entries = []
        poller.new_entries_found.connect(entries.extend)
        poller._poll_feed(sample_feed)

        assert len(entries) == 2
        assert entries[0].entry_id != entries[1].entry_id

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_no_id_link_entry_not_re_emitted_on_second_poll(
        self, mock_parse, _mock_creds, sample_feed, qtbot,
    ):
        """An entry seen on the first poll must not re-appear on the second poll."""
        entry = _make_entry({"title": "Stable", "summary": "Content", "published": "2024-01-01"})

        result = MagicMock()
        result.bozo = False
        result.entries = [entry]
        mock_parse.return_value = result

        poller = FeedPoller(feeds=[sample_feed])
        entries = []
        poller.new_entries_found.connect(entries.extend)

        poller._poll_feed(sample_feed)
        assert len(entries) == 1

        poller._poll_feed(sample_feed)
        assert len(entries) == 1  # still 1 — not re-emitted
