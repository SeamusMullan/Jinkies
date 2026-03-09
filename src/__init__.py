"""Jinkies — Atom feed monitor application."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("jinkies")
except PackageNotFoundError:
    __version__ = "unknown"
