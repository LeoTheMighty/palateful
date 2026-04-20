# Story efi-8 — Eval: `field_inference_accuracy` + `hallucination_rate` metrics + baseline

**Status:** done
**Epic:** epic-extractor-field-inference
**Depends on:** efi-3 (persisted `inferred_fields` + `confidence_score` in `parsed_recipe`).

## Scope

Two new soft-gate eval metrics for the `EXTRACTOR_INFER_MISSING_FIELDS`
pipeline:

1. `field_inference_accuracy` — how close inferred values land to
   ground truth across the 9 inferable fields. Numeric ±20% (servings
   ±1 floor), enum exact-match case-insensitive, description
   SequenceMatcher ≥ 0.6 or raw ratio.
2. `hallucination_rate` — anti-metric. Counts (fixture × inferable-field)
   pairs where GT has a value AND extractor marked as inferred (the
   model guessed when the source had the answer).

Registered in `eval.config.yaml` under `field_inference`. Baseline
JSON placeholder at `services/eval/baselines/field_inference_baseline.json`
with null sentinels — populated by the first real run.

## Implementation notes

- Both metrics consume `Iterable[tuple[dict, dict]]` pairs where
  `(extracted, expected)`. Callers iterate fixtures and produce pairs
  by running extractors on inputs then joining with expected outputs.
- `INFERABLE_FIELDS` imported from `utils.services.recipe_extractors.inference_prompt`
  — single source of truth (same tuple backend extractors, guardrails,
  and submit_correction use).
- `json_ld` extractions always emit `inferred_fields: []` so they
  contribute zero pairs to either metric. Not a bug; by design.
- 19 unit tests cover: numeric tolerance (in/out + servings floor),
  case-insensitive enum match, description ≥0.6 vs raw ratio, missing
  ground truth, not-flagged, overall-mean math, defensive non-dict
  inputs, per-field breakdown on hallucination, whitespace-only GT
  handling, non-list `inferred_fields` tolerance.

## File list

- `services/eval/src/metrics/field_inference_accuracy.py` [NEW]
- `services/eval/src/metrics/hallucination_rate.py` [NEW]
- `services/eval/baselines/field_inference_baseline.json` [NEW] — placeholder
- `services/eval/eval.config.yaml` [MODIFY] — `field_inference` section + thresholds
- `services/eval/README.md` [MODIFY] — doc section
- `services/eval/tests/test_field_inference_metrics.py` [NEW] — 19 tests

## Acceptance criteria — coverage

| AC | How |
|----|-----|
| 1 | `field_inference_accuracy.py` — numeric ±20% + servings ±1 floor + exact case-insensitive enum + SequenceMatcher description. Per-field means + overall. |
| 2 | `hallucination_rate.py` — counts flagged-as-inferred-despite-gt-present pairs. Rate = hallucinations / extractable_pairs. |
| 3 | `eval.config.yaml` — `field_inference` metrics section + soft-gate thresholds. |
| 4 | Both metrics take per-pair iterables → any runner can iterate per-extractor and pass per-extractor pairs. json_ld contributes zero pairs by construction. |
| 5 | `services/eval/baselines/field_inference_baseline.json` placeholder committed — structure defined even without real numbers. |
| 6 | Runner callers emit metric output as part of the standard results payload (wiring in runner not touched — metrics are functions the runner invokes). |
| 7 | 19 unit tests on synthetic mock pairs cover every score branch. |
| 8 | README documents soft-gate status + the "threshold tightens post-ship from correction-log data" plan. |
