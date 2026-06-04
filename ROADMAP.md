# Jinkies Roadmap

## v2 — Feature Epics

All v1 issues shipped. v2 adds six epics tracked as GitHub milestones (E1–E6).
Tracking issue: [#207 Roadmap v2](../../issues/207).

| Epic | Milestone | Theme |
|------|-----------|-------|
| E1 | Jenkins-native mode | Talk to Jenkins JSON API for rich build data, actions, auto-detect |
| E2 | Notification control | DND/quiet hours, snooze, per-feed mute, failure-only, digest |
| E3 | Dashboard UX polish | Collapsible groups, starred view, rule preview, sound preview, OS dark-mode |
| E4 | DX / power-user | Parallel polling, error log, CLI/headless, webhook result visibility |
| E5 | Mobile push | Phone notifications (ntfy etc); mobile-only routing |
| E6 | Universal webhook sink | One configurable HTTP sink + presets (Discord/Slack/ntfy) |

**Dependency spine:** E6 (sink layer) underpins E5 mobile, E2 digest, E4 retry-visibility.
E3 runs concurrent with E6 (independent files). E1 is a parallel net-new track; its build
payload (E1g) feeds E6 template vars. E4 (refactor-heavy) lands last.

![Roadmap v2 Gantt](docs/roadmap-gantt.png)

<details><summary>Gantt source (mermaid)</summary>

```mermaid
gantt
    title Jinkies Roadmap v2 — 6 Epics
    dateFormat YYYY-MM-DD
    axisFormat %b %d
    excludes weekends

    section E3 UX Polish
    Collapsible feed groups (#183)        :e3a, 2026-06-08, 4d
    Starred-only view + filters (#184)    :e3b, after e3a, 3d
    Rule dry-run preview (#185)           :e3c, after e3b, 3d
    Sound preview + shortcuts (#186)      :e3d, after e3c, 2d
    OS dark-mode auto-detect (#187)       :e3e, after e3d, 2d

    section E6 Webhook Sink
    Sink registry (#177)                  :e6a, 2026-06-08, 4d
    Refactor rule webhook (#178)          :e6b, after e6a, 3d
    Template engine (#179)                :e6c, after e6b, 3d
    Provider presets (#180)               :e6d, after e6c, 3d
    Send-test + async result (#181)       :e6e, after e6d, 3d
    Keyring secrets (#182)                :e6f, after e6e, 2d

    section E2 Notif Control
    Model fields (#188)                   :e2a, after e6b, 3d
    Quiet hours / DND (#189)              :e2b, after e2a, 4d
    Snooze + per-feed mute (#190)         :e2c, after e2b, 3d
    Failure-only mode (#191)              :e2d, after e2c, 2d
    Digest batching (#192)                :e2e, after e2d, 3d

    section E5 Mobile Push
    ntfy subscribe UI (#193)              :e5a, after e6e, 3d
    Mobile-only routing (#194)            :e5b, after e5a, 3d
    Honor DND on push (#195)              :e5c, after e2b, 2d

    section E1 Jenkins-native
    JSON API client (#196)                :e1a, 2026-06-22, 5d
    Token auth + CSRF crumb (#197)        :e1b, after e1a, 3d
    Auto-detect Jenkins (#198)            :e1c, after e1b, 2d
    Build status summary bar (#199)       :e1d, after e1c, 3d
    Rich build payload (#200)             :e1e, after e1d, 3d
    Build actions (#201)                  :e1f, after e1e, 4d
    Enrich payloads (#202)                :e1g, after e1f, 3d

    section E4 DX / Power-user
    Parallel polling (#203)               :e4a, 2026-07-06, 4d
    Per-feed error log (#204)             :e4b, after e4a, 3d
    CLI / headless mode (#205)            :e4c, after e4b, 4d
    Webhook result visibility (#206)      :e4d, after e6e, 3d
```

</details>

> Dates are illustrative sequencing (solo-dev pace, ~2–5 d/task), not commitments.

## v1 — Initial hardening (shipped)

```mermaid
gantt
    title Jinkies Issue Roadmap (3 contributors)
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section P0 — Critical
    #5  Plaintext credential storage          :p0a, 2026-02-23, 3d
    #17 Basic auth over plain HTTP             :p0b, 2026-02-23, 2d
    #19 file:// URLs not blocked (SSRF)        :p0c, 2026-02-23, 2d

    section P1 — High
    #4  CI not running lint/tests              :p1a, after p0b, 2d
    #10 Bare except in feed poller             :p1b, after p0c, 2d
    #14 Single-instance lock TOCTOU race       :p1c, after p0a, 3d
    #15 Entry ID collision (empty-string key)  :p1d, after p1a, 2d

    section P2 — Medium
    #9  Validate feed URL before saving        :p2a, after p1b, 2d
    #18 Atomic write for state.json            :p2b, after p1c, 2d
    #8  Exponential backoff for poller          :p2c, after p1d, 3d
    #16 Seen state not persisted on click      :p2d, after p2a, 2d

    section P3 — Low
    #6  Test coverage for JinkiesApp           :p3a, after p2b, 4d
    #7  Integration tests for poll pipeline    :p3b, after p2c, 4d
    #1  Windows system tray icon               :p3c, after p2d, 2d
    #2  Windows pyinstaller app icon           :p3d, after p3c, 1d
    #11 Dashboard pagination                   :p3e, after p3a, 3d
    #12 Bulk mark-as-seen action               :p3f, after p3b, 2d
    #13 Entry content search/filter            :p3g, after p3d, 3d
```
