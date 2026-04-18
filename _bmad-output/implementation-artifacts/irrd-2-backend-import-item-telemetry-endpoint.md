# Story irrd-2: Backend — `GET /v1/import-items/{id}/telemetry` + stage logging

**Status:** in-progress
**Epic:** epic-import-row-rich-detail

## Goal

Ship a compact telemetry endpoint + a single sanctioned way to write
stage-transition audit rows, so the Flutter caret expansion (irrd-4/-5)
can render a 4-stage timeline + raw-text previews in one round trip.

The epic assumed `error_logs.import_item_id` already existed — it does
not. This story adds the column (+ `stage`) alongside the partial index
and routes every import-task stage log through the new helper.

## Scope

### Schema

- `error_logs` gains `import_item_id UUID NULL` and `stage VARCHAR(32)
  NULL` columns. Both nullable — the existing error rows (API errors,
  UnitAliasMiss audits, etc.) don't have an item id or a stage.
- Partial index `ix_error_logs_import_item_created` on
  `(import_item_id, created_at DESC) WHERE import_item_id IS NOT NULL`.
  Created `CONCURRENTLY` inside an `autocommit_block()` so the prod
  deploy doesn't take a long lock on the (growing) error_logs table.
  Mirrors the `20260418030000_add_archive_partial_indexes.py` pattern.

### Helper

- `libraries/utils/utils/logging/stage_logging.py` ·
  `log_stage_transition(*, import_item_id, stage, status,
  error_message=None, raw_output_preview=None, metadata=None)`. Mirrors
  the `unit_logging.log_unit_alias_miss` pattern (own short-lived
  `Database()` so the caller's transaction can roll back without losing
  the audit row; never raises).
- Writes one `error_logs` row with `error_type="StageTransition"`,
  `service="audit"`, `import_item_id`, `stage`. Metadata (including
  `status`, optional `raw_output_preview`, optional caller-provided
  kwargs) lives in the `stack_trace` column as JSON. Preview capped at
  4096 chars defensively at the helper level too, not just the read
  path.

### Stage log calls

- `parse_source_task._dispatch_extraction_tasks` — per item, emits a
  `("parsed", "ok")` log after stamping `last_successful_stage`.
- `extract_recipe_task._extract_single_item` — `("extracted",
  "started")` on entry, `("extracted", "ok")` on the happy path,
  `("extracted", "failed")` on exception.
- `match_ingredients_task.execute` — `("matched", "started")` on
  entry, `("matched", "ok")` on the happy path, `("matched", "failed")`
  on exception.
- `create_recipe_task.execute` — `("created", "started")` on entry,
  `("created", "ok")` on the happy path, `("created", "failed")` on
  exception.

### AST-lint enforcement

- `libraries/utils/test/test_stage_transition_enforcement.py` walks
  `libraries/utils/utils/tasks/import_tasks/` and
  `libraries/utils/utils/tasks/parser_tasks/`, fails CI if any module
  other than `stage_logging.py` emits the literal
  `"StageTransition"` string. Mirrors
  `test_unit_alias_miss_enforcement.py`.

### Endpoint

- `services/api/src/api/v1/import_job/get_import_item_telemetry.py` ·
  `GetImportItemTelemetry(Endpoint)`.
  - Route: `GET /v1/import-items/{item_id}/telemetry`.
  - Loads item + job; 404 if missing, 403 if caller doesn't own the
    job (either directly or via `RecipeBookUser` membership — mirrors
    `GetImportItem`).
  - Queries `error_logs` filtered by `import_item_id` + `stage IN
    ("parsed", "extracted", "matched", "created")`, ordered by
    `created_at`. Legacy rows without a stage tag are filtered out
    naturally by the `stage` predicate.
  - Groups rows per stage; derives `started_at` (first "started" row),
    `completed_at` (latest "ok"/"failed"/"skipped" row), `duration_ms`
    (delta, or null if either side missing), `status` (terminal status
    if any, else "started" → "pending" in output vocabulary, else
    "pending").
  - Synthesizes previews:
    - `parsed`: `item.raw_data.get("text")` if present (photo OCR path)
      joined by `\n---\n` across a list — truncated to 4096.
    - `extracted`: `json.dumps(item.parsed_recipe, indent=2,
      default=str, sort_keys=True)[:4096]`, only when the item has
      reached the extracted stage.
    - `matched` / `created`: null.
  - Each entry emits a `truncated: bool` flag.
  - Unreached stages → `status: "pending"`, all timestamps null,
    preview null.

### Router wiring

- `services/api/src/api/v1/import_job/__init__.py` exports the new
  endpoint. `services/api/src/routers/v1/import_router.py` mounts the
  GET route.

## Acceptance criteria

1. Alembic migration adds the two columns + partial index
   `CONCURRENTLY`. Verified via `alembic upgrade head && alembic check`.
2. `log_stage_transition` helper exists + is exported. Existing call
   sites in import tasks route through it.
2a. AST-lint test fails if any non-helper module emits
    `"StageTransition"` as a literal.
2b. Per the handoff gotcha: no bare `log_stage_transition` call
    existed before this story — the migration is effectively
    "create the helper and route new calls through it", not
    "re-route existing calls".
3. Endpoint returns a 4-entry stage array matching the spec shape.
4. Authorization: 403 if caller doesn't own the item; 404 if item
   doesn't exist.
5. Empty-telemetry: brand-new item returns 4 entries, all
   `status: "pending"`, all timestamps null, previews null. No 500.
6. Truncation: oversized preview caps at 4096 and emits
   `truncated: true`. Under-cap preview emits `truncated: false`.
7. Legacy: `error_logs` rows without a `stage` tag don't break the
   endpoint (filtered out by the `stage IS NOT NULL` predicate).
8. Migration reversible — round-trip verified on test DB.
9. P95 < 300ms at 10k error_log rows — captured as a fixture + timing
   assertion in the integration test.

### Out of scope (per handoff)

- `manual` `awaiting_review_reason` write path — not in scope;
  follow-up story when an admin-route endpoint lands.
- `list_import_jobs` eager loading — vacuously satisfied upstream.

## File list

### Created

- `services/migrator/migrations/versions/20260418060000_add_error_logs_import_item_telemetry.py`
- `libraries/utils/utils/logging/stage_logging.py`
- `libraries/utils/test/test_stage_transition_enforcement.py`
- `services/api/src/api/v1/import_job/get_import_item_telemetry.py`
- `services/api/tests/test_import_telemetry.py`
- `_bmad-output/implementation-artifacts/irrd-2-qa-walkthrough.md`

### Modified

- `libraries/utils/utils/models/error_log.py`
- `libraries/utils/utils/logging/__init__.py`
- `libraries/utils/utils/tasks/import_tasks/parse_source_task.py`
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`
- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py`
- `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`
- `services/api/src/api/v1/import_job/__init__.py`
- `services/api/src/routers/v1/import_router.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
