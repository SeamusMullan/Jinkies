"""Feed import utilities for Jinkies.

Supports importing feeds from OPML subscription lists and
local Atom/XML feed files.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import feedparser

from src.models import Feed


def import_opml(path: str | Path) -> list[Feed]:
    """Import feed subscriptions from an OPML file.

    Args:
        path: Path to the .opml or .xml file.

    Returns:
        List of Feed objects extracted from the OPML outline.

    Raises:
        ValueError: If the file cannot be parsed as valid OPML.
    """
    path = Path(path)
    try:
        tree = ET.parse(path)  # noqa: S314
    except ET.ParseError as e:
        msg = f"Invalid OPML file: {e}"
        raise ValueError(msg) from e

    root = tree.getroot()
    feeds: list[Feed] = []
    _collect_opml_outlines(root, feeds)
    return feeds


def _collect_opml_outlines(element: ET.Element, feeds: list[Feed]) -> None:
    """Recursively collect feed outlines from an OPML element tree.

    Args:
        element: Current XML element to search.
        feeds: List to append discovered feeds to.
    """
    for outline in element.iter("outline"):
        xml_url = outline.get("xmlUrl")
        if xml_url:
            name = outline.get("title") or outline.get("text") or xml_url
            feeds.append(Feed(url=xml_url, name=name))


def import_local_feed(path: str | Path) -> list[Feed]:
    """Import feeds from a local Atom/RSS XML file.

    Parses the file with feedparser to extract the feed title and URL.
    For Jenkins-style feeds, also extracts per-job feed URLs from entries.

    Args:
        path: Path to the local .atom, .xml, or .rss file.

    Returns:
        List of Feed objects. The first is the main feed; additional
        entries are per-job feeds if detected (e.g. Jenkins).

    Raises:
        ValueError: If the file cannot be parsed as a valid feed.
    """
    path = Path(path)
    parsed = feedparser.parse(str(path))

    if parsed.bozo and not parsed.entries and not parsed.feed.get("title"):
        error_msg = (
            str(parsed.bozo_exception) if parsed.bozo_exception else "Not a valid feed"
        )
        msg = f"Cannot parse feed file: {error_msg}"
        raise ValueError(msg)

    title = parsed.feed.get("title", path.stem)
    base_url = _extract_base_url(parsed)
    feed_url = _build_feed_url(parsed, base_url, path)

    feeds = [Feed(url=feed_url, name=title)]

    # Extract per-job feeds from entries (Jenkins-style)
    job_feeds = _extract_job_feeds(parsed, base_url)
    feeds.extend(job_feeds)

    return feeds


def _extract_base_url(parsed: feedparser.FeedParserDict) -> str:
    """Extract the base server URL from a parsed feed.

    Args:
        parsed: The feedparser result.

    Returns:
        The base URL (e.g. "http://localhost:8080") or empty string.
    """
    for link in parsed.feed.get("links", []):
        href = link.get("href", "")
        if link.get("rel") == "alternate" and href:
            return href.rstrip("/")
    return ""


def _build_feed_url(
    parsed: feedparser.FeedParserDict,
    base_url: str,
    path: Path,
) -> str:
    """Determine the actual feed URL from parsed metadata and filename.

    Checks for a self link first, then tries to reconstruct from
    the base URL and filename (handles Jenkins rssAll/rssLatest/rssFailed).

    Args:
        parsed: The feedparser result.
        base_url: The base server URL.
        path: The local file path (used for filename hints).

    Returns:
        The best-guess feed URL.
    """
    # Prefer explicit self link
    for link in parsed.feed.get("links", []):
        if link.get("rel") == "self" and link.get("href"):
            return link["href"]

    # Try to reconstruct from base URL + filename
    if base_url:
        stem = path.stem.split("(")[0].strip()
        known_feed_paths = {"rssAll", "rssLatest", "rssFailed"}
        if stem in known_feed_paths:
            return f"{base_url}/{stem}"
        # If base URL looks like a server root, use it with the filename
        return f"{base_url}/{stem}"

    return str(path)


def _extract_job_feeds(
    parsed: feedparser.FeedParserDict,
    base_url: str,
) -> list[Feed]:
    """Extract per-job Atom feed URLs from entry links.

    For Jenkins feeds, each entry links to a build like
    ``/job/Folder/job/Name/42/``. This extracts unique job paths
    and constructs per-job feed URLs.

    Args:
        parsed: The feedparser result.
        base_url: The base server URL.

    Returns:
        List of per-job Feed objects, empty if no jobs detected.
    """
    if not base_url:
        return []

    seen_jobs: dict[str, str] = {}  # job_path -> entry_title

    for entry in parsed.entries:
        link = entry.get("link", "")
        if not link or "/job/" not in link:
            continue

        # Extract the job path: everything up to the build number
        # e.g. http://localhost:8080/job/Folder/job/Name/42/ -> job/Folder/job/Name
        after_base = link.removeprefix(base_url).strip("/")
        parts = after_base.split("/")

        # Walk parts to find job segments (pairs of "job" + name)
        job_segments: list[str] = []
        i = 0
        while i < len(parts) - 1:
            if parts[i] == "job":
                job_segments.extend(["job", parts[i + 1]])
                i += 2
            else:
                break

        if not job_segments:
            continue

        job_path = "/".join(job_segments)
        if job_path not in seen_jobs:
            # Use the entry title for a readable name, strip build info
            entry_title = entry.get("title", "")
            job_name = entry_title.rsplit("#", 1)[0].strip().rstrip("»").strip()
            if not job_name:
                job_name = job_segments[-1]
            seen_jobs[job_path] = job_name

    return [
        Feed(url=f"{base_url}/{job_path}/rssAll", name=name)
        for job_path, name in sorted(seen_jobs.items())
    ]
