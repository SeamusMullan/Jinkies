"""URL validation utilities for Jinkies feed monitor.

Validates feed URLs against an allowlist of safe schemes
to prevent SSRF and local file disclosure attacks.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}
_CONNECTIVITY_TIMEOUT_SECS = 5


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


def check_feed_connectivity(url: str, timeout: int = _CONNECTIVITY_TIMEOUT_SECS) -> str | None:
    """Perform a lightweight HEAD request to check that the URL is reachable.

    Args:
        url: The feed URL to probe (must already pass ``validate_feed_url``).
        timeout: Maximum seconds to wait for a response (default 5).

    Returns:
        An error message if the host is unreachable or returns an error status,
        or None if the connection succeeded.
    """
    req = urllib.request.Request(url, method="HEAD")  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as _resp:  # noqa: S310
            pass
    except urllib.error.HTTPError as exc:
        return f"Server returned HTTP {exc.code}. Check that the URL is correct."
    except urllib.error.URLError as exc:
        return f"Could not connect to the server: {exc.reason}"
    except OSError as exc:
        return f"Connection error: {exc}"
    return None
