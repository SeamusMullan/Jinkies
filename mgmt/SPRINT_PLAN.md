# Jinkies Sprint Plan — P3 Cleanup

**Date:** 2026-04-22
**Devs:** 2
**Duration:** 5 working days (Apr 23–28)

## Open Issues Summary

| # | Title | Type | Size | Complexity |
|---|-------|------|------|------------|
| **#13** | Entry content search/filter in dashboard | Feature/UI | **L** | New widget + real-time filtering + state mgmt |
| **#6** | JinkiesApp test coverage (>70%) | Testing | **L** | Mock-heavy, startup/shutdown/signals |
| **#51** | NotificationDialog tests | Testing | **M** | pytest-qt, animations, class-level state |
| **#49** | Config dir platform-specific tests | Testing | **S** | Parametrized, mock `sys.platform` |
| **#64** | Toolbar tooltip accessibility | Enhancement | **XS** | Add `setToolTip` calls to existing actions |

## Dependency Graph

```mermaid
graph TD
    subgraph "No Dependencies — All Independent"
        A["#64 Tooltips<br/>XS · 0.5d"]
        B["#49 Config path tests<br/>S · 0.5d"]
        C["#51 NotificationDialog tests<br/>M · 1.5d"]
        D["#6 App.py test coverage<br/>L · 2d"]
        E["#13 Search/filter UI<br/>L · 3d"]
    end

    style A fill:#90EE90
    style B fill:#90EE90
    style C fill:#FFFFE0
    style D fill:#FFD700
    style E fill:#FFD700
```

## Gantt — 2 Devs, 5 Days

```mermaid
gantt
    title Jinkies Sprint — Remaining Issues (2 Devs)
    dateFormat YYYY-MM-DD
    axisFormat %a %b %d

    section Dev A (UI Focus)
    #64 Toolbar tooltips           :a1, 2026-04-23, 0.5d
    #13 Search/filter UI           :a2, after a1, 3d
    Buffer / review / polish       :a3, after a2, 1.5d

    section Dev B (Testing Focus)
    #49 Config dir platform tests  :b1, 2026-04-23, 0.5d
    #51 NotificationDialog tests   :b2, after b1, 1.5d
    #6  App.py test coverage >70%  :b3, after b2, 2d
    Buffer / review                :b4, after b3, 0.5d

    section Milestones
    All P3 issues closed           :milestone, 2026-04-28, 0d
```

## Dev Assignment Rationale

**Dev A — UI track:**
- Start with #64 (tooltips) — quick win, warm up on dashboard code
- Then #13 (search/filter) — biggest feature, needs dashboard.py familiarity from #64
- Buffer for code review + edge case testing

**Dev B — Testing track:**
- Start with #49 (config paths) — small, isolated, quick win
- Then #51 (NotificationDialog) — medium complexity, pytest-qt
- Then #6 (app.py coverage) — largest test task, touches all subsystems
- Buffer for review

## Effort Breakdown

```mermaid
pie title Dev-Days by Category
    "UI Feature (#13)" : 3
    "UI Polish (#64)" : 0.5
    "Testing (#6)" : 2
    "Testing (#51)" : 1.5
    "Testing (#49)" : 0.5
    "Buffer/Review" : 2
```

## Key Risks

| Risk | Mitigation |
|------|-----------|
| #13 search UI scope creep (content search = parsing HTML summaries) | Start with title-only filter, content search as follow-up |
| #6 app.py heavy Qt dependencies hard to mock | Use `pytest-qt`'s `qtbot`, mock subsystems at boundary |
| #51 animation timing flaky in CI | Use `QSignalSpy` + `waitUntil`, skip real timers |

## Quick Stats

- **3,199 LOC** source, **3,254 LOC** tests (1:1 ratio)
- After sprint: 3 testing gaps closed, 1 new feature, 1 accessibility fix
- All P0/P1/P2 already shipped — project in strong shape
