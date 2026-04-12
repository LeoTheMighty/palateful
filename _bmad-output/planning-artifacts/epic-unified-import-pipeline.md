# Epic 13: Unified Recipe Import Pipeline & Eval Suite

## Overview

The recipe import pipeline is ~85% wired but has critical gaps: the frontend orchestrates the OCR→import handoff (breaks if user leaves), import failures are invisible, ingredient mismatches block recipe creation, and there's no way to compare extraction strategies. This epic makes the pipeline fully server-side, adds comprehensive visibility via the activity feed, and builds an eval suite to optimize and verify every stage.

**Goal:** Any input (photo, URL, text, spreadsheet) → recipe in the database, fully server-side, with evals proving each stage works and full visibility in the activity feed.

## Current Pipeline (Broken)

```
App: upload → submit parser → [poll parser] → [read S3] → [call startImport] → [poll import] → review
     ^^^^^^^^^^^^^^^^^^^^^^    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
     Works                     Frontend orchestration — breaks if app closes
```

## Target Pipeline

```
App: upload → submit parser → poll for result → see recipe / review
Backend: parser → OCR → read S3 → extract recipe → match ingredients → create recipe → notify
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
         Fully server-side, activities at every step
```

## Story Map

| Story | Title | Est | Dependencies |
|-------|-------|-----|-------------|
| 13.1 | Server-Side Pipeline Orchestration | 2 days | None |
| 13.2 | Import Activity & Notification Overhaul | 1.5 days | 13.1 |
| 13.3 | Fix Pipeline Gaps | 1 day | 13.1 |
| 13.4 | Standard Recipe JSON Schema & Validation | 0.5 day | None |
| 13.5 | Eval Framework & Fixtures | 2 days | 13.4 |
| 13.6 | GPT-4o-mini Vision Track | 1 day | 13.4 |
| 13.7 | Prompt Optimization | 1.5 days | 13.5, 13.6 |
| 13.8 | End-to-End Integration & Eval Gates | 1.5 days | 13.7 |
| 13.9 | Import History Frontend | 1 day | 13.2 |
| 13.10 | Import Activity Attention View | 1.5 days | 13.9 |
| 13.11 | Unified Import Status | 1 day | 13.10 |
| 13.12 | Parser Batch Data Model & Grouped Import Pipeline | 2 days | 13.1 |
| 13.13 | Photo Batch Import UX | 1.5 days | 13.12 |
| 13.14 | Live Import Progress Controller & Strip | 1.5 days | 13.12, 13.13 |

**Total: ~19.5 days**

**Parallel tracks:**
```
Track A (pipeline):  13.1 → 13.2 → 13.3
Track B (evals):     13.4 → 13.5 → 13.7 → 13.8
                     13.4 → 13.6 ↗
Track C (frontend):  13.2 → 13.9 → 13.10 → 13.11
Track D (batches):   13.12 → 13.13 → 13.14
```

---

## Story 13.1: Server-Side Pipeline Orchestration

As a user,
I want to submit a photo/file for import and have the entire extraction happen on the backend,
so that I can close the app and come back to find my recipe ready.

### Acceptance Criteria

1. `ParserJob` has `recipe_book_id` field — backend knows where to create the recipe
2. When Batch OCR succeeds, a Celery task automatically reads S3 output and creates an ImportJob + ImportItem
3. The import pipeline (extract → match → create) runs entirely server-side with no frontend calls required
4. App only submits the parser job and then polls a single status endpoint
5. If the app is closed during processing, the recipe still gets created
6. `ParserJob` links to `ImportJob` via FK for traceability

### Technical Approach

- Add `recipe_book_id` and `import_job_id` columns to `ParserJob` model
- New Celery beat task: `check_parser_jobs_task` — runs every 30s, finds ParserJobs with `status=submitted`, syncs status from Batch, and on success: reads S3, creates ImportJob/ImportItem, dispatches `parse_source_task`
- Alternatively: after `submit_parser_job`, dispatch a Celery task `watch_parser_job_task(parser_job_id)` that polls Batch until complete, then triggers the import chain
- Update `GET /v1/parser/jobs/{id}` to include import_job_id and final recipe status

