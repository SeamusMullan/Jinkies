# Jinkies — Feature Roadmap & Dependency Graph

## Issue Registry

| # | Issue | GH | Priority | Phase |
|---|-------|----|----------|-------|
| 1 | Full QSS dark theme | [#163](https://github.com/SeamusMullan/Jinkies/issues/163) | P1 | A |
| 2 | Modern vector icons (qtawesome) | [#164](https://github.com/SeamusMullan/Jinkies/issues/164) | P1 | A |
| 3 | Entry preview pane | [#165](https://github.com/SeamusMullan/Jinkies/issues/165) | P1 | A |
| 4 | Keyboard-first navigation | [#166](https://github.com/SeamusMullan/Jinkies/issues/166) | P1 | A |
| 5 | Unread count badge on tray icon | [#167](https://github.com/SeamusMullan/Jinkies/issues/167) | P2 | A |
| 6 | Drag-and-drop feed reordering | [#168](https://github.com/SeamusMullan/Jinkies/issues/168) | P2 | A |
| 7 | Per-feed poll interval | [#169](https://github.com/SeamusMullan/Jinkies/issues/169) | P2 | B |
| 8 | Feed groups / folders | [#170](https://github.com/SeamusMullan/Jinkies/issues/170) | P2 | B |
| 9 | Entry starring / bookmarks | [#171](https://github.com/SeamusMullan/Jinkies/issues/171) | P2 | B |
| 10 | Entry rules / alerts | [#172](https://github.com/SeamusMullan/Jinkies/issues/172) | P2 | C |
| 11 | OPML export | [#173](https://github.com/SeamusMullan/Jinkies/issues/173) | P3 | A |
| 12 | Feed health dashboard | [#174](https://github.com/SeamusMullan/Jinkies/issues/174) | P2 | C |
| 13 | Feed discovery / auto-detect | [#175](https://github.com/SeamusMullan/Jinkies/issues/175) | P2 | B |
| 14 | Webhook / script trigger | [#176](https://github.com/SeamusMullan/Jinkies/issues/176) | P3 | C |

---

## Dependency Graph

```
PHASE A — no model changes, fully parallel-safe
─────────────────────────────────────────────────
  #1 QSS theme ──────────────────────────────┐
  #2 Icons ──── depends on #1 (style must     │ land together or
               be set before icon colours)    │ icons on top of theme
  #3 Preview pane ──────────────────────────── dashboard.py layout
  #4 Keyboard nav ── soft dep on #3 (preview  │
                     nav optional but better) │
  #5 Tray badge ─── independent (app.py only) │
  #6 Drag-drop ──── independent (list widget) │
  #11 OPML export ── independent (feed_import)│
                                              │
  ⚠ CONFLICT ZONE: #1 + #2 both touch         │
    src/app.py (stylesheet apply) and          │
    src/dashboard.py — serialize, don't merge  │
  ⚠ CONFLICT ZONE: #3 + #4 both modify        │
    dashboard.py layout/keypress handlers —    │
    do #3 first, branch #4 off its HEAD        │

PHASE B — small model changes, mostly parallel-safe
─────────────────────────────────────────────────────
  #7 Per-feed interval ── touches models.py (Feed),
  │                       feed_poller.py (scheduler),
  │                       settings_dialog.py (FeedEditDialog)
  │
  #8 Feed groups ──── depends on #6 (ordering settled)
  │                   touches models.py (Feed.group),
  │                   dashboard.py (list widget grouping),
  │                   settings_dialog.py (FeedEditDialog)
  │
  #9 Entry starring ─ touches models.py (FeedEntry.starred),
  │                   store.json schema,
  │                   dashboard.py (star column, filter)
  │
  #13 Feed discovery ─ independent; touches
                        settings_dialog.py (FeedEditDialog only)

  ⚠ CONFLICT ZONE: #7 + #8 both touch models.py and
    settings_dialog.py — serialize or split into
    separate functions and rebase cleanly
  ⚠ CONFLICT ZONE: #8 + #9 both touch dashboard.py
    (list widget vs table columns) — can be parallel
    IF changes are in clearly separate methods
  ✓ #7 and #9 touch different models fields — parallel safe
  ✓ #13 touches only FeedEditDialog — safe alongside all B items

PHASE C — depends on B being merged
──────────────────────────────────────
  #10 Entry rules ─── depends on #7 (per-feed timing),
  │                   depends on #9 (starring as rule action)
  │                   touches: models.py (Rule model),
  │                            feed_poller.py (rule eval),
  │                            settings_dialog.py (rule table UI)
  │
  #12 Feed health ─── depends on #7 (per-feed timing data)
  │                   touches: feed_poller.py (stats tracking),
  │                            new src/health_view.py
  │
  #14 Webhook ──────── depends on #10 (rule as trigger)
                       touches: feed_poller.py (dispatch),
                                settings_dialog.py (webhook field on rule)

  ✓ #12 and #10/#14 touch different parts of feed_poller.py
    (#12 = stats collection, #10/#14 = entry dispatch) — parallel safe
    IF both branch from same merged B HEAD
```

---

## File → Issue Ownership Map

Use this to predict merge conflicts before branching.

| File | Issues that touch it |
|------|----------------------|
| `src/app.py` | #1 (theme apply), #5 (tray badge) |
| `src/dashboard.py` | #1 (stylesheet), #2 (icons), #3 (preview pane), #4 (keybindings), #6 (drag-drop), #8 (group list), #9 (star column) |
| `src/settings_dialog.py` | #1 (theme toggle), #7 (per-feed interval), #8 (group field), #10 (rule table), #13 (discovery), #14 (webhook field) |
| `src/models.py` | #7 (`Feed.poll_interval_secs`), #8 (`Feed.group`), #9 (`FeedEntry.starred`), #10 (`Rule` model) |
| `src/feed_poller.py` | #7 (per-feed scheduler), #10 (rule eval), #12 (stats), #14 (webhook dispatch) |
| `src/feed_import.py` | #11 (OPML export) |
| `src/notifier.py` | #10 (rule → notification action) |
| `src/audio.py` | #10 (rule → sound action) |
| `src/url_validation.py` / new `src/feed_discover.py` | #13 |
| new `src/health_view.py` | #12 |
| new `src/theme.py` (or `src/styles.py`) | #1 |

---

## Parallel Work Rules

1. **#1 before #2** — icons reference theme colours; land theme first.
2. **#3 before #4** — keyboard nav in preview pane requires pane to exist.
3. **#6 before #8** — group ordering logic builds on stable drag-drop.
4. **All of Phase B before Phase C** — rules (#10), webhooks (#14), and health (#12) all reference B's model additions.
5. **#7 and #8 must not be in-flight on `models.py` simultaneously** — one person merges first, other rebases.
6. **#10 and #12 can be parallel** — different concerns in `feed_poller.py` but rebase carefully.
7. **#3 and #6 are fully parallel** — different widgets, no shared methods.
8. **#5 and #11 are fully independent** — safe to merge at any time in Phase A.
