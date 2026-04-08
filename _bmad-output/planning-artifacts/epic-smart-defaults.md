# Epic: Smart Defaults & Frictionless Actions

## Overview

Implement a unified "smart defaults" system across Palateful so that common actions (adding to cart, saving recipes, planning meals) happen instantly without forcing users to pick from lists every time. The pattern: auto-select the default, show a snackbar with "Change" option, and track the previous default for auto-recovery when a temporary list is completed/archived.

## Design Principles (from Party Mode discussion)

1. **Auto-set on creation** — first/new item becomes default, no ceremony
2. **Silent for singles, explicit for bulk** — one item = use default + snackbar; many items = ask with default pre-selected
3. **One-deep recovery** — track previous default, auto-restore when current is completed/archived
4. **Consistent visual language** — star/pin badge on default item across all list views
5. **Time-aware calendar** — meal type inferred from time of day, not asked
6. **Learned suggestions** — remember frequent free-text entries as quick chips

## Story Map

| Story | Title | Est. Effort | Dependencies |
|-------|-------|-------------|--------------|
| 1 | Default Shopping List — Backend & State | 3–4 hours | None |
| 2 | Default Shopping List — Frontend UX | 4–6 hours | Story 1 |
| 3 | Default Recipe Book — Consistency Pass | 2–3 hours | None (pattern exists) |
| 4 | Calendar Meal Planning — Smart Pre-fills & Quick Add | 1–2 days | None |
| 5 | Auto-Recovery & Context Switching | 3–4 hours | Stories 1 & 3 |

**Total estimated effort: 3–5 days**