---

## Story 13.2: Import Activity & Notification Overhaul

As a user,
I want to see all my import activity — ongoing, completed, failed, needs review — in the activity tab,
so that I never lose track of an import and can always find what needs attention.

### Acceptance Criteria

1. Activities created for ALL import events:
   - `import_started` — when import begins (already exists)
   - `import_extracting` — when OCR/extraction is in progress
   - `import_needs_review` — when items flagged for ingredient review (MISSING today)
   - `import_item_complete` — when a recipe is auto-approved and created
   - `import_failed` — when items fail extraction or matching (MISSING today)
   - `import_complete` — when all items processed (already exists)
2. New API endpoint: `GET /v1/import-jobs` — list all user's import jobs with status, counts, dates
3. Activity page shows "Active Imports" section at top with progress indicators
4. Tapping any import activity navigates to the import review screen
5. Failed imports show error details and option to retry
6. Past imports accessible via "View import history" link

### Technical Approach

- Add activity creation calls in `extract_recipe_task`, `match_ingredients_task` (for needs_review and failures)
- New endpoint in import router: `GET /v1/import-jobs` with query params (status, limit, offset)
- Update activity screen to show active imports section
- Add "Import History" screen accessible from activity page

---

## Story 13.3: Fix Pipeline Gaps

As a user,
I want my recipes to be created even when some ingredients don't match perfectly,
so that I don't have to manually review every single ingredient.

### Acceptance Criteria

1. Unmatched ingredients auto-create a new `Ingredient` with `pending_review=True` instead of blocking
2. `create_recipe_task` never drops ingredients — all parsed ingredients appear in the final recipe
3. High-confidence extractions (all ingredients matched >0.85) auto-approve without user review
4. `ImportItem.status` flow: extracting → matching → approved (auto) or awaiting_review (low confidence)
5. User review is only required when extraction confidence is low or ingredients are ambiguous

### Technical Approach

- Modify `match_ingredients_task.py`: when no match found, create `Ingredient(canonical_name=parsed_name, pending_review=True, submitted_by_id=user_id)` and use that ID
- Modify `create_recipe_task.py`: don't skip ingredients without `matched_ingredient_id` — should never happen after above fix
- Add auto-approve threshold: if all ingredients matched with confidence >0.85, set `item.status = "approved"` and dispatch `create_recipe_task` immediately

---

## Story 13.4: Standard Recipe JSON Schema & Validation

As a developer,
I want a canonical JSON schema that all recipe extractors must output,
so that the pipeline has a clear contract and evals can validate compliance.

### Acceptance Criteria

1. JSON Schema defined in `libraries/utils/utils/schemas/recipe_extraction_schema.py`
2. Schema covers: title, description, ingredients (name, quantity, unit, notes), steps (instruction, order), prep_time, cook_time, servings, tags, source_url, image_url, primary_vibe, secondary_vibe
3. Validation function: `validate_extraction_result(data) → (valid: bool, errors: list)`
4. All existing extractors (text_extractor, ai_extractor, json_ld_extractor) output this schema
5. Schema is versioned (v1) for future evolution

---

## Story 13.5: Eval Framework & Fixtures

As a developer,
I want an eval suite that tests each pipeline stage against ground truth fixtures,
so that I can measure accuracy, compare strategies, and prevent regressions.

### Acceptance Criteria

1. Eval runner at `services/eval/` that tests each stage independently
2. Fixtures directory with 10-15 test cases across input types:
   - 5 photos (cookbook pages, handwritten, screenshots, phone photos)
   - 5 URLs (popular recipe sites with varying formats)
   - 3 text inputs (copy-pasted, messy formatting, multi-recipe)
   - 2 spreadsheets (CSV exports)
