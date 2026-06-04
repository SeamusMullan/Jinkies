"""Secure secret storage for Jinkies notification sinks.

Stores per-sink secrets (e.g. Pushover app token, ntfy access token) in the
OS keyring instead of plaintext config files.  Mirrors the design of
:mod:`src.credential_store` but is keyed by sink name and an arbitrary secret
key, so a single sink can hold several named secrets (e.g. Pushover needs both
an ``app_token`` and a ``user_key``).
"""

from __future__ import annotations

import logging

import keyring

logger = logging.getLogger(__name__)

_SERVICE_PREFIX = "jinkies-sink"


def _service_name(sink_name: str) -> str:
    """Build the keyring service name for a sink.

    Args:
        sink_name: The sink's unique name.

    Returns:
        A service name in the form ``jinkies-sink:<sink_name>``.
    """
    return f"{_SERVICE_PREFIX}:{sink_name}"


def store_sink_secret(sink_name: str, key: str, value: str) -> None:
    """Store a named secret for a sink in the OS keyring.

    Args:
        sink_name: The sink's unique name.
        key: The secret's key (e.g. ``"app_token"``).
        value: The secret value.
    """
    keyring.set_password(_service_name(sink_name), key, value)
    logger.debug("Stored sink secret %s for %s", key, sink_name)


def get_sink_secret(sink_name: str, key: str) -> str | None:
    """Retrieve a named secret for a sink from the OS keyring.

    Args:
        sink_name: The sink's unique name.
        key: The secret's key.

    Returns:
        The stored value, or ``None`` if not present.
    """
    return keyring.get_password(_service_name(sink_name), key)


def delete_sink_secret(sink_name: str, key: str) -> None:
    """Remove a named secret for a sink from the OS keyring.

    Missing secrets are ignored.

    Args:
        sink_name: The sink's unique name.
        key: The secret's key.
    """
    try:
        keyring.delete_password(_service_name(sink_name), key)
    except keyring.errors.PasswordDeleteError:
        pass
    logger.debug("Deleted sink secret %s for %s", key, sink_name)
