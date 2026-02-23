"""URL validation utilities for Jinkies feed monitor.

Validates feed URLs against an allowlist of safe schemes
to prevent SSRF and local file disclosure attacks.
"""

from __future__ import annotations

from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


def validate_feed_url(url: str) -> str | None:
    """Validate a feed URL against the allowed scheme allowlist.

    Args:
        url: The URL to validate.

    Returns:
        An error message if invalid, or None if the URL is acceptable.
    """
    if not url or not url.strip():
        return "URL must not be empty."
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return (
            f"URL scheme '{parsed.scheme or ''}' is not allowed. "
            "Only http:// and https:// feed URLs are supported."
        )
    if not parsed.netloc:
        return "URL must include a hostname."
    return None
