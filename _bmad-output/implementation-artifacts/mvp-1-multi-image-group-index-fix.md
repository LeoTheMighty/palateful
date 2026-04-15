# Story MVP.1: Fix Multi-Image `group_index` Client Bug

Status: ready-for-dev

## Story

As a user importing a recipe from multiple photos,
I want all the photos I upload in one session to be treated as a single recipe,
so that the extractor runs once and produces one combined recipe instead of N separate ones.

## Context

The backend aggregation logic in `watch_parser_batch_task.py:199-226` correctly groups `ParserJob` rows by `group_index` and concatenates their OCR text into a single `ImportItem` before calling the extract task. **The backend is not the bug.**

The bug lives in the Flutter client at `app/lib/features/recipes/add_recipe/photo_capture_screen.dart:137`:

```dart
_groupAssignments[newIndex] = newIndex; // default 1 group per image
```

When a user adds images sequentially via `_addImage`, each image is assigned its own group index (image 0 → group 0, image 1 → group 1, …). If the user submits via `_submitGrouped()` at line 352, the client sends `group_index: [0, 1, 2, …]` — the backend sees N distinct groups and dispatches N extract calls.

`_submitAsOneRecipe()` at line 341 hardcodes `group_index: 0` for all images and works correctly, but is only reached via an explicit user path.

## Acceptance Criteria

1. Adding multiple images in `photo_capture_screen.dart` and submitting without explicitly creating separate groups results in **one** `ImportItem` and **one** extract task call on the backend.
2. Users who explicitly split images into multiple groups (existing UX) continue to get one recipe per group — this story does not break multi-recipe batch uploads.
3. Widget test verifies the client request body: adding 2 images then submitting yields a request where every image has `group_index: 0`.
4. Backend integration test exists for the 2-image → 1 `ImportItem` path (filling a historical coverage gap in `watch_parser_batch_task`).

## Tasks / Subtasks

- [ ] Task 1: Fix the default group assignment in the Flutter client (AC: #1, #2)
  - [ ] Modify `app/lib/features/recipes/add_recipe/photo_capture_screen.dart:137`
  - [ ] Change `_groupAssignments[newIndex] = newIndex;` to `_groupAssignments[newIndex] = 0;`
  - [ ] Verify manual group-assignment UX (if any) still functions — users who explicitly split into groups must still be able to
  - [ ] Sanity check `_submitGrouped()` at line 352: with the new default, `_groupAssignments[i] ?? 0` now resolves to `0` for all ungrouped images, which is the intended behavior

- [ ] Task 2: Add widget test for ungrouped multi-image submit (AC: #3)
  - [ ] Test location: `app/test/features/recipes/add_recipe/photo_capture_screen_test.dart` (create if missing)
  - [ ] Pump `PhotoCaptureScreen`, simulate adding 2 images, tap submit
  - [ ] Intercept the HTTP request (via `MockClient` or similar) and assert the `group_index` field is `0` for every image in the payload
  - [ ] Second test case: user explicitly splits images into 2 groups → assert `group_index: [0, 1]` to prevent regressing the multi-recipe path

- [ ] Task 3: Add backend integration test for multi-image aggregation (AC: #4)
  - [ ] Test location: `services/worker/tests/tasks/test_watch_parser_batch_task.py` (or wherever `watch_parser_batch_task` tests live)
  - [ ] Seed two `ParserJob` rows with the same `import_job_id` and `group_index=0`, different `extracted_text`
  - [ ] Run `watch_parser_batch_task`
  - [ ] Assert exactly **one** `ImportItem` created with concatenated text containing both jobs' text (separated by `PAGE_SEPARATOR`)
  - [ ] Assert the downstream extract task is dispatched exactly once

## Dev Notes

- This is intentionally a one-line source fix plus tests. Do not use this story as a pretext to refactor the photo capture flow.
- The `_groupAssignments` map remains in place — users who want to split images into separate recipes still can; the default just changes from "everyone gets their own group" to "everyone shares group 0 unless told otherwise."
- The backend test in Task 3 is not strictly required to fix the bug, but closes a historical coverage gap: the multi-image aggregation path has never had a test despite being core to OCR import UX.
- Do NOT modify `watch_parser_batch_task.py` or any backend code in this story. The backend is correct; the bug is purely client-side.

### Project Structure Notes

- Flutter test directory follows existing convention (`app/test/features/...` mirroring `app/lib/features/...`).
- Backend worker tests: verify actual path during implementation; `services/worker/tests/` is the likely location based on `pythonpath` changes in recent commit `db8030d`.

### References

- Party Mode investigation identified root cause at `photo_capture_screen.dart:137`
- Backend aggregation logic: `libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py:199-226`
- Parser job creation endpoint: `services/api/src/api/v1/parser/create_parser_batch.py:60` (correctly accepts client-provided `group_index`)
- [Epic: epic-mvp-finalization.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
