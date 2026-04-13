"""Threaded Atom/RSS feed polling for Jinkies.

Runs feed polling in a QThread with Qt signal/slot integration
for communicating new entries and errors to the main thread.

Exponential backoff
-------------------
When a feed request fails (network error, 5xx, or parse error),
the poller enters a per-feed *backoff* state so that it does not
hammer the server repeatedly.  The backoff delay starts at
``_BACKOFF_BASE_SECS`` (60 s / 1 min) and doubles with every
consecutive failure, capped at ``max_backoff_secs`` (default
3 600 s / 60 min).  A successful poll resets the counter to zero.

The ``feed_backoff_changed`` signal is emitted whenever the backoff
state of a feed changes so that the UI can reflect the delay in the
feed list tooltip.
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

#: Starting backoff interval in seconds (1 minute).
_BACKOFF_BASE_SECS: int = 60


class FeedPoller(QThread):
    """Background thread that polls Atom/RSS feeds on a timer.

    Signals:
        new_entries_found: Emitted with a list of new FeedEntry objects.
        feed_error: Emitted with (feed_url, error_message) on failure.
        poll_complete: Emitted after each full polling cycle.
        poll_time_updated: Emitted with (feed_url, iso_timestamp) after a
            successful poll so the main thread can update the Feed object.
        feed_backoff_changed: Emitted with (feed_url, backoff_seconds) when
            the backoff state of a feed changes.  A value of ``0`` means the
            feed has recovered and its backoff has been cleared.

    Attributes:
        feeds: List of Feed objects to poll.
        poll_interval: Seconds between poll cycles.
        seen_ids: Set of already-seen entry IDs.
        max_backoff_secs: Maximum backoff delay in seconds (default 3600).
    """

    new_entries_found = Signal(list)
    feed_error = Signal(str, str)
    poll_complete = Signal()
    poll_time_updated = Signal(str, str)
    feed_backoff_changed = Signal(str, int)

    def __init__(
        self,
        feeds: list[Feed],
        poll_interval: int = 60,
        seen_ids: set[str] | None = None,
        max_backoff_secs: int = 3600,
    ) -> None:
        """Initialize the feed poller.

        Args:
            feeds: List of feeds to monitor.
            poll_interval: Seconds between poll cycles.
            seen_ids: Set of entry IDs already seen.
            max_backoff_secs: Upper limit for the exponential backoff delay
                in seconds.  Defaults to 3600 (60 minutes).
        """
        super().__init__()
        self._feeds_lock = Lock()
        self.feeds = feeds
        self.poll_interval = poll_interval
        self.seen_ids: set[str] = seen_ids or set()
        self.max_backoff_secs = max_backoff_secs
        self._pause_event = Event()
        self._pause_event.set()  # Start unpaused
        self._sleep_interrupt_event = Event()
        # Per-feed backoff state (only accessed from the poller thread).
        self._backoff_counts: dict[str, int] = {}
        self._next_poll_times: dict[str, float] = {}

    def run(self) -> None:
        """Execute the polling loop.

        Polls all enabled feeds sequentially, emitting signals for new
        entries and errors, then sleeps until the next cycle.  Feeds that
        are currently in an exponential-backoff window are skipped until
        their backoff delay has elapsed.
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
                if time.time() < self._next_poll_times.get(feed.url, 0.0):
                    # Feed is still within its backoff window; skip this cycle.
                    continue
                self._poll_feed(feed)

            self.poll_complete.emit()
            self._interruptible_sleep(self.poll_interval)

    def _poll_feed(self, feed: Feed) -> None:
        """Poll a single feed and emit signals for new entries.

        On failure the feed enters an exponential-backoff state so that
        subsequent cycles skip it until the backoff window elapses.  A
        successful poll resets the backoff counter.

        Args:
            feed: The feed to poll.
        """
        try:
            parsed = self._fetch_feed(feed)
            if parsed.bozo and not parsed.entries:
                error_msg = str(parsed.bozo_exception) if parsed.bozo_exception else "Parse error"
                self._handle_poll_failure(feed, error_msg)
                return

            # Successful parse — reset any active backoff before processing.
            self._handle_poll_success(feed)

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
            self._handle_poll_failure(feed, str(e))
        except Exception:
            logger.exception("Unexpected error polling feed %s", feed.url)
            raise

    def _compute_backoff_secs(self, failure_count: int) -> int:
        """Compute the exponential backoff delay for a given failure count.

        Backoff starts at ``_BACKOFF_BASE_SECS`` (1 min) and doubles with
        every consecutive failure, capped at :attr:`max_backoff_secs`.

        Args:
            failure_count: Number of consecutive failures so far (0-indexed).
                Pass ``0`` for the delay after the very first failure.

        Returns:
            Delay in seconds before the next poll attempt.
        """
        return min(_BACKOFF_BASE_SECS * (2 ** failure_count), self.max_backoff_secs)

    def _handle_poll_success(self, feed: Feed) -> None:
        """Reset backoff state after a successful poll.

        Clears the failure counter and scheduled next-poll time for *feed*.
        Emits ``feed_backoff_changed(url, 0)`` only if the feed was
        previously in a backoff state so that the UI can remove the
        backoff indicator.

        Args:
            feed: The feed whose poll succeeded.
        """
        was_in_backoff = feed.url in self._backoff_counts
        self._backoff_counts.pop(feed.url, None)
        self._next_poll_times.pop(feed.url, None)
        if was_in_backoff:
            self.feed_backoff_changed.emit(feed.url, 0)

    def _handle_poll_failure(self, feed: Feed, error_msg: str) -> None:
        """Record a poll failure and schedule the next retry with backoff.

        Emits both ``feed_error`` (with the human-readable message) and
        ``feed_backoff_changed`` (with the computed delay in seconds) so
        that callers can update error indicators and backoff state
        independently.

        Args:
            feed: The feed whose poll failed.
            error_msg: Human-readable description of the error.
        """
        self.feed_error.emit(feed.url, error_msg)
        failure_count = self._backoff_counts.get(feed.url, 0)
        backoff_secs = self._compute_backoff_secs(failure_count)
        self._backoff_counts[feed.url] = failure_count + 1
        self._next_poll_times[feed.url] = time.time() + backoff_secs
        self.feed_backoff_changed.emit(feed.url, backoff_secs)

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

        Conditional GET support: if the feed has a cached ``etag`` or
        ``modified`` value from a previous poll, these are sent as
        ``If-None-Match`` / ``If-Modified-Since`` request headers so that
        the server can reply with HTTP 304 (Not Modified) when the feed
        content has not changed, avoiding a full re-download.  On a
        successful response the values are stored back onto the feed object
        for use in the next poll.

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
            headers: dict[str, str] = {"Authorization": f"Basic {b64}"}
            if feed.etag:
                headers["If-None-Match"] = feed.etag
            if feed.modified:
                headers["If-Modified-Since"] = feed.modified
            req = urllib.request.Request(  # noqa: S310
                feed.url,
                headers=headers,
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                    content = resp.read()
                    etag = resp.headers.get("ETag")
                    last_modified = resp.headers.get("Last-Modified")
            except urllib.error.HTTPError as exc:
                if exc.code == 304:
                    # Server says content has not changed; return an empty
                    # result so the poller skips entry processing.
                    return feedparser.parse("")
                raise
            if etag:
                feed.etag = etag
            if last_modified:
                feed.modified = last_modified
            return feedparser.parse(content)

        # Use socket_timeout so a slow or unresponsive server cannot block
        # the poller thread indefinitely and prevent clean shutdown.
        # Pass etag/modified so feedparser sends conditional-GET headers and
        # the server can respond with 304 when nothing has changed.
        parsed = feedparser.parse(
            feed.url,
            socket_timeout=30,
            etag=feed.etag,
            modified=feed.modified,
        )
        etag = getattr(parsed, "etag", None)
        modified = getattr(parsed, "modified", None)
        if etag:
            feed.etag = etag
        if modified:
            feed.modified = modified
        return parsed

    def _interruptible_sleep(self, seconds: int) -> None:
        """Sleep for *seconds*, waking early on shutdown or interval change.

        Uses a :class:`threading.Event` so that callers like
        :meth:`update_interval` can interrupt the sleep immediately instead
        of waiting for the current interval to expire.

        Args:
            seconds: Total seconds to sleep.
        """
        self._sleep_interrupt_event.clear()
        deadline = time.monotonic() + seconds
        while True:
            if self.isInterruptionRequested():
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            # Wait up to 0.1 s (or the remaining time if less).
            # Returns True if the event was set (early wake), False on timeout.
            if self._sleep_interrupt_event.wait(timeout=min(0.1, remaining)):
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

        The currently sleeping :meth:`_interruptible_sleep` is woken
        immediately so the next poll cycle uses the new interval without
        waiting for the old one to expire.

        Args:
            interval: New interval in seconds.
        """
        self.poll_interval = interval
        self._sleep_interrupt_event.set()
