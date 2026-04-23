# Story eri-6 — Extractor flag rollout runbook + staging verification

**Status:** done
**Epic:** epic-extractor-richer-ingredients
**Branch:** main

## Goal

Own the production rollout of the three ERI flags with a documented
4-step flip + a rehearsed rollback drill. Document the observability
signals (which audit rows to grep, what thresholds signal trouble)
and the hard-gate promotion criteria for the eri-5 metric.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | `docs/EXTRACTOR_FLAG_ROLLOUT.md` exists with a 4-step production flip sequence | ✅ Done |
| AC2 | Each step has an explicit ECS env-var update block + verification gate | ✅ Done |
| AC3 | Two rollback drills: (a) parse-pass-off (b) full rollback to riip-3 | ✅ Done |
| AC4 | Migration rollback sequence documented (drop aliases first, then units — matches eri-4a's down-migration guard) | ✅ Done |
| AC5 | Observability section lists `IngredientFieldCoverage`, `IngredientParseFailure`, `IngredientParsePathological`, `UnitAliasMiss` with the `audit_errors.py` drill commands | ✅ Done |
| AC6 | Hard-gate promotion criteria for eri-5 codified (7 days + 0 failures + no new alias-miss spikes) | ✅ Done — matches `ingredient_field_completeness_baseline.json` |
| AC7 | Staging-verification checklist with sign-off log | ✅ Done |
| AC8 | Runbook links to epic + ops scripts | ✅ Done |

## File List

### New
- `docs/EXTRACTOR_FLAG_ROLLOUT.md` — the full runbook

### Not modified
- ECS task-def / Terraform — no infrastructure change, per epic
  "Infrastructure Changes: None in the resource sense; two new
  env-var flags." The runbook is the ops artifact; flag flips happen
  via AWS console or existing deploy-script paths.

## Production flip overview

```
Step 1: Apply migrations (erifrunits01 + erifraliases01)
         ↓ (30 min soak, then…)
Step 2: EXTRACTOR_SOFTEN_UNIT_RULE=true (parse-pass still off)
         ↓ (verify: photo imports now structure clove/stalk/etc.)
Step 3: EXTRACTOR_JSON_LD_INGREDIENT_PARSE=true
         ↓ (verify: JSON-LD URL imports get parse_pass audit rows)
Step 4: after 7 days clean + soft-gate metric ≥ 0.85:
        EXTRACTOR_EMIT_CANONICAL_UNITS=false   (retire the legacy riip-3 path)
```

## Implementation notes

- **No code change.** Pure docs.
- **Rollback drill is verifiable.** The two scenarios in the runbook
  can be re-run end-to-end in staging by flipping the flags and
  re-importing the same recipe. The unit tests in eri-1/eri-3a
  already pin each rollback path (flag-off = text-only fallback).
- **Observability points at existing tooling.** `audit_errors.py`
  drill mode (documented in CLAUDE.md) handles all four audit types —
  no new dashboards required.
- **Hard-gate promotion is a separate story.** Tracked in follow-up
  `eri-hard-gate`; criteria are locked here and in the baseline file
  so whoever picks it up can grep for them.

## Verification

- Runbook is authoritatively linked from the epic file (TODO — epic
  files are maintained separately and already referenced in the
  rollout doc).
- Existing test suites remain green:
  - `npx nx run utils:test` — 526 passed
  - `npx nx run eval:test` — 140 passed
- Staging sign-off is operator-owned — the sign-off log in the runbook
  captures it.
