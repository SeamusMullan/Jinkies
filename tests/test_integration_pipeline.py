"""Integration tests for the full polling → notification pipeline.

Exercises the end-to-end flow:
  poll detects new entry → ``new_entries_found`` signal fires →
  notification shown → audio played → entry marked seen.

These tests wire ``FeedPoller``, ``Notifier``, and ``AudioPlayer`` together
in the same way that ``JinkiesApp._on_new_entries`` does in production, using
a mocked HTTP feed so no real network calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.audio import AudioPlayer
from src.feed_poller import FeedPoller
from src.models import Feed, FeedEntry
from src.notifier import Notifier

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FEED_URL = "https://example.com/feed.atom"
_ENTRY_URL = "https://example.com/entry/42"


# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def integration_feed() -> Feed:
    """A single enabled feed used across all integration tests."""
    return Feed(url=_FEED_URL, name="Integration Test Feed", enabled=True)


@pytest.fixture
def single_entry_result() -> MagicMock:
    """A mock feedparser result containing one Atom entry."""
    entry = MagicMock()
    entry.get = lambda key, default="": {
        "id": _ENTRY_URL,
        "title": "Integration Entry",
        "link": _ENTRY_URL,
        "published": "2024-06-01T12:00:00Z",
    }.get(key, default)

    result = MagicMock()
    result.bozo = False
    result.entries = [entry]
    return result


@pytest.fixture
def two_entry_result() -> MagicMock:
    """A mock feedparser result containing two Atom entries from the same feed."""
    alpha = MagicMock()
    alpha.get = lambda key, default="": {
        "id": "entry-alpha",
        "title": "Alpha",
        "link": "https://example.com/alpha",
        "published": "2024-06-01T10:00:00Z",
    }.get(key, default)

    beta = MagicMock()
    beta.get = lambda key, default="": {
        "id": "entry-beta",
        "title": "Beta",
        "link": "https://example.com/beta",
        "published": "2024-06-01T11:00:00Z",
    }.get(key, default)

    result = MagicMock()
    result.bozo = False
    result.entries = [alpha, beta]
    return result


# ---------------------------------------------------------------------------
# Helper: a pipeline handler that mirrors JinkiesApp._on_new_entries
# ---------------------------------------------------------------------------


def _make_pipeline_handler(
    notifier: Notifier,
    audio: AudioPlayer,
    seen_ids: set[str],
    received: list[FeedEntry],
) -> object:
    """Return a slot function that replicates the production pipeline logic.

    Mirrors ``JinkiesApp._on_new_entries``:
    1. Accumulate entries for assertion.
    2. Play the ``"new_entry"`` audio cue.
    3. Build the notification title/body based on entry count.
    4. Call ``notifier.notify``.
    5. Mark each entry as seen.

    Args:
        notifier: The (possibly mocked) Notifier instance.
        audio: The (possibly mocked) AudioPlayer instance.
        seen_ids: A mutable set that accumulates seen entry IDs.
        received: A mutable list that accumulates received FeedEntry objects.

    Returns:
        A callable suitable for connecting to ``FeedPoller.new_entries_found``.
    """

    def on_new_entries(entries: list[FeedEntry]) -> None:
        received.extend(entries)
        audio.play("new_entry")

        count = len(entries)
        if count == 1:
            title = entries[0].title
            body = f"From: {entries[0].feed_url}"
        else:
            title = f"{count} new entries"
            body = f"From {len({e.feed_url for e in entries})} feed(s)"

        notifier.notify("Jinkies!", f"{title}\n{body}")

        for entry in entries:
            seen_ids.add(entry.entry_id)

    return on_new_entries


# ---------------------------------------------------------------------------
# Integration test suite
# ---------------------------------------------------------------------------


class TestPollingNotificationPipeline:
    """Integration tests for the poll → signal → notify → audio pipeline.

    Each test wires ``FeedPoller``, ``Notifier``, and ``AudioPlayer`` together
    using the same logic as ``JinkiesApp._on_new_entries`` and verifies the
    observable outputs of the full pipeline.
    """

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_new_entries_signal_carries_correct_feed_entry(
        self,
        mock_parse: MagicMock,
        _mock_creds: MagicMock,
        integration_feed: Feed,
        single_entry_result: MagicMock,
        qtbot: object,
    ) -> None:
        """``new_entries_found`` must emit a list with a correctly populated FeedEntry.

        Verifies that every field on the emitted ``FeedEntry`` matches the
        corresponding field in the mocked feedparser entry.
        """
        mock_parse.return_value = single_entry_result
        poller = FeedPoller(feeds=[integration_feed])

        received: list[FeedEntry] = []
        poller.new_entries_found.connect(received.extend)
        poller._poll_feed(integration_feed)

        assert len(received) == 1
        entry = received[0]
        assert isinstance(entry, FeedEntry)
        assert entry.title == "Integration Entry"
        assert entry.link == _ENTRY_URL
        assert entry.feed_url == _FEED_URL
        assert entry.entry_id == _ENTRY_URL
        assert entry.published == "2024-06-01T12:00:00Z"
        assert entry.seen is False

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_notifier_called_with_single_entry_arguments(
        self,
        mock_parse: MagicMock,
        _mock_creds: MagicMock,
        integration_feed: Feed,
        single_entry_result: MagicMock,
        qtbot: object,
    ) -> None:
        """Notifier must be called with the entry title and feed URL for one new entry."""
        mock_parse.return_value = single_entry_result
        mock_notifier = MagicMock(spec=Notifier)
        mock_audio = MagicMock(spec=AudioPlayer)
        seen_ids: set[str] = set()
        received: list[FeedEntry] = []

        poller = FeedPoller(feeds=[integration_feed])
        poller.new_entries_found.connect(
            _make_pipeline_handler(mock_notifier, mock_audio, seen_ids, received),
        )
        poller._poll_feed(integration_feed)

        mock_notifier.notify.assert_called_once_with(
            "Jinkies!",
            f"Integration Entry\nFrom: {_FEED_URL}",
        )

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_notifier_called_with_multiple_entry_arguments(
        self,
        mock_parse: MagicMock,
        _mock_creds: MagicMock,
        integration_feed: Feed,
        two_entry_result: MagicMock,
        qtbot: object,
    ) -> None:
        """Notifier must summarise count and feed count when multiple entries arrive."""
        mock_parse.return_value = two_entry_result
        mock_notifier = MagicMock(spec=Notifier)
        mock_audio = MagicMock(spec=AudioPlayer)
        seen_ids: set[str] = set()
        received: list[FeedEntry] = []

        poller = FeedPoller(feeds=[integration_feed])
        poller.new_entries_found.connect(
            _make_pipeline_handler(mock_notifier, mock_audio, seen_ids, received),
        )
        poller._poll_feed(integration_feed)

        mock_notifier.notify.assert_called_once_with(
            "Jinkies!",
            "2 new entries\nFrom 1 feed(s)",
        )

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_audio_player_called_with_new_entry_event(
        self,
        mock_parse: MagicMock,
        _mock_creds: MagicMock,
        integration_feed: Feed,
        single_entry_result: MagicMock,
        qtbot: object,
    ) -> None:
        """AudioPlayer must be called with the ``"new_entry"`` event type."""
        mock_parse.return_value = single_entry_result
        mock_notifier = MagicMock(spec=Notifier)
        mock_audio = MagicMock(spec=AudioPlayer)
        seen_ids: set[str] = set()
        received: list[FeedEntry] = []

        poller = FeedPoller(feeds=[integration_feed])
        poller.new_entries_found.connect(
            _make_pipeline_handler(mock_notifier, mock_audio, seen_ids, received),
        )
        poller._poll_feed(integration_feed)

        mock_audio.play.assert_called_once_with("new_entry")

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_entry_marked_seen_in_poller_seen_ids(
        self,
        mock_parse: MagicMock,
        _mock_creds: MagicMock,
        integration_feed: Feed,
        single_entry_result: MagicMock,
        qtbot: object,
    ) -> None:
        """The poller's internal ``seen_ids`` must contain the entry ID after polling.

        ``FeedPoller.seen_ids`` is updated synchronously inside ``_poll_feed``
        so that the same entry is never emitted twice across polls.
        """
        mock_parse.return_value = single_entry_result
        poller = FeedPoller(feeds=[integration_feed])
        poller._poll_feed(integration_feed)

        assert _ENTRY_URL in poller.seen_ids

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_entry_marked_seen_in_pipeline_handler(
        self,
        mock_parse: MagicMock,
        _mock_creds: MagicMock,
        integration_feed: Feed,
        single_entry_result: MagicMock,
        qtbot: object,
    ) -> None:
        """Pipeline handler must record entry IDs in its own seen-ID store."""
        mock_parse.return_value = single_entry_result
        mock_notifier = MagicMock(spec=Notifier)
        mock_audio = MagicMock(spec=AudioPlayer)
        seen_ids: set[str] = set()
        received: list[FeedEntry] = []

        poller = FeedPoller(feeds=[integration_feed])
        poller.new_entries_found.connect(
            _make_pipeline_handler(mock_notifier, mock_audio, seen_ids, received),
        )
        poller._poll_feed(integration_feed)

        assert _ENTRY_URL in seen_ids

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_full_pipeline_single_entry(
        self,
        mock_parse: MagicMock,
        _mock_creds: MagicMock,
        integration_feed: Feed,
        single_entry_result: MagicMock,
        qtbot: object,
    ) -> None:
        """Full pipeline: poll → signal → notifier + audio called + entry seen.

        This is the primary end-to-end scenario: a single new entry is
        discovered, the signal fires with the correct ``FeedEntry``, the audio
        cue is played, the notification is dispatched, and the entry ID is
        recorded as seen.
        """
        mock_parse.return_value = single_entry_result
        mock_notifier = MagicMock(spec=Notifier)
        mock_audio = MagicMock(spec=AudioPlayer)
        seen_ids: set[str] = set()
        received: list[FeedEntry] = []

        poller = FeedPoller(feeds=[integration_feed])
        poller.new_entries_found.connect(
            _make_pipeline_handler(mock_notifier, mock_audio, seen_ids, received),
        )
        poller._poll_feed(integration_feed)

        # Signal carried a valid FeedEntry
        assert len(received) == 1
        entry = received[0]
        assert isinstance(entry, FeedEntry)
        assert entry.title == "Integration Entry"
        assert entry.link == _ENTRY_URL

        # Notifier called with expected arguments
        mock_notifier.notify.assert_called_once_with(
            "Jinkies!",
            f"Integration Entry\nFrom: {_FEED_URL}",
        )

        # AudioPlayer called with the correct event type
        mock_audio.play.assert_called_once_with("new_entry")

        # Entry recorded as seen
        assert _ENTRY_URL in seen_ids

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_full_pipeline_multiple_entries(
        self,
        mock_parse: MagicMock,
        _mock_creds: MagicMock,
        integration_feed: Feed,
        two_entry_result: MagicMock,
        qtbot: object,
    ) -> None:
        """Full pipeline with two entries: all FeedEntry objects received and both marked seen."""
        mock_parse.return_value = two_entry_result
        mock_notifier = MagicMock(spec=Notifier)
        mock_audio = MagicMock(spec=AudioPlayer)
        seen_ids: set[str] = set()
        received: list[FeedEntry] = []

        poller = FeedPoller(feeds=[integration_feed])
        poller.new_entries_found.connect(
            _make_pipeline_handler(mock_notifier, mock_audio, seen_ids, received),
        )
        poller._poll_feed(integration_feed)

        # Both entries received by the signal
        assert len(received) == 2
        assert {e.title for e in received} == {"Alpha", "Beta"}
        assert all(isinstance(e, FeedEntry) for e in received)

        # Audio played exactly once for the batch
        mock_audio.play.assert_called_once_with("new_entry")

        # Notification summarises the batch
        mock_notifier.notify.assert_called_once_with(
            "Jinkies!",
            "2 new entries\nFrom 1 feed(s)",
        )

        # Both entries marked seen
        assert "entry-alpha" in seen_ids
        assert "entry-beta" in seen_ids

    @patch("src.feed_poller.get_credentials", return_value=None)
    @patch("src.feed_poller.feedparser.parse")
    def test_seen_entry_not_re_notified_on_second_poll(
        self,
        mock_parse: MagicMock,
        _mock_creds: MagicMock,
        integration_feed: Feed,
        single_entry_result: MagicMock,
        qtbot: object,
    ) -> None:
        """An entry seen on the first poll must not re-trigger notification on the second poll.

        ``FeedPoller`` tracks seen IDs internally so that the same entry is
        never emitted more than once, even when the feed still lists it.
        """
        mock_parse.return_value = single_entry_result
        mock_notifier = MagicMock(spec=Notifier)
        mock_audio = MagicMock(spec=AudioPlayer)
        seen_ids: set[str] = set()
        received: list[FeedEntry] = []

        poller = FeedPoller(feeds=[integration_feed])
        poller.new_entries_found.connect(
            _make_pipeline_handler(mock_notifier, mock_audio, seen_ids, received),
        )

        # First poll – entry is new; pipeline fires
        poller._poll_feed(integration_feed)
        assert mock_notifier.notify.call_count == 1
        assert mock_audio.play.call_count == 1

        # Second poll – feed unchanged; entry already in seen_ids; pipeline silent
        poller._poll_feed(integration_feed)
        assert mock_notifier.notify.call_count == 1
        assert mock_audio.play.call_count == 1
