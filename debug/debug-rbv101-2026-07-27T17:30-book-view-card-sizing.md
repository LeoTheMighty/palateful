---
hash: rbv101
type: debug
created: 2026-07-27T17:30:00-06:00
title: Recipe-book view renders meal and recipe cards at different sizes
from: BUGS.md
status: ready
branch: feat/debug-rbv101
---

## Goal
Everything in the recipe-book detail view renders at the same card size — meals and recipes visually uniform in the mixed grid.

## Acceptance criteria
- [ ] Repro exists (screenshot or widget test demonstrating the size mismatch in the book-detail mixed grid)
- [ ] Root cause documented with evidence in the status log
- [ ] Fix + regression test (widget test pinning card dimensions across both item types)

## Technical notes
- Reported in BUGS.md (top, newest entry): "Everything in the recipe book view should be the same size, meals and recipes."
- The book-detail screen renders recipes + meals in a single mixed grid sorted by `updated_at` (see the ffm-5 skip note in `_bmad-output/implementation-artifacts/sprint-status.yaml` for context on that screen's layout).

## Status log
- 2026-07-27T17:30 — imported from BUGS.md during BMAD→devx migration
