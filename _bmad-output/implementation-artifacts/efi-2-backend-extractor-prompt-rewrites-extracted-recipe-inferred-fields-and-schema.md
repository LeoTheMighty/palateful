# Story efi-2 — Extractor prompt rewrites + `ExtractedRecipe.inferred_fields` + parsing + schema

**Status:** done
**Epic:** epic-extractor-field-inference
**Depends on:** efi-1 (INFERABLE_FIELDS, inference_rule(), parse_inferred_fields helper)

## Scope

Teach each of the three LLM-based extractors (ai, vision, text) to emit
a top-level `inferred_fields` array when the flag is on, and parse it
into `ExtractedRecipe.inferred_fields`. Add the dataclass field and a
permissive schema property. `json_ld.py` stays untouched — Schema.org
data is authoritative and never inferred.

## Implementation notes

- `parse_inferred_fields(raw)` lives in `inference_prompt.py` and is
  shared by all three extractors — filters to `INFERABLE_FIELDS`,
  dedupes, preserves first-seen order, tolerates non-list / non-string
  garbage by returning `[]`.
- Each extractor caches `infer_missing_fields()` once at the top of its
  prompt-builder to avoid mid-prompt inconsistency if the env flips.
- Prompt skeleton line `"inferred_fields": []` is **conditional** —
  absent entirely when the flag is off. AC7's "flag off must not
  mention 'inferred_fields'" is strict; leaking the key name would
  prime the model to emit it regardless.
- Text and vision prompts each have TWO conditional rules
  (`include_rule` + `null_rule`) because both have an "only include
  present" bullet AND a "set missing to null" bullet.
- Vision prompt's OCR-disambiguation "infer from context when
  characters are unclear" bullet stays verbatim in both flag states —
  it's about OCR character recognition, not field-level inference.
- `ExtractedRecipe.inferred_fields: list[str] = field(default_factory=list)`
  lands between `confidence_source` and `raw_data`. Default factory
  means every construction site — including `json_ld.py` — emits `[]`
  automatically.

## File list

- `libraries/utils/utils/services/recipe_extractors/base.py` [MODIFY] — `ExtractedRecipe.inferred_fields` field
- `libraries/utils/utils/services/recipe_extractors/inference_prompt.py` [MODIFY] — `parse_inferred_fields` helper
- `libraries/utils/utils/services/recipe_extractors/ai_extractor.py` [MODIFY] — prompt + skeleton line + parse call
- `libraries/utils/utils/services/recipe_extractors/text_extractor.py` [MODIFY] — same
- `libraries/utils/utils/services/recipe_extractors/vision_extractor.py` [MODIFY] — same
- `libraries/utils/utils/services/recipe_extractors/json_ld.py` [MODIFY] — comment only, no behavior change
- `libraries/utils/utils/schemas/recipe_extraction_schema.py` [MODIFY] — `inferred_fields: array<string>` property (not required)
- `libraries/utils/test/test_extractor_inferred_fields.py` [NEW] — 28 tests

## Acceptance criteria — coverage

- AC1 — `ExtractedRecipe.inferred_fields: list[str]` with default factory, after `confidence_source`, before `raw_data`. ✅
- AC2 — `ai_extractor.py` splices `inference_rule()` after `confidence_rule()`; "Only include fields you can find" is scoped to non-inferable when flag on, verbatim when off; `_parse_ai_response` reads via `parse_inferred_fields`. ✅
- AC3 — `vision_extractor.py` same splice + parse behaviour; OCR-disambiguation instruction stays verbatim. ✅
- AC4 — `text_extractor.py` same splice + parse behaviour; "Set missing fields to null rather than guessing" is scoped when flag on, kept verbatim when off. ✅
- AC5 — `json_ld.py` untouched behavior; ExtractedRecipe's default factory yields `inferred_fields=[]`. Comment added for future readers. ✅
- AC6 — schema adds `inferred_fields: array<string>` property. Not in `required`. Permissive (no enum restriction on items — the allow-list is enforced at parse + guardrails). ✅
- AC7 — flag-off contract tests pass: prompt does NOT contain `inferred_fields` AT ALL; prior "Only include present" phrasing is intact for each extractor. ✅
- AC8 — parse tests per extractor: valid/dedup/filter/missing/null/dupe inputs all land at the expected `inferred_fields` list. ✅
- AC9 — No live wiring of guardrails, penalty, or API surface. Downstream comes in efi-3 / efi-4. ✅
- AC10 — Regression: all 339 pre-existing utils tests continue to pass (367 total after adding 28 new). ✅

## Follow-ups

- efi-3 wires `apply_guardrails` and `apply_inference_penalty` into `extract_recipe_task.py` and adds the `recipes.inferred_fields` migration.
- efi-4 hoists `inferred_fields` onto import-item response roots and adds `POST /v1/import-items/{id}/corrections`.
