"""Tests for src.url_validation."""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from src.url_validation import check_feed_connectivity, validate_feed_url


class TestValidateFeedUrl:
    @pytest.mark.parametrize("url", [
        "https://example.com/feed.atom",
        "https://jenkins.local:8443/rssAll",
        "http://example.com/feed.xml",
        "http://192.168.1.1/rss",
    ])
    def test_valid_urls(self, url):
        assert validate_feed_url(url) is None

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "file:///home/user/.ssh/id_rsa",
        "data:text/xml,<feed/>",
        "javascript:alert(1)",
        "ftp://example.com/feed.xml",
        "gopher://example.com/",
    ])
    def test_blocked_schemes(self, url):
        error = validate_feed_url(url)
        assert error is not None
        assert "not allowed" in error

    def test_empty_string(self):
        error = validate_feed_url("")
        assert error is not None
        assert "empty" in error.lower()

    def test_whitespace_only(self):
        error = validate_feed_url("   ")
        assert error is not None
        assert "empty" in error.lower()

    def test_no_scheme(self):
        error = validate_feed_url("example.com/feed")
        assert error is not None
        assert "not allowed" in error

    def test_scheme_only_no_host(self):
        error = validate_feed_url("https://")
        assert error is not None
        assert "hostname" in error.lower()


class TestCheckFeedConnectivity:
    """Tests for check_feed_connectivity."""

    def test_successful_connection_returns_none(self):
        """A 200 response should return None (no error)."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200

        with patch("src.url_validation.urllib.request.urlopen", return_value=mock_resp):
            assert check_feed_connectivity("https://example.com/feed") is None

    def test_http_4xx_returns_error(self):
        """A 404 HTTPError should return an error message."""
        exc = urllib.error.HTTPError(
            url="https://example.com/feed",
            code=404,
            msg="Not Found",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        with patch("src.url_validation.urllib.request.urlopen", side_effect=exc):
            error = check_feed_connectivity("https://example.com/feed")
        assert error is not None
        assert "404" in error

    def test_url_error_returns_error(self):
        """A URLError (e.g. DNS failure) should return an error message."""
        exc = urllib.error.URLError("Name or service not known")
        with patch("src.url_validation.urllib.request.urlopen", side_effect=exc):
            error = check_feed_connectivity("https://nonexistent.invalid/feed")
        assert error is not None
        assert "connect" in error.lower()

    def test_os_error_returns_error(self):
        """A low-level OSError should return an error message."""
        with patch(
            "src.url_validation.urllib.request.urlopen",
            side_effect=OSError("timed out"),
        ):
            error = check_feed_connectivity("https://example.com/feed")
        assert error is not None
        assert "connection error" in error.lower()

    def test_custom_timeout_is_passed(self):
        """The timeout parameter should be forwarded to urlopen."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200

        with patch(
            "src.url_validation.urllib.request.urlopen", return_value=mock_resp
        ) as mock_open:
            check_feed_connectivity("https://example.com/feed", timeout=3)

        _, kwargs = mock_open.call_args
        assert kwargs.get("timeout") == 3
