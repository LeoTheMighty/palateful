# Story 13.10: Import Activity Attention View

**Status:** pending

## Summary

Redesign the Import History screen into an "Import Activity" screen with a YNAB-inspired attention-first UX. The default view shows only actionable items (needs review, failed, processing) with items expanded inline under lightweight job headers. Completed/skipped jobs are hidden behind a "Show import history" toggle. Clearing all actionable items reveals an "All Set!" resting state. "Skip" is renamed to "Dismiss" throughout. Filter chips are removed entirely.

## User Value

The current import history screen is a flat chronological list that shows everything — users have to mentally filter to find what needs attention. This redesign surfaces only what matters, creates a satisfying "clear the queue" workflow, and provides a calm resting state when everything is handled.

## Design Reference

Inspired by YNAB's transaction approval flow:
- Default view shows only unapproved/actionable items
- Progressive disclosure — completed items hidden until requested
- Clearing items one by one → "All caught up!" resting state
- Visual priority: amber dot (review) > red (failed) > spinner (processing) > muted (done)

## Acceptance Criteria

### Attention View (Default)

1. Screen title is "Import Activity" (not "Import History")
2. Filter chips are removed — no more All/Processing/Needs Review/Completed/Failed tabs
3. Default view fetches only jobs with status `awaiting_review`, `failed`, or `processing`
4. Jobs are displayed as lightweight section headers (source type icon + relative timestamp + item count) — NOT cards
5. Items within each "Needs Review" job are expanded by default — each item shows recipe name and is tappable
6. Items are grouped into sections: "Processing" (top, if any), "Needs Review" (middle), "Failed" (bottom)
7. Each section has a clear section header with status icon and label:
   - Processing: blue spinner + "Processing"
   - Needs Review: amber/orange filled dot + "Needs Review"
   - Failed: red error icon + "Failed"
8. Relative timestamps are shown on each job header: "7m ago", "2h ago", "Yesterday", "Mar 15"
9. Timestamps use the most relevant time: `completed_at` for finished, `started_at` for processing, `created_at` as fallback

### Status Icon System

10. Needs Review items: amber/orange filled circle icon
11. Processing items: small CircularProgressIndicator (blue)
12. Completed items: green check_circle (only visible in history view)
13. Failed items: red error icon
14. Skipped/Dismissed items: gray remove_circle_outline (only visible in history view)

### Dismiss Flow (replaces "Skip")

15. "Skip" button on `ImportItemReviewScreen` is renamed to "Dismiss"
16. On approve or dismiss, user auto-returns to the Import Activity list
17. The cleared item animates away (slide-out-left) using `AnimatedList`
18. The section item count updates immediately (optimistic UI)
19. Failed items section shows a "Dismiss All Failed" button that bulk-dismisses all failed items in that job (parallel skip API calls)

### "All Set!" Resting State

20. When zero actionable items remain (no needs_review, no failed, no processing), the attention area shows an "All Set!" state:
    - Green check_circle icon (large, 64px)
    - "All Set!" text
    - No "Done" button — user navigates away themselves using back button or bottom nav
21. The "Show import history" link remains visible below the "All Set!" state

### History Toggle

22. Below the attention view (or "All Set!" state), a "Show import history" text button is always visible
23. Tapping it loads and displays completed/skipped/cancelled jobs in a muted visual style
24. History jobs are displayed as collapsed cards (not expanded) — tappable to view details
25. History section is clearly visually separated from the attention area (divider or muted background)

### Navigation

26. Route stays at `/activity/import-history` (or update to `/activity/import-activity`)
27. Activity screen's "Import History" button label updates to "Import Activity"
28. Active Imports section on activity screen still links to this screen

## Tasks

### Task 1: Rename "Skip" to "Dismiss" in ImportItemReviewScreen

**File:** `app/lib/features/recipes/add_recipe/import_item_review_screen.dart`

- [ ] Change "Skip" button label to "Dismiss"
- [ ] Change "Skip This Item" on failed view to "Dismiss"
- [ ] Ensure `context.pop(false)` behavior unchanged (backend `skip` endpoint still used)

### Task 2: Rewrite ImportHistoryScreen as Import Activity screen

**File:** `app/lib/features/activity/import_history_screen.dart`

- [ ] Change screen title from "Import History" to "Import Activity"
- [ ] Remove filter chips entirely
- [ ] Fetch jobs with status `awaiting_review`, `failed`, `processing` for default view
- [ ] For each job with actionable items, fetch items via `listImportItems(jobId)`
- [ ] Build section-grouped layout: Processing → Needs Review → Failed
- [ ] Each section has a header with icon, label, and count
- [ ] Jobs appear as lightweight headers (source icon + relative time) under each section
- [ ] Items within "Needs Review" jobs are expanded inline by default
- [ ] Use `AnimatedList` for item removal animations
- [ ] Implement optimistic removal — remove item from local state on approve/dismiss, don't wait for reload
- [ ] Show "All Set!" state when no actionable items remain
- [ ] Add "Show import history" text button at bottom
- [ ] "Show import history" fetches completed/skipped/cancelled jobs and appends them in muted style
- [ ] Use contextual timestamps: `completed_at` for finished, `started_at` for processing, `created_at` fallback

### Task 3: Implement "Dismiss All Failed" bulk action

- [ ] Add a "Dismiss All Failed" button in the Failed section for each job
- [ ] On tap, fire parallel `skipImportItem` calls for all failed items in that job
- [ ] Show brief loading indicator on the button
- [ ] On completion, animate all failed items away and update section

### Task 4: Update Activity screen references

**File:** `app/lib/features/activity/activity_screen.dart`

- [ ] Update "Import History" button label to "Import Activity"
- [ ] Update any navigation references if route changes

### Task 5: Update route if needed

**File:** `app/lib/core/router/app_router.dart`

- [ ] Update route label/comment if renaming

## API Endpoints Used (No Backend Changes)

- `GET /v1/import-jobs?status=awaiting_review` — fetch jobs needing review
- `GET /v1/import-jobs?status=failed` — fetch failed jobs
- `GET /v1/import-jobs?status=processing` — fetch processing jobs
- `GET /v1/import-jobs?status=completed` — fetch history (on toggle)
- `GET /v1/import-jobs/{job_id}/items` — fetch items within a job
- `POST /v1/import-items/{item_id}/skip` — dismiss an item (existing "skip" endpoint)
- `POST /v1/import-items/{item_id}/approve` — approve an item

## Out of Scope

- Backend API changes (all endpoints exist)
- Push notifications
- Batch import status widget merge (Story 13.11)
- Swipe gestures for approve/dismiss (future enhancement)