3. Each fixture has a ground truth JSON matching the standard schema
4. Scoring per fixture:
   - `ingredients_precision` — % of extracted ingredients that are correct
   - `ingredients_recall` — % of actual ingredients that were extracted
   - `amounts_accuracy` — % of quantities/units correct
   - `steps_completeness` — % of steps captured in correct order
   - `metadata_accuracy` — title, times, servings correct
   - `overall_f1` — combined score
5. Strategy comparison mode: run multiple extractors on same fixtures, output comparison table
6. CLI: `npx nx run eval:test` outputs results to console and JSON report

---

## Story 13.6: GPT-4o-mini Vision Track

As a developer,
I want to extract structured recipe data directly from images using GPT-4o-mini vision,
so that photo imports work in seconds without GPU infrastructure.

### Acceptance Criteria

1. New extractor: `libraries/utils/utils/services/recipe_extractors/vision_extractor.py`
2. Takes an image (PIL Image or bytes) → structured recipe JSON matching standard schema
3. Single OpenAI API call with image input, no GPU, no Batch
4. Response time: <15 seconds per image
5. Cost: ~$0.01-0.03 per image
6. Wired into the import pipeline as an alternative strategy to HunyuanOCR → text_extractor
7. Eval results compared against HunyuanOCR track

### Technical Approach

- Use OpenAI's vision API: `model="gpt-4o-mini"`, pass image as base64 in message content
- Prompt: "Extract this recipe as JSON with the following schema: {schema}"
- Parse JSON response, validate against standard schema
- Register as strategy in eval framework for comparison

---

## Story 13.7: Prompt Optimization

As a developer,
I want to use the eval suite to find the best prompts for each extractor,
so that extraction accuracy is maximized for every input type.

### Acceptance Criteria

1. HunyuanOCR prompt tested: raw text output vs structured JSON output
2. GPT-4o-mini text_extractor prompt iterated for highest F1 score
3. GPT-4o-mini vision_extractor prompt iterated for highest F1 score
4. Results documented: which strategy wins for which input type
5. Best prompts committed as the defaults in each extractor
6. Eval scores for each strategy recorded in a comparison report

---

## Story 13.8: End-to-End Integration & Eval Gates

As a developer,
I want all input types to produce recipes end-to-end with eval verification,
so that the pipeline is reliable and regressions are caught before deploy.

### Acceptance Criteria

1. E2E test: submit image → recipe in database → matches ground truth
2. E2E test: submit URL → recipe in database → matches ground truth
3. E2E test: submit text → recipe in database → matches ground truth
4. Strategy routing: system picks best extractor per input type based on eval data
5. Eval fixtures expanded to 30+ across all input types
6. CI integration: `npx nx run eval:test` runs in CI, fails deploy if accuracy drops below thresholds
7. Accuracy thresholds:
   - URL import: ≥95% overall F1
   - Photo import: ≥85% overall F1
   - Text import: ≥90% overall F1
   - Spreadsheet import: ≥95% overall F1

---

## Story 13.10: Import Activity Attention View

As a user,
I want the import screen to show me only what needs my attention by default,
so that I can quickly review or dismiss items and reach a clear "All Set" state.

### Acceptance Criteria

1. Screen renamed from "Import History" to "Import Activity"
2. Filter chips removed — default view shows only actionable items (awaiting_review, failed, processing)
3. Items within jobs are expanded inline under lightweight job headers (source icon + relative time)
4. Sections grouped: Processing → Needs Review → Failed
5. Clear status icons: amber dot (review), blue spinner (processing), red error (failed), green check (completed)
6. "Skip" renamed to "Dismiss" throughout
7. On approve/dismiss, item animates away (slide-out), count updates optimistically
8. "Dismiss All Failed" bulk action per job section
9. When zero actionable items remain, show "All Set!" resting state (green check + text)
10. "Show import history" toggle at bottom loads completed/skipped jobs in muted style
11. Contextual timestamps: completed_at for finished, started_at for processing, created_at fallback

