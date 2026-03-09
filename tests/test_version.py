"""Tests for runtime __version__ exposure in src/__init__.py."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import pytest

import src


def _package_not_installed() -> bool:
    """Return True when the jinkies package is not installed."""
    try:
        version("jinkies")
        return False
    except PackageNotFoundError:
        return True


def test_version_is_a_string() -> None:
    """__version__ should be a non-empty string."""
    assert isinstance(src.__version__, str)
    assert src.__version__ != ""


@pytest.mark.skipif(
    condition=_package_not_installed(),
    reason="jinkies package is not installed; skipping metadata resolution check",
)
def test_version_matches_metadata() -> None:
    """__version__ should match the installed package metadata."""
    assert src.__version__ == version("jinkies")
