"""Threaded Atom/RSS feed polling for Jinkies.

Runs feed polling in a QThread with Qt signal/slot integration
for communicating new entries and errors to the main thread.
"""

from __future__ import annotations

import base64
import datetime
import time
import urllib.request
from threading import Event
from typing import TYPE_CHECKING

import feedparser
from PySide6.QtCore import QThread, Signal

from src.credential_store import get_credentials
from src.models import Feed, FeedEntry

if TYPE_CHECKING:
    pass


class FeedPoller(QThread):
    """Background thread that polls Atom/RSS feeds on a timer.

    Signals:
        new_entries_found: Emitted with a list of new FeedEntry objects.
        feed_error: Emitted with (feed_url, error_message) on failure.
        poll_complete: Emitted after each full polling cycle.

    Attributes:
        feeds: List of Feed objects to poll.
        poll_interval: Seconds between poll cycles.
        seen_ids: Set of already-seen entry IDs.
    """

    new_entries_found = Signal(list)
    feed_error = Signal(str, str)
    poll_complete = Signal()

    def __init__(
        self,
        feeds: list[Feed],
        poll_interval: int = 60,
        seen_ids: set[str] | None = None,
    ) -> None:
        """Initialize the feed poller.

        Args:
            feeds: List of feeds to monitor.
            poll_interval: Seconds between poll cycles.
            seen_ids: Set of entry IDs already seen.
        """
        super().__init__()
        self.feeds = feeds
        self.poll_interval = poll_interval
        self.seen_ids: set[str] = seen_ids or set()
        self._pause_event = Event()
        self._pause_event.set()  # Start unpaused

    def run(self) -> None:
        """Execute the polling loop.

        Polls all enabled feeds sequentially, emitting signals for new
        entries and errors, then sleeps until the next cycle.
        """
        while not self.isInterruptionRequested():
            self._pause_event.wait()
            if self.isInterruptionRequested():
                break

            for feed in self.feeds:
                if self.isInterruptionRequested():
                    break
                if not feed.enabled:
                    continue
                self._poll_feed(feed)

            self.poll_complete.emit()
            self._interruptible_sleep(self.poll_interval)

    def _poll_feed(self, feed: Feed) -> None:
        """Poll a single feed and emit signals for new entries.

        Args:
            feed: The feed to poll.
        """
        try:
            parsed = self._fetch_feed(feed)
            if parsed.bozo and not parsed.entries:
                error_msg = str(parsed.bozo_exception) if parsed.bozo_exception else "Parse error"
                self.feed_error.emit(feed.url, error_msg)
                return

            new_entries = []
            for entry in parsed.entries:
                entry_id = entry.get("id", entry.get("link", ""))
                if not entry_id or entry_id in self.seen_ids:
                    continue

                self.seen_ids.add(entry_id)
                published = entry.get("published", entry.get("updated", ""))
                new_entries.append(
                    FeedEntry(
                        feed_url=feed.url,
                        title=entry.get("title", "Untitled"),
                        link=entry.get("link", ""),
                        published=published,
                        entry_id=entry_id,
                        seen=False,
                    )
                )

            feed.last_poll_time = datetime.datetime.now(tz=datetime.UTC).isoformat()

            if new_entries:
                self.new_entries_found.emit(new_entries)

        except Exception as e:  # noqa: BLE001
            self.feed_error.emit(feed.url, str(e))

    def _fetch_feed(self, feed: Feed) -> feedparser.FeedParserDict:
        """Fetch and parse a feed, handling authentication if configured.

        Credentials are retrieved from the OS keyring.  If the feed URL
        is not HTTPS and credentials exist, the fetch is refused and a
        ``feed_error`` signal is emitted.

        For feeds with auth credentials, fetches the content manually
        with HTTP Basic auth to bypass content-type issues (e.g. Jenkins
        serving Atom feeds as text/html).

        Args:
            feed: The feed to fetch.

        Returns:
            The parsed feedparser result.

        Raises:
            ValueError: If auth credentials exist but the URL is not HTTPS.
        """
        creds = get_credentials(feed.url)
        if creds:
            if not feed.url.startswith("https://"):
                msg = (
                    f"Refusing to send credentials over insecure HTTP "
                    f"for feed: {feed.url}"
                )
                raise ValueError(msg)
            username, token = creds
            credentials = f"{username}:{token}"
            b64 = base64.b64encode(credentials.encode()).decode()
            req = urllib.request.Request(  # noqa: S310
                feed.url,
                headers={"Authorization": f"Basic {b64}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                content = resp.read()
            return feedparser.parse(content)
        return feedparser.parse(feed.url)

    def _interruptible_sleep(self, seconds: int) -> None:
        """Sleep in small increments to allow quick shutdown.

        Args:
            seconds: Total seconds to sleep.
        """
        for _ in range(seconds * 10):
            if self.isInterruptionRequested():
                return
            time.sleep(0.1)

    def pause(self) -> None:
        """Pause the polling loop."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume the polling loop."""
        self._pause_event.set()

    @property
    def is_paused(self) -> bool:
        """Check if the poller is currently paused.

        Returns:
            True if paused.
        """
        return not self._pause_event.is_set()

    def update_feeds(self, feeds: list[Feed]) -> None:
        """Update the list of feeds to poll.

        Args:
            feeds: New list of feeds.
        """
        self.feeds = feeds

    def update_interval(self, interval: int) -> None:
        """Update the polling interval.

        Args:
            interval: New interval in seconds.
        """
        self.poll_interval = interval
