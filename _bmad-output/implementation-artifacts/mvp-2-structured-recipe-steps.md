# Story MVP.2: Structured Recipe Steps — Schema, Prompt, Persistence, Graceful Fallback

Status: ready-for-dev

## Story

As Leo dogfooding Palateful,
I want recipe steps extracted as a structured list instead of a single markdown blob,
so that the JSON debug output for the entire recipe is consistently structured end-to-end and I can trust the extraction pipeline enough to use the app daily.

## Context

The extractor currently produces structured JSON for every field of a recipe **except** the steps, which come back as a single markdown string like `"1. Chop onions. 2. Sauté. 3. ..."`. This is inconsistent with the rest of the schema and makes the debug output feel fragile.

Current state:
- **Prompt**: `libraries/utils/utils/services/recipe_extractors/ai_extractor.py:31` — `"instructions": "Step-by-step instructions as a single string"`
- **Schema**: `libraries/utils/utils/services/recipe_extractors/base.py:27` — `instructions: str | None = None`
- **Persistence**: `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py:157` — dumps the string into `recipes.instructions` (`Text` column at `models/recipe.py:29`)
- **Unused infra**: `models/recipe_step.py` exists with `step_number: int` and `instruction: str` columns — the `recipe_steps` table is schema-ready but never populated

This story changes the extractor to produce a structured `steps: list[ExtractedStep]`, persists those rows into `recipe_steps`, and adds a graceful fallback so that if structured parsing fails at the LLM boundary, the legacy `recipes.instructions` field still receives the raw text. This means a broken extraction degrades to "what we had before" instead of a hard failure.

## Acceptance Criteria

1. `ExtractedRecipe` schema exposes a structured `steps: list[ExtractedStep] | None` field, where `ExtractedStep` has at minimum `step_number: int` and `instruction: str`.
2. The LLM prompt in `ai_extractor.py` requests structured steps via OpenAI structured outputs (`response_format={"type": "json_schema", ...}`), not free-form markdown.
3. On successful extraction, `extract_recipe_task` persists one row per step into the `recipe_steps` table, with correct `step_number` ordering and foreign key to the owning `recipes.id`.
4. On extraction failure (Pydantic `ValidationError`, malformed JSON, or missing `steps` field), the extractor catches the error, logs the raw LLM response, sets `steps=None`, and dumps the raw response text into the legacy `recipes.instructions` column so the user still sees *something*.
5. A fallback metric counter is incremented whenever the graceful fallback path is taken, so dogfood sessions can surface the fallback rate.
6. The legacy `recipes.instructions` column remains in place as `nullable` — do NOT drop it in this story.
7. Golden fixture tests cover: a clean single-image recipe, a multi-image recipe, and a noisy OCR recipe. All three must produce populated `recipe_steps` rows with monotonically increasing `step_number`.
8. Contract test asserts the `ExtractedRecipe` schema round-trips cleanly for a known-good LLM response.
9. Fallback unit test: feed the extractor a malformed LLM response and assert (a) no crash, (b) `steps` is `None`, (c) `recipes.instructions` contains the raw text, (d) the fallback metric is incremented.

## Tasks / Subtasks

