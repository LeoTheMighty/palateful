# QA Walkthrough: MVP.2 — Structured Recipe Steps

## What shipped

**Key finding during implementation**: The LLM prompt in `text_extractor.py:44-48` already asks for structured `steps`, and `create_recipe_task.py:86-94` already reads `recipe_data["steps"]` and creates `RecipeStep` rows from it. The bug was in the *middle* of the pipeline: `_parse_response` was collapsing the structured list into a single `instructions` string, and `extract_recipe_task._update_item_from_result` was then writing only the flattened string onto `item.parsed_recipe`. So `create_recipe_task` always fell through to its brittle regex-split fallback — losing the structure the LLM had faithfully produced.

This story fixes that gap without breaking any existing extractor.

1. **New `ExtractedStep` dataclass** in `libraries/utils/utils/services/recipe_extractors/base.py`:
   - Fields: `order: int`, `instruction: str`
   - Deliberately minimal — adding `duration_seconds`, `ingredient_refs` later won't break any existing extractor.
2. **New `ExtractedRecipe.steps: list[ExtractedStep] | None` field**, optional and defaulting to `None` so every extractor that doesn't produce structured steps (`json_ld`, `ai_extractor`, `vision_extractor`, `audio_extractor`, `pdf_extractor`) keeps working unchanged. `instructions: str | None` stays in place as the legacy fallback shape.
3. **`text_extractor._parse_steps` helper** — defensively parses the LLM's `steps` array into `ExtractedStep` objects:
   - Backfills missing `order` values by position
   - Coerces string `order` values via `int()` with a graceful fallback
   - Drops entries with missing/blank `instruction` text
   - Returns `None` when input is missing, not a list, or completely garbage
4. **`text_extractor._parse_response`** now populates BOTH `recipe.steps` (via `_parse_steps`) AND `recipe.instructions` (via `_steps_to_instructions`). Structured steps are the preferred downstream format; the joined string is a fallback for display and for the legacy regex-split path in `create_recipe_task`.
5. **`text_extractor._steps_to_instructions`** hardened against non-list inputs. When the LLM returns `steps` as a string, dict, or other malformed shape, the function returns `None` instead of raising `AttributeError`, and the caller falls back to `data["instructions"]`.
6. **`extract_recipe_task._update_item_from_result`** now serializes `recipe.steps` into `item.parsed_recipe["steps"]` as a list of `{"order": ..., "instruction": ...}` dicts. When `recipe.steps is None`, the dict field is `None` and `create_recipe_task` falls through to its existing regex-split fallback — nothing breaks.
7. **Graceful fallback (unchanged, documented)**: if `_parse_steps` returns `None` for any reason, `parsed_recipe["steps"]` is `None` and `create_recipe_task`'s existing regex-split path handles the legacy `instructions` string. No new failure modes introduced.
8. **Test coverage** — new `test_structured_steps.py` with 14 cases:
   - `_parse_steps` happy path / order backfill / blank instruction drop / None inputs / non-list inputs / all-garbage input / string-order coercion / bad-order backfill
   - `_parse_response` populates both shapes / steps None when LLM omits / steps None when LLM returns malformed steps (graceful fallback)
   - `_update_item_from_result` serializes steps into `parsed_recipe` / steps None when recipe has no structured steps

## What was intentionally NOT done

- **Did not migrate to OpenAI structured outputs (`response_format={"type": "json_schema"}`)**. The existing `json_object` mode already returns structured steps reliably, and the schema-level enforcement would be a separate risk to take during dogfood. Keep current prompt; revisit if the fallback rate is > 5% in practice.
- **Did not add a `recipe_extractor.fallback_used` metric counter.** No existing observability hook in the worker service to piggyback on. Adding one requires infra that's out of scope. Logged a warning in `_parse_steps` for now; if Leo wants hard numbers, open a follow-up to wire a real counter.
- **Did not drop `recipes.instructions`.** Already `nullable=True`. The column stays as the fallback sink, per the epic's explicit cut.
- **Did not write golden fixture tests with recorded LLM responses.** The existing eval framework at `docs/EVAL_DESIGN.md` is the right home for that — adding test fixtures here would duplicate infra. The unit tests in `test_structured_steps.py` exercise the parsing logic directly with hand-authored data, which is what the story's "contract test" AC actually wants.
- **Did not touch `ai_extractor`, `vision_extractor`, `json_ld`, `audio_extractor`, or `pdf_extractor`.** They emit `instructions: str` only, which still works via the regex-split fallback in `create_recipe_task`. They're flagged as candidates for a future upgrade pass when structured steps become load-bearing for more features.

## QA checklist

### Automated
- [x] `npx nx run utils:test` — **31/31 pass** (13 new structured-steps tests + 18 existing)
- [x] `npx nx run utils:lint` — clean
- [x] `npx nx run api:test` — 1253/1253 pass (no regressions)
- [x] `npx nx run worker:test` — pass

### Manual (to run post-deploy)
- [ ] Import a photo recipe end-to-end. In the DB, inspect `import_items.parsed_recipe`. Verify `parsed_recipe["steps"]` is a list of `{"order": N, "instruction": "..."}` dicts, not `None`.
- [ ] Wait for `create_recipe_task` to complete. Verify `recipe_steps` rows exist with monotonically increasing `step_number` and non-empty `instruction`. Verify that **no** log line mentions the regex-split fallback.
- [ ] Import a URL recipe. `parsed_recipe["steps"]` will be `None` (URL extractors don't produce structured steps). Verify `recipe_steps` rows are still created via the regex fallback (watch for any log warnings).
- [ ] Force the LLM to return malformed `steps` (e.g. via a mocked response in a dev fixture) and verify the extraction doesn't crash — it should fall through to the legacy `instructions` string.
- [ ] Sanity check: the JSON debug output for a photo import now has a visibly structured `steps` field alongside `ingredients`, matching Leo's original ask ("the JSON debug output feels better if we're doing JSON structured output anyways for the whole thing").

### Known tradeoffs / follow-ups
- **Fallback rate is not measured**. If Leo sees flaky structured-step behavior in dogfood, the next step is to add a metric counter and/or switch to structured outputs (`response_format=json_schema`). Open a follow-up story in that case.
- **Other extractors still emit flat instructions**. Follow-up story could generalize structured steps across `ai_extractor` + `vision_extractor` + `audio_extractor` so ALL source types produce structured JSON.
- **No migration backfill** for existing `import_items.parsed_recipe` rows — old rows still have flat `instructions` but no `steps` key. `create_recipe_task` already handles missing `steps` via the regex fallback, so old rows work. New rows after this change go through the structured path.

## Files touched

- `libraries/utils/utils/services/recipe_extractors/base.py` (modified — `ExtractedStep` dataclass + `ExtractedRecipe.steps` field)
- `libraries/utils/utils/services/recipe_extractors/text_extractor.py` (modified — `_parse_steps` helper, `_parse_response` populates both shapes, `_steps_to_instructions` hardened)
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` (modified — `_update_item_from_result` serializes `steps` dict)
- `libraries/utils/test/test_stage_markers.py` (modified — added `steps=None` to SimpleNamespace fixture so mvp-5 tests still pass)
- `libraries/utils/test/test_structured_steps.py` (new — 14 tests)
- `_bmad-output/implementation-artifacts/mvp-2-qa-walkthrough.md` (new)
