# Story 3.4: Exception Review Queue

Status: done

## Story

As a user,
I want to review and correct only the imports that need attention,
so that I don't have to babysit every import — just fix the exceptions.

## Acceptance Criteria

1. User can view a list of import items that need review (awaiting_review status)
2. User can edit recipe fields (name, description, ingredients, instructions, times, servings) before approving
3. User edits are saved via the `user_edits` field and merged during recipe creation
4. User can approve or skip individual items from the review screen
5. Review queue is accessible from the bulk import results screen and recipe book detail menu
6. Failed items show error details with option to skip

## Tasks / Subtasks

- [x] Task 1: Add missing API client methods (AC: #2, #3)
  - [x] Add `getImportItem(itemId)` method
  - [x] Add `updateImportItem(itemId, userEdits)` method

- [x] Task 2: Create import review screen (AC: #1, #2, #3, #4, #6)
  - [x] Show parsed recipe fields in editable form
  - [x] Save user_edits on field changes
  - [x] Approve and skip buttons
  - [x] Handle failed items with error display

- [x] Task 3: Create import review list screen (AC: #1, #5)
  - [x] List items needing review with status indicators
  - [x] Navigate to individual item review
  - [x] Show summary counts (review, completed, failed)

- [x] Task 4: Navigation integration (AC: #5)
  - [x] Add routes for review list and item review screens
  - [x] Navigate from bulk import results to review queue
  - [ ] Add "Review Imports" option in recipe book detail menu (deferred — needs list-jobs-for-book endpoint)

## Code Review Action Items

- [ ] [MEDIUM] AC #5 partial: Review queue accessible from bulk import results but not recipe book detail menu — requires "list import jobs for book" endpoint (deferred)
- [x] [MEDIUM] Cancel debounce timer in `_approve()` before saving — stale timer fires after approval [import_item_review_screen.dart:166]
- [x] [MEDIUM] Update story tasks to `[x]` to reflect completed work
- [x] [LOW] Fix null handling in `_populateControllers` — use direct null check instead of string comparison [import_item_review_screen.dart:94-99]
- [x] [LOW] Include null values for cleared numeric fields in `_buildUserEdits` [import_item_review_screen.dart:141-148]

## Dev Notes

### Backend Already Complete

All endpoints exist and are wired up:
- `GET /v1/import-items/{item_id}` — full item with raw_data, parsed_recipe, user_edits
- `PUT /v1/import-items/{item_id}` — accepts `user_edits: dict`
- `POST /v1/import-items/{item_id}/approve` — requires parsed_recipe OR user_edits
- `POST /v1/import-items/{item_id}/skip` — marks as skipped
- `GET /v1/import-jobs/{job_id}/items?status=awaiting_review` — filtered list

### Missing from API Client

- `getImportItem(itemId)` — not exposed in Flutter API client
- `updateImportItem(itemId, userEdits)` — not exposed in Flutter API client

### user_edits Structure

The `user_edits` dict mirrors the parsed_recipe structure. During recipe creation, user_edits fields override parsed_recipe fields. Example:
```json
{
  "name": "Corrected Recipe Name",
  "ingredients": [{"text": "2 cups flour"}, {"text": "1 cup sugar"}],
  "instructions": "Corrected step-by-step..."
}
```

### DO NOT:
- Implement side-by-side OCR comparison (future enhancement)
- Add swipe-to-resolve gesture (Story mentions it but it's polish — keep simple for now)
- Add manual recipe entry for dead links (just skip)
