"""Pluggable notification sinks for Jinkies.

A *sink* is a destination that a triggered rule can fire at: an HTTP webhook
(Discord, Slack, ntfy, Pushover, or a custom endpoint) or a local shell script.
Sinks replace the previous inline fire-and-forget dispatch in
:mod:`src.feed_poller` with a registry of named, configurable, testable
destinations whose send results are captured rather than silently swallowed.

Design notes
------------
* :class:`SinkPayload` is the normalized data a sink renders.  It is built from
  a :class:`~src.models.FeedEntry` plus the resolved feed display name and
  Jenkins status keyword.
* :func:`render_template` does *safe* ``str.format_map`` templating — missing
  keys render as the empty string and there is **no** ``eval`` / arbitrary code
  path, so a user-authored template cannot execute code.
* Secrets (Pushover/ntfy tokens) are never stored in templates or config.
  Templates may reference ``{secret:KEY}`` placeholders which are resolved at
  send time from :mod:`src.sink_secret_store` (the OS keyring).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from src.sink_secret_store import get_sink_secret

if TYPE_CHECKING:
    from src.models import FeedEntry

logger = logging.getLogger(__name__)

#: HTTP request timeout for webhook sinks, in seconds.
_HTTP_TIMEOUT_SECS: int = 10

#: Placeholder pattern for keyring-resolved secrets, e.g. ``{secret:token}``.
_SECRET_RE = re.compile(r"\{secret:([A-Za-z0-9_]+)\}")


@dataclass
class SinkPayload:
    """Normalized payload a sink renders into a request or environment.

    Attributes:
        title: Entry title.
        link: Entry link URL.
        status: Jenkins status keyword (e.g. ``"failed"``) or ``""``.
        feed_name: Display name of the originating feed.
        feed_url: URL of the originating feed.
        published: Published timestamp string.
        summary: Entry summary/body text.
    """

    title: str
    link: str
    status: str
    feed_name: str
    feed_url: str
    published: str
    summary: str = ""

    @classmethod
    def from_entry(
        cls, entry: FeedEntry, feed_name: str, status: str = ""
    ) -> SinkPayload:
        """Build a payload from a feed entry.

        Args:
            entry: The feed entry that triggered the rule.
            feed_name: Resolved display name for the entry's feed.
            status: Jenkins status keyword, or ``""`` if not applicable.

        Returns:
            A populated :class:`SinkPayload`.
        """
        return cls(
            title=entry.title,
            link=entry.link,
            status=status,
            feed_name=feed_name,
            feed_url=entry.feed_url,
            published=entry.published,
            summary=entry.summary,
        )

    @classmethod
    def sample(cls) -> SinkPayload:
        """Return a representative payload for use by 'Send test' actions."""
        return cls(
            title="Jinkies test — Build #42 (failed)",
            link="https://jenkins.example.com/job/demo/42/",
            status="failed",
            feed_name="Demo Feed",
            feed_url="https://jenkins.example.com/job/demo/rssAll",
            published="2026-06-04T12:00:00Z",
            summary="This is a test notification from Jinkies.",
        )


class _SafeDict(dict):
    """``dict`` whose missing keys format to the empty string."""

    def __missing__(self, key: str) -> str:  # noqa: D105
        return ""


def render_template(template: str, payload: SinkPayload) -> str:
    """Render *template* against *payload* fields with safe substitution.

    Uses ``str.format_map`` so only ``{field}`` placeholders matching payload
    attributes are substituted; unknown placeholders render as empty strings
    rather than raising.  There is no code-execution path.

    Args:
        template: Template string using ``{title}``, ``{link}``, ``{status}``,
            ``{feed_name}``, ``{feed_url}``, ``{published}``, ``{summary}``.
        payload: The data to substitute.

    Returns:
        The rendered string.
    """
    try:
        return template.format_map(_SafeDict(asdict(payload)))
    except (ValueError, IndexError):
        # Malformed template (e.g. stray brace or positional {0}); return as-is
        # rather than crashing the dispatch.
        return template


def _resolve_secrets(text: str, sink_name: str) -> str:
    """Replace ``{secret:KEY}`` placeholders with keyring values.

    Args:
        text: The string possibly containing secret placeholders.
        sink_name: Name of the sink whose secrets to look up.

    Returns:
        The string with secrets substituted (missing secrets render empty).
    """

    def _sub(match: re.Match[str]) -> str:
        return get_sink_secret(sink_name, match.group(1)) or ""

    return _SECRET_RE.sub(_sub, text)


@dataclass
class ProviderPreset:
    """A template bundle for a notification provider.

    Attributes:
        name: Human-readable provider name.
        transport: ``"http"`` or ``"script"``.
        url_template: Default URL template (user typically edits this).
        headers: Default header name→value templates.
        body_template: Default request body template.
        content_type: Default ``Content-Type`` (informational; may be set in
            headers too).
        secret_fields: Keyring secret keys this provider expects (e.g.
            ``("token",)``), surfaced as masked fields in the UI.
    """

    name: str
    transport: str = "http"
    url_template: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body_template: str = ""
    content_type: str = "application/json"
    secret_fields: tuple[str, ...] = ()


#: Built-in provider presets keyed by a stable identifier.
PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "custom": ProviderPreset(
        name="Custom",
        transport="http",
        url_template="",
        headers={"Content-Type": "application/json"},
        body_template='{"text": "{title} — {link}"}',
        content_type="application/json",
    ),
    "discord": ProviderPreset(
        name="Discord",
        transport="http",
        url_template="https://discord.com/api/webhooks/",
        headers={"Content-Type": "application/json"},
        body_template='{"content": "**{title}**\\n{link}"}',
        content_type="application/json",
    ),
    "slack": ProviderPreset(
        name="Slack",
        transport="http",
        url_template="https://hooks.slack.com/services/",
        headers={"Content-Type": "application/json"},
        body_template='{"text": "{title}\\n{link}"}',
        content_type="application/json",
    ),
    "ntfy": ProviderPreset(
        name="ntfy",
        transport="http",
        url_template="https://ntfy.sh/your-topic-name",
        headers={
            "Title": "{feed_name}: {status}",
            "Tags": "jenkins",
        },
        body_template="{title}\n{link}",
        content_type="text/plain",
    ),
    "pushover": ProviderPreset(
        name="Pushover",
        transport="http",
        url_template="https://api.pushover.net/1/messages.json",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body_template=(
            "token={secret:app_token}&user={secret:user_key}"
            "&title={feed_name}&message={title} {link}"
        ),
        content_type="application/x-www-form-urlencoded",
        secret_fields=("app_token", "user_key"),
    ),
    "script": ProviderPreset(
        name="Script",
        transport="script",
        body_template="",
    ),
}


@dataclass
class SinkConfig:
    """User configuration for a single named sink.

    Serialized to ``config.json``.  **Secrets are never stored here** — they
    live in the OS keyring and are referenced via ``{secret:KEY}`` placeholders.

    Attributes:
        name: Unique identifier referenced by :attr:`~src.models.Rule.sinks`.
        provider: Key into :data:`PROVIDER_PRESETS`.
        transport: ``"http"`` or ``"script"``.
        url: HTTP endpoint (for ``http`` transport).
        headers: Header name→value templates.
        body_template: Request body template, or ``""`` to use the preset's.
        script: Shell command (for ``script`` transport).
        enabled: Whether the sink is active.
    """

    name: str
    provider: str = "custom"
    transport: str = "http"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body_template: str = ""
    script: str = ""
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary (no secrets)."""
        return {
            "name": self.name,
            "provider": self.provider,
            "transport": self.transport,
            "url": self.url,
            "headers": dict(self.headers),
            "body_template": self.body_template,
            "script": self.script,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SinkConfig:
        """Deserialize from a dictionary."""
        return cls(
            name=data.get("name", ""),
            provider=data.get("provider", "custom"),
            transport=data.get("transport", "http"),
            url=data.get("url", ""),
            headers=dict(data.get("headers", {})),
            body_template=data.get("body_template", ""),
            script=data.get("script", ""),
            enabled=bool(data.get("enabled", True)),
        )


@dataclass
class SendResult:
    """Outcome of a single sink dispatch.

    Attributes:
        ok: Whether the dispatch succeeded.
        status_code: HTTP status code, if applicable.
        error: Human-readable error message, or ``None`` on success.
    """

    ok: bool
    status_code: int | None = None
    error: str | None = None


class Sink(ABC):
    """A destination that a triggered rule fires at."""

    name: str

    @abstractmethod
    def send(self, payload: SinkPayload) -> SendResult:
        """Dispatch *payload*. Must not raise; returns a :class:`SendResult`."""

    def test(self) -> SendResult:
        """Dispatch a representative sample payload (for 'Send test')."""
        return self.send(SinkPayload.sample())


class WebhookSink(Sink):
    """An HTTP webhook sink rendering a templated request body and headers."""

    def __init__(self, config: SinkConfig) -> None:
        """Initialize from a sink configuration.

        Args:
            config: The sink configuration to dispatch with.
        """
        self.name = config.name
        self._config = config
        preset = PROVIDER_PRESETS.get(config.provider)
        # Headers/body fall back to the provider preset when unset.
        self._headers = config.headers or (dict(preset.headers) if preset else {})
        self._body_template = config.body_template or (
            preset.body_template if preset else ""
        )

    def send(self, payload: SinkPayload) -> SendResult:  # noqa: D102
        url = self._config.url.strip()
        if not url:
            return SendResult(ok=False, error="Sink URL is empty")
        if not url.startswith("https://"):
            return SendResult(
                ok=False,
                error="Refusing to send over non-HTTPS URL",
            )
        body = _resolve_secrets(render_template(self._body_template, payload), self.name)
        headers = {
            k: _resolve_secrets(render_template(v, payload), self.name)
            for k, v in self._headers.items()
        }
        headers.setdefault("User-Agent", "Jinkies/1.0")
        req = urllib.request.Request(  # noqa: S310 — scheme validated above
            url,
            data=body.encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECS) as resp:  # noqa: S310
                return SendResult(ok=True, status_code=getattr(resp, "status", None))
        except urllib.error.HTTPError as exc:
            return SendResult(ok=False, status_code=exc.code, error=f"HTTP {exc.code}")
        except Exception as exc:  # noqa: BLE001 — surface, don't crash dispatch
            return SendResult(ok=False, error=str(exc))


class ScriptSink(Sink):
    """A sink that runs a shell command with ``JINKIES_*`` environment vars."""

    def __init__(self, config: SinkConfig) -> None:
        """Initialize from a sink configuration.

        Args:
            config: The sink configuration; ``config.script`` is executed.
        """
        self.name = config.name
        self._script = config.script

    def send(self, payload: SinkPayload) -> SendResult:  # noqa: D102
        if not self._script.strip():
            return SendResult(ok=False, error="Sink script is empty")
        env = os.environ.copy()
        env.update({
            "JINKIES_TITLE": payload.title,
            "JINKIES_LINK": payload.link,
            "JINKIES_FEED_URL": payload.feed_url,
            "JINKIES_PUBLISHED": payload.published,
            "JINKIES_SUMMARY": payload.summary,
            "JINKIES_STATUS": payload.status,
            "JINKIES_FEED_NAME": payload.feed_name,
        })
        try:
            subprocess.Popen(  # noqa: S602 — shell command is user-authored by design
                self._script,
                shell=True,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return SendResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            return SendResult(ok=False, error=str(exc))


def build_sink(config: SinkConfig) -> Sink:
    """Instantiate the appropriate :class:`Sink` for *config*.

    Args:
        config: The sink configuration.

    Returns:
        A :class:`WebhookSink` or :class:`ScriptSink`.
    """
    if config.transport == "script":
        return ScriptSink(config)
    return WebhookSink(config)


class SinkRegistry:
    """Thread-safe registry mapping sink names to :class:`Sink` instances."""

    def __init__(self, sinks: list[SinkConfig] | None = None) -> None:
        """Initialize with an optional list of sink configurations.

        Args:
            sinks: Initial sink configurations.
        """
        from threading import Lock  # noqa: PLC0415

        self._lock = Lock()
        self._sinks: dict[str, Sink] = {}
        if sinks:
            self.update(sinks)

    def update(self, sinks: list[SinkConfig]) -> None:
        """Replace the registry contents with enabled sinks from *sinks*.

        Args:
            sinks: New list of sink configurations.
        """
        built = {s.name: build_sink(s) for s in sinks if s.enabled and s.name}
        with self._lock:
            self._sinks = built

    def get(self, name: str) -> Sink | None:
        """Return the sink named *name*, or ``None`` if absent/disabled."""
        with self._lock:
            return self._sinks.get(name)
