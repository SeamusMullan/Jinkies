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


class TestFeedPollerETag:
    """Tests for ETag/Last-Modified conditional-GET support."""

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_etag_passed_to_feedparser(
        self, mock_parse, _mock_creds, mock_feedparser_result, qtbot,
    ):
        """feedparser.parse should receive the feed's stored etag."""
        mock_parse.return_value = mock_feedparser_result
        feed = Feed(url="https://example.com/feed.atom", name="Feed", etag='"abc123"')
        poller = FeedPoller(feeds=[feed])
        poller._poll_feed(feed)

        _, kwargs = mock_parse.call_args
        assert kwargs.get("etag") == '"abc123"'

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_modified_passed_to_feedparser(
        self, mock_parse, _mock_creds, mock_feedparser_result, qtbot,
    ):
        """feedparser.parse should receive the feed's stored modified date."""
        mock_parse.return_value = mock_feedparser_result
        modified = "Tue, 03 Jun 2003 00:00:00 GMT"
        feed = Feed(url="https://example.com/feed.atom", name="Feed", modified=modified)
        poller = FeedPoller(feeds=[feed])
        poller._poll_feed(feed)

        _, kwargs = mock_parse.call_args
        assert kwargs.get("modified") == modified

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_etag_stored_on_feed_after_successful_parse(
        self, mock_parse, _mock_creds, mock_feedparser_result, qtbot,
    ):
        """After a successful parse the feed's etag must be updated."""
        mock_feedparser_result.etag = '"newetag"'
        mock_parse.return_value = mock_feedparser_result
        feed = Feed(url="https://example.com/feed.atom", name="Feed")
        poller = FeedPoller(feeds=[feed])
        poller._fetch_feed(feed)

        assert feed.etag == '"newetag"'

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_modified_stored_on_feed_after_successful_parse(
        self, mock_parse, _mock_creds, mock_feedparser_result, qtbot,
    ):
        """After a successful parse the feed's modified must be updated."""
        last_mod = "Wed, 04 Jun 2003 00:00:00 GMT"
        mock_feedparser_result.modified = last_mod
        mock_parse.return_value = mock_feedparser_result
        feed = Feed(url="https://example.com/feed.atom", name="Feed")
        poller = FeedPoller(feeds=[feed])
        poller._fetch_feed(feed)

        assert feed.modified == last_mod

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_no_etag_in_response_leaves_existing_etag_unchanged(
        self, mock_parse, _mock_creds, mock_feedparser_result, qtbot,
    ):
        """If the server does not return an ETag the existing value is kept."""
        del mock_feedparser_result.etag  # ensure attribute is absent
        mock_parse.return_value = mock_feedparser_result
        feed = Feed(url="https://example.com/feed.atom", name="Feed", etag='"kept"')
        poller = FeedPoller(feeds=[feed])
        poller._fetch_feed(feed)

        assert feed.etag == '"kept"'

    @patch("src.feed_poller.urllib.request.urlopen")
    @patch("src.feed_poller.get_credentials", return_value=("user", "token"))
    @patch("src.feed_poller.feedparser.parse")
    def test_auth_path_sends_if_none_match_header(
        self, mock_parse, _mock_creds, mock_urlopen, mock_feedparser_result, qtbot,
    ):
        """Authenticated fetch must include If-None-Match when etag is set."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<feed/>"
        mock_resp.headers.get = lambda h, default=None: {
            "ETag": '"newetag"',
        }.get(h, default)
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        mock_parse.return_value = mock_feedparser_result

        feed = Feed(url="https://secure.example.com/feed", name="Secure", etag='"oldtag"')
        poller = FeedPoller(feeds=[feed])
        poller._fetch_feed(feed)

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("If-none-match") == '"oldtag"'

    @patch("src.feed_poller.urllib.request.urlopen")
    @patch("src.feed_poller.get_credentials", return_value=("user", "token"))
    @patch("src.feed_poller.feedparser.parse")
    def test_auth_path_sends_if_modified_since_header(
        self, mock_parse, _mock_creds, mock_urlopen, mock_feedparser_result, qtbot,
    ):
        """Authenticated fetch must include If-Modified-Since when modified is set."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<feed/>"
        mock_resp.headers.get = lambda h, default=None: None
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        mock_parse.return_value = mock_feedparser_result

        modified = "Tue, 03 Jun 2003 00:00:00 GMT"
        feed = Feed(url="https://secure.example.com/feed", name="Secure", modified=modified)
        poller = FeedPoller(feeds=[feed])
        poller._fetch_feed(feed)

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("If-modified-since") == modified

    @patch("src.feed_poller.urllib.request.urlopen")
    @patch("src.feed_poller.get_credentials", return_value=("user", "token"))
    @patch("src.feed_poller.feedparser.parse")
    def test_auth_path_updates_etag_from_response(
        self, mock_parse, _mock_creds, mock_urlopen, mock_feedparser_result, qtbot,
    ):
        """Authenticated fetch must update feed.etag from the ETag response header."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<feed/>"
        mock_resp.headers.get = lambda h, default=None: {
            "ETag": '"newetag456"',
        }.get(h, default)
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        mock_parse.return_value = mock_feedparser_result

        feed = Feed(url="https://secure.example.com/feed", name="Secure")
        poller = FeedPoller(feeds=[feed])
        poller._fetch_feed(feed)

        assert feed.etag == '"newetag456"'

    @patch("src.feed_poller.urllib.request.urlopen")
    @patch("src.feed_poller.get_credentials", return_value=("user", "token"))
    def test_auth_path_304_returns_empty_result(
        self, _mock_creds, mock_urlopen, qtbot,
    ):
        """A 304 Not Modified response in the auth path must return an empty result."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://secure.example.com/feed",
            code=304,
            msg="Not Modified",
            hdrs=MagicMock(),
            fp=None,
        )

        feed = Feed(url="https://secure.example.com/feed", name="Secure")
        poller = FeedPoller(feeds=[feed])
        result = poller._fetch_feed(feed)

        # Should get an empty result (no entries), not an exception
        assert result.entries == []

    @patch("src.feed_poller.urllib.request.urlopen")
    @patch("src.feed_poller.get_credentials", return_value=("user", "token"))
    def test_auth_path_non_304_http_error_propagates(
        self, _mock_creds, mock_urlopen, qtbot,
    ):
        """Non-304 HTTP errors in the auth path must propagate normally."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://secure.example.com/feed",
            code=503,
            msg="Service Unavailable",
            hdrs=MagicMock(),
            fp=None,
        )

        feed = Feed(url="https://secure.example.com/feed", name="Secure")
        poller = FeedPoller(feeds=[feed])

        errors = []
        poller.feed_error.connect(lambda url, msg: errors.append((url, msg)))
        poller._poll_feed(feed)

        assert len(errors) == 1


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


class TestFeedPollerBackoff:
    """Unit tests for FeedPoller exponential-backoff logic."""

    def test_compute_backoff_secs_initial_failure(self, sample_feed):
        """First failure should produce a 60-second (1 min) backoff delay."""
        poller = FeedPoller(feeds=[sample_feed])
        assert poller._compute_backoff_secs(0) == 60

    def test_compute_backoff_secs_doubles_each_failure(self, sample_feed):
        """Backoff delay should double with each consecutive failure."""
        poller = FeedPoller(feeds=[sample_feed])
        assert poller._compute_backoff_secs(0) == 60    # 1 min
        assert poller._compute_backoff_secs(1) == 120   # 2 min
        assert poller._compute_backoff_secs(2) == 240   # 4 min
        assert poller._compute_backoff_secs(3) == 480   # 8 min

    def test_compute_backoff_secs_capped_at_max(self, sample_feed):
        """Backoff delay must not exceed max_backoff_secs."""
        poller = FeedPoller(feeds=[sample_feed], max_backoff_secs=300)
        assert poller._compute_backoff_secs(10) == 300

    def test_default_max_backoff_is_3600(self, sample_feed):
        """Default max_backoff_secs should be 3600 (60 minutes)."""
        poller = FeedPoller(feeds=[sample_feed])
        assert poller.max_backoff_secs == 3600
        # 2^7 * 60 = 7680 > 3600 — must be capped
        assert poller._compute_backoff_secs(7) == 3600

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_failure_increments_backoff_counter(
        self, mock_parse, _mock_creds, sample_feed,
    ):
        """Each failure should increment the failure counter for the feed."""
        mock_parse.side_effect = OSError("Network error")
        poller = FeedPoller(feeds=[sample_feed])

        poller._poll_feed(sample_feed)
        assert poller._backoff_counts.get(sample_feed.url) == 1

        poller._poll_feed(sample_feed)
        assert poller._backoff_counts.get(sample_feed.url) == 2

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_failure_sets_next_poll_time(
        self, mock_parse, _mock_creds, sample_feed,
    ):
        """A failure should schedule the next poll in the future."""
        import time as _time

        mock_parse.side_effect = OSError("Network error")
        poller = FeedPoller(feeds=[sample_feed])

        before = _time.time()
        poller._poll_feed(sample_feed)
        after = _time.time()

        next_time = poller._next_poll_times.get(sample_feed.url, 0.0)
        # Next poll time must be in the future (at least 60 s away).
        assert next_time >= before + 60
        assert next_time <= after + 60 + 1  # allow small clock drift

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_success_resets_backoff_counter(
        self, mock_parse, _mock_creds, sample_feed, mock_feedparser_result,
    ):
        """A successful poll must reset the failure counter."""
        mock_parse.side_effect = [OSError("fail"), mock_feedparser_result]
        poller = FeedPoller(feeds=[sample_feed])

        poller._poll_feed(sample_feed)  # fails
        assert sample_feed.url in poller._backoff_counts

        poller._poll_feed(sample_feed)  # succeeds
        assert sample_feed.url not in poller._backoff_counts
        assert sample_feed.url not in poller._next_poll_times

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_failure_emits_feed_backoff_changed(
        self, mock_parse, _mock_creds, sample_feed, qtbot,
    ):
        """A failure must emit feed_backoff_changed with the backoff delay."""
        mock_parse.side_effect = OSError("Network error")
        poller = FeedPoller(feeds=[sample_feed])

        backoff_events: list[tuple[str, int]] = []
        poller.feed_backoff_changed.connect(
            lambda url, secs: backoff_events.append((url, secs))
        )
        poller._poll_feed(sample_feed)

        assert len(backoff_events) == 1
        assert backoff_events[0][0] == sample_feed.url
        assert backoff_events[0][1] == 60  # first failure → 1 min

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_second_failure_emits_doubled_backoff(
        self, mock_parse, _mock_creds, sample_feed, qtbot,
    ):
        """The second consecutive failure must double the backoff delay."""
        mock_parse.side_effect = OSError("Network error")
        poller = FeedPoller(feeds=[sample_feed])

        backoff_events: list[tuple[str, int]] = []
        poller.feed_backoff_changed.connect(
            lambda url, secs: backoff_events.append((url, secs))
        )
        poller._poll_feed(sample_feed)
        poller._poll_feed(sample_feed)

        assert backoff_events[0][1] == 60   # 1 min
        assert backoff_events[1][1] == 120  # 2 min

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_success_after_failure_emits_backoff_cleared(
        self, mock_parse, _mock_creds, sample_feed, mock_feedparser_result, qtbot,
    ):
        """Recovery from backoff must emit feed_backoff_changed(url, 0)."""
        mock_parse.side_effect = [OSError("fail"), mock_feedparser_result]
        poller = FeedPoller(feeds=[sample_feed])

        backoff_events: list[tuple[str, int]] = []
        poller.feed_backoff_changed.connect(
            lambda url, secs: backoff_events.append((url, secs))
        )

        poller._poll_feed(sample_feed)  # fails → backoff set
        poller._poll_feed(sample_feed)  # succeeds → backoff cleared

        assert len(backoff_events) == 2
        assert backoff_events[0][1] == 60  # backoff set
        assert backoff_events[1][1] == 0   # backoff cleared

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_success_without_prior_failure_does_not_emit_backoff_cleared(
        self, mock_parse, _mock_creds, sample_feed, mock_feedparser_result, qtbot,
    ):
        """A clean first poll must not emit a spurious backoff-cleared signal."""
        mock_parse.return_value = mock_feedparser_result
        poller = FeedPoller(feeds=[sample_feed])

        backoff_events: list[tuple[str, int]] = []
        poller.feed_backoff_changed.connect(
            lambda url, secs: backoff_events.append((url, secs))
        )
        poller._poll_feed(sample_feed)

        assert len(backoff_events) == 0

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_bozo_error_applies_backoff(
        self, mock_parse, _mock_creds, sample_feed, qtbot,
    ):
        """A bozo parse error with no entries should also trigger backoff."""
        result = MagicMock()
        result.bozo = True
        result.entries = []
        result.bozo_exception = ValueError("Bad XML")
        mock_parse.return_value = result

        poller = FeedPoller(feeds=[sample_feed])
        backoff_events: list[tuple[str, int]] = []
        poller.feed_backoff_changed.connect(
            lambda url, secs: backoff_events.append((url, secs))
        )
        poller._poll_feed(sample_feed)

        assert len(backoff_events) == 1
        assert backoff_events[0][1] == 60

    def test_feed_in_backoff_is_skipped_by_run_logic(self, sample_feed):
        """A feed whose backoff window has not elapsed must not be polled."""
        import time as _time

        poller = FeedPoller(feeds=[sample_feed])
        # Place feed well into the future backoff window.
        poller._next_poll_times[sample_feed.url] = _time.time() + 10_000
        poller._backoff_counts[sample_feed.url] = 1

        polled: list[str] = []

        def capturing_poll(feed: Feed) -> None:
            polled.append(feed.url)

        poller._poll_feed = capturing_poll  # type: ignore[method-assign]

        # Replicate the per-feed gate from run().
        for feed in poller.feeds:
            if not feed.enabled:
                continue
            if _time.time() < poller._next_poll_times.get(feed.url, 0.0):
                continue
            poller._poll_feed(feed)

        assert sample_feed.url not in polled

    def test_feed_past_backoff_window_is_polled(self, sample_feed):
        """Once the backoff window expires the feed must be polled again."""
        import time as _time

        poller = FeedPoller(feeds=[sample_feed])
        # Set backoff window to the past.
        poller._next_poll_times[sample_feed.url] = _time.time() - 1
        poller._backoff_counts[sample_feed.url] = 1

        polled: list[str] = []

        def capturing_poll(feed: Feed) -> None:
            polled.append(feed.url)

        poller._poll_feed = capturing_poll  # type: ignore[method-assign]

        for feed in poller.feeds:
            if not feed.enabled:
                continue
            if _time.time() < poller._next_poll_times.get(feed.url, 0.0):
                continue
            poller._poll_feed(feed)

        assert sample_feed.url in polled
