# Story eri-5 — `ingredient_field_completeness` metric + 7 fixtures + baseline

**Status:** done
**Epic:** epic-extractor-richer-ingredients
**Branch:** main

## Goal

Add a per-field ingredient extraction accuracy metric
(`ingredient_field_completeness`) with a paired hallucination anti-metric
(`ingredient_hallucination_rate`). Seed 7 fixtures — 3 happy-path + 4
negative-case — that anchor the historically-broken regressions
(clove, gram, stalks, range, substring, no-hallucinated-notes, mixed
structure). Commit a baseline JSON and register both metrics in
`eval.config.yaml` under a new `ingredient_fidelity` suite.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | `ingredient_field_completeness` function scoring qty/unit/name/notes per field, per extractor, and overall | ✅ Done — `services/eval/src/metrics/ingredient_field_completeness.py` |
| AC2 | `ingredient_hallucination_rate` sub-metric in the same module | ✅ Done — returned as `ingredient_hallucination_rate` in the result dict |
| AC3 | Quantity scoring: ±5% tolerance | ✅ Done |
| AC4 | Text scoring: case-insensitive exact match | ✅ Done |
| AC5 | Null-vs-null correctness semantics | ✅ Done — both sides null counts as 1.0; GT-null + extracted-non-null tallies a hallucination |
| AC6 | 7 fixtures: clove jsonld, gram jsonld, stalks text, no-notes text, pinchful substring text, range jsonld, mixed-structure jsonld | ✅ Done — `services/eval/fixtures/ingredient_fidelity/` |
| AC7 | Each fixture has all 4 fields (qty/unit/name/notes) explicitly set in ground truth, even if null | ✅ Done — asserted by `test_every_expected_ingredient_has_all_four_fields` |
| AC8 | Baseline JSON in `services/eval/baselines/ingredient_field_completeness_baseline.json` with soft-gate thresholds | ✅ Done |
| AC9 | `eval.config.yaml` registers `ingredient_fidelity: [ingredient_field_completeness, ingredient_hallucination_rate]` with soft-gate thresholds | ✅ Done |
| AC10 | Pre-ERI eval regression pinning — existing fixtures still pass | ✅ Done — `npx nx run eval:test` reports 126 → 140 passed (+14 new); existing 126 unchanged |

## File List

### New
- `services/eval/src/metrics/ingredient_field_completeness.py` —
  metric function returning `{per_field, per_extractor, overall,
  sample_count, ingredient_hallucination_rate}`
- `services/eval/fixtures/ingredient_fidelity/1_clove_garlic_jsonld.yaml`
- `services/eval/fixtures/ingredient_fidelity/300_gram_vinegar_jsonld.yaml`
- `services/eval/fixtures/ingredient_fidelity/2_stalks_celery_text.yaml`
- `services/eval/fixtures/ingredient_fidelity/no_notes_simple_text.yaml`
- `services/eval/fixtures/ingredient_fidelity/pinchful_substring_text.yaml`
- `services/eval/fixtures/ingredient_fidelity/range_quantity_jsonld.yaml`
- `services/eval/fixtures/ingredient_fidelity/mixed_structure_jsonld.yaml`
- `services/eval/baselines/ingredient_field_completeness_baseline.json`
- `services/eval/tests/test_ingredient_field_completeness.py` — 14 tests

### Modified
- `services/eval/eval.config.yaml` — new `ingredient_fidelity` suite +
  two soft-gate threshold entries

## Metric contract

```python
compute_ingredient_field_completeness(
    pairs: Iterable[tuple[dict, dict]]
) -> dict[str, Any]
```

Returns:

```
{
  "per_field":       {"quantity": {"score": float|None, "sample_count": int}, ...},
  "per_extractor":   {"json_ld_parse_pass": {...}, "ai": {...}, ...},
  "overall":         float | None,              # mean of per-field means
  "sample_count":    int,                       # total field slots scored
  "ingredient_hallucination_rate": float | None # GT-null + extracted-non-null / all slots
}
```

## Soft-gate thresholds

- `ingredient_field_completeness_overall_min: 0.85`
- `ingredient_hallucination_rate_overall_max: 0.10`
- `_enforcement: soft` — reported-only in v1; never CI-blocking
- Hard-gate promotion trigger (tracked in follow-up `eri-hard-gate`):
  - 7 days post-ship with overall ≥ 0.85
  - 0 `IngredientParseFailure` audit rows in last 48h
  - 0 new `UnitAliasMiss` tied to the 15 eri-4a seeds

## Fixture choice rationale

| Fixture | Why |
|--|--|
| `1_clove_garlic_jsonld.yaml` | Primary regression: `clove` no longer folds into `name` |
| `300_gram_vinegar_jsonld.yaml` | Metric units land + alias `gram→g` |
| `2_stalks_celery_text.yaml` | text_extractor + eri-4b alias `stalks→stalk` |
| `no_notes_simple_text.yaml` | Anti-hallucination (notes must be null when source has no qualifier) |
| `pinchful_substring_text.yaml` | Substring-ambiguity rule (`pinchful` ≠ `pinch`) |
| `range_quantity_jsonld.yaml` | Range rule: q=first, notes="to N units" |
| `mixed_structure_jsonld.yaml` | Subset-filter + splice-in-order (eri-3b) |

## Implementation notes

- **Fixture format.** YAML with `source_type: jsonld | text | image`,
  a `source_strings` / `source_text` input, and an `expected`
  ground-truth block. Keeps the metric test pure-Python — no OpenAI
  calls required.
- **No wiring into `fixture_runner.py` yet.** The existing runner
  scans `text/`, `images/`, `urls/`, pairs them with `expected/*.json`,
  and runs the real extractor against real OpenAI. The new
  ingredient-fidelity suite is a different shape (small focused
  examples, YAML, meant for unit-test-speed feedback) — wiring it
  into the end-to-end runner is deferred to the production flip
  (eri-6) where we'd also want real API calls.
- **`per_extractor` key.** When the `extracted` recipe dict carries
  `extractor_used` (e.g. `"json_ld_parse_pass"`, `"ai"`,
  `"vision_ai"`), the metric buckets scores by extractor for
  attribution.

## Verification

- `npx nx run eval:test` — 140 passed (was 126; +14 new) / 0 failed
- `npx nx run eval:lint` — clean
- `cd services/eval && poetry run pytest tests/test_ingredient_field_completeness.py -v` — 14 passed
- Existing 126 tests still pass — pre-ERI regression pin held
