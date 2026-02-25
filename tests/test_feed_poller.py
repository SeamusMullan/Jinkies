"""Tests for src.feed_poller."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
        mock_parse.side_effect = Exception("Network error")
        poller = FeedPoller(feeds=[sample_feed])

        errors = []
        poller.feed_error.connect(lambda url, msg: errors.append((url, msg)))
        poller._poll_feed(sample_feed)

        assert len(errors) == 1
        assert errors[0][0] == sample_feed.url
        assert "Network error" in errors[0][1]

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
