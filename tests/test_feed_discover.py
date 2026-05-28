"""Tests for src.feed_discover.discover_feeds."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from src.feed_discover import discover_feeds

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RSS_HTML = b"""\
<!DOCTYPE html>
<html>
<head>
  <title>Example</title>
  <link rel="alternate" type="application/rss+xml"
        title="Example RSS" href="https://example.com/feed.rss"/>
</head>
<body><p>hello</p></body>
</html>
"""

_ATOM_HTML = b"""\
<!DOCTYPE html>
<html>
<head>
  <title>Example</title>
  <link rel="alternate" type="application/atom+xml"
        title="Example Atom" href="https://example.com/feed.atom"/>
</head>
<body></body>
</html>
"""

_RELATIVE_HTML = b"""\
<!DOCTYPE html>
<html>
<head>
  <link rel="alternate" type="application/rss+xml"
        title="Relative Feed" href="/feeds/rss"/>
</head>
<body></body>
</html>
"""

_BOTH_HTML = b"""\
<!DOCTYPE html>
<html>
<head>
  <link rel="alternate" type="application/rss+xml"
        title="RSS Feed" href="https://example.com/rss"/>
  <link rel="alternate" type="application/atom+xml"
        title="Atom Feed" href="https://example.com/atom"/>
</head>
<body></body>
</html>
"""

_NO_FEED_HTML = b"""\
<!DOCTYPE html>
<html><head><title>No feeds here</title></head><body></body></html>
"""


def _make_response(body: bytes, content_type: str = "text/html; charset=utf-8") -> MagicMock:
    """Return a mock urllib response object."""
    resp = MagicMock()
    resp.read.return_value = body
    resp.headers = {"Content-Type": content_type}
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDiscoverFeeds:
    def test_finds_rss_link(self):
        with patch("src.feed_discover.urllib.request.urlopen", return_value=_make_response(_RSS_HTML)):
            results = discover_feeds("https://example.com")
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com/feed.rss"
        assert results[0]["type"] == "rss"
        assert results[0]["title"] == "Example RSS"

    def test_finds_atom_link(self):
        with patch("src.feed_discover.urllib.request.urlopen", return_value=_make_response(_ATOM_HTML)):
            results = discover_feeds("https://example.com")
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com/feed.atom"
        assert results[0]["type"] == "atom"
        assert results[0]["title"] == "Example Atom"

    def test_handles_relative_urls(self):
        with patch("src.feed_discover.urllib.request.urlopen", return_value=_make_response(_RELATIVE_HTML)):
            results = discover_feeds("https://example.com/blog/")
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com/feeds/rss"

    def test_returns_empty_on_network_error(self):
        with patch("src.feed_discover.urllib.request.urlopen", side_effect=OSError("no network")):
            results = discover_feeds("https://example.com")
        assert results == []

    def test_returns_empty_when_no_feeds_in_html(self):
        with patch("src.feed_discover.urllib.request.urlopen", return_value=_make_response(_NO_FEED_HTML)):
            results = discover_feeds("https://example.com")
        assert results == []

    def test_finds_multiple_feeds(self):
        with patch("src.feed_discover.urllib.request.urlopen", return_value=_make_response(_BOTH_HTML)):
            results = discover_feeds("https://example.com")
        assert len(results) == 2
        types = {r["type"] for r in results}
        assert types == {"rss", "atom"}

    def test_deduplicates_same_url(self):
        html = b"""\
<!DOCTYPE html><html><head>
  <link rel="alternate" type="application/rss+xml" href="/rss"/>
  <link rel="alternate" type="application/rss+xml" href="/rss"/>
</head></html>
"""
        with patch("src.feed_discover.urllib.request.urlopen", return_value=_make_response(html)):
            results = discover_feeds("https://example.com")
        assert len(results) == 1

    def test_returns_empty_on_timeout(self):
        import urllib.error

        with patch("src.feed_discover.urllib.request.urlopen", side_effect=TimeoutError()):
            results = discover_feeds("https://example.com", timeout=1)
        assert results == []
