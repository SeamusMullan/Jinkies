"""Data models for Jinkies feed monitor.

Defines the core data structures used throughout the application:
Feed, FeedEntry, and AppConfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    """

    url: str
    name: str
    enabled: bool = True
    sound_file: str | None = None
    last_poll_time: str | None = None
    auth_user: str | None = None
    auth_token: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        Returns:
            Dictionary representation of this Feed.
        """
        return {
            "url": self.url,
            "name": self.name,
            "enabled": self.enabled,
            "sound_file": self.sound_file,
            "last_poll_time": self.last_poll_time,
            "auth_user": self.auth_user,
            "auth_token": self.auth_token,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Feed:
        """Deserialize from a dictionary.

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
    """

    poll_interval_secs: int = 60
    feeds: list[Feed] = field(default_factory=list)
    sound_map: dict[str, str] = field(default_factory=lambda: {
        "new_entry": "new_entry.wav",
        "error": "error.wav",
    })
    notification_style: str = "native"

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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with config fields.

        Returns:
            An AppConfig instance.
        """
        return cls(
            poll_interval_secs=data.get("poll_interval_secs", 60),
            feeds=[Feed.from_dict(f) for f in data.get("feeds", [])],
            sound_map=data.get("sound_map", {
                "new_entry": "new_entry.wav",
                "error": "error.wav",
            }),
            notification_style=data.get("notification_style", "native"),
        )
