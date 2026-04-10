# Story 13.2: Import Activity & Notification Overhaul

## Summary

Added a new `GET /v1/import-jobs` endpoint for listing all import jobs for the current user with pagination and status filtering, and added activity creation for missing import lifecycle events (needs-review, extraction failure, matching failure).

## Changes

### 1. New endpoint: GET /v1/import-jobs

- **File**: `services/api/src/api/v1/import_job/list_import_jobs.py` (new)
- Queries `ImportJob` where `user_id` = current user, ordered by `created_at desc`
- Params: `status` (optional filter), `limit` (default 20), `offset` (default 0)
- Response: list of jobs with id, status, source_type, total_items, succeeded_items, failed_items, pending_review_items, recipe_book_id, created_at, completed_at + total count and has_more flag
- Wired into `services/api/src/routers/v1/import_router.py`
- Exported from `services/api/src/api/v1/import_job/__init__.py`

### 2. Activity creation for missing import events

#### a) match_ingredients_task.py - "import_needs_review" activity
- When item status becomes `awaiting_review` after ingredient matching
- Type: `import_needs_review`
- Title: `{recipe_name} needs review`
- Subtitle: `Some ingredients need confirmation`
- action_url: `/recipes/import/review/{item_id}`

#### b) extract_recipe_task.py - "import_failed" activity on extraction error
- When extraction throws an exception
- Type: `import_failed`
- Title: `Import failed`
- Subtitle: error message
- action_url: `/recipes/import/review-list/{job_id}`

#### c) match_ingredients_task.py - "import_failed" activity on matching error
- When ingredient matching throws an exception
- Type: `import_failed`
- Title: `{recipe_name} failed to import`
- Subtitle: error message
- action_url: `/recipes/import/review-list/{job_id}`

## Activity types coverage (after this story)

| Event | Activity type | Created in |
|---|---|---|
| Import started | `import_started` | `start_import.py` (existing) |
| Recipe auto-approved | `import_complete` | `match_ingredients_task.py` (existing) |
| Recipe needs review | `import_needs_review` | `match_ingredients_task.py` (new) |
| Extraction failed | `import_failed` | `extract_recipe_task.py` (new) |
| Matching failed | `import_failed` | `match_ingredients_task.py` (new) |
| Job completed | `import_complete` | `create_recipe_task.py` (existing) |

## Testing

- Run `npx nx run api:test -- --no-cov` to verify no regressions
