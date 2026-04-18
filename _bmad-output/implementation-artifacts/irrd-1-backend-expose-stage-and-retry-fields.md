# Story irrd-1: Backend — expose stage + retry fields + awaiting_review_reason

**Status:** done
**Epic:** epic-import-row-rich-detail

## Goal

Surface three fields the Flutter caret expansion (irrd-4/-5/-6) will need on
every import-item list + detail payload, so the client can render a stage
timeline + retry history + 1-word reason chip without a second fetch:

1. `last_successful_stage` — already on the model, never exposed.
2. `last_retry_at` — new column, stamped by the retry endpoint on dispatch.
3. `awaiting_review_reason` — new column with a CHECK-constrained value set,
   set by `match_ingredients_task` at the moment of the status transition,
   cleared by the retry endpoint.

## What shipped

- **Migration `20260418050000_add_last_retry_at_and_awaiting_review_reason`**
  (rev `irrd1fields0`). Adds two nullable columns to `import_items` plus a
  CHECK constraint binding `awaiting_review_reason` to the four-value set
  `{low_confidence, unmatched_ingredients, missing_title, manual}`. Reversible
  — verified by applying `alembic downgrade -1 && alembic upgrade head` on
  a clean test DB. `alembic check` reports no drift after the upgrade.

- **`ImportItem` model** (`libraries/utils/utils/models/import_item.py`)
  gains `last_retry_at: datetime | None` and `awaiting_review_reason:
  str | None`.

- **`retry_import_item.py`** stamps `item.last_retry_at = func.now()` and
  clears `item.awaiting_review_reason = None` atomically with the existing
  retry-count increment. Covered by a new test
  (`test_retry_stamps_last_retry_at_and_clears_awaiting_review_reason`).

- **`match_ingredients_task.py`** sets `awaiting_review_reason` at the same
  branch where `item.status = "awaiting_review"` is set. Priority:
  `missing_title` > `unmatched_ingredients` > `low_confidence`. On the
  approved branch, the reason is explicitly cleared to `None` so a stale
  value from a prior retry doesn't leak through.

- **`GetImportItem.Response`**, **`ListImportItems.ItemSummary`** add
  `last_successful_stage: str | None`, `last_retry_at: datetime | None`,
  `awaiting_review_reason: str | None`. `list_import_jobs.py` was audited —
  it does NOT eager-load items today, so there is nothing to widen there
  (AC6 vacuously satisfied).

- **`import_activity_detail.dart` audit comment** updated: the three fields
  move from `MISSING-needs-backend` to `rendered` (with back-references to
  the stories that will render them). `confidence_score` /
  `confidence_source` remain `MISSING-needs-backend` — irrd-3 will land them.

## Acceptance criteria — status

1. Migration adds `last_retry_at TIMESTAMPTZ NULL` — **done**
2. `ImportItem` model gains the field with default null — **done**
3. `retry_import_item.py` sets `last_retry_at = func.now()` — **done**, test added
4. `GetImportItem` response adds all three fields — **done**, test added
5. `list_import_items` item summaries include all three fields — **done**
6. `list_import_jobs` per-item summaries expose all three — **vacuously
   done**; the endpoint does not eager-load items. When/if a future story
   adds eager loading, this AC will need to be re-checked.
7. `match_ingredients_task.py` and `extract_recipe_task.py` audited for
   routing-reason persistence — **done**; routing lives entirely in
   `match_ingredients_task.py` and the reason is set there. `extract_recipe_task`
   was audited and left alone — it transitions items to `matching`, not
   `awaiting_review`. `missing_title` is detected in the match task (the
   single routing funnel) rather than intercepting at extract, which would
   have required also changing the downstream dispatch condition.
8. Field audit in `import_activity_detail.dart` comment block updated — **done**
9. Migration is reversible; up+down verified via alembic on test DB — **done**
10. Integration test: retry populates `last_retry_at` within 1s — **done**
    (`test_retry_stamps_last_retry_at_and_clears_awaiting_review_reason`).
11. Route item into `awaiting_review` via each rule path — **done, 3 of 4**.
    Covered in `libraries/utils/test/test_awaiting_review_reason.py`:
    - `test_low_confidence_match_sets_low_confidence_reason`
    - `test_unmatched_ingredient_sets_unmatched_reason`
    - `test_missing_title_beats_match_issues` +
      `test_missing_title_wins_over_unmatched`
    - **Deferred:** `manual` path — no code path today sets this value; the
      schema supports it and the CHECK allows it so a future admin-route
      endpoint can populate it, but there is nothing to test yet. Flagged
      on epic-review as a follow-up.

## File list

### Created

- `services/migrator/migrations/versions/20260418050000_add_last_retry_at_and_awaiting_review_reason.py`
- `libraries/utils/test/test_awaiting_review_reason.py`

### Modified

- `libraries/utils/utils/models/import_item.py`
- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py`
- `services/api/src/api/v1/import_job/get_import_item.py`
- `services/api/src/api/v1/import_job/list_import_items.py`
- `services/api/src/api/v1/import_job/retry_import_item.py`
- `services/api/tests/conftest.py` — `MockImportItem` gains `last_retry_at`
  + `awaiting_review_reason` defaults
- `services/api/tests/test_import.py` — new retry + GetImportItem asserts
- `app/lib/features/activity/widgets/import_activity_detail.dart` — audit
  comment block refreshed

## Local CI

- `npx nx run api:lint` — **pass**
- `npx nx run utils:lint` — **pass**
- `npx nx run migrator:lint` — **pass**
- `npx nx run api:test` — **1687 passed** (coverage 100%)
- `poetry run pytest libraries/utils/test/test_awaiting_review_reason.py libraries/utils/test/test_stage_markers.py` — **10 passed**
- `alembic upgrade head && alembic check` — no drift
- `alembic downgrade -1 && alembic upgrade head` — clean round-trip
