"""Data models for Jinkies feed monitor.

Defines the core data structures used throughout the application:
Feed, FeedEntry, and AppConfig.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

#: Minimum allowed value for :attr:`AppConfig.poll_interval_secs`.
_POLL_INTERVAL_MIN: int = 1

#: Minimum allowed value for :attr:`AppConfig.max_entries`.
_MAX_ENTRIES_MIN: int = 1

#: Minimum allowed value for :attr:`AppConfig.seen_ids_max_age_days`.
_SEEN_IDS_MAX_AGE_MIN: int = 1

#: Set of recognised values for :attr:`AppConfig.notification_style`.
_VALID_NOTIFICATION_STYLES: frozenset[str] = frozenset({"native", "custom"})


@dataclass
class Feed:
    """An Atom/RSS feed to monitor.

    Attributes:
        url: The feed URL.
        name: Display name for the feed.
        enabled: Whether polling is active for this feed.
        sound_file: Optional custom sound file path override.
        last_poll_time: ISO 8601 timestamp of last successful poll.
        auth_user: Optional username for HTTP Basic authentication.
        auth_token: Optional API token/password for HTTP Basic authentication.
        etag: HTTP ETag header value from the last successful poll, used
            to send conditional ``If-None-Match`` requests and avoid
            re-downloading unchanged feeds.
        modified: HTTP Last-Modified header value (RFC 7231 date string)
            from the last successful poll, used to send conditional
            ``If-Modified-Since`` requests.
    """

    url: str
    name: str
    enabled: bool = True
    sound_file: str | None = None
    last_poll_time: str | None = None
    auth_user: str | None = None
    auth_token: str | None = None
    etag: str | None = None
    modified: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        Credentials are never written to the config file.  Instead a
        ``has_auth`` flag indicates whether credentials are stored in
        the OS keyring.

        Returns:
            Dictionary representation of this Feed.
        """
        return {
            "url": self.url,
            "name": self.name,
            "enabled": self.enabled,
            "sound_file": self.sound_file,
            "last_poll_time": self.last_poll_time,
            "has_auth": bool(self.auth_user and self.auth_token),
            "etag": self.etag,
            "modified": self.modified,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Feed:
        """Deserialize from a dictionary.

        Handles both legacy configs (with plaintext ``auth_user``/
        ``auth_token``) and new configs (with ``has_auth`` flag).
        Legacy plaintext credentials are preserved in the dataclass
        fields so that ``load_config`` can migrate them to the keyring.

        Args:
            data: Dictionary with feed fields.

        Returns:
            A Feed instance.
        """
        return cls(
            url=data["url"],
            name=data["name"],
            enabled=data.get("enabled", True),
            sound_file=data.get("sound_file"),
            last_poll_time=data.get("last_poll_time"),
            auth_user=data.get("auth_user"),
            auth_token=data.get("auth_token"),
            etag=data.get("etag"),
            modified=data.get("modified"),
        )


@dataclass
class FeedEntry:
    """A single entry from a feed.

    Attributes:
        feed_url: URL of the feed this entry belongs to.
        title: Entry title.
        link: URL to the full entry.
        published: ISO 8601 publication timestamp.
        entry_id: Unique identifier for this entry.
        seen: Whether the user has seen this entry.
    """

    feed_url: str
    title: str
    link: str
    published: str
    entry_id: str
    seen: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        Returns:
            Dictionary representation of this FeedEntry.
        """
        return {
            "feed_url": self.feed_url,
            "title": self.title,
            "link": self.link,
            "published": self.published,
            "entry_id": self.entry_id,
            "seen": self.seen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedEntry:
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with entry fields.

        Returns:
            A FeedEntry instance.
        """
        return cls(
            feed_url=data["feed_url"],
            title=data["title"],
            link=data["link"],
            published=data.get("published", ""),
            entry_id=data["entry_id"],
            seen=data.get("seen", False),
        )


@dataclass
class AppConfig:
    """Application configuration.

    Attributes:
        poll_interval_secs: Seconds between poll cycles.
        feeds: List of monitored feeds.
        sound_map: Mapping of event type to WAV file path.
        notification_style: Either "native" or "custom".
        max_entries: Maximum number of feed entries to keep in memory and on
            disk.  Oldest entries are evicted when the limit is exceeded.
        seen_ids_max_age_days: Days after which a seen entry ID is pruned from
            state.  Entries older than this may re-appear as new if they are
            still present in the feed.
    """

    poll_interval_secs: int = 60
    feeds: list[Feed] = field(default_factory=list)
    sound_map: dict[str, str] = field(default_factory=lambda: {
        "new_entry": "new_entry.wav",
        "error": "error.wav",
    })
    notification_style: str = "native"
    max_entries: int = 10_000
    seen_ids_max_age_days: int = 30

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        Returns:
            Dictionary representation of this AppConfig.
        """
        return {
            "poll_interval_secs": self.poll_interval_secs,
            "feeds": [f.to_dict() for f in self.feeds],
            "sound_map": self.sound_map,
            "notification_style": self.notification_style,
            "max_entries": self.max_entries,
            "seen_ids_max_age_days": self.seen_ids_max_age_days,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Deserialize from a dictionary.

        Validates ``poll_interval_secs``, ``notification_style``, and
        ``max_entries`` before constructing the instance.  Invalid values
        are replaced with safe defaults and a warning is emitted so callers
        can detect and repair corrupt or hand-edited configuration files.

        * ``poll_interval_secs`` is clamped to a minimum of
          :data:`_POLL_INTERVAL_MIN` (1 second) to prevent busy-loops.
        * ``notification_style`` must be one of the values in
          :data:`_VALID_NOTIFICATION_STYLES` (``"native"`` or ``"custom"``);
          unrecognised values fall back to ``"native"``.
        * ``max_entries`` is clamped to a minimum of
          :data:`_MAX_ENTRIES_MIN` (1) to ensure at least one entry is kept.

        Args:
            data: Dictionary with config fields.

        Returns:
            An AppConfig instance.
        """
        raw_interval = data.get("poll_interval_secs", 60)
        if raw_interval < _POLL_INTERVAL_MIN:
            logger.warning(
                "poll_interval_secs value %r is below the minimum of %d; "
                "clamping to %d.",
                raw_interval,
                _POLL_INTERVAL_MIN,
                _POLL_INTERVAL_MIN,
            )
            raw_interval = _POLL_INTERVAL_MIN

        raw_style = data.get("notification_style", "native")
        if raw_style not in _VALID_NOTIFICATION_STYLES:
            logger.warning(
                "notification_style value %r is not recognised; "
                "falling back to 'native'. Valid values: %s.",
                raw_style,
                sorted(_VALID_NOTIFICATION_STYLES),
            )
            raw_style = "native"

        raw_max_entries = data.get("max_entries", 10_000)
        if raw_max_entries < _MAX_ENTRIES_MIN:
            logger.warning(
                "max_entries value %r is below the minimum of %d; "
                "clamping to %d.",
                raw_max_entries,
                _MAX_ENTRIES_MIN,
                _MAX_ENTRIES_MIN,
            )
            raw_max_entries = _MAX_ENTRIES_MIN

        raw_max_age = data.get("seen_ids_max_age_days", 30)
        if raw_max_age < _SEEN_IDS_MAX_AGE_MIN:
            logger.warning(
                "seen_ids_max_age_days value %r is below the minimum of %d; "
                "clamping to %d.",
                raw_max_age,
                _SEEN_IDS_MAX_AGE_MIN,
                _SEEN_IDS_MAX_AGE_MIN,
            )
            raw_max_age = _SEEN_IDS_MAX_AGE_MIN

        return cls(
            poll_interval_secs=raw_interval,
            feeds=[Feed.from_dict(f) for f in data.get("feeds", [])],
            sound_map=data.get("sound_map", {
                "new_entry": "new_entry.wav",
                "error": "error.wav",
            }),
            notification_style=raw_style,
            max_entries=raw_max_entries,
            seen_ids_max_age_days=raw_max_age,
        )