- [ ] Task 1: Define `ExtractedStep` and update `ExtractedRecipe` schema (AC: #1)
  - [ ] Add `ExtractedStep` Pydantic model to `libraries/utils/utils/services/recipe_extractors/base.py`
    - Fields: `step_number: int`, `instruction: str`
    - Leave room for future additions (`duration_seconds`, `ingredient_refs`) but **do not add them in this story**
  - [ ] Replace `instructions: str | None = None` at `base.py:27` with `steps: list[ExtractedStep] | None = None`
  - [ ] Grep for any callsite that reads `.instructions` from an `ExtractedRecipe` — audit them, update to consume `steps` or the new fallback path

- [ ] Task 2: Update the LLM prompt to use OpenAI structured outputs (AC: #2)
  - [ ] Modify `libraries/utils/utils/services/recipe_extractors/ai_extractor.py:31`
  - [ ] Replace the `"instructions": "Step-by-step instructions as a single string"` prompt hint with a structured `steps` schema description
  - [ ] Switch the OpenAI call to use `response_format={"type": "json_schema", "json_schema": {...}}` with the Pydantic-derived schema, so the model is constrained at the API level, not just by prompt instruction
  - [ ] Keep the rest of the recipe schema unchanged — this story only restructures the steps field

- [ ] Task 3: Persist `recipe_steps` rows (AC: #3, #6)
  - [ ] Modify `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py:157`
  - [ ] After the recipe row is inserted, iterate `recipe.steps` and insert one `RecipeStep` row per entry with the correct `recipe_id` FK and `step_number`
  - [ ] Leave the `recipes.instructions` write path in place but only populate it when falling back (Task 4). On the happy path, `recipes.instructions` is `None`
  - [ ] Verify the existing `recipe_steps` model at `libraries/utils/utils/models/recipe_step.py` is imported correctly and no migration is needed (schema already exists)

- [ ] Task 4: Implement graceful fallback at the extractor boundary (AC: #4, #5)
  - [ ] Wrap the structured-output parse in `ai_extractor.py` in a try/except around `ValidationError` and JSON parsing errors
  - [ ] On failure:
    - Log the raw LLM response at `WARNING` level with a tag like `extractor_fallback`
    - Return an `ExtractedRecipe` with `steps=None` and the raw text placed in a dedicated `_fallback_instructions: str | None` attribute (or equivalent mechanism — pick whatever fits the extractor's return shape)
  - [ ] In `extract_recipe_task.py`, when `recipe.steps is None` and `_fallback_instructions` is set, write the raw text into `recipes.instructions` as the fallback
  - [ ] Increment a counter metric (e.g. via existing observability helper — match whatever `services/worker` already uses) with name `recipe_extractor.fallback_used` tagged by `source` (photo vs url vs text)

- [ ] Task 5: Golden fixture tests (AC: #7)
  - [ ] Add fixtures under `libraries/utils/tests/fixtures/recipe_extractors/` (or wherever existing extractor fixtures live — grep for `ai_extractor` tests)
  - [ ] Three fixtures minimum: `clean_single_image.json`, `multi_image_concatenated.json`, `noisy_ocr.json`
  - [ ] Each fixture contains a saved OCR/text input and the expected `ExtractedRecipe` output
  - [ ] Tests assert structured `steps` are populated with monotonically increasing `step_number`
  - [ ] Consider whether these fixtures should call the real OpenAI API (nightly) or use a recorded response (PR CI) — recommend recorded responses for PR CI, real calls for a separate nightly eval (see `docs/EVAL_DESIGN.md`)

- [ ] Task 6: Contract and fallback unit tests (AC: #8, #9)
  - [ ] Contract test: feed a hand-authored valid LLM response JSON into the parsing layer, assert it round-trips to `ExtractedRecipe` cleanly
  - [ ] Fallback test: feed a malformed LLM response (missing `steps`, wrong types, truncated JSON), assert:
    - No exception escapes the extractor
    - `steps is None` on the returned object
    - `_fallback_instructions` contains the raw text
    - The `recipe_extractor.fallback_used` metric is incremented (use a test double / in-memory metric registry)

## Dev Notes

- **Do not drop or rename `recipes.instructions`.** Keep it as the fallback sink. A follow-up tech-debt story will handle deprecation once metrics confirm the fallback rate is low.
- **Do not add step-level features** like timers or ingredient references in this story. The schema should leave room for them, but they are explicitly out of scope (see epic cuts).
- The `recipe_steps` table schema already exists (`models/recipe_step.py`) — no Alembic migration is needed for this story, only for the nullability change on `recipes.instructions` if it isn't already nullable (grep the current migration state).
- **Verify `recipes.instructions` nullability** before writing migration code. If already `nullable=True`, skip the migration subtask entirely.
- Use OpenAI **structured outputs** (`response_format={"type": "json_schema"}`) rather than `response_format={"type": "json_object"}` — the former gives hard schema guarantees at the API level and dramatically reduces fallback rate.
- The fallback path is **load-bearing for dogfood confidence** — it is better for Leo to see a slightly-ugly fallback recipe than a failed import. Do not skimp on fallback test coverage.

### Project Structure Notes

- Extractor code lives in `libraries/utils/utils/services/recipe_extractors/` — shared library used by multiple services.
- Import tasks live in `libraries/utils/utils/tasks/import_tasks/` — shared Celery task definitions.
- Model definitions in `libraries/utils/utils/models/` — SQLAlchemy models shared across API, worker, migrator.
- Eval fixtures likely live under `services/eval/` or `libraries/utils/tests/fixtures/` — confirm at implementation time.

### References

- Current extractor prompt: `libraries/utils/utils/services/recipe_extractors/ai_extractor.py:31`
- Current schema: `libraries/utils/utils/services/recipe_extractors/base.py:27`
- Current persistence: `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py:157`
- Unused destination table model: `libraries/utils/utils/models/recipe_step.py`
- Legacy string column: `libraries/utils/utils/models/recipe.py:29`
- Eval framework context: `docs/EVAL_DESIGN.md`
- [Epic: epic-mvp-finalization.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
