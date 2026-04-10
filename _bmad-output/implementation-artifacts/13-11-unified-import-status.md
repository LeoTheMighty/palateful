# Story 13.11: Unified Import Status

**Status:** pending

## Summary

Merge the home screen's `BatchImportStatusWidget` into the Import Activity screen so there is one unified place for all import status. The home screen widget becomes a lightweight notification badge that deep-links to Import Activity instead of being its own expandable status panel.

## User Value

Currently import status lives in two disconnected places: a collapsible bar on the home screen (for active photo imports) and the Import Activity screen (for all jobs). This is confusing — users see status in one place but have to go to another to take action. Unifying them means one screen to rule all imports.

## Dependencies

- Story 13.10 (Import Activity Attention View) must be complete first

## Acceptance Criteria

1. Home screen's `BatchImportStatusWidget` is replaced with a compact notification badge
2. Badge shows: icon + "X recipes to review" or "Processing X photos..." — single line
3. Tapping the badge navigates to Import Activity screen (`/activity/import-history` or `/activity/import-activity`)
4. Badge disappears when no active/actionable imports exist
5. The expanded job list that currently lives in `BatchImportStatusWidget` is removed — that detail now lives in Import Activity
6. Active photo imports (uploading, submitting, polling) show as "Processing" items in Import Activity with their filename and status text
7. The `BatchParserService` stream is consumed by Import Activity to show real-time photo import progress alongside server-side job status

## Tasks

### Task 1: Simplify BatchImportStatusWidget to notification badge

**File:** `app/lib/features/home/widgets/batch_import_status_widget.dart`

- [ ] Remove expandable job list (`_buildJobList`, `_buildJobRow`, `_expanded` state)
- [ ] Keep only the collapsed bar, simplified to a single-line badge
- [ ] Badge text: "X recipes to review" (if awaiting_review jobs exist) or "Processing X photos..." (if active)
- [ ] On tap: navigate to Import Activity screen instead of toggling expand
- [ ] Remove dismiss/retry buttons from the badge — those actions live in Import Activity now
- [ ] Remove `BatchJobResultSheet` usage — results are viewed in Import Activity

### Task 2: Add BatchParserService integration to Import Activity

**File:** `app/lib/features/activity/import_history_screen.dart`

- [ ] Subscribe to `BatchParserService.jobStream` for real-time local photo import status
- [ ] Show active local jobs (uploading/submitting/polling) in the "Processing" section
- [ ] Show filename and status text (Uploading.../Submitting.../Processing...) for each
- [ ] When a local job completes, it should appear as a server-side job in the attention view (via refresh)

### Task 3: Clean up unused code

- [ ] Remove `BatchJobResultSheet` if no longer used elsewhere
- [ ] Remove any expanded-list related code from the widget

## Out of Scope

- Changes to `BatchParserService` itself — the service stays, only the UI consumer changes
- Backend changes
