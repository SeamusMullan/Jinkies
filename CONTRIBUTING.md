# Contributing to Jinkies

Thank you for your interest in contributing! This document covers everything you need to know to get started.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Branching Strategy](#branching-strategy)
- [Commit Messages](#commit-messages)
- [Pull Requests](#pull-requests)
- [Code Style](#code-style)
- [Testing](#testing)
- [Code Ownership](#code-ownership)

---

## Code of Conduct

Be respectful and constructive. Harassment, personal attacks, or discriminatory language will not be tolerated. If you experience or witness unacceptable behaviour, contact the maintainer directly via a private GitHub message.

---

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/Jinkies.git
   cd Jinkies
   ```
3. **Add the upstream** remote:
   ```bash
   git remote add upstream https://github.com/SeamusMullan/Jinkies.git
   ```
4. **Create a branch** from `main`:
   ```bash
   git fetch upstream
   git checkout -b feature/my-feature upstream/main
   ```

---

## Development Setup

Jinkies uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a virtual environment and install all dependencies (including dev)
uv sync --dev

# Run the app in development mode
uv run python main.py
# Note: the app minimises to the system tray on launch — check your tray area.
```

**Linux — additional system packages required for PySide6:**

```bash
sudo apt-get update && sudo apt-get install -y \
    libgl1 libegl1 libxkbcommon-x11-0 \
    libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xfixes0
```

**macOS** — no additional packages needed beyond Xcode command-line tools.

**Windows** — no additional packages needed; run `uv sync --dev` in PowerShell.

---

## Branching Strategy

| Branch pattern | Purpose |
|---|---|
| `main` | Stable, released code. Never commit directly. |
| `feature/<short-description>` | New features |
| `fix/<short-description>` | Bug fixes |
| `chore/<short-description>` | Maintenance (deps, CI, docs) |
| `test/<short-description>` | Test-only changes |

Always branch off from `main`:

```bash
git fetch upstream
git checkout -b feature/my-feature upstream/main
```

---

## Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `revert`

**Scopes (aligned to modules):** `audio`, `config`, `dashboard`, `feed-import`, `feed-poller`, `models`, `notifier`, `settings`, `app`, `ci`, `build`

**Examples:**
```
feat(feed-poller): add exponential backoff on transient failures
fix(notifier): use dbus instead of string platform check on Linux
docs: add branching and commit guidelines to CONTRIBUTING
test(app): add integration tests for JinkiesApp lifecycle
chore(deps): pin PySide6 to 6.10.x for reproducibility
revert(dashboard): revert entry pagination (broke keyboard nav)
```

---

## Pull Requests

### Before Opening a PR

- [ ] All existing tests pass: `uv run pytest`
- [ ] Linter passes with no new violations: `uv run ruff check src tests`
- [ ] New behaviour is covered by tests
- [ ] Docstrings follow Google style (required by ruff `D` rules)
- [ ] Type annotations are present on all new public functions
- [ ] The PR targets `main`

### PR Size

Keep PRs small and focused. A PR should do one thing. If you find yourself writing "and also..." in the description, consider splitting.

### Review Process

1. Open a draft PR early to get feedback on direction.
2. At least **one approving review** is required before merge.
3. All CI checks must pass.

---

## Code Style

The project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting. Configuration lives in `pyproject.toml`.

```bash
# Check for lint violations
uv run ruff check src tests

# Auto-fix safe violations
uv run ruff check --fix src tests

# Format code
uv run ruff format src tests
```

Key rules enforced:

| Rule set | Meaning |
|---|---|
| `E`, `F`, `W` | PEP 8 and pyflakes |
| `I` | Import ordering (isort-compatible) |
| `ANN` | Type annotations on public API |
| `D` | Google-style docstrings |
| `S` | Security (bandit-style) |
| `UP` | Use modern Python idioms |

Qt method overrides (camelCase) are exempt from `N802`.

---

## Testing

Tests live in `tests/` and use `pytest` + `pytest-qt`.

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src --cov-report=term-missing

# Run a specific test file
uv run pytest tests/test_feed_poller.py -v
```

**Guidelines:**

- Every new public function needs at least one test.
- UI tests should use `qtbot` fixtures from `pytest-qt`.
- Mock external I/O (network, filesystem, audio) — do not make real HTTP calls in tests.
- Aim to keep overall coverage above **70%**.

---

## Code Ownership

See [CODEOWNERS](.github/CODEOWNERS) for module-level ownership. Owners are automatically requested as reviewers for changes touching their areas.
