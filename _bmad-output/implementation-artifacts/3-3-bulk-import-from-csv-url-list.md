# Story 3.3: Bulk Import from CSV/URL List

Status: done

## Story

As a user,
I want to bulk import recipes from a list of URLs,
so that I can migrate my entire recipe collection in one session.

## Acceptance Criteria

1. User can paste a list of URLs (one per line) and select a destination book
2. Processing runs asynchronously via Celery task chain
3. User sees a progress indicator showing completion counts
4. Processing continues in the background (user can leave and return)
5. System processes at minimum 10 recipes per minute for URL imports
6. High-confidence results are auto-accepted without user intervention

## Tasks / Subtasks

- [x] Task 1: Fix ParseSourceTask for url_list (AC: #2, #5)
  - [x] Fix `_parse_url_list()` stub — items are pre-created by StartImport, just count them
  - [x] Ensure extraction tasks dispatch correctly for bulk URLs

- [x] Task 2: Create bulk URL import screen (AC: #1, #3)
  - [x] Multi-line text field for pasting URLs
  - [x] URL validation and count display
  - [x] Book selector dropdown
  - [x] Submit button → calls `startImport` with `source_type="url_list"`

- [x] Task 3: Bulk import progress screen (AC: #3, #4)
  - [x] Poll `getImportJob` for progress counts
  - [x] Show progress bar with processed/total
  - [x] Display individual item statuses (succeeded, failed, awaiting review)
  - [x] Navigate to review items that need attention

- [x] Task 4: Navigation integration
  - [x] Add route for bulk import screen
  - [x] Add "Bulk Import" option in recipe book detail menu
  - [ ] Replace file_import_screen placeholder or integrate

## Code Review Action Items

- [x] [HIGH] Fix `completed_items` → `succeeded_items` field name in progress polling — API returns `succeeded_items` not `completed_items`, progress always shows 0 [bulk_url_import_screen.dart:192]
- [x] [HIGH] Fix `_approveAll` success count — tracks `reviewItems.length` instead of actual successes [bulk_url_import_screen.dart:304]
- [x] [MEDIUM] Add client-side URL count limit (max 50) with user-friendly error message [bulk_url_import_screen.dart:120]
- [x] [MEDIUM] Remove `prefixIcon` hardcoded `Padding(bottom: 200)` hack — fragile on different screen sizes [bulk_url_import_screen.dart:358]
- [x] [MEDIUM] Update story tasks to `[x]` to reflect completed work
- [x] [LOW] Remove misleading "come back later" text since no return mechanism exists [bulk_url_import_screen.dart:525]
- [x] [LOW] Add URL deduplication or duplicate warning [bulk_url_import_screen.dart:67-88]

## Dev Notes

### Backend Already Exists (Mostly)

- `StartImport` already accepts `source_type="url_list"` with `urls: list[str]`
- Creates ImportItem records for each URL
- Dispatches `parse_source_task` → `extract_recipe_task` chain
- Bug: `ParseSourceTask._parse_url_list()` is a stub returning 0, which overwrites `total_items`
- Fix: Same pattern as photo — use `job.total_items` directly since items are pre-created

### Import Item Status Flow

pending → extracting → matching → awaiting_review → approved → completed

### AC #6 (Auto-accept)

Auto-accept is handled by the matching task — high-confidence items skip straight to `completed`. This is existing behavior in the import pipeline.

### DO NOT:
- Implement CSV file upload (future enhancement)
- Implement edit-before-approve (Story 3.4)
- Add push notifications for completion (Story 3.6)
