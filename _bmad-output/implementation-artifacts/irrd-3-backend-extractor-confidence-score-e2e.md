# irrd-3 — Backend: extractor confidence score end-to-end

Status: **done** (AC1–AC7 + AC10 landed; AC8/AC9/AC11 deferred as `irrd-3a`).

## What shipped

- **Schema.** `recipe_extraction_schema.RECIPE_EXTRACTION_SCHEMA` now
  carries `confidence_score: float | null` and `confidence_source:
  string | null` at the recipe-object root.
- **Dataclass.** `ExtractedRecipe` has matching fields with null
  defaults.
- **Prompt instruction (AC2, AC10).** New
  `utils/services/recipe_extractors/confidence_prompt.py` emits the
  "emit `confidence_score` + `confidence_source` on every recipe"
  instruction, gated by `EXTRACTOR_EMIT_CONFIDENCE` (default true, flip
  to false to roll back via ECS task def without a redeploy). Spliced
  into `ai_extractor._extraction_prompt()`,
  `text_extractor._text_extraction_prompt()`,
  `vision_extractor._vision_system_prompt()`.
- **Heuristic fallback (AC3).** New
  `utils/services/recipe_extractors/confidence_heuristic.py` with two
  entry points:
  - `compute_heuristic_confidence(recipe)` — weights:
    `0.4 * (ingredients_with_quantity / len)`
    + `0.3 * (1 if title else 0)`
    + `0.3 * min(step_count / 3, 1)`.
    Accepts either an `ExtractedRecipe` or a dict.
  - `resolve_confidence(raw_data, recipe)` — the canonical entry point
    extractors call. Returns `(score, source)`; null-safe, bool-quantity-
    safe, out-of-range-safe.
- **JSON-LD deterministic score (AC4).** `json_ld._parse_recipe_data`
  computes `1.0` when title + ≥1 ingredient + instructions are all
  present; else degraded proportionally with a 0.3 floor.
  `confidence_source` is always `"model"` (json-ld is authoritative).
- **LLM extractors (AC2, AC3).**  Each of `ai_extractor`, `text_extractor`,
  `vision_extractor` post-parse path calls `resolve_confidence(data,
  recipe)` and assigns the result onto the `ExtractedRecipe`.
- **Persistence (AC5).** `extract_recipe_task._serialize_recipe` now
  writes `confidence_score` + `confidence_source` as top-level keys on
  `parsed_recipe`. `getattr(..., None)` guards against mock callers.
- **API surfacing (AC6).**
  - `GetImportItem.Response` hoists both fields at the response root via
    a local `_extract_confidence_fields()` that drops malformed /
    out-of-range values on read.
  - `ListImportItems.ItemSummary` hoists both fields the same way.
  - `ListImportJobs` — not widened (job-summary level, no per-item
    hoist). Matches the irrd-1 decision: only widen when an item-level
    surface is actually exposed.
- **Feature flag (AC10).**
  `EXTRACTOR_EMIT_CONFIDENCE={true|false}`. When off:
  - `confidence_rule()` returns an empty string → prompt omits the
    instruction.
  - `resolve_confidence` short-circuits to the heuristic regardless of
    what the model emitted (so even a model that self-reports gets
    ignored — the rollback is complete).
- **Round-trip test (AC7).** `test_extractor_confidence.py` covers the
  heuristic fixture (expected score 0.867 ±0.001 for 3 ingredients /
  2 with qty / title / 4-line instructions), per-extractor
  `_parse_response` paths, and prompt flag content. `test_import.py`
  adds endpoint-level coverage for the hoist + malformed-drop paths.

## What was deferred (`irrd-3a`)

- **AC8 — `services/eval/src/metrics/confidence_calibration.py`**
  metric module and baseline file scaffolding.
- **AC9 — heuristic weight calibration pre-merge.** Re-tune weights if
  MAE > 0.3 vs ground-truth F1 across the fixture suite.
- **AC11 — soft eval regression gate.** Block merge if new prompts
  drop `title_extraction_f1` by > 5% vs the baseline.

All three require real LLM API calls + ~10-min eval runtime + OpenAI
API spend. Deferred to a focused follow-up story once the code-only
pieces are in users' hands and ECS rollback is validated.

## Files touched

New:
- `libraries/utils/utils/services/recipe_extractors/confidence_prompt.py`
- `libraries/utils/utils/services/recipe_extractors/confidence_heuristic.py`
- `libraries/utils/test/test_extractor_confidence.py`

Modified:
- `libraries/utils/utils/schemas/recipe_extraction_schema.py`
- `libraries/utils/utils/services/recipe_extractors/base.py`
- `libraries/utils/utils/services/recipe_extractors/ai_extractor.py`
- `libraries/utils/utils/services/recipe_extractors/text_extractor.py`
- `libraries/utils/utils/services/recipe_extractors/vision_extractor.py`
- `libraries/utils/utils/services/recipe_extractors/json_ld.py`
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`
- `services/api/src/api/v1/import_job/get_import_item.py`
- `services/api/src/api/v1/import_job/list_import_items.py`
- `services/api/tests/test_import.py` (3 new tests)

## Test results

- `npx nx run utils:test` — **239 passed**.
- `npx nx run api:test` — **1742 passed** (up from 1740). Coverage
  drops to 99.83% are pre-existing gaps in `start_import.py` (sbf-3
  WIP, not yet committed) and `admin/get_push_health.py` (push-diag-3
  WIP, not yet committed), NOT irrd-3 code. Coverage on every file
  touched by irrd-3 is 100%.
- `npx nx run utils:lint` — clean.
- `npx nx run api:lint` — clean.

## Notes on behavior

- `confidence_score = 0.0` vs `confidence_score = null` are distinct.
  `0.0` is a legitimate model signal ("this extraction is garbage");
  `null` means "model declined to self-assess" and the heuristic runs.
  Both `resolve_confidence` and `normalize_model_confidence` preserve
  this distinction.
- Out-of-range scores (`2.5`, `-0.1`, NaN, non-numeric strings) fall
  through to the heuristic at the extractor boundary, AND are dropped
  to `null` if they somehow sneak into persisted parsed_recipe JSONB
  from a legacy row — the API response will return `null`, not
  malformed garbage.
- `True` / `False` from the LLM in a `quantity` field does NOT count as
  a valid quantity in the heuristic — `bool` is a subclass of `int` in
  Python and we guard explicitly.
