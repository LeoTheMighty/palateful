# QA Walkthrough: MVP.6 — Retry Import Item Endpoint

## What shipped

1. **`POST /v1/import-items/{item_id}/retry`** — new endpoint that resumes a failed import item from the pipeline stage after its `last_successful_stage` marker.
2. **Stage-aware dispatch** via a table-driven lookup (`_STAGE_PLAN`) instead of an if/elif chain. Mapping:
   - `NULL` or unknown → `parse_source_task` (full restart), item status → `"pending"`
   - `"parsed"` → `extract_recipe_task`, item status → `"extracting"`
   - `"extracted"` → `match_ingredients_task`, item status → `"matching"`
   - `"matched"` → `create_recipe_task`, item status → `"approved"`
3. **Reset logic**: clears `error_message`, `error_code`, increments `retry_count`, sets new status.
4. **Parent job unstick**: if `job.status == "failed"` (sweeper case), flips it back to `processing` and clears `error_message` / `completed_at`. If the job is already in a non-failed state, it is left untouched.
5. **Ownership check**: must be owner or editor of the recipe book that owns the parent job.
6. **Accepted risk**: concurrent retries are permitted per Leo's explicit decision. Two tasks racing on the same item can produce duplicate `Recipe` rows from `create_recipe_task`. Documented in the endpoint source, the story, the epic, and this walkthrough. No `retry_in_progress` guard.
7. **Forward-compat**: unknown `last_successful_stage` values (e.g. from a future stage marker) fall back to a full restart instead of crashing.
8. **Test coverage**: 12 new test cases in `TestRetryImportItem`:
   - Not found (item, job)
   - Forbidden (no membership, viewer role)
   - Non-retryable status (item completed + job completed → 400)
   - Stage dispatch (NULL → parse, "parsed" → extract, "extracted" → match, "matched" → create)
   - Sweeper case (item still `extracting`, parent job `failed`)
   - Item failed + job still processing → job not flipped
   - Unknown stage marker → full restart fallback

## QA checklist

### Automated
- [x] `npx nx run api:test` — **1241 / 1241 pass, 100.00% coverage**
- [x] `npx nx run api:lint` — clean

### Manual (to run post-deploy)
- [ ] Force a URL import to fail at the extract stage (bad URL → extractor throws)
- [ ] Call `POST /v1/import-items/{id}/retry` with the failed item's ID
- [ ] Verify response: `dispatched_task = "extract_recipe_task"`, `resumed_from_stage = "parsed"`, `status = "extracting"`
- [ ] Verify in DB: `retry_count` incremented, `error_message` NULL, `status = "extracting"`
- [ ] Let the retry run — should progress through matching + create stages normally
- [ ] Second test: force a match failure, retry, verify `dispatched_task = "match_ingredients_task"` (skips extract — confirms OCR/LLM cost is not re-paid)
- [ ] Sweeper-case test: kill a worker mid-extract, let the sweeper mark the job failed, hit retry on the child item — verify the endpoint accepts it, flips the job back to `processing`, and dispatches `extract_recipe_task`

### Known tradeoffs / follow-ups
- **Concurrent retry risk accepted**: if duplicate recipes appear in dogfood, open a follow-up story to add `retry_in_progress` atomic guard.
- **Full-restart path dispatches `parse_source_task(job.id)`** which re-processes all items under the parent job, not just this one. For url_list imports with partial failures, this over-retries. Acceptable for MVP; narrow down in a follow-up if it becomes painful.
- **No retry activity feed entry**: the endpoint does not create a `user_activity` row on retry. Frontend feedback (mvp-8) covers the UX without needing a backend activity.

## Files touched

- `services/api/src/api/v1/import_job/retry_import_item.py` (new)
- `services/api/src/api/v1/import_job/__init__.py` (register endpoint)
- `services/api/src/routers/v1/import_router.py` (wire route)
- `services/api/tests/test_import.py` (append `TestRetryImportItem`)
- `_bmad-output/implementation-artifacts/mvp-6-qa-walkthrough.md` (new)
