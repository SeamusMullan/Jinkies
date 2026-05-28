"""Feed discovery via HTML link sniffing for Jinkies.

Fetches a web page and extracts RSS/Atom feed URLs from
``<link rel="alternate" type="application/rss+xml">`` and
``<link rel="alternate" type="application/atom+xml">`` elements.
"""

from __future__ import annotations

import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

_USER_AGENT = "Jinkies/1.0 feed-discovery (+https://github.com/seamusmullan/Jinkies)"
_FEED_TYPES = {
    "application/rss+xml": "rss",
    "application/atom+xml": "atom",
}


class _FeedLinkParser(HTMLParser):
    """Minimal HTML parser that collects <link rel="alternate"> feed elements."""

    def __init__(self) -> None:
        super().__init__()
        self.feeds: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "link":
            return
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        rel = attr_map.get("rel", "").lower()
        mime = attr_map.get("type", "").lower().strip()
        href = attr_map.get("href", "").strip()
        if rel != "alternate" or mime not in _FEED_TYPES or not href:
            return
        self.feeds.append({
            "url": href,
            "title": attr_map.get("title", "").strip(),
            "type": _FEED_TYPES[mime],
        })


def discover_feeds(url: str, timeout: int = 10) -> list[dict[str, str]]:
    """Fetch *url* and return a list of discovered feed links.

    Sniffs ``<link rel="alternate">`` elements in the HTML response for
    RSS and Atom feed URLs.

    Args:
        url: The website URL to probe.
        timeout: HTTP request timeout in seconds (default 10).

    Returns:
        A list of dicts, each with keys ``"url"``, ``"title"``, and
        ``"type"`` (``"rss"`` or ``"atom"``).  Relative URLs are resolved
        against *url*.  Returns an empty list if nothing is found or any
        error occurs.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})  # noqa: S310
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            # Only attempt to parse HTML-ish content types
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(512 * 1024)  # cap at 512 KB
        if "html" not in content_type.lower() and not raw.lstrip().startswith(b"<"):
            return []
        html = raw.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return []

    try:
        parser = _FeedLinkParser()
        parser.feed(html)
        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for entry in parser.feeds:
            resolved = urljoin(url, entry["url"])
            if resolved not in seen:
                seen.add(resolved)
                results.append({
                    "url": resolved,
                    "title": entry["title"],
                    "type": entry["type"],
                })
        return results
    except Exception:  # noqa: BLE001
        return []
