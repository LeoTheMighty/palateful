# Story efi-1 — Backend scaffolding: INFERABLE_FIELDS + flag + `inference_prompt` + `inference_guardrails` + `apply_inference_penalty` + `log_inferred_field_clamp`

**Status:** done
**Epic:** epic-extractor-field-inference
**Depends on:** none (first story in epic).

## Scope

Build the inference feature's scaffolding — flag + prompt fragment
generator + guardrails + confidence penalty + sanctioned audit log —
with comprehensive unit tests. No extractor / task / schema / API code
is modified; those come in efi-2..4. `ExtractedRecipe.inferred_fields`
is accessed via `getattr` / attribute-set so the dataclass can stay
untouched until efi-2 adds the real field.

## Implementation notes

- Flag read pattern mirrors `confidence_prompt.emit_confidence()`
  verbatim. `EXTRACTOR_INFER_MISSING_FIELDS` default-on, accepts the
  same `"false" / "0" / "no" / "off"` off-values.
- `inference_rule()` returns an empty string when the flag is off, so
  callers can splice `{inference_rule()}` into a prompt and get no
  content when disabled.
- Guardrails mutate the recipe in place and return the same object for
  ergonomic chaining. Invalid vibes are dropped AND removed from
  `inferred_fields` entirely (the field stops being inferred, it's
  simply absent). Numeric fields that fail type/coercion (e.g., bool,
  non-numeric string) have the attribute nulled but stay in
  `inferred_fields` — the model still *claimed* to have inferred this
  field, and the provenance signal is worth keeping for the correction
  log.
- `log_inferred_field_clamp` uses its own short-lived `Database()`
  instance (mirrors `stage_logging.log_stage_transition`) so an
  extractor rollback doesn't take the audit row with it. Never raises.
- AST-lint test `test_inference_log_enforcement.py` mirrors the
  `StageTransition` / `UnitAliasMiss` precedent: scans `libraries/`
  and `services/` for any literal `"InferredFieldClamped"` outside the
  sanctioned helper and fails CI if one appears.
- `apply_inference_penalty(score, inferred_count)`: flat
  `0.05 × min(inferred_count, 5)`, capped at 0.25 penalty. Coerces
  NaN / infinite inputs to 0.0 up front so the clamp can't leak a
  non-finite score downstream (would break JSON / Postgres serialization).

## File list

- `libraries/utils/utils/services/recipe_extractors/inference_prompt.py` [NEW] — `INFERABLE_FIELDS`, `infer_missing_fields()`, `inference_rule()`
- `libraries/utils/utils/services/recipe_extractors/inference_guardrails.py` [NEW] — `apply_guardrails(recipe, import_item_id)` + per-field clamp / truncate / validate
- `libraries/utils/utils/logging/inference_logging.py` [NEW] — `log_inferred_field_clamp(...)` + `INFERRED_FIELD_CLAMPED_ERROR_TYPE` constant
- `libraries/utils/utils/logging/__init__.py` [MODIFY] — export `log_inferred_field_clamp`
- `libraries/utils/utils/services/recipe_extractors/confidence_heuristic.py` [MODIFY] — append `apply_inference_penalty` helper
- `libraries/utils/test/test_inference_prompt.py` [NEW]
- `libraries/utils/test/test_inference_guardrails.py` [NEW]
- `libraries/utils/test/test_confidence_inference_penalty.py` [NEW]
- `libraries/utils/test/test_inference_log_enforcement.py` [NEW]

## Acceptance criteria — coverage

- AC1 — `INFERABLE_FIELDS` exports 9 names; `infer_missing_fields()` reads env at call time; `inference_rule()` returns empty string when flag is off. ✅
- AC2 — `inference_rule()` names all 9 fields, includes the NEVER clause for name/ingredients/steps, requires `inferred_fields` as an always-present array, and has a worked `cook_time_minutes` example. ✅
- AC3 — `apply_guardrails(recipe, import_item_id)` iterates `inferred_fields`, clamps numerics, truncates strings, validates vibes (drop-and-remove-from-inferred), mutates in place, returns the same recipe. ✅
- AC4 — Every clamp / drop writes one `error_logs` row via `log_inferred_field_clamp` with `service="audit"`, `error_type="InferredFieldClamped"`, `metadata={field, raw, clamped_or_dropped, reason}`. ✅
- AC5 — `test_inference_log_enforcement.py` AST-scans `libraries/` + `services/` for bare `"InferredFieldClamped"` literals outside the helper. ✅
- AC6 — `apply_inference_penalty(score, inferred_count)` subtracts `0.05 × min(count, 5)`, clamps to [0, 1], coerces NaN/inf to 0. ✅
- AC7 — Unit tests cover every clamp/drop/flag/penalty branch. Guardrails: 22 tests. Prompt: 25 tests. Penalty: 19 tests. Log enforcement: 1 test. ✅
- AC8 — No extractor / task / schema / API code modified. `ExtractedRecipe.inferred_fields` is accessed via `getattr`/`setattr` so the dataclass stays untouched until efi-2. ✅

## Follow-ups

- efi-2 adds the real `ExtractedRecipe.inferred_fields` dataclass field and wires `inference_rule()` into each extractor prompt.
- efi-3 wires `apply_guardrails` and `apply_inference_penalty` into `extract_recipe_task.py` and adds the `recipes.inferred_fields` migration.
- efi-4 hoists `inferred_fields` onto import-item response roots and adds `POST /v1/import-items/{id}/corrections`.
