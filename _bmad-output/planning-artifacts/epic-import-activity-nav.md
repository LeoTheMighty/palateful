# Epic: Import Flow Overhaul + Activity Center + Nav Restructure

## Overview

A mega-epic that transforms three interconnected areas of Palateful: restructures the bottom navigation to replace Books with an Activity tab, moves recipe books to a recency-sorted horizontal scroll on the Home screen, builds an Activity center for background job visibility and partner updates, and overhauls the entire import flow — adding text paste, spreadsheet/CSV import (AI-powered, no column mapping), and fixing critical discoverability gaps.

## Design Principles (from Party Mode discussion)

1. **No modals** — all navigation is push-based, no sheets or overlays for major flows
2. **AI does the work** — spreadsheet import uses LLM parsing, not column mapping
3. **Silent for singles, explicit for bulk** — carries over from defaults epic
4. **Confidence-based review** — high confidence auto-approves, low confidence flags for user input
5. **Recency over hierarchy** — books sorted by last opened, not alphabetical
6. **Activity is ambient** — badge on tab visible from everywhere, not hidden behind a bell icon

## Story Map

| Story | Title | Est. Effort | Dependencies |
|-------|-------|-------------|--------------|
| 1 | Nav Restructure — Books to Home, Activity Tab Shell | 4–6 hours | None (foundational) |
| 2 | Books Horizontal Scroll on Home — Recency Sorting | 3–4 hours | Story 1 |
| 3 | Activity Tab MVP — Model, API, Feed UI | 1–2 days | Story 1 |
| 4 | Import Quick Wins — URL, Onboarding, Empty States | 3–4 hours | None |
| 5 | Text Paste Import | 1 day | Story 4 |
| 6 | Activity Feed Integration — Import Status, Partner Activity, Reminders | 1–2 days | Story 3 |
| 7 | Spreadsheet Import — AI-Powered CSV/XLSX | 3–4 days | Stories 4, 6 |
| 8 | Import Polish — Auto-Approve, Shared Files | 1–2 days | Story 7 |

**Total estimated effort: 10–16 days**

**Critical path: Story 1 → Story 2 + Story 3 (parallel) → Story 6 → Story 7 → Story 8**
**Independent: Story 4 → Story 5 (can run in parallel with nav work)**
