# eri-6 QA walkthrough — extractor flag rollout runbook

Docs-only story. No test suite impact.

## Smoke

1. **Runbook exists and is readable.**
   ```bash
   test -f docs/EXTRACTOR_FLAG_ROLLOUT.md && wc -l docs/EXTRACTOR_FLAG_ROLLOUT.md
   ```

2. **Four steps + two rollback drills are present.**
   ```bash
   grep -c "^### Step" docs/EXTRACTOR_FLAG_ROLLOUT.md  # -> 4
   grep -c "^### Scenario:" docs/EXTRACTOR_FLAG_ROLLOUT.md  # -> 3 (parse-pass off, full rollback, migration rollback)
   ```

3. **Three audit types are documented with drill commands.**
   ```bash
   grep -E "IngredientFieldCoverage|IngredientParseFailure|IngredientParsePathological" docs/EXTRACTOR_FLAG_ROLLOUT.md
   ```

4. **Hard-gate promotion criteria cross-reference the baseline.**
   ```bash
   grep "7 days" docs/EXTRACTOR_FLAG_ROLLOUT.md
   grep "7 days" services/eval/baselines/ingredient_field_completeness_baseline.json
   ```

## Ops rehearsal (recommended before first prod flip)

1. Copy the sign-off log from the runbook into a shared doc / ticket.
2. Apply the migrations to staging.
3. Flip each flag in order on staging; run the verification step
   after each flip.
4. Rehearse the two rollback drills end-to-end.
5. Only then flip in prod.

## What's deferred
- **Hard-gate promotion** — separate story `eri-hard-gate` triggered by
  the 7-days-clean criteria in the baseline.
- **Retirement of `_CANONICAL_RULE`** — once `EXTRACTOR_EMIT_CANONICAL_UNITS`
  is flipped off and stable for 24 h, a follow-up PR should remove the
  legacy code path entirely.
