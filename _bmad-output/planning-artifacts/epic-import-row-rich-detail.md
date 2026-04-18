<!-- refined via party-mode 2026-04-18 -->
# Epic: Import Row Rich Detail — Caret Expansion, Stage Telemetry, Confidence Score

## Overview

The Activity Hub redesign (epic-activity-hub-redesign) shipped the two-tab shell, color-coded Imports sections, and a collapsed `ImportRow` widget with a reserved slot for a caret. This epic fills that caret in with the **"information-heavy but readable"** per-row detail view Leo explicitly asked for — the one he used to love on the old Add Recipe "In Progress" list (type + stage + raw parser output + confidence).

Each row, when expanded, reveals a stage timeline (parsed / extracted / matched / created, each with ✓ / ⏳ / ✗), raw parser text preview (OCR output for photo imports, extractor output for all), confidence score (prominent on yellow Needs Review rows, lower-key elsewhere), retry history, error detail, and source reference. All of this is derived from an existing telemetry stream (`error_logs` table, filtered per import item) plus a new `confidence_score` field produced by the extractors themselves.

**Three cross-layer concerns roll up into this epic** because they share a single end-user output (the caret expansion content):
1. Surface backend fields that exist but aren't exposed (`last_successful_stage`, `last_retry_at` — the backlogged `bugs-act-2a` work).
2. Produce + expose + render a **confidence score** end-to-end (extractor → API → UI).
3. Build the Flutter caret-expansion UI that pulls it all together.

## Goal

Leo taps a caret on any import row in the Imports tab and the row expands in-place to reveal: the stage it's at, every stage that came before, the OCR or extracted text the backend is currently looking at, a confidence score (prominent when yellow), retry history if any, and the error detail if failed. He stays on the Imports tab the whole time — no navigation required for the normal triage case. Tapping the caret again collapses. Expansion state is remembered for the session so he can scroll away and come back.

## End-User Flow

1. Leo opens `/activity?tab=imports`. Sees the four color-coded sections from the prior epic.
2. Spots a yellow (Needs Review) row: "Mom's Chocolate Cake · 62%". Taps the caret (or anywhere on the row chrome).
3. Row expands inline. Above the fold: stage timeline reads "Parsed ✓ · Extracted ✓ · Matched ⏳ · Created —" with the matched-ingredients count underneath ("7 of 9 ingredients matched confidently"). Confidence score "62%" rendered as a sizable badge with a warning glyph (< 0.8 threshold). Source reference shows a photo thumbnail with "View original" link.
4. Leo taps **Show extracted text** inside the expansion — reveals the raw parser text (e.g., "1 cup flour\n2 eggs\n..."). Monospaced, scrollable, 2KB-truncated with "Copy" button.
5. Confident he understands what the extractor saw, Leo taps **Review →** on the row → opens the existing per-item review flow (unchanged from today).
6. Back on the Imports tab, he sees a red (Failed) row "Garlic Bread · failed at Matching". Taps the caret → expanded view shows error: "Could not match ingredient: '1 clove garilc' (sic)". Stage timeline: "Parsed ✓ · Extracted ✓ · Matched ✗". Retry count: 0. Leo taps **Retry** on the row → fires the existing retry endpoint; row moves back to In Progress.
7. Bottom of the list, a blue (In Progress) row ticks in real time: stage label updates every 30s poll. Leo opens its caret — sees "Parsed ✓ · Extracted ⏳ · Matched — · Created —" with the raw parser text already populated (OCR succeeded, extractor running). This is the info-density he missed.
8. Leo collapses all rows, backgrounds the app, returns 10min later — each row that had been expanded is still expanded (session-remembered state).

## Frontend Changes

**Required — medium.**

