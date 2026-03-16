# Story 3.1: URL Recipe Import

Status: done

## Story

As a user,
I want to import a recipe by pasting a URL,
so that I can save recipes I find online without manual data entry.

## Acceptance Criteria

1. User can enter a URL to a recipe page and select a destination book
2. System extracts structured recipe data using JSON-LD with AI fallback
3. User sees a preview of the extracted recipe before saving
4. User can approve the import to create the recipe
5. Extraction completes within a few seconds for standard recipe sites
6. Source URL is preserved on the created recipe

## Tasks / Subtasks

- [x] Task 1: Add import-related API client methods to Flutter (AC: #1-#4)
  - [x] Add `startImport(bookId, sourceType, {url, urls})`
  - [x] Add `getImportJob(jobId)`
  - [x] Add `listImportItems(jobId)`
  - [x] Add `approveImportItem(itemId)`
  - [x] Add `skipImportItem(itemId)`
  - [x] Add `cancelImportJob(jobId)`

- [x] Task 2: Create URL import screen (AC: #1, #5)
  - [x] URL text input with validation
  - [x] Book selector dropdown (reuse recipe books list)
  - [x] Import button → calls `startImport`
  - [x] Polls `getImportJob` for status updates with loading indicator
  - [x] On extraction complete, loads import items and shows preview

- [x] Task 3: Recipe preview and approve flow (AC: #2, #3, #4, #6)
  - [x] Display extracted recipe name, ingredients, instructions, image, times
  - [x] Approve button → calls `approveImportItem` → navigates to recipe or shows success
  - [x] Skip/cancel buttons
  - [x] Error handling for failed extractions

- [x] Task 4: Navigation integration
  - [x] Add route for URL import screen in app_router.dart
  - [x] Add "Import from URL" option in recipe wizard or book detail screen
  - [x] Add entry point accessible from the add recipe flow

## Dev Notes

### Backend Already Exists

The entire backend pipeline is implemented:
- `POST /recipe-books/{book_id}/import` — StartImport endpoint (source_type="url")
- `GET /import-jobs/{job_id}` — Poll for status
- `GET /import-jobs/{job_id}/items` — List extracted items
- `POST /import-items/{item_id}/approve` — Approve and create recipe
- `POST /import-items/{item_id}/skip` — Skip item
- Celery tasks: ParseSourceTask → ExtractRecipeTask (JSON-LD + AI fallback)

This story only needs Flutter implementation.

### Import Flow

1. User enters URL + selects book → `POST /recipe-books/{bookId}/import`
2. App polls `GET /import-jobs/{jobId}` every 2 seconds
3. When job status reaches "awaiting_review" or "completed", load items
4. Show preview of `parsed_recipe` data from import item
5. User taps Approve → `POST /import-items/{itemId}/approve`
6. Recipe creation happens async, show success

### DO NOT:
- Implement edit-before-approve (future enhancement)
- Add bulk URL import UI (Story 3.3)
- Create new backend endpoints (everything exists)
- Add share sheet integration (Story 3.5)
