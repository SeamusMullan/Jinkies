"""Tests for src.url_validation."""

from __future__ import annotations

import pytest

from src.url_validation import validate_feed_url


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
