# Story cmt-3 — Recipe-level timer eval metric + fixture extensions

**Status:** in-progress
**Epic:** epic-cook-mode-timers
**Depends on:** cmt-1 (extractor now emits steps+timers).

## Scope

Add a `timer_extraction_f1` metric to the `RecipeExtractionEvaluator`. Extend three fixtures with an additive `expected_timers` recipe-level multiset (no restructuring of `instructions: string`). The gate is **soft only** — reported, not enforced — per AC5.

## Metric rules

- **Predicted** timers gathered by walking `actual["steps"][i]["timers"]`. If only `instructions` is present, the predicted set is empty (v1 simplification — Dart-regex fallback equivalence is out of scope).
- **Expected** timers gathered from the new top-level `expected_timers` field.
- **Match rule per pair:**
  - Duration: exact OR `|pred - exp| / exp ≤ 0.2`.
  - Label similarity: `difflib.SequenceMatcher(None, pred.lower(), exp.lower()).ratio() >= 0.6`.
  - Both required.
- Greedy 1-1 matching.
- Precision = matched/predicted; recall = matched/expected; F1 = harmonic mean.
- Per-fixture F1 aggregated by arithmetic mean across the suite.

## Fixture picks

- `simple_pasta.json` — 1 timer (cook garlic 1 min).
- `chicken_tikka_masala.json` — 6 timers (bake 15, onion 5, garlic/ginger 1, simmer 15, simmer 5, simmer 5).
- `chocolate_chip_cookies.json` — 2 timers (beat 3 min, bake 10 min).

## File list

- `services/eval/fixtures/expected/simple_pasta.json` [MODIFY] — add `expected_timers`
- `services/eval/fixtures/expected/chicken_tikka_masala.json` [MODIFY] — add `expected_timers`
- `services/eval/fixtures/expected/chocolate_chip_cookies.json` [MODIFY] — add `expected_timers`
- `services/eval/src/evaluators/recipe_extraction_evaluator.py` [MODIFY] — `timer_extraction_f1` metric + aggregation
- `services/eval/tests/test_recipe_extraction_timers.py` [NEW] — synthetic F1 tests + aggregation

## Acceptance criteria

- AC1 — 3 fixtures extended additively with `expected_timers: [{duration_minutes:int,label:str}]`.
- AC2 — `timer_extraction_f1` computed per-fixture with duration slack ±20% + label SequenceMatcher ≥0.6 + greedy 1-1 match.
- AC3 — Metric surfaces in evaluator output alongside existing metrics.
- AC4 — Unit: 3 expected, 2 predicted (1 exact + 1 within-slack) → F1 ≈ 0.80 ±0.05.
- AC5 — Soft gate only; no CI merge-block.
- AC6 — Regression guard noted as manual-review comment — no CI enforcement.
- AC7 — Baseline comment line to be recorded post-merge in evaluator code.
