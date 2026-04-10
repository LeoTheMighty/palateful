# Story 13.9: Import History Frontend

**Status:** complete

## Summary

Add a dedicated Import History screen accessible from the Activity tab, and an "Active Imports" section pinned to the top of the activity feed. The backend `GET /v1/import-jobs` endpoint already exists (story 13.2) — this is purely frontend work.

## Acceptance Criteria

1. `listImportJobs({status?, limit, offset})` API client method wired to `GET /v1/import-jobs`
2. Import History screen shows all import jobs sorted by most recent, with source type icon, status chip, item counts, and relative timestamp
3. Status filter tabs/chips to filter by: All, Processing, Needs Review, Completed, Failed
4. Pagination via "load more" or infinite scroll
5. Tapping a job navigates to existing `ImportReviewListScreen` at `/recipes/import/review-list/{jobId}`
6. Activity screen has a persistent "Import History" button that navigates to the new screen
7. Activity screen shows an "Active Imports" section at top when any jobs have status `processing` or `awaiting_review`
8. Empty state when no import jobs exist

## Tasks

### Task 1: Add `listImportJobs` to API client

**File:** `app/lib/core/services/api_client.dart`

- [x] Add method after `cancelImportJob`:
  ```dart
  Future<Response> listImportJobs({String? status, int limit = 20, int offset = 0}) {
    return _dio.get('/v1/import-jobs', queryParameters: {
      'limit': limit,
      'offset': offset,
      if (status != null) 'status': status,
    });
  }
  ```

### Task 2: Create Import History screen

**File:** `app/lib/features/activity/import_history_screen.dart` (new)

- [x] StatefulWidget with `_jobs` list, `_isLoading`, `_error`, `_hasMore`, `_offset` state
- [x] `_loadJobs({bool loadMore = false})` — calls `listImportJobs`, appends on loadMore
- [x] Filter chips at top: All, Processing, Needs Review, Completed, Failed — changing filter resets list
- [x] Each job card shows:
  - Source type icon (url → link, photo → camera, text → description, spreadsheet → table_chart, pdf → picture_as_pdf, audio → mic, url_list → list)
  - Job status chip with color (processing → tertiary, awaiting_review → tertiary, completed → primary, failed → error, cancelled → outline)
  - Item counts: "{succeeded} imported" + conditionally "{pending_review} to review" / "{failed} failed"
  - Relative time (use `timeago` style: "2h ago", "Mar 15", etc.)
- [x] Tapping card → `context.push('/recipes/import/review-list/$jobId')`
- [x] "Load more" button at bottom when `hasMore` is true
- [x] Pull-to-refresh
- [x] Empty state: icon + "No imports yet"
- [x] Refresh when returning from review screen (listen for pop result)

### Task 3: Add route for Import History

**File:** `app/lib/core/router/app_router.dart`

- [x] Import `ImportHistoryScreen`
- [x] Add route `/activity/import-history` under the activity shell branch (inside `_activityNavigatorKey` branch, as a sibling to `/activity`)

### Task 4: Add "Import History" button and "Active Imports" section to Activity screen

**File:** `app/lib/features/activity/activity_screen.dart`

- [x] Add `_activeJobs` list to state
- [x] In `_loadActivities`, also call `listImportJobs(status: 'processing')` and `listImportJobs(status: 'awaiting_review')` to populate `_activeJobs` (combine both results)
- [x] Add "Import History" action button in the app bar (history icon)
- [x] Before the day-grouped activity list, render an "Active Imports" section if `_activeJobs` is not empty:
  - Section header "Active Imports"
  - Compact cards showing job source type, status, and item counts
  - Tapping navigates to `/recipes/import/review-list/{jobId}`
- [x] Wrap the activity list body in a Column or add to ListView so active imports appear above

## API Response Reference

```
GET /v1/import-jobs?status=...&limit=20&offset=0

{
  "jobs": [
    {
      "id": "uuid",
      "status": "completed|processing|awaiting_review|failed|cancelled",
      "source_type": "url|url_list|photo|text|spreadsheet|pdf|audio",
      "total_items": 3,
      "succeeded_items": 2,
      "failed_items": 1,
      "pending_review_items": 0,
      "recipe_book_id": "uuid",
      "created_at": "2026-04-10T...",
      "completed_at": "2026-04-10T..." | null
    }
  ],
  "total": 15,
  "has_more": false
}
```

## Out of Scope

- Push notifications for import status changes (already handled)
- Modifying ImportReviewListScreen or ImportItemReviewScreen
- Backend changes (API already exists)
