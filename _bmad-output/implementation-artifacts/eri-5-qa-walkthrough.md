# eri-5 QA walkthrough — ingredient_field_completeness + 7 fixtures

Eval-service only. No prod surface. Soft-gate metric; no CI block yet.

## Pre-reqs
- Python 3.13, Poetry, NX.
- PyYAML (comes with eval's poetry env).

## Smoke

1. **Metric tests pass.**
   ```bash
   cd services/eval && poetry run pytest tests/test_ingredient_field_completeness.py -v
   ```
   Expected: 14 passed.

2. **Full eval suite + lint.**
   ```bash
   npx nx run eval:test
   npx nx run eval:lint
   ```
   Expected: 140 passed (was 126, +14), clean lint.

## Fixture sanity

3. **All 7 fixtures parse and have the 4 required ground-truth fields.**
   The tests `test_exactly_seven_ingredient_fidelity_fixtures_exist`
   and `test_every_expected_ingredient_has_all_four_fields` enforce
   this. Run them directly:
   ```bash
   cd services/eval && poetry run pytest \
     tests/test_ingredient_field_completeness.py::test_exactly_seven_ingredient_fidelity_fixtures_exist \
     tests/test_ingredient_field_completeness.py::test_every_expected_ingredient_has_all_four_fields -v
   ```

4. **Perfect-extraction smoke — metric returns 1.0 for every fixture
   when extracted == expected.**
   Covered by `test_perfect_extraction_scores_one`.

## Baseline sanity

5. **Baseline file is valid JSON, soft-gated, 0.85 threshold.**
   ```bash
   cd services/eval && poetry run python -c "
   import json
   data = json.loads(open('baselines/ingredient_field_completeness_baseline.json').read())
   assert data['thresholds']['_enforcement'] == 'soft'
   assert data['thresholds']['ingredient_field_completeness_overall_min'] == 0.85
   print('OK')
   "
   ```

## Config sanity

6. **`eval.config.yaml` registers the new suite.**
   ```bash
   cd services/eval && poetry run python -c "
   import yaml
   cfg = yaml.safe_load(open('eval.config.yaml').read())
   assert cfg['metrics']['ingredient_fidelity'] == ['ingredient_field_completeness', 'ingredient_hallucination_rate']
   print('OK')
   "
   ```

## Rollback behavior

7. The metric + fixtures are additive — no existing behavior changed.
   Full `npx nx run eval:test` confirms pre-ERI fixtures still pass.

## What's deferred

- **Real-API eval run.** The fixtures + metric wire up but no end-to-end
  run with real OpenAI is triggered here. That's gated on the production
  flag flip (eri-6) + sufficient prod traffic to form a meaningful
  baseline.
- **Hard-gate promotion.** Follow-up story `eri-hard-gate` — trigger:
  7 days post-ship + 0 `IngredientParseFailure` + no new `UnitAliasMiss`
  tied to the 15 eri-4a seeds.
