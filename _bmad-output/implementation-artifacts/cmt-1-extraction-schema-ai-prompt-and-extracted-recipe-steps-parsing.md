# Story cmt-1 — Extraction schema + AI prompt + `ExtractedRecipe.steps` timers parsing

**Status:** in-progress
**Epic:** epic-cook-mode-timers
**Depends on:** none (first story in epic).

## Scope

Teach the AI HTML-page extractor (`ai_extractor.py`) to emit a structured `steps: [{order, instruction, timers: [...]}]` payload, on top of the single joined `instructions` string it produces today. The extraction JSON schema is updated to document `timers`. Downstream persistence (`create_recipe_task`) is **not** touched in this story — that's cmt-2.

## Implementation notes

- The epic says "ExtractedStep dataclass stays unmodified and unused in v1" — in reality the dataclass IS already used by `text_extractor._parse_steps` and `_serialize_recipe`. The path of least disruption is to **extend `ExtractedStep` with an optional `timers: list[dict] = field(default_factory=list)` field**. All existing call-sites continue to work; AI extractor can populate `timers` when the model emits them. Spec deviation documented here; downstream contract unchanged.
- `_serialize_recipe` in `extract_recipe_task.py` is extended to copy `s.timers` into the per-step dict so `parsed_recipe["steps"][i]["timers"]` is present on the way to `create_recipe_task`.
- Schema update is **additive + permissive**: no validation on timer values beyond "it's a list of objects". Invalid timer entries are filtered at persistence time in cmt-2.
- Prompt additions are surgical: schema fragment + rule + one positive example + one negative example + the "steps supersedes instructions" clarification.

## File list

- `libraries/utils/utils/schemas/recipe_extraction_schema.py` [MODIFY] — add `timers` to step items
- `libraries/utils/utils/services/recipe_extractors/base.py` [MODIFY] — add `timers` field to `ExtractedStep`
- `libraries/utils/utils/services/recipe_extractors/ai_extractor.py` [MODIFY] — prompt + `_parse_steps` helper + populate `recipe.steps` in `_parse_ai_response`
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` [MODIFY] — include `timers` in `_serialize_recipe` output
- `libraries/utils/test/test_ai_extractor_timers.py` [NEW] — mock-response unit tests

## Acceptance criteria

- AC1 — `recipe_extraction_schema.py` step items schema includes `timers: array<object>` (properties: `duration_minutes: integer`, `label: string`). `instructions: string` retained.
- AC2 — `ai_extractor.py` prompt emits: (a) `steps` schema fragment including `timers`, (b) actively-tended rule, (c) positive example ("Simmer for 10 minutes, stirring." → timer: 10 min simmer), (d) negative example ("Let dough rise overnight." → no timer), (e) "steps supersedes instructions" note.
- AC3 — `ExtractedStep` gains `timers: list[dict]` defaulting to empty list. Comment explains the field.
- AC4 — `_parse_ai_response` parses `data.get("steps")` into `ExtractedStep` instances with timers populated; absent/empty `steps` leaves `ExtractedRecipe.steps` as `None`.
- AC5 — Unit: mock response with `steps:[{order:1,instruction:"Simmer 10 min",timers:[{duration_minutes:10,label:"simmer"}]}]` → `recipe.steps[0].timers == [{"duration_minutes":10,"label":"simmer"}]`.
- AC6 — Unit: mock response with only `instructions: "…"` (no `steps`) → `recipe.steps is None`, `recipe.instructions` populated.
- AC7 — Unit: mock response with `steps:[{timers:[{"duration_minutes":"25","label":"bake"}]}]` passes through unchanged (filtering happens at persist time).
- AC8 — `_serialize_recipe` in `extract_recipe_task.py` includes `timers: s.timers` on each step dict.
- AC9 — `npx nx run utils:lint` clean. `npx nx run api:test` + utils tests pass.
