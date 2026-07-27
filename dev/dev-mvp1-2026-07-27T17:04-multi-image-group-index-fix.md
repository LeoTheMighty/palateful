---
hash: mvp1
type: dev
created: 2026-07-27T17:04:00-06:00
title: Fix multi-image group_index so one upload session yields one recipe
from: _bmad-output/planning-artifacts/epic-mvp-finalization.md
status: blocked
branch: feat/dev-mvp1
---

## Goal
Multi-image photo imports currently produce N separate recipes because each image added in `photo_capture_screen.dart` gets its own default `group_index`. The intended behavior is one recipe per upload session unless the user explicitly splits images into groups. The backend aggregation in `watch_parser_batch_task.py` already groups correctly by `group_index`; the fix (once unblocked) is client-side, plus tests on both sides.

## Acceptance criteria
- [ ] Adding multiple images in `photo_capture_screen.dart` and submitting without explicitly creating separate groups results in **one** `ImportItem` and **one** extract task call on the backend.
- [ ] Users who explicitly split images into multiple groups (existing UX) continue to get one recipe per group — this story does not break multi-recipe batch uploads.
- [ ] Widget test verifies the client request body: adding 2 images then submitting yields a request where every image has `group_index: 0`.
- [ ] Backend integration test exists for the 2-image → 1 `ImportItem` path (filling a historical coverage gap in `watch_parser_batch_task`).

## Technical notes
- **BLOCKED — do not start.** Sprint-status marks this story `blocked`. Per the epic (`epic-mvp-finalization.md`, Story Map + Sequencing Phase 1): "Diagnosis blocked … Awaiting diagnostic information from Leo. Initial fix hypothesis was invalidated by code review (see mvp-1 story 'Blocker' section)." Note: the referenced "Blocker" section was never actually written into the story file — the epic's sequencing note is the only durable record of the blocker.
- The story file `_bmad-output/implementation-artifacts/mvp-1-multi-image-group-index-fix.md` still describes the **invalidated** hypothesis: a one-line change of `_groupAssignments[newIndex] = newIndex;` to `= 0;`. Treat its Tasks section as stale until re-diagnosed; its ACs (copied above) remain the target behavior.
- The suspect line still exists on main, now at `app/lib/features/recipes/add_recipe/photo_capture_screen.dart:167` (story cites line 137 — file has drifted).
- Backend aggregation reference: `libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py:199-226` (correct per the story; do not modify backend beyond the coverage-gap test).
- Unblock path: obtain a reproduction / diagnostic data from Leo (which submit path was used, actual `group_index` values sent, resulting ImportItem count), re-diagnose, then update this spec's notes and flip `status: ready`.
- Original BMAD story key: mvp-1-multi-image-group-index-fix.

## Status log
- 2026-07-27T17:04 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration
- 2026-07-27T17:04 — blocked reason recorded: awaiting diagnostic info from Leo; initial client-side one-line fix hypothesis invalidated by code review (epic-mvp-finalization.md Sequencing Phase 1); the "Blocker" section the epic cites was never added to the story file
