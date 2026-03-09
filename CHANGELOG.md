# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-09

### Added

- Cross-platform Atom/RSS feed monitor built with PySide6.
- Monitor multiple feeds simultaneously with configurable per-feed poll intervals.
- Audio cues for new entries and polling errors using `QSoundEffect`.
- Desktop notifications: native on Linux/macOS, custom dialog on Windows.
- System tray icon with close-to-tray behaviour.
- Dashboard window with feed list, entry table, and stats panel.
- Settings dialog to add, edit, and remove feeds.
- Confirmation dialog shown before removing a feed to prevent accidental deletion.
- Feed URL validation before saving to config — invalid URLs are rejected immediately.
- Entry deduplication: entries already present (e.g. loaded from `store.json`) are not added twice.
- Configurable maximum entry count per feed; oldest entries are evicted when the limit is exceeded.
- Error-notification throttling per feed — the error alert fires only on the first failure to avoid notification spam.
- JSON-based configuration (`config.json`) and state persistence (`store.json`) in the platform-appropriate config directory:
  - Linux: `~/.config/jinkies/`
  - macOS: `~/Library/Application Support/jinkies/`
  - Windows: `%APPDATA%\jinkies\`
- Platform-specific PyInstaller build scripts (`scripts/`) and a single-file spec (`jinkies.spec`).
- GitHub Actions CI pipeline that lints, tests, and builds for Linux, macOS, and Windows.
- `pytest` + `pytest-qt` test suite with coverage reporting.

### Upgrade notes

This is the initial public release — no migration is required.

[Unreleased]: https://github.com/SeamusMullan/Jinkies/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SeamusMullan/Jinkies/releases/tag/v0.1.0
