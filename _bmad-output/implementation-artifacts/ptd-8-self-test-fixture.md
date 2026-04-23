# Story ptd-8 — Self-test synthetic regression fixture

**Epic:** epic-perf-debug-tooling
**Status:** in-progress → review → done
**Owner:** /dev
**Started:** 2026-04-23

## Context

ptd-4's `tools/perf-audit-diff.py` is the critical assert-logic
behind the CI guard. If a refactor silently breaks its comparator
(e.g., off-by-one, wrong field lookup, exception-swallow that returns
exit 0), every downstream PR passes regardless of actual regressions
and the whole guard becomes noise. ptd-8 ships a self-test that
proves the assert-logic still flags a known-bad budget.

> Tests for the test.

## Implementation

### New fixtures

- `tools/perf-audit-test-fixtures/observed.csv` — canned 5-GET home
  observed CSV (matches the real ptd-2 output).
- `tools/perf-audit-test-fixtures/regression.yaml` — synthetic budget
  with `home.total = 3` and two endpoints pinned to 0. Feeding
  `observed.csv` against this should produce violations.
- `tools/perf-audit-test-fixtures/baseline.yaml` — synthetic budget
  sized to match `observed.csv` exactly. Feeding the same CSV should
  produce no violations (happy-path confirmation — guards against a
  false-positive regression in the comparator).

### New script

- `tools/perf-audit-self-test.sh` — pipes `observed.csv` into
  `perf-audit-diff.py --mode assert` twice:
  1. Against `regression.yaml` — expects exit 1 (detected violations).
  2. Against `baseline.yaml` — expects exit 0 (no violations).
  Both branches must match; any deviation exits 1 with a clear
  "assert-logic regressed" message.

The check runs in under 100ms — safe to run as a cheap CI step
before `bin/perf-audit --assert` so a broken comparator fails fast.

## Acceptance Criteria

- [x] (1) `tools/perf-audit-test-fixtures/regression.yaml` is a
  synthetic budget with one screen (home) pinned under the observed
  count.
- [x] (2) CI runs the self-test — **wired in ptd-5**. The script is
  runnable today via `tools/perf-audit-self-test.sh`.
- [x] (3) Regression-detection logic broken by a bad refactor
  produces the self-test failing. Verified locally by temporarily
  monkey-patching `assert_budget` to return `[]`; self-test
  correctly exited 1 with "expected exit 1, got 0".
- [x] (4) Documented in `docs/PERFORMANCE_OPS.md` — **deferred to
  ptd-7** (write-docs-last).

## QA walkthrough

```bash
tools/perf-audit-self-test.sh
# → "perf-audit-self-test: OK (regression detected, baseline clean)"

# Simulate a broken comparator: edit perf-audit-diff.py's
# assert_budget to `return []` unconditionally, re-run:
tools/perf-audit-self-test.sh
# → "regression.yaml expected exit 1, got 0" then exit 1
# Revert the edit.
```

## Non-goals (deferred)

- **Shell-side exit-code matrix** (strict vs warn-mode on `bin/perf-audit`
  with the regression fixture) — the self-test targets the Python
  comparator, which is the actually-regression-prone surface. Strict-
  mode is a one-line bash branch; adding a synthetic matrix for it
  is scope creep.
- **Self-test-for-the-self-test** — we stop the tower-of-tests at
  one layer.

## File List

- `tools/perf-audit-test-fixtures/observed.csv` (new)
- `tools/perf-audit-test-fixtures/regression.yaml` (new)
- `tools/perf-audit-test-fixtures/baseline.yaml` (new)
- `tools/perf-audit-self-test.sh` (new)
- `_bmad-output/implementation-artifacts/ptd-8-self-test-fixture.md` (new — this file)
