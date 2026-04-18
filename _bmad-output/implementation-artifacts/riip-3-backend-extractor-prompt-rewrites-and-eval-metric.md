# Story riip-3: Backend — extractor prompt rewrites + eval compliance metric

**Status:** done
**Epic:** epic-review-import-ingredient-polish

## Goal
Stop the LLM from emitting freeform unit words. Each extractor's prompt
now enumerates the canonical token list (`tsp, tbsp, cup, fl oz, ml, l,
g, kg, oz, lb, each, pinch, dash, clove, slice, mg, gallon, quart,
pint`) and forbids full words + trailing punctuation. The change is
gated behind `EXTRACTOR_EMIT_CANONICAL_UNITS` (default true) so it can
be flipped via ECS task def without redeploy. Eval suite gains
`unit_enum_compliance` metric for baseline observation; the deploy
gate is deferred to companion story `riip-3a` per epic ACs.

## Scope (from epic)
- New helper module `unit_prompt.py` exposes `CANONICAL_UNIT_TOKENS`,
  `emit_canonical_units()` (env-flag read at call time) and
  `unit_rule(*, freeform_fallback)` returning the right `- "unit": …`
  bullet for the prompt.
- `ai_extractor.py`, `text_extractor.py`, `vision_extractor.py`:
  - The static `EXTRACTION_PROMPT` / `TEXT_EXTRACTION_PROMPT` /
    `VISION_SYSTEM_PROMPT` strings became private builder functions
    `_extraction_prompt()` / `_text_extraction_prompt()` /
    `_vision_system_prompt()` so the flag can flip between calls.
  - Each builder injects `unit_rule(freeform_fallback=…)` at the
    "unit:" line and updates the worked examples to canonical tokens
    (e.g., "9 tablespoons butter → unit: tbsp").
  - Backward-compat module-level constants kept (evaluated once at
    import) for tests / other importers.
- New eval metric `services/eval/src/metrics/unit_enum_compliance.py`
  computes `{compliance, total_units, compliant, non_compliant_breakdown}`.
  Wired into `RecipeExtractionEvaluator._calculate_metrics` so every
  per-case result carries the breakdown.
- Companion gate work (`riip-3a`) is intentionally deferred — the ACs
  call out ≥1 week of baseline data first.

## File List
- `libraries/utils/utils/services/recipe_extractors/unit_prompt.py` — new
- `libraries/utils/utils/services/recipe_extractors/ai_extractor.py` — modified
- `libraries/utils/utils/services/recipe_extractors/text_extractor.py` — modified
- `libraries/utils/utils/services/recipe_extractors/vision_extractor.py` — modified
- `libraries/utils/test/test_extractor_unit_prompt.py` — new (22 tests)
- `services/eval/src/metrics/unit_enum_compliance.py` — new
- `services/eval/src/evaluators/recipe_extraction_evaluator.py` — modified
- `services/eval/tests/test_unit_enum_compliance.py` — new (7 tests)

## Notes
- `unit_prompt.py` reads the flag with `os.environ.get(...)` at call
  time; flip semantics match the AC ("apply to the next request").
- The canonical token list is replicated in three places (prompt,
  normalizer cache seed, migration seed). A guard test
  (`test_canonical_token_list_matches_seed_migration`) reads the
  migration source and asserts equality so the lists can't drift.
- Coordination with `epic-import-row-rich-detail` (irrd-3): both
  stories touch the extractor prompts. Per AC9 the prompts are now
  function-built, so adding the confidence-score emit instruction
  later is an additive change to the same builder function — minimal
  merge collision surface.

## QA walkthrough
See `_bmad-output/implementation-artifacts/riip-3-qa-walkthrough.md`.
