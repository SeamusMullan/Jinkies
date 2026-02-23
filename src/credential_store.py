"""Secure credential storage for Jinkies feed monitor.

Stores HTTP Basic auth credentials in the OS keyring instead of
plaintext config files. Enforces HTTPS-only for authenticated feeds
as defense-in-depth against credential leakage.
"""

from __future__ import annotations

import logging

import keyring

logger = logging.getLogger(__name__)

_SERVICE_PREFIX = "jinkies"


def _service_name(feed_url: str) -> str:
    """Build the keyring service name for a feed URL.

    Args:
        feed_url: The feed URL to derive a service name from.

    Returns:
        A service name in the form ``jinkies:<feed_url>``.
    """
    return f"{_SERVICE_PREFIX}:{feed_url}"


def _require_https(feed_url: str) -> None:
    """Validate that the feed URL uses HTTPS.

    Args:
        feed_url: The URL to validate.

    Raises:
        ValueError: If the URL does not start with ``https://``.
    """
    if not feed_url.startswith("https://"):
        msg = (
            f"Refusing to store credentials for non-HTTPS URL: {feed_url}. "
            "Credentials must only be sent over encrypted connections."
        )
        raise ValueError(msg)


def store_credentials(feed_url: str, username: str, token: str) -> None:
    """Store authentication credentials in the OS keyring.

    Args:
        feed_url: The feed URL the credentials belong to.
        username: The HTTP Basic auth username.
        token: The HTTP Basic auth token/password.

    Raises:
        ValueError: If the feed URL is not HTTPS.
    """
    _require_https(feed_url)
    service = _service_name(feed_url)
    keyring.set_password(service, "username", username)
    keyring.set_password(service, "token", token)
    logger.debug("Stored credentials for %s", feed_url)


def get_credentials(feed_url: str) -> tuple[str, str] | None:
    """Retrieve authentication credentials from the OS keyring.

    Args:
        feed_url: The feed URL to look up credentials for.

    Returns:
        A ``(username, token)`` tuple, or ``None`` if no credentials
        are stored for this feed.
    """
    service = _service_name(feed_url)
    username = keyring.get_password(service, "username")
    token = keyring.get_password(service, "token")
    if username and token:
        return (username, token)
    return None


def delete_credentials(feed_url: str) -> None:
    """Remove authentication credentials from the OS keyring.

    Args:
        feed_url: The feed URL whose credentials should be deleted.
    """
    service = _service_name(feed_url)
    try:
        keyring.delete_password(service, "username")
    except keyring.errors.PasswordDeleteError:
        pass
    try:
        keyring.delete_password(service, "token")
    except keyring.errors.PasswordDeleteError:
        pass
    logger.debug("Deleted credentials for %s", feed_url)
