"""Tests for FeedPoller webhook and script dispatch."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.feed_poller import FeedPoller
from src.models import FeedEntry


@pytest.fixture()
def entry() -> FeedEntry:
    return FeedEntry(
        feed_url="https://example.com/feed",
        title="Build #42 failed",
        link="https://example.com/build/42",
        published="2024-01-01T00:00:00Z",
        entry_id="entry-42",
        summary="Stage compile: ERROR",
    )


@pytest.fixture()
def poller() -> FeedPoller:
    return FeedPoller(feeds=[], poll_interval=60)


class TestDispatchWebhook:
    def test_posts_correct_json_payload(self, poller, entry):
        """_dispatch_webhook must POST all entry fields as JSON."""
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            poller._dispatch_webhook("https://hook.example.com/notify", entry)

        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        payload = json.loads(req.data.decode())
        assert payload["title"] == entry.title
        assert payload["link"] == entry.link
        assert payload["feed_url"] == entry.feed_url
        assert payload["published"] == entry.published
        assert payload["summary"] == entry.summary

    def test_posts_to_correct_url(self, poller, entry):
        """_dispatch_webhook must target the supplied URL."""
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            poller._dispatch_webhook("https://hook.example.com/notify", entry)

        req = mock_open.call_args[0][0]
        assert req.full_url == "https://hook.example.com/notify"

    def test_sets_content_type_header(self, poller, entry):
        """_dispatch_webhook must send Content-Type: application/json."""
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            poller._dispatch_webhook("https://hook.example.com/notify", entry)

        req = mock_open.call_args[0][0]
        assert req.get_header("Content-type") == "application/json"

    def test_swallows_network_exception(self, poller, entry):
        """_dispatch_webhook must not propagate exceptions."""
        with patch("urllib.request.urlopen", side_effect=OSError("Network down")):
            # Should not raise
            poller._dispatch_webhook("https://hook.example.com/notify", entry)

    def test_swallows_any_exception(self, poller, entry):
        """_dispatch_webhook must swallow all exception types silently."""
        with patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
            poller._dispatch_webhook("https://hook.example.com/notify", entry)


class TestDispatchScript:
    def test_passes_entry_fields_as_env_vars(self, poller, entry):
        """_dispatch_script must set all JINKIES_* env vars."""
        with patch("subprocess.Popen") as mock_popen:
            poller._dispatch_script("echo $JINKIES_TITLE", entry)

        mock_popen.assert_called_once()
        _, kwargs = mock_popen.call_args
        env = kwargs["env"]
        assert env["JINKIES_TITLE"] == entry.title
        assert env["JINKIES_LINK"] == entry.link
        assert env["JINKIES_FEED_URL"] == entry.feed_url
        assert env["JINKIES_PUBLISHED"] == entry.published
        assert env["JINKIES_SUMMARY"] == entry.summary

    def test_runs_with_shell_true(self, poller, entry):
        """_dispatch_script must use shell=True so the command string is interpreted."""
        with patch("subprocess.Popen") as mock_popen:
            poller._dispatch_script("my-script.sh", entry)

        _, kwargs = mock_popen.call_args
        assert kwargs["shell"] is True

    def test_passes_script_string(self, poller, entry):
        """_dispatch_script must forward the script string to Popen."""
        with patch("subprocess.Popen") as mock_popen:
            poller._dispatch_script("my-script.sh --flag", entry)

        args, _ = mock_popen.call_args
        assert args[0] == "my-script.sh --flag"

    def test_swallows_popen_exception(self, poller, entry):
        """_dispatch_script must not propagate exceptions from Popen."""
        with patch("subprocess.Popen", side_effect=OSError("No such file")):
            poller._dispatch_script("nonexistent-cmd", entry)

    def test_swallows_any_exception(self, poller, entry):
        """_dispatch_script must swallow all exception types silently."""
        with patch("subprocess.Popen", side_effect=RuntimeError("unexpected")):
            poller._dispatch_script("cmd", entry)

    def test_devnull_stdout_stderr(self, poller, entry):
        """_dispatch_script must suppress stdout and stderr output."""
        import subprocess
        with patch("subprocess.Popen") as mock_popen:
            poller._dispatch_script("cmd", entry)

        _, kwargs = mock_popen.call_args
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