- **New `ImportRowCaret` widget.** Slots into the `trailing` space reserved by `ImportRow` in the prior epic. Renders a downward chevron by default, rotates on expand. Handles tap to toggle.
- **New `ImportRowExpansion` widget.** Rendered below the collapsed row when expanded. Layout:
  - **Stage timeline** (horizontal strip of 4 chips: Parsed, Extracted, Matched, Created — each shows ✓ if completed, ⏳ if current, ✗ if failed at that stage, — if not reached). Derived from `last_successful_stage` + `status`.
  - **Confidence badge** (only if `confidence_score` is present on parsed_recipe). Low (<0.5) = warning glyph + "Low". Medium (0.5–0.8) = numeric percentage. High (>0.8) = checkmark + percentage. On yellow rows, rendered as a prominent inline badge next to the recipe name in the collapsed row *and* in the expansion. On other states, only in the expansion, smaller.
  - **Raw parser text collapsible** — inside the expansion, a "Show extracted text" toggle reveals a monospaced scrollable container with the raw text. Source depends on stage: OCR output (from parser batch's `extracted_text`) for parser-stage, extracted-recipe JSON (from `parsed_recipe`) for extractor-stage. Both are shown when available; labeled clearly.
  - **Retry history** — "Retried 2 times · last at 3m ago" (pulled from `retry_count` + `last_retry_at`). Empty if never retried.
  - **Error detail** — only if `status = failed`. Reuses the existing `ImportActivityDetail` widget's error-block rendering (`Show more` disclosure for long errors).
  - **Source reference** — thumbnail + reference. URL opens in browser, photo opens in image viewer, text expands inline. Reuses existing `ImportActivityDetail` source-row logic.
  - **Action buttons** — inline at the bottom of the expansion: **Review →** (yellow rows), **Retry** (red rows), **View Recipe** (green rows). Blue (In Progress) rows have no action buttons — cancel stays out-of-scope per the PRD 2026-04-18 addendum ("Cancel-in-progress from the row" explicitly deferred).
- **`ImportRowExpansionState` provider.** A `StateProvider<Set<String>>` keyed on import-item-id that holds the expanded-state set. Session-scoped (discarded on cold start). Each `ImportRow` reads from + writes to it.
- **Telemetry fetch.** Lazily fetch `GET /v1/import-items/{id}/telemetry` on first expansion; cache per-session. Subsequent expansions render from cache. If the underlying import-item is actively polling and its stage advances, invalidate the cache so re-expansion reflects reality (or, simpler: re-fetch on every expand — the endpoint is cheap per NFR55).
- **Sticky expansion across state transitions.** If a blue row's import-item transitions to yellow mid-session and the user had the row expanded, the expansion persists across the state transition — the row just moves into the Needs Review section with its expansion still open.
- **Confidence badge on collapsed row (yellow only).** As per FR141, yellow rows surface the confidence score in the collapsed row itself (not just in the expansion). Colored by threshold: red glyph for <0.5, yellow numeric for 0.5–0.8, green check for >0.8.
- **Accessibility.** Caret has a semantic label ("Show details for Mom's Chocolate Cake"). Expansion is announced to screen readers on toggle. Stage timeline uses semantic labels not just color.

## Backend Changes

**Required — medium.** Cross-layer work here is the extractor changes + telemetry endpoint + field exposure.

### Expose missing fields (the backlogged `bugs-act-2a` work)

- **`GetImportItem` response** gains `last_successful_stage: str | null` (already stored on model, never serialized — single-line schema addition) and `last_retry_at: datetime | null` (new column).
- **Migration** adds `last_retry_at TIMESTAMPTZ NULL` column to `import_items`. `retry_import_item.py` updates to set this timestamp when dispatching retry task.
- **Index** on `error_logs(import_item_id, created_at)` to support NFR55 (telemetry endpoint P95 < 300ms).

### New telemetry endpoint

- **`GET /v1/import-items/{id}/telemetry`.** Returns a stage log as an array of:
  ```json
  { "stage": "parsed" | "extracted" | "matched" | "created",
    "status": "pending" | "ok" | "failed" | "skipped",
    "started_at": "2026-04-18T14:02:31Z" | null,
    "completed_at": "2026-04-18T14:02:34Z" | null,
    "duration_ms": 3000 | null,
    "raw_output_preview": "1 cup flour\n2 eggs\n..." | null }
  ```
- **Derivation:** the endpoint queries `error_logs` filtered by `import_item_id = ?`, groups by a new `stage` tag (added to the log payload by existing stage-transition log calls in the import tasks), and emits the timeline. For stages that don't have a log entry yet, `status = pending` with nulls. `raw_output_preview` pulls from:
  - Parser stage: `parser_batch.jobs[*].extracted_text` (truncated to 2KB), joined by newline if multi-group.
  - Extractor stage: `import_item.parsed_recipe` serialized as pretty JSON (truncated to 2KB).
  - Matched / Created stages: null (no human-readable raw output).
- **Authorization:** user must own the import-item.
- **Contract is additive** — does not replace `GetImportItem`, which stays the primary detail endpoint.

### Confidence score — end-to-end

- **Extractors** (`ai_extractor.py`, `vision_extractor.py`, `text_extractor.py`, `json_ld_extractor.py`) produce a top-level `confidence_score: float` (0.0–1.0) in their output JSON. For LLM-based extractors, the prompt instructs the model to emit a self-reported confidence between 0 and 1. For deterministic extractors (json_ld), confidence = 1.0 if all required fields present, else degraded proportionally.
- **Heuristic fallback.** If the LLM output is missing the field or the value is non-numeric / out-of-range, extractor post-processing computes a heuristic: `0.4 * min(ingredient_matched_rate, 1.0) + 0.3 * (1.0 if title else 0.0) + 0.3 * min(step_count / 3.0, 1.0)`. Result annotated `confidence_source: "heuristic" | "model"` on `parsed_recipe`.
- **Persistence.** `confidence_score` lives inside `parsed_recipe` JSONB (no new column). `GetImportItem` surfaces it at the response root as a convenience field so the Flutter caret doesn't have to drill into nested JSON.
- **List endpoints.** `GET /v1/import-jobs` item summaries and `GET /v1/import-items/{job_id}` include `confidence_score` in each item so the Imports tab collapsed rows render without a second fetch.

## Infrastructure Changes

**None.**

- One Alembic migration for `last_retry_at` column + `error_logs(import_item_id, created_at)` index. No new AWS resources, no env vars, no IAM changes.
- Extractor prompt changes are code-only.

## Design Principles (refined via party-mode 2026-04-18)

1. **Caret expansion replaces the detail-screen tap for common triage.** Users who want the full `ImportActivityDetail` still tap through — but 80% of "what's going on?" questions answer inline.
2. **Preserve the at-a-glance scan for Leo's old workflow.** Collapsed blue rows render a **compact 3-dot stage pill** (current stage pulsing); collapsed yellow rows render a **1-word reason chip** ("low confidence" / "unmatched ingredients" / "missing title") alongside the confidence badge. Full 4-chip stage timeline stays expansion-only.
3. **Stage timeline is derived, not stored.** Already-existing `error_logs` + `last_successful_stage` are the sources of truth. No new `stage_history` table. Stage logging routes through a single `log_stage_transition` helper enforced by an AST-lint test.
4. **Confidence is end-to-end or it's nothing.** A placeholder "Low / Med / High" bucketed from heuristics-only would undermine trust. Build the real thing now.
5. **`confidence_score = null` vs `0.0` are different signals.** Null = "model declined to self-assess" → heuristic fallback fires; 0.0 = "legitimate low score" → persist as-is. Schema is `float | None`.
6. **Heuristic weights are calibrated against eval fixtures, not arbitrary.** Pre-merge, verify mean absolute error vs ground-truth F1 is ≤ 0.3; retune weights if not.
7. **Feature-flag extractor prompt changes.** `EXTRACTOR_EMIT_CONFIDENCE` env var defaults true but is flippable via ECS task def without redeploy, in case the new prompt regresses eval scores.
8. **Session-scoped expansion memory, per-row isolation.** Use a `StateNotifierProvider` with per-id `select` so expanding one row doesn't rebuild every other row in the list.
9. **Raw output preview is 4KB-capped** (bumped from 2KB to cover typical multi-page OCR). Response always carries a `truncated: bool` flag. Full-text via presigned S3 URL is a follow-up.
10. **Partial index on `error_logs`** — `WHERE import_item_id IS NOT NULL` — keeps the index small since most error rows don't have an item_id. Created `CONCURRENTLY` outside a transaction.
11. **Expanded row max height = 60% of viewport**, with internal scroll when content exceeds. Prevents the "I can't see the collapse button" trap.
12. **Blue row trailing slot reconciliation.** `Stack(CircularProgressIndicator, IconButton(chevron))` — the ring is `IgnorePointer` (read-only visual), the chevron is tappable (interactive). Resolves the ahr-4 "blue is visually read-only" rule with the irrd-4 "all rows have caret" rule.
13. **Reuse existing detail components inside the expansion.** `ImportActivityDetail` built in bugs-act-2 is the error + source + timestamp scaffold. Caret-expansion rehomes it.

## File Structure (anticipated)

```
app/lib/features/activity/widgets/
├── import_row.dart                           # MODIFIED — mount caret + expansion slot
├── import_row_caret.dart                     # NEW — chevron toggle widget
├── import_row_expansion.dart                 # NEW — expanded-row layout
├── stage_timeline.dart                       # NEW — 4-chip stage strip
├── confidence_badge.dart                     # NEW — low/med/high with glyph
├── raw_text_preview.dart                     # NEW — monospaced scrollable collapsible
└── import_activity_detail.dart               # MODIFIED — expose its sub-blocks for reuse inside expansion

app/lib/features/activity/providers/
└── import_row_expansion_provider.dart        # NEW — session-scoped Set<String>

app/lib/features/activity/models/
└── import_item_telemetry.dart                # NEW — stage log model

app/lib/core/api_client/
└── api_client.dart                           # MODIFIED — getImportItemTelemetry method

services/api/src/api/v1/import_job/
├── get_import_item.py                        # MODIFIED — expose last_successful_stage, last_retry_at, confidence_score
├── list_import_items.py                      # MODIFIED — include confidence_score per item
├── list_import_jobs.py                       # MODIFIED — include confidence_score in item summaries
├── get_import_item_telemetry.py              # NEW — GET /v1/import-items/{id}/telemetry
└── retry_import_item.py                      # MODIFIED — set last_retry_at on retry dispatch

libraries/utils/utils/models/
└── import_item.py                            # MODIFIED — add last_retry_at column

libraries/utils/utils/services/recipe_extractors/
├── ai_extractor.py                           # MODIFIED — prompt emits confidence_score
├── vision_extractor.py                       # MODIFIED — prompt emits confidence_score
├── text_extractor.py                         # MODIFIED — prompt emits confidence_score
├── json_ld_extractor.py                      # MODIFIED — deterministic confidence
└── confidence_heuristic.py                   # NEW — fallback computation

libraries/utils/utils/tasks/import_tasks/
└── extract_recipe_task.py                    # MODIFIED — persist confidence, apply heuristic if needed, emit stage log with stage tag

services/migrator/migrations/versions/
└── XXXX_add_last_retry_at_and_error_log_index.py   # NEW migration
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| irrd-1 | Backend: expose `last_successful_stage` + `last_retry_at` on GetImportItem + `last_retry_at` column migration + retry task updates | 🔴 P0 | 0.5 d | epic-activity-hub-redesign (rows exist) |
| irrd-2 | Backend: `GET /v1/import-items/{id}/telemetry` endpoint + `error_logs` index + stage tagging in existing import tasks | 🔴 P0 | 1 d | irrd-1 |
| irrd-3 | Backend: extractor confidence_score (prompt changes + heuristic fallback + persistence + API exposure on three endpoints) | 🔴 P0 | 1.5 d | None (parallel with irrd-1/2) |
| irrd-4 | Flutter: `ImportRowCaret` + `ImportRowExpansion` + expansion state provider + lazy telemetry fetch | 🔴 P0 | 1.5 d | irrd-1, irrd-2 |
| irrd-5 | Flutter: `StageTimeline`, `ConfidenceBadge`, `RawTextPreview` sub-widgets | 🔴 P0 | 1 d | irrd-4 |
| irrd-6 | Flutter: confidence badge on collapsed yellow rows + wire action buttons (Review / Retry / View Recipe) into expansion | 🟡 P1 | 0.5 d | irrd-3, irrd-5 |
| irrd-7 | Accessibility + semantics + widget tests across expansion components | 🟡 P1 | 0.5 d | irrd-5, irrd-6 |

**Total estimated effort: 6.5 days**

**Parallel tracks:**
- Track A (backend fields): irrd-1 → irrd-2
- Track B (confidence): irrd-3 (parallel with A)
- Track C (frontend): irrd-4 → irrd-5 → irrd-6 → irrd-7 (serial, blocked on A + B)

---

## Story irrd-1: Backend — expose stage + retry fields, add `last_retry_at` column

As the Imports backend,
I want to expose `last_successful_stage` and `last_retry_at` on the import-item detail + list responses, so the frontend can render a stage timeline without a second fetch.

### Acceptance Criteria

1. Migration adds `last_retry_at TIMESTAMPTZ NULL` to `import_items`. Historical retried rows (`retry_count > 0`) keep `last_retry_at = NULL` — the field is best-effort forward-looking; down-migration drops cleanly.
2. `ImportItem` model gains the field with default null.
3. `retry_import_item.py` sets `item.last_retry_at = func.now()` before dispatching the retry task (atomic with the existing retry-count increment).
4. `GetImportItem` response schema adds `last_successful_stage: str | null`, `last_retry_at: datetime | null`, **and `awaiting_review_reason: Literal["low_confidence","unmatched_ingredients","missing_title","manual"] | null`** — derived server-side from the routing logic that flipped the item into `awaiting_review` (or null if not in that state).
5. `list_import_items` item summaries include all three fields.
6. `list_import_jobs` per-item summaries (when eager-loading items) also expose all three.
7. `match_ingredients_task.py` and `extract_recipe_task.py` are audited to ensure the routing-reason is persisted (e.g., on `import_item.raw_data['awaiting_review_reason']` or a new column — pick the cheaper option; workshop recommendation is a column for query simplicity).
8. Field audit in `import_activity_detail.dart`'s existing comment block is updated: `last_successful_stage`, `last_retry_at`, and `awaiting_review_reason` move from "MISSING-needs-backend" to "rendered".
9. Migration is reversible; tests for up + down migration.
10. Integration test: create item → retry via endpoint → assert `last_retry_at` populated within 1s of call.
11. Integration test: route an item into `awaiting_review` via each rule path (low confidence, unmatched ingredients, missing title, manual) — assert `awaiting_review_reason` reflects the path.

### Key Files

- Create: `services/migrator/migrations/versions/XXXX_add_last_retry_at_to_import_items.py`
- Modify: `libraries/utils/utils/models/import_item.py`
- Modify: `services/api/src/api/v1/import_job/get_import_item.py`, `list_import_items.py`, `list_import_jobs.py`, `retry_import_item.py`
- Modify: `app/lib/features/activity/widgets/import_activity_detail.dart` (comment audit update)
- Tests: `services/api/tests/api/v1/import_job/retry_import_item_test.py`

---

## Story irrd-2: Backend — `GET /v1/import-items/{id}/telemetry` + error_logs indexing

As the Imports backend,
I want a compact telemetry endpoint that returns a per-stage log for one import item, so the Flutter caret expansion can render a stage timeline + raw text preview in one round trip.

### Acceptance Criteria

1. Alembic migration adds **partial index** `ix_error_logs_import_item_created` on `error_logs(import_item_id, created_at)` `WHERE import_item_id IS NOT NULL`. Created `CONCURRENTLY` outside transaction (per ahr-1 pattern). Verifies query plan uses the index via explicit `EXPLAIN ANALYZE` captured in story notes.
2. **New helper `log_stage_transition(item_id, stage, status, **kwargs)`** in `libraries/utils/utils/logging/stage_logging.py`. Every import-task + parser-task stage log call routes through it — it's the only way to log a stage transition.
2a. **AST-lint enforcement test** in `libraries/utils/tests/logging/test_stage_tag_enforcement.py` scans all `.py` files under `libraries/utils/utils/tasks/import_tasks/` and `libraries/utils/utils/tasks/parser_tasks/` and asserts that no bare `log_error(...)` call happens without a `stage=` kwarg or without being routed through `log_stage_transition`. This test fails CI if a future PR adds a bare log call.
2b. Existing log calls in `extract_recipe_task.py`, `match_ingredients_task.py`, `create_recipe_task.py`, and the parser watch tasks are migrated to the new helper.
3. New endpoint `GET /v1/import-items/{item_id}/telemetry` returns:
    - Array of 4 stage entries: `parsed`, `extracted`, `matched`, `created`.
    - Each entry populated from the latest matching `error_logs` row for that stage (or synthesized from `parser_batch` data for the `parsed` stage when the item came from a parser batch).
    - `raw_output_preview` for `parsed` = parser_batch `extracted_text` joined by `\n---\n` across groups, truncated to **4096 chars**.
    - `raw_output_preview` for `extracted` = `parsed_recipe` pretty-JSON dump, truncated to **4096 chars**.
    - Response carries a per-entry `truncated: bool` flag.
    - `matched` / `created` get null previews.
    - Missing stages (not yet reached) emit `status: "pending"`, all timestamps null.
4. Authorization: 403 if caller doesn't own the item.
5. Response P95 < 300ms on a dataset of 10k error_log rows (verified via test fixture).
6. Integration test: seed import item with 2 stages of logs; call endpoint; assert shape matches spec; assert truncation caps preview at 4096 AND sets `truncated: true`.
7. **Empty-telemetry test:** brand-new item with no logs yet — endpoint returns 200 with 4 stages all `status: "pending"`, all timestamps null, previews null. No 500, no empty-array edge case.
8. **Cache-invalidation test** (paired with irrd-4): seed an item in `extracting` → fetch telemetry → advance item to `awaiting_review` → fetch again → assert new stage data returned (not cached / stale).
9. Legacy: existing `error_logs` rows without a `stage` tag don't break the endpoint — they're filtered out of telemetry (but still retrievable via admin error logs).

### Key Files

- Create: `services/migrator/migrations/versions/XXXX_add_error_logs_import_item_index.py`
- Create: `services/api/src/api/v1/import_job/get_import_item_telemetry.py`
- Modify: import-task stage log calls (audit across `libraries/utils/utils/tasks/import_tasks/`, `libraries/utils/utils/tasks/parser_tasks/`)
- Wire endpoint into import router.
- Tests: `services/api/tests/api/v1/import_job/get_import_item_telemetry_test.py`

---

## Story irrd-3: Backend — confidence score end-to-end (extractors → persistence → API)

As the extraction pipeline,
I want every extractor to emit a confidence score (either from the LLM or from a heuristic fallback) and persist it on `parsed_recipe`, so the frontend can render a meaningful confidence badge on every import row.

### Acceptance Criteria

1. Standard extraction schema (`libraries/utils/utils/schemas/recipe_extraction_schema.py`) adds **`confidence_score: float | None`** (nullable; 0.0–1.0 when set) and `confidence_source: Literal["model", "heuristic"]` as required top-level fields. `null` and `0.0` are semantically distinct: `null` = "model declined to self-assess", `0.0` = "model scored this as a total miss".
2. `ai_extractor.py`, `vision_extractor.py`, `text_extractor.py` prompts are updated to instruct the model: *"After the recipe, emit `confidence_score` as a float in [0.0, 1.0] representing how confident you are in the full extraction. Emit `null` if you cannot self-assess; emit `0.0` if the extraction failed meaningfully. Emit `confidence_source: 'model'` alongside."*
3. Post-processing in each extractor:
    - If LLM emitted a numeric `confidence_score` in [0, 1] (including 0.0), use as-is with `confidence_source: 'model'`.
    - If LLM emitted `null` OR malformed (non-numeric, out-of-range), run heuristic and apply `confidence_source: 'heuristic'`.
    - Heuristic formula (initial weights, subject to calibration in AC9): `0.4 * min(ingredient_matched_rate, 1.0) + 0.3 * (1.0 if title else 0.0) + 0.3 * min(step_count / 3.0, 1.0)`.
    - `ingredient_matched_rate` is the fraction of parsed ingredients that had `matched_ingredient_id` set after the match stage — this is a post-match heuristic, so for the extract-stage fallback, use a proxy: `sum(ing.quantity IS NOT NULL for ing in ingredients) / max(len(ingredients), 1)`.
4. `json_ld_extractor.py` (deterministic path) sets `confidence_score = 1.0` if all of {title, ingredients (≥1), instructions (≥1)} are present; else `max(0.3, (present_count / 3))`. Always `confidence_source: 'model'` (since json-ld is authoritative).
5. `extract_recipe_task.py` persists `confidence_score` + `confidence_source` as top-level keys on `import_item.parsed_recipe` JSONB.
6. `GetImportItem`, `list_import_items`, `list_import_jobs` responses surface `confidence_score` + `confidence_source` at the response root (for item objects — convenience hoist from `parsed_recipe`).
7. **Deterministic heuristic fixture test.** Unit test pins the expected heuristic output for a canonical parsed_recipe: 3 ingredients with quantity (2 of 3 matched), title present, 4 steps → expected = `0.4 * (2/3) + 0.3 * 1 + 0.3 * min(4/3, 1) = 0.267 + 0.3 + 0.3 = 0.867`. Test asserts value to 3 decimal places. **Round-trip integration test** feeds a canonical photo fixture through `parse_source_task` → `extract_recipe_task`, asserts `import_item.parsed_recipe['confidence_score']` ∈ [0, 1] and `GetImportItem` returns it at the response root.
8. **Eval suite (epic 13.5) addition — concrete.** New metric module `services/eval/metrics/confidence_calibration.py` runs against fixtures in `tests/fixtures/extractor_eval/*.json`. Formula: `mean(abs(confidence - ground_truth_f1))` across all fixtures. Baseline stored to `services/eval/baselines/confidence_calibration_baseline.json` checked into repo.
9. **Heuristic weight calibration pre-merge.** Before merging irrd-3, run the eval suite. If mean absolute error > 0.3 vs the fixture ground-truth F1s, retune heuristic weights (shift proportionally toward whichever factor correlates most) until MAE ≤ 0.3. Calibrated weights land in this PR.
10. **Feature-flag the new prompt** behind `EXTRACTOR_EMIT_CONFIDENCE` env var (default `true`, flippable via ECS task def without redeploy). When `false`, extractors skip the confidence emission instruction and always run the heuristic fallback. Acceptance test covers both flag states.
11. **Soft eval regression gate.** New prompts must not drop `title_extraction_f1` (or equivalent title-focused metric from the eval suite) by more than 5% vs the prior baseline (`services/eval/baselines/extraction_baseline.json`). If regression, block merge until prompts are retuned. Baseline is updated post-merge.

### Key Files

- Modify: `libraries/utils/utils/schemas/recipe_extraction_schema.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/ai_extractor.py`, `vision_extractor.py`, `text_extractor.py`, `json_ld_extractor.py`
- Create: `libraries/utils/utils/services/recipe_extractors/confidence_heuristic.py`
- Modify: `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`
- Modify: `services/api/src/api/v1/import_job/get_import_item.py`, `list_import_items.py`, `list_import_jobs.py`
- Tests: per-extractor unit tests; integration test round-tripping a real photo-import through the pipeline and asserting persistence.

---

## Story irrd-4: Flutter — `ImportRowCaret` + `ImportRowExpansion` + lazy telemetry fetch

As Leo,
I want to tap a caret on any import row to expand it inline and see the rich detail,
so I can triage without leaving the Imports tab.

### Acceptance Criteria

1. `ImportRow` mounts a new `ImportRowCaret` in its `trailing` slot. Caret toggles expansion via a **`StateNotifierProvider<ExpandedRowsNotifier, Set<String>>`** (`importRowExpansionProvider`). Each row watches via `ref.watch(importRowExpansionProvider.select((s) => s.contains(itemId)))` so toggling one row's state does NOT rebuild every other row in the list.
2. When expanded, `ImportRowExpansion` renders below the collapsed row inside a `SliverAnimatedSize` (or equivalent inside a `CustomScrollView`); inside a plain `ListView`, expansion is followed by `Scrollable.ensureVisible(context, alignment: 0.1)` post-animation to prevent the scroll-jump trap where expansion near viewport bottom hides the collapse button.
3. **Expanded row max height = 60% of viewport** via a `ConstrainedBox(maxHeight: MediaQuery.size.height * 0.6)`; content inside scrolls internally when it exceeds.
4. First expansion triggers a fetch of `GET /v1/import-items/{id}/telemetry` and `GET /v1/import-items/{id}` (full detail). Cached per-session in a `FutureProvider.family<TelemetryBundle, String>`.
5. **Cache invalidation is explicit via `ref.listen`:** the expansion widget listens to the item's `(status, last_successful_stage)` tuple from the list payload; when the tuple changes, it calls `ref.invalidate(telemetryProvider(itemId))`, forcing a refetch.
6. On re-expansion within the session, cached data renders immediately (no loading spinner) unless invalidated per AC5.
7. Collapse state: expansion is removed from the set; animation reverses.
8. Session-only: provider is never persisted to shared prefs; on app restart, all rows start collapsed.
9. Expansion persists across state transitions: if a blue item becomes yellow while the row is expanded, the expansion remains open as the row moves into the Needs Review section.
10. **State-transition-while-expanded animation polish:** on status change of an expanded row, freeze the row in place for 500ms with a subtle highlight flash, then animate into its new section position. Prevents the jarring "my row just teleported" effect.
11. Caret has a semantic label ("Show details for {recipeName}") that updates with expansion state ("Hide details for..."). Screen reader announces expansion state change.
12. **Blue row trailing slot reconciliation.** `Stack(children: [CircularProgressIndicator (IgnorePointer), IconButton(chevron)])` — the progress ring is read-only visual (from ahr-4 locked decision), the chevron on top is tappable. Widget exposes a `showProgressRing: bool` param; true only on blue state.
13. `ImportRowExpansion` renders skeletal placeholders for each sub-block (stage timeline, confidence badge, raw text, retry history, error detail, source, actions) with loading spinners while telemetry fetches on first open.
14. **Semantic grouping** — expansion is announced to screen readers as a single semantic region ("Import details for {recipeName}, N items") with child elements (timeline chips, badge, preview toggle, action buttons) addressable on demand. Uses `Semantics(container: true, label: ...)`.
15. Error-path: if the telemetry API fails, expansion renders the already-fetched bits (from list payload — stage, status, source, confidence) and an inline "Couldn't load full details · Retry" row for the missing raw text.
16. Integration test: tap caret on a row, assert expansion opens + telemetry fetch fires. Tap again, assert expansion closes. Open 3 different rows' carets, assert each holds independent state AND that expanding row 2 does NOT cause row 1's `build` to run (verified via a rebuild-count test probe).

### Key Files

- Modify: `app/lib/features/activity/widgets/import_row.dart`
- Create: `app/lib/features/activity/widgets/import_row_caret.dart`
- Create: `app/lib/features/activity/widgets/import_row_expansion.dart`
- Create: `app/lib/features/activity/providers/import_row_expansion_provider.dart`
- Create: `app/lib/features/activity/models/import_item_telemetry.dart`
- Modify: `app/lib/core/api_client/api_client.dart`
- Tests: `app/test/features/activity/widgets/import_row_expansion_test.dart`

---

## Story irrd-5: Flutter — `StageTimeline`, `ConfidenceBadge`, `RawTextPreview`

As Leo,
I want a clean stage timeline, a readable confidence badge, and a collapsible raw-text preview inside the expansion,
so the information density doesn't overwhelm me but is there when I want it.

### Acceptance Criteria

1. `StageTimeline` widget renders a horizontal strip of 4 chips: **Parsed · Extracted · Matched · Created**. Each chip shows:
    - ✓ (check glyph, green) if that stage's `status == "ok"`
    - ⏳ (hourglass glyph, blue, **subtle pulse animation** on current-stage chip) if current stage (derived from `last_successful_stage + 1`)
    - ✗ (x glyph, red) if `status == "failed"`
    - — (em-dash, muted) if not reached
2. **Compact 3-dot stage pill** (`CompactStagePill`) is a separate widget — 4 small dots in a row (●●○○), current stage pulsing. Rendered in the COLLAPSED row for **blue-state rows only** (so Leo gets his at-a-glance scan). Full 4-chip `StageTimeline` stays expansion-only.
3. Hover/long-press on each chip shows duration + timestamp tooltip (e.g., "Extracted · 3s · 2m ago").
4. `ConfidenceBadge` widget takes a `{score: double | null, source: 'model' | 'heuristic'}` and renders:
    - `score == null`: `—` glyph with tooltip "score unavailable"
    - < 0.5: warning glyph + "Low ({N}%)"
    - 0.5–0.8: neutral glyph + "{N}%"
    - > 0.8: checkmark + "{N}%"
    - `source == 'heuristic'` adds a subtle "*est" superscript (tap reveals "estimated, not model-reported")
    - Color from `ImportStateColors.needsReview` for <0.5, muted for 0.5–0.8, `ImportStateColors.autoImported` for >0.8
5. `RawTextPreview` widget takes a label + text payload and renders a collapsed "Show extracted text" row. Tap expands to reveal monospaced `SelectableText` in a scrollable container (max height 300px). Header shows "Truncated" pill if `truncated: true`. "Copy" button in the top-right copies to clipboard with snackbar confirmation.
6. Inside `ImportRowExpansion`: `RawTextPreview` renders once per non-empty preview in the telemetry response (one for parsed-stage OCR text, one for extracted-stage JSON — each labeled).
7. All widgets are theme-extension-aware (use `ImportStateColors` tokens for state-dependent coloring).
8. Widget tests: stub each widget with representative inputs, assert rendered chrome matches expected (chip glyphs, badge thresholds including null case, preview initial-collapsed state, truncated-pill render). Test the pulsing animation runs on the current-stage chip (verifies `AnimationController` is active).

### Key Files

- Create: `app/lib/features/activity/widgets/stage_timeline.dart`
- Create: `app/lib/features/activity/widgets/confidence_badge.dart`
- Create: `app/lib/features/activity/widgets/raw_text_preview.dart`
- Tests: widget tests per-widget in `app/test/features/activity/widgets/`

---

## Story irrd-6: Flutter — confidence badge on collapsed yellow rows + expansion action buttons

As Leo,
I want to see the confidence score at a glance on yellow rows (without expanding), and to take the right next action from inside any expanded row,
so my triage path is: scan yellow scores → expand the ambiguous ones → tap Review / Retry / View from the expansion.

### Acceptance Criteria

1. `ImportRow` (collapsed) on yellow state renders `ConfidenceBadge` inline next to the recipe name **plus a 1-word `AwaitingReviewReasonChip`** driven by `awaiting_review_reason` from the list payload — values: "low confidence", "unmatched ingredients", "missing title", "manual review". Lets Leo skip expansion on obviously-action items. On other states (blue/red/green), neither badge nor reason chip is in the collapsed row.
2. `ImportRow` (collapsed) on **blue state** renders `CompactStagePill` inline next to the recipe name — 4 small dots with the current stage pulsing. Restores Leo's at-a-glance stage scan from the old Add Recipe in-progress view.
3. `ImportRowExpansion` renders action buttons inline at the bottom, by state:
    - Yellow (Needs Review): **Review →** (primary) + **Archive** (secondary). Review navigates to the existing `/recipes/import/review/:itemId` route.
    - Red (Failed): **Retry** (primary) + **Archive** (secondary). Retry calls the existing retry endpoint; on success, row transitions to In Progress; expansion closes.
    - Green (Auto-Imported): **View Recipe** (primary, navigates to recipe detail) + **Archive** (secondary).
    - Blue (In Progress): no action buttons in the expansion for this release. (Per PRD out-of-scope: cancel stays detail-screen-only, but since the ImportHistoryScreen is retired, this means cancel is effectively a follow-up story.)
3. Action button taps are optimistic where possible:
    - Archive fires `POST /v1/import-items/{id}/archive` optimistically (row disappears), 3s snackbar-undo.
    - Retry fires endpoint, row's local status updates to `pending` on success; expansion remains open so the stage timeline redraws with Parsed ⏳ etc.
    - Review + View Recipe are pure navigations.
4. Button layout respects WCAG ≥44pt tap targets; on narrow screens, buttons wrap to two rows rather than truncating.
5. Widget test: for each state, pump the expansion with a mock item and assert the right button set renders.
6. Integration test: pump a yellow row, tap Review, assert navigation to `/recipes/import/review/:itemId`.

### Key Files

- Modify: `app/lib/features/activity/widgets/import_row.dart` (inline badge on yellow)
- Modify: `app/lib/features/activity/widgets/import_row_expansion.dart` (action button row)
- Modify: `app/lib/features/activity/providers/activity_archive_provider.dart` (reused for expansion-triggered archives)
- Tests: `app/test/features/activity/widgets/import_row_actions_test.dart`

---

## Story irrd-7: Accessibility + semantics audit + widget test pass

As a future-self reader and as a user on VoiceOver,
I want the expansion components to be screen-reader-friendly and fully test-covered,
so the feature doesn't regress and is usable beyond sighted-tap.

### Acceptance Criteria

1. Every chip/glyph in `StageTimeline` has a `Semantics` label (e.g., "Extracted · completed · 3 seconds · 2 minutes ago"). Color is NOT the only disambiguator.
2. `ConfidenceBadge` emits semantics: "Confidence: {low/medium/high}, {N}%, source {model/heuristic}".
3. `RawTextPreview` `Show extracted text` row has semantic label "Show extracted text"; expanded container has semantic label "Extracted text · {N} characters".
4. Caret semantics toggles on expansion: "Show details for {recipeName}" ↔ "Hide details for {recipeName}".
5. Widget test coverage: every widget in this epic has a test file asserting render + tap + a11y semantics.
6. Integration test walks a full flow: tap yellow caret → assert stage timeline + confidence + preview render → tap Review → assert navigation.
7. Manual VoiceOver + TalkBack check on a real device; story notes record what Leo heard.

### Key Files

- Semantics audit: modify all widgets created in irrd-4 / irrd-5 / irrd-6.
- Tests: ensure coverage in `app/test/features/activity/widgets/`.

---

## Dependencies

- **Cross-epic:** Depends on `epic-activity-hub-redesign` being at least through ahr-4 (the `ImportRow` shell + trailing slot + tab infrastructure).
- **Parallelizable internally:** irrd-1/-2 (stage fields + telemetry) and irrd-3 (confidence) can ship in parallel backends. Frontend irrd-4 onward waits on both.
- **No merge-freeze collisions** with `epic-review-import-ingredient-polish` (different files: that epic lives in the review-import surface, not the activity-hub surface).

## Open Questions for the User

- **Cancel-in-progress from the expansion's Blue state.** Blue rows currently have no swipe action, so cancel has no surface. The PRD marks cancel out-of-scope. Agree to leave blue expansions action-less for this epic and spawn a follow-up story if/when a cancel endpoint lands? Recommended: yes.
- **Per-ingredient confidence.** PRD explicitly defers this. Confirm the per-item score (single number per import) is enough, and per-ingredient breakdowns wait for a future epic. Recommended: yes.

(Both recommendations default if you don't flag otherwise in workshop.)

## Definition of Done (Epic Level)

- Every row in the Imports tab has a working caret toggle.
- Expanded rows show stage timeline + confidence (where applicable) + raw text preview + retry history + error detail + source reference + contextual action buttons.
- Yellow Needs Review rows show confidence badge in the COLLAPSED view too (the glanceable signal).
- All three LLM-based extractors emit `confidence_score`; heuristic fallback kicks in on malformed output; `json_ld_extractor` emits deterministic confidence; `confidence_source` annotates.
- `GET /v1/import-items/{id}/telemetry` returns stage log + truncated raw-text previews within 300ms P95.
- `last_successful_stage` and `last_retry_at` fields are visible on the API detail response and rendered in the UI.
- No regressions in the Activity Hub Notifications tab or prior-epic swipe/archive behavior.
- VoiceOver + TalkBack walk the full flow without relying on color alone.
