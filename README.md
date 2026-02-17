# Jinkies

Cross-platform Atom/RSS feed monitor with audio cues and desktop notifications, built with PySide6.

## Features

- Monitor multiple Atom/RSS feeds with configurable poll intervals
- Audio cues for new entries and errors
- Desktop notifications (native on Linux/macOS, custom dialog on Windows)
- System tray integration with close-to-tray
- Dashboard with feed list, entry table, and stats
- JSON-based configuration and state persistence

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

## Development Setup

```bash
# Install dependencies
uv sync --dev

# Run the app
uv run python main.py

# Lint
uv run ruff check src/ tests/

# Run tests
uv run pytest
```

## Project Structure

```
src/
  models.py          # Data classes (Feed, FeedEntry, AppConfig)
  config.py          # JSON config/state persistence
  feed_poller.py     # QThread-based feed polling
  audio.py           # QSoundEffect audio playback
  notifier.py        # Cross-platform notifications
  dashboard.py       # Main window UI
  settings_dialog.py # Settings panel
  app.py             # Application glue and system tray
```

## Building

Platform-specific build scripts are in `scripts/`. CI builds all platforms via GitHub Actions.

```bash
# Linux
./scripts/build_linux.sh

# macOS
./scripts/build_macos.sh

# Windows (PowerShell)
./scripts/build_windows.ps1
```

## Configuration

Config files are stored in the platform-appropriate location:
- Linux: `~/.config/jinkies/`
- macOS: `~/Library/Application Support/jinkies/`
- Windows: `%APPDATA%/jinkies/`