### Technical Approach

- Rewrite `import_history_screen.dart` with attention-first layout
- Use `AnimatedList` for removal animations
- Fetch jobs by status (3 parallel API calls), then fetch items for each
- Optimistic UI: remove items from local state immediately, don't wait for reload
- No backend changes needed — all endpoints exist

---

## Story 13.11: Unified Import Status

As a user,
I want one place for all import status instead of separate widgets on home and activity screens,
so that I always know where to look for import progress.

### Acceptance Criteria

1. Home screen's `BatchImportStatusWidget` becomes a compact notification badge (single line)
2. Badge text: "X recipes to review" or "Processing X photos..."
3. Tapping badge navigates to Import Activity screen
4. Expanded job list removed from home widget — detail lives in Import Activity
5. Import Activity shows real-time photo import progress via `BatchParserService` stream
6. Badge disappears when no active/actionable imports exist

### Technical Approach

- Simplify `batch_import_status_widget.dart` to notification badge only
- Add `BatchParserService` stream subscription to Import Activity screen
- Show local active jobs in Processing section alongside server-side jobs

---

## Story 13.12: Parser Batch Data Model & Grouped Import Pipeline

As a user,
I want multiple photos of the same recipe to be imported as a single recipe,
so that page 1 and page 2 of a cookbook don't become two fragmented recipes.

### The Bug This Fixes

`WatchParserJobTask._handle_success` currently creates one `ImportJob(total_items=1)` per parser job, so N photos → N recipes. Combined with `submit_batch_parser_job.py` not passing `recipe_book_id`, the multi-image flow relies on a fragile frontend fallback path that dies if the user navigates away.

### Acceptance Criteria

1. New `parser_batches` table with `id, user_id, recipe_book_id, status, group_count, error_message, timestamps`
2. `parser_jobs` gains `parser_batch_id` (FK, CASCADE) and `group_index` (Int default 0)
3. `import_jobs` gains `parser_batch_id` (FK, SET NULL) for traceability
4. New endpoint `POST /v1/parser/batches` accepts `{recipe_book_id, items: [{s3_key, group_index}]}`, creates batch + N parser jobs, submits one AWS Batch job, dispatches `WatchParserBatchTask`
5. New endpoint `GET /v1/parser/batches/{id}` returns nested job + import job state
6. New endpoint `GET /v1/parser/batches?active=true&limit=20` lists user's active batches
7. New `WatchParserBatchTask` waits for all jobs in a batch to reach terminal state, then fans out to one `ImportJob` per `group_index` with OCR texts concatenated within each group
8. Per-group `s3_keys` threaded through `raw_data` so downstream `extract_recipe_task` can pick correct `image_url`
9. `parser_batch.status` reflects aggregate: `succeeded | partial | failed`
10. Old `WatchParserJobTask` retained for single-image path; new batch path uses new task exclusively
11. Test coverage for happy path, partial failure, total failure, idempotency

### Technical Approach

- Migration in `services/migrator/migrations/versions/` following existing naming convention
- New model: `libraries/utils/utils/models/parser_batch.py`
- New task: `libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py`
- New endpoints in `services/api/src/api/v1/parser/` (one file each), wired in `parser_router.py`
- Scope limited to photo import — other paths (URL bulk, PDF, spreadsheet, text, audio) untouched

---

## Story 13.13: Photo Batch Import UX

As a user,
I want to select multiple photos and decide in one tap whether they're one recipe or several,
so that the common case (one recipe, N pages) is effortless and the edge case (multiple recipes in one selection) is still possible.

### Acceptance Criteria

