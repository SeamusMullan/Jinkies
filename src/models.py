"""Data models for Jinkies feed monitor.

Defines the core data structures used throughout the application:
Feed, FeedEntry, AppConfig, and Rule.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

#: Minimum allowed value for :attr:`AppConfig.poll_interval_secs`.
_POLL_INTERVAL_MIN: int = 1

#: Minimum allowed value for :attr:`AppConfig.max_entries`.
_MAX_ENTRIES_MIN: int = 1

#: Minimum allowed value for :attr:`AppConfig.seen_ids_max_age_days`.
_SEEN_IDS_MAX_AGE_MIN: int = 1

#: Minimum allowed value for :attr:`AppConfig.page_size`.
_PAGE_SIZE_MIN: int = 1

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
        poll_interval_secs: Per-feed poll interval override in seconds.
            When ``None`` the global :attr:`AppConfig.poll_interval_secs`
            is used.  Minimum value is 1 second if provided.
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
    poll_interval_secs: int | None = None
    group: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        Credentials are never written to the config file.  Instead a
        ``has_auth`` flag indicates whether credentials are stored in
        the OS keyring.

        Returns:
            Dictionary representation of this Feed.
        """
        d: dict[str, Any] = {
            "url": self.url,
            "name": self.name,
            "enabled": self.enabled,
            "sound_file": self.sound_file,
            "last_poll_time": self.last_poll_time,
            "has_auth": bool(self.auth_user and self.auth_token),
            "etag": self.etag,
            "modified": self.modified,
            "group": self.group,
        }
        if self.poll_interval_secs is not None:
            d["poll_interval_secs"] = self.poll_interval_secs
        return d

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
        raw_feed_interval = data.get("poll_interval_secs")
        if raw_feed_interval is not None and raw_feed_interval < _POLL_INTERVAL_MIN:
            logger.warning(
                "Feed poll_interval_secs value %r is below the minimum of %d; "
                "clamping to %d.",
                raw_feed_interval,
                _POLL_INTERVAL_MIN,
                _POLL_INTERVAL_MIN,
            )
            raw_feed_interval = _POLL_INTERVAL_MIN
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
            poll_interval_secs=raw_feed_interval,
            group=data.get("group"),
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
        summary: Optional plain-text summary or content snippet for the entry.
    """

    feed_url: str
    title: str
    link: str
    published: str
    entry_id: str
    seen: bool = False
    summary: str = ""
    starred: bool = False

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
            "summary": self.summary,
            "starred": self.starred,
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
            summary=data.get("summary", ""),
            starred=data.get("starred", False),
        )


@dataclass
class Rule:
    """A user-defined rule: condition -> action on new feed entries.

    Attributes:
        name: Display name for the rule.
        enabled: Whether the rule is active.
        feed_url: Match only entries from this feed URL.  ``None`` matches all feeds.
        keyword: Case-insensitive substring match against entry title.
            ``None`` skips the keyword check.
        status: Jenkins status keyword to match (e.g. ``"stable"``, ``"failed"``,
            ``"unstable"``).  ``None`` skips the status check.
        sound_file: Path to a WAV file to play when the rule fires.
            ``None`` plays no additional sound.
        notification: Whether to send a desktop notification when the rule fires.
        highlight_color: Hex colour string (e.g. ``"#ff8800"``) for row highlight.
            ``None`` means no highlight.
        webhook_url: Legacy single-webhook action.  Retained for backward
            compatibility; new configs should reference named sinks instead.
        script: Legacy inline shell-command action, retained for backward
            compatibility.
        sinks: Names of configured sinks (see :class:`~src.notify_sinks.SinkConfig`)
            to fire when this rule matches.
    """

    name: str
    enabled: bool = True
    # Condition fields
    feed_url: str | None = None
    keyword: str | None = None
    status: str | None = None
    # Action fields
    sound_file: str | None = None
    notification: bool = False
    highlight_color: str | None = None
    webhook_url: str | None = None
    script: str | None = None
    sinks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        Returns:
            Dictionary representation of this Rule.
        """
        return {
            "name": self.name,
            "enabled": self.enabled,
            "feed_url": self.feed_url,
            "keyword": self.keyword,
            "status": self.status,
            "sound_file": self.sound_file,
            "notification": self.notification,
            "highlight_color": self.highlight_color,
            "webhook_url": self.webhook_url,
            "script": self.script,
            "sinks": list(self.sinks),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rule:
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with rule fields.

        Returns:
            A Rule instance.
        """
        return cls(
            name=data.get("name", ""),
            enabled=bool(data.get("enabled", True)),
            feed_url=data.get("feed_url"),
            keyword=data.get("keyword"),
            status=data.get("status"),
            sound_file=data.get("sound_file"),
            notification=bool(data.get("notification", False)),
            highlight_color=data.get("highlight_color"),
            webhook_url=data.get("webhook_url"),
            script=data.get("script"),
            sinks=list(data.get("sinks", [])),
        )

    def matches(self, entry: FeedEntry) -> bool:
        """Return True if this rule's conditions match *entry*.

        All specified conditions must match (AND logic).  A condition set to
        ``None`` is treated as a wildcard and always passes.

        Args:
            entry: The feed entry to test.

        Returns:
            True if every non-None condition matches.
        """
        if self.feed_url is not None and entry.feed_url != self.feed_url:
            return False
        if self.keyword is not None and self.keyword.lower() not in entry.title.lower():
            return False
        if self.status is not None:
            # Inline import avoided via lazy import at call site to prevent
            # circular imports; jenkins_status lives in src.notifier.
            from src.notifier import jenkins_status  # noqa: PLC0415
            result = jenkins_status(entry.title)
            if result is None:
                return False
            kw, _ = result
            if kw != self.status.lower():
                return False
        return True


@dataclass
class SavedFilter:
    """A named, reusable dashboard filter preset.

    Attributes:
        name: Display name for the preset.
        feed_filter: The feed-filter combo selection text (e.g. ``"All Feeds"``,
            ``"⭐ Starred"``, a group entry, or a feed name).
        search_text: Search-box text.
        include_content: Whether the "Include content" search option is on.
    """

    name: str
    feed_filter: str = "All Feeds"
    search_text: str = ""
    include_content: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "feed_filter": self.feed_filter,
            "search_text": self.search_text,
            "include_content": self.include_content,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SavedFilter:
        """Deserialize from a dictionary."""
        return cls(
            name=data.get("name", ""),
            feed_filter=data.get("feed_filter", "All Feeds"),
            search_text=data.get("search_text", ""),
            include_content=bool(data.get("include_content", False)),
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
        page_size: Number of entries to show per page in the entry table.
        theme: UI theme name.  ``"dark"`` for the built-in dark palette;
            any other value (e.g. ``"light"``) uses the platform default.
        show_tray_badge: Whether to draw an unread-count badge on the system
            tray icon.  When ``False`` the plain icon is always used.
    """

    poll_interval_secs: int = 60
    feeds: list[Feed] = field(default_factory=list)
    sound_map: dict[str, str] = field(default_factory=lambda: {
        "new_entry": "new_entry.wav",
        "error": "error.wav",
    })
    notification_style: str = "custom"
    max_entries: int = 10_000
    seen_ids_max_age_days: int = 30
    page_size: int = 100
    theme: str = "aero"
    show_tray_badge: bool = True
    rules: list[Rule] = field(default_factory=list)
    sinks: list[Any] = field(default_factory=list)
    saved_filters: list[SavedFilter] = field(default_factory=list)
    collapsed_groups: list[str] = field(default_factory=list)

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
            "page_size": self.page_size,
            "theme": self.theme,
            "show_tray_badge": self.show_tray_badge,
            "rules": [r.to_dict() for r in self.rules],
            "sinks": [s.to_dict() for s in self.sinks],
            "saved_filters": [f.to_dict() for f in self.saved_filters],
            "collapsed_groups": list(self.collapsed_groups),
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
        from src.notify_sinks import SinkConfig as _SinkConfig  # noqa: PLC0415

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

        raw_page_size = data.get("page_size", 100)
        if raw_page_size < _PAGE_SIZE_MIN:
            logger.warning(
                "page_size value %r is below the minimum of %d; "
                "clamping to %d.",
                raw_page_size,
                _PAGE_SIZE_MIN,
                _PAGE_SIZE_MIN,
            )
            raw_page_size = _PAGE_SIZE_MIN

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
            page_size=raw_page_size,
            theme=data.get("theme", "aero"),
            show_tray_badge=bool(data.get("show_tray_badge", True)),
            rules=[Rule.from_dict(r) for r in data.get("rules", [])],
            sinks=[_SinkConfig.from_dict(s) for s in data.get("sinks", [])],
            saved_filters=[
                SavedFilter.from_dict(f) for f in data.get("saved_filters", [])
            ],
            collapsed_groups=list(data.get("collapsed_groups", [])),
        )
