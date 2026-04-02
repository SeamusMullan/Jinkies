"""Threaded Atom/RSS feed polling for Jinkies.

Runs feed polling in a QThread with Qt signal/slot integration
for communicating new entries and errors to the main thread.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import http.client
import logging
import time
import urllib.error
import urllib.request
import uuid
from threading import Event, Lock
from typing import TYPE_CHECKING

import feedparser
from PySide6.QtCore import QThread, Signal

from src.credential_store import get_credentials
from src.models import Feed, FeedEntry
from src.url_validation import validate_feed_url

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class FeedPoller(QThread):
    """Background thread that polls Atom/RSS feeds on a timer.

    Signals:
        new_entries_found: Emitted with a list of new FeedEntry objects.
        feed_error: Emitted with (feed_url, error_message) on failure.
        poll_complete: Emitted after each full polling cycle.
        poll_time_updated: Emitted with (feed_url, iso_timestamp) after a
            successful poll so the main thread can update the Feed object.

    Attributes:
        feeds: List of Feed objects to poll.
        poll_interval: Seconds between poll cycles.
        seen_ids: Set of already-seen entry IDs.
    """

    new_entries_found = Signal(list)
    feed_error = Signal(str, str)
    poll_complete = Signal()
    poll_time_updated = Signal(str, str)

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
        self._feeds_lock = Lock()
        self.feeds = feeds
        self.poll_interval = poll_interval
        self.seen_ids: set[str] = seen_ids or set()
        self._pause_event = Event()
        self._pause_event.set()  # Start unpaused
        self._wakeup_event = Event()  # Set by update_interval() to abort sleep early

    def run(self) -> None:
        """Execute the polling loop.

        Polls all enabled feeds sequentially, emitting signals for new
        entries and errors, then sleeps until the next cycle.
        """
        while not self.isInterruptionRequested():
            self._pause_event.wait()
            if self.isInterruptionRequested():
                break

            with self._feeds_lock:
                feeds_snapshot = list(self.feeds)
            for feed in feeds_snapshot:
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
                entry_id = self._get_entry_id(entry)
                if entry_id in self.seen_ids:
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

            self.poll_time_updated.emit(
                feed.url,
                datetime.datetime.now(tz=datetime.UTC).isoformat(),
            )

            if new_entries:
                self.new_entries_found.emit(new_entries)

        except (OSError, ValueError, http.client.HTTPException, urllib.error.URLError) as e:
            self.feed_error.emit(feed.url, str(e))
        except Exception:
            logger.exception("Unexpected error polling feed %s", feed.url)
            raise

    def _get_entry_id(self, entry: object) -> str:
        """Return a stable unique ID for a feed entry.

        Tries the entry's ``id`` field, then ``link``.  If neither is
        present, computes a SHA-256 hash of the concatenated title,
        summary and published/updated fields so that structurally
        identical entries still map to the same key across restarts.
        If none of those content fields exist either, a UUID is used as
        a last resort (the entry will re-notify after a restart).

        Args:
            entry: A feedparser entry mapping.

        Returns:
            A non-empty string that uniquely identifies the entry.
        """
        entry_id = entry.get("id", "") or entry.get("link", "")
        if entry_id:
            return entry_id

        title = entry.get("title", "")
        summary = entry.get("summary", "")
        published = entry.get("published", entry.get("updated", ""))
        content = f"{title}|{summary}|{published}"
        if any([title, summary, published]):
            return hashlib.sha256(content.encode()).hexdigest()

        return str(uuid.uuid4())

    def _fetch_feed(self, feed: Feed) -> feedparser.FeedParserDict:
        """Fetch and parse a feed, handling authentication if configured.

        Credentials are retrieved from the OS keyring.  If the feed URL
        is not HTTPS and credentials exist, the fetch is refused and a
        ``feed_error`` signal is emitted.

        For feeds with auth credentials, fetches the content manually
        with HTTP Basic auth to bypass content-type issues (e.g. Jenkins
        serving Atom feeds as text/html).

        A 30-second socket timeout is applied to all network fetches so
        that a slow or unresponsive server cannot block the poller thread
        indefinitely and prevent a clean application shutdown.

        Args:
            feed: The feed to fetch.

        Returns:
            The parsed feedparser result.

        Raises:
            ValueError: If auth credentials exist but the URL is not HTTPS.
        """
        url_error = validate_feed_url(feed.url)
        if url_error:
            self.feed_error.emit(feed.url, url_error)
            return feedparser.parse("")

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
        # Use socket_timeout so a slow or unresponsive server cannot block
        # the poller thread indefinitely and prevent clean shutdown.
        return feedparser.parse(feed.url, socket_timeout=30)

    def _interruptible_sleep(self, seconds: int) -> None:
        """Sleep for *seconds*, waking early on shutdown or interval change.

        Checks :py:meth:`isInterruptionRequested` at most every 0.1 s so
        that a clean shutdown is never delayed more than one tick.
        Additionally, the sleep returns immediately when ``_wakeup_event``
        is set — which :py:meth:`update_interval` does — so a new poll
        interval takes effect without waiting for the full old interval to
        expire.

        Args:
            seconds: Total seconds to sleep.
        """
        deadline = time.monotonic() + seconds
        while not self.isInterruptionRequested():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            # Block for at most 0.1 s so interruption is detected quickly.
            # Returns True early when _wakeup_event is set (interval changed).
            if self._wakeup_event.wait(timeout=min(remaining, 0.1)):
                self._wakeup_event.clear()
                return

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
        with self._feeds_lock:
            self.feeds = feeds

    def update_interval(self, interval: int) -> None:
        """Update the polling interval and interrupt any in-progress sleep.

        Sets ``_wakeup_event`` so that :py:meth:`_interruptible_sleep`
        returns immediately, allowing the new interval to take effect from
        the very next poll cycle rather than after the old interval expires.

        Args:
            interval: New interval in seconds.
        """
        self.poll_interval = interval
        self._wakeup_event.set()