1. Images begin uploading to S3 **immediately on selection** — no "process" button required; upload progress shown per thumbnail
2. Once all uploads complete, the screen shows a primary "Import as one recipe" button and a tertiary "These are separate recipes →" link
3. Primary button calls `POST /v1/parser/batches` with `group_index=0` for every image, then **immediately pops back to the import hub** with a confirmation snackbar — no wait screen
4. Secondary link transitions to a grouping view (grid of thumbnails, each badged `Recipe 1`, `Recipe 2`, ... defaulting to one-per-image)
5. Grouping view uses **tap-to-assign** with a chip row (`Recipe 1`, `Recipe 2`, `+ New recipe`) — no drag-and-drop
6. Live counter: "Will create N recipes" at top of grouping view
7. Recipe numbers auto-compact when reassignments leave gaps
8. Grouping submit calls `POST /v1/parser/batches` with assembled `items: [{s3_key, group_index}]`, then pops back
9. Existing recipe preview / approval flow inside `photo_capture_screen.dart` is **removed** — review now happens via the existing `ImportReviewListScreen` reached from Needs Review
10. All parser-job and import-job polling state is deleted from `_PhotoCaptureScreenState` — the screen no longer owns any polling (handed off to 13.14's provider)
11. After submit + pop-back, the user can immediately start another import — no global lock

### Technical Approach

- Add `createParserBatch`, `getParserBatch`, `listParserBatches` to `api_client.dart`
- Major rewrite of `photo_capture_screen.dart` around a `_Phase { picking, grouping, submitting }` state enum
- Per-image upload state tracked on `_SelectedImage` with background upload kicked off on add
- Grouping state = `Map<int imageIndex, int groupIndex>` with compaction helper
- Scope: photo capture screen only; no changes to other import screens

---

## Story 13.14: Live Import Progress Controller & Strip

As a user,
I want to see my active imports ticking live at the top of the Add Recipe sheet,
so that I can start multiple imports in quick succession and watch each one progress without navigating away — plus peek at extracted OCR text for debugging.

### Acceptance Criteria

1. New Riverpod provider `importBatchesProvider` polls `GET /v1/parser/batches?active=true` on a **5s** interval while any batch is active, **30s** when idle
2. Provider survives navigation — polling does not die when the photo capture screen is popped
3. Provider exposes `refresh()` + `markJustStarted(batchId)` — photo capture screen calls both after a successful submit so the new batch appears in the strip within one frame
4. Polling pauses on `AppLifecycleState.paused`, resumes on `resumed`
5. Recently-completed batches linger in the strip for **5 minutes** after `completed_at` before auto-dismissing
6. New `ImportBatchesStrip` widget embedded at the top of `add_recipe_sheet.dart`, **above** the import-type buttons
7. Strip renders **nothing** when there are zero active or recently-completed batches
8. Each row shows: source-type icon + progress pill + status label + disclosure chevron
9. Status labels map to batch state: "Reading text X/Y", "Structuring recipe", "Ready to review", "N of M recipes ready" (partial), "Failed"
10. Row expansion reveals per-parser-job debug info: input filename, status, and a "Show extracted text" toggle that displays `extractedText` in a monospaced scrollable container — **the "click more to see text" debug affordance**
11. Just-started batches pulse/highlight for ~3 seconds then settle
12. Tapping a `succeeded` / `awaiting_review` row navigates to `ImportReviewListScreen` for the most recent such import job
13. Strip does NOT duplicate the Needs Review section from `activity_screen.dart` — Needs Review picks up batches automatically once their import jobs flip to `awaiting_review` (already wired via 13.9 / 13.10)

### Technical Approach

- New provider: `app/lib/features/recipes/add_recipe/state/import_batches_provider.dart`
- New models: `app/lib/features/recipes/add_recipe/models/import_batch.dart`
- New widget: `app/lib/features/recipes/add_recipe/widgets/import_batches_strip.dart`
- Embed via `Consumer` in `add_recipe_sheet.dart`
- Convert `PhotoCaptureScreen` to `ConsumerStatefulWidget` if not already (to call `markJustStarted` on submit)
