#!/usr/bin/env bash
# create_issues.sh — Create labels and all tracked concern-point issues on GitHub.
#
# Usage:
#   export GITHUB_TOKEN=ghp_your_token_here
#   bash scripts/create_issues.sh
#
# Requires: curl, jq

set -euo pipefail

# ── Preflight ─────────────────────────────────────────────────────────────────
for cmd in curl jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Error: '$cmd' is required but not installed." >&2
    exit 1
  fi
done

: "${GITHUB_TOKEN:?Error: GITHUB_TOKEN is not set. Export it before running this script.}"

REPO="SeamusMullan/Jinkies"
API_BASE="https://api.github.com/repos/${REPO}"

# ── Helpers ───────────────────────────────────────────────────────────────────
api_post() {
  local endpoint="$1"
  local payload="$2"
  local response http_status body

  response=$(curl -s -w "\n%{http_code}" -X POST "${API_BASE}${endpoint}" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$payload")

  body=$(echo "$response" | head -n -1)
  http_status=$(echo "$response" | tail -n 1)

  if [[ "$http_status" -lt 200 || "$http_status" -ge 300 ]]; then
    echo "  API error ${http_status}: $(echo "$body" | jq -r '.message // .')" >&2
    return 1
  fi

  echo "$body"
}

ensure_label() {
  local name="$1" color="$2" description="$3"
  local payload
  payload=$(jq -n --arg n "$name" --arg c "$color" --arg d "$description" \
    '{name: $n, color: $c, description: $d}')

  # Try to create; ignore 422 (already exists)
  local response http_status
  response=$(curl -s -w "\n%{http_code}" -X POST "${API_BASE}/labels" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$payload")
  http_status=$(echo "$response" | tail -n 1)

  if [[ "$http_status" == "201" ]]; then
    echo "  Label created: ${name}"
  elif [[ "$http_status" == "422" ]]; then
    echo "  Label exists:  ${name}"
  else
    echo "  Label warning (${http_status}): ${name}" >&2
  fi
}

create_issue() {
  local title="$1" body="$2" labels="$3"
  echo "Creating issue: ${title}"
  local payload result
  payload=$(jq -n --arg t "$title" --arg b "$body" --argjson l "$labels" \
    '{title: $t, body: $b, labels: $l}')
  result=$(api_post "/issues" "$payload")
  echo "  -> $(echo "$result" | jq -r '"\(.number) \(.html_url)"')"
}

# ── Labels ────────────────────────────────────────────────────────────────────
echo "==> Ensuring labels exist..."
ensure_label "bug"          "d73a4a" "Something is broken"
ensure_label "enhancement"  "a2eeef" "New feature or improvement"
ensure_label "chore"        "e4e669" "Maintenance, deps, CI"
ensure_label "ci"           "0075ca" "CI/CD pipeline"
ensure_label "security"     "b60205" "Security concern"
ensure_label "testing"      "c5def5" "Test coverage"
ensure_label "feed-poller"  "f9d0c4" "Feed polling subsystem"
ensure_label "settings"     "bfd4f2" "Settings UI"
ensure_label "dashboard"    "d4c5f9" "Dashboard UI"
ensure_label "ui"           "d4c5f9" "User interface"
ensure_label "app"          "e4e669" "Application lifecycle"
echo ""

# ── Issues ────────────────────────────────────────────────────────────────────
echo "==> Creating issues..."

create_issue \
  "Lint and tests are not actually executed in the build workflow" \
  "## Problem

The \`lint-and-test\` job in \`.github/workflows/build.yml\` installs dependencies but never calls \`ruff check\` or \`pytest\`. The build job runs unconditionally even when tests fail or the linter errors.

## Acceptance criteria
- [ ] \`uv run ruff check src tests\` runs and must pass before the build job
- [ ] \`uv run pytest\` runs and must pass before the build job
- [ ] Job fails fast on any violation" \
  '["bug","ci"]'

create_issue \
  "HTTP Basic auth credentials stored in plaintext JSON" \
  "## Problem

\`models.Feed\` stores \`auth_user\` and \`auth_token\` in plaintext inside \`~/.config/jinkies/config.json\`. Any process with read access to the home directory (or a backup tool) can expose these credentials.

## Acceptance criteria
- [ ] Credentials are stored in the OS keyring (e.g. \`keyring\` library: macOS Keychain, GNOME Keyring, Windows Credential Manager)
- [ ] Plain config file never contains credentials
- [ ] Migration path documented for existing configs" \
  '["bug","security"]'

create_issue \
  "JinkiesApp (app.py) has zero test coverage" \
  "## Problem

\`src/app.py\` (371 lines) is the application controller that wires every subsystem together, but it has no tests at all. Regressions in startup, shutdown, signal handling, or single-instance locking cannot be detected automatically.

## Acceptance criteria
- [ ] Unit tests for \`JinkiesApp\` startup and teardown
- [ ] Single-instance lock logic tested (both first launch and duplicate launch)
- [ ] Signal/slot wiring from \`FeedPoller\` → \`Notifier\`/\`AudioPlayer\` tested with mocks
- [ ] Coverage for \`app.py\` above 70 %" \
  '["enhancement","testing"]'

create_issue \
  "Add integration tests for the full polling → notification pipeline" \
  "## Problem

There are unit tests for individual components (\`FeedPoller\`, \`Notifier\`, \`AudioPlayer\`) but no integration test that verifies the end-to-end flow: poll detects new entry → signal fires → notification shown → audio played → entry marked seen.

## Acceptance criteria
- [ ] At least one integration test using \`pytest-qt\` that exercises the full pipeline with a mocked HTTP feed
- [ ] Test verifies \`new_entries\` signal carries correct \`FeedEntry\` objects
- [ ] Test verifies \`Notifier\` and \`AudioPlayer\` are called with expected arguments" \
  '["enhancement","testing"]'

create_issue \
  "Feed poller should use exponential backoff for transient network failures" \
  "## Problem

When a feed request fails (network error, 5xx), \`FeedPoller\` emits an error signal but retries at the same fixed interval. Repeated failures hammer the server and flood the user with error notifications.

## Acceptance criteria
- [ ] Failed feeds enter a backoff state: 1 min → 2 min → 4 min → … up to a configurable max (default 60 min)
- [ ] Successful poll resets the backoff counter
- [ ] Backoff state visible in the dashboard status bar or feed list
- [ ] Unit tests for backoff logic" \
  '["enhancement","feed-poller"]'

create_issue \
  "Validate feed URL before saving to config" \
  "## Problem

The user can type any string into the URL field and it is saved to config without validation. Invalid URLs cause silent polling errors and a confusing UX.

## Acceptance criteria
- [ ] URL is validated (parseable, scheme is http/https) before the feed is saved
- [ ] A basic connectivity check (HEAD request with short timeout) is offered optionally
- [ ] Helpful error message shown in the dialog when validation fails
- [ ] Unit tests for validation logic" \
  '["enhancement","feed-poller","settings"]'

create_issue \
  "Replace bare except in feed poller with specific exception types" \
  "## Problem

\`feed_poller.py\` uses a bare \`except\` (suppressed with \`# noqa: BLE001\`) to catch all exceptions during polling. This swallows unexpected errors like \`KeyboardInterrupt\` or \`MemoryError\` and makes debugging very difficult.

## Acceptance criteria
- [ ] Replace bare except with explicit exception types (\`OSError\`, \`feedparser\` exceptions, \`urllib\` errors, etc.)
- [ ] \`noqa: BLE001\` suppression removed
- [ ] Unhandled exception types are re-raised or logged at ERROR level with full traceback" \
  '["bug","feed-poller"]'

create_issue \
  "Entry table needs pagination for feeds with large entry counts" \
  "## Problem

The entry table loads all entries into memory and renders them all at once. Feeds with hundreds or thousands of entries cause slow startup, high memory use, and an unusable scrollable list.

## Acceptance criteria
- [ ] Entry table is paginated or uses \`QAbstractItemModel\` with lazy loading
- [ ] Page size is configurable (default 100)
- [ ] Navigation controls (prev/next page, page indicator) shown when results exceed page size" \
  '["enhancement","dashboard","ui"]'

create_issue \
  "Add bulk mark-as-seen action to the dashboard" \
  "## Problem

There is no way to mark all entries (or all entries for a selected feed) as seen at once. Users who return after a long absence must click every entry individually.

## Acceptance criteria
- [ ] \"Mark all as seen\" action in toolbar and/or context menu
- [ ] Action can be scoped to the currently selected feed or to all feeds
- [ ] Confirmation dialog for \"mark all feeds as seen\" to prevent accidents" \
  '["enhancement","dashboard","ui"]'

create_issue \
  "Add entry content search and filter to the dashboard" \
  "## Problem

The dashboard only allows filtering by feed. There is no way to search entry titles or content, making it difficult to find specific items in large lists.

## Acceptance criteria
- [ ] Search/filter bar above entry table
- [ ] Filters entry titles in real time as the user types
- [ ] Optionally searches entry content/summary
- [ ] Filter state resets when feed selection changes" \
  '["enhancement","dashboard","ui"]'

create_issue \
  "Single-instance lock has a TOCTOU race condition" \
  "## Problem

The single-instance lock in \`app.py\` reads the PID file, checks if the process is alive with \`os.kill(pid, 0)\`, then writes the new PID. There is a race window between the check and the write where two instances can both conclude they are first and both start.

## Acceptance criteria
- [ ] Use atomic file locking (e.g. \`fcntl.flock\` on POSIX, \`msvcrt.locking\` on Windows, or a cross-platform library such as \`filelock\`)
- [ ] Lock is released on clean exit and on crash (lock file not left behind)
- [ ] Unit test that simulates two concurrent starts and verifies only one proceeds" \
  '["bug","app"]'

echo ""
echo "Done."
