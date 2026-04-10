# 13.1 Server-Side Pipeline Orchestration

**Status:** in-progress

## Summary

Move the OCR-to-import pipeline orchestration from the Flutter client to the backend so that closing the app no longer orphans OCR results.

## Changes

### Model Changes
- Added `recipe_book_id` (FK to recipe_books, nullable) and `import_job_id` (FK to import_jobs, nullable) to `ParserJob` model

### Migration
- `20260410000000_add_recipe_book_id_to_parser_jobs.py` — adds both columns with foreign keys

### API Changes
- `submit_parser_job.py` now accepts optional `recipe_book_id` in request body
- When `recipe_book_id` is provided, dispatches `WatchParserJobTask` after Batch job submission

### New Celery Task
- `WatchParserJobTask` in `libraries/utils/utils/tasks/import_tasks/watch_parser_job_task.py`
- Polls AWS Batch every 30 seconds (up to 40 attempts = 20 min)
- On success: reads S3 output, updates ParserJob, creates ImportJob + ImportItem, dispatches `parse_source_task`
- On failure: updates ParserJob status, creates failure activity

### Flutter Changes
- `api_client.dart` — `submitParserJob` now accepts optional `recipeBookId`
- `photo_capture_screen.dart` — passes `_selectedBookId` as `recipeBookId` when submitting single-image parser job

## Testing
- Run `npx nx run api:test -- --no-cov` to verify existing tests pass
