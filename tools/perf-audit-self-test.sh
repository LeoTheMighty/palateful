#!/usr/bin/env bash
# ptd-8 — self-test for the perf-audit assert-logic.
#
# Feeds a canned observed CSV (tools/perf-audit-test-fixtures/observed.csv)
# into tools/perf-audit-diff.py against two synthetic budgets:
#
#   regression.yaml — under-sized; diff.py MUST exit 1.
#   baseline.yaml   — sized to match; diff.py MUST exit 0.
#
# If either branch returns the wrong exit code, the assert-logic has
# regressed — CI fails. "Tests for the test."
#
# Exit codes:
#   0 — both branches behaved as expected.
#   1 — one or both branches failed the expectation.
#   2 — tooling error.

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIFF_TOOL="$ROOT/tools/perf-audit-diff.py"
FIXTURES="$ROOT/tools/perf-audit-test-fixtures"

if [ ! -x "$DIFF_TOOL" ]; then
  echo "perf-audit-self-test: diff helper $DIFF_TOOL missing." >&2
  exit 2
fi
for f in observed.csv regression.yaml baseline.yaml; do
  if [ ! -f "$FIXTURES/$f" ]; then
    echo "perf-audit-self-test: fixture $FIXTURES/$f missing." >&2
    exit 2
  fi
done

failures=0

# 1. Regression scenario must exit 1.
set +e
"$DIFF_TOOL" --mode assert --budget "$FIXTURES/regression.yaml" \
  < "$FIXTURES/observed.csv" > /dev/null 2>&1
rc=$?
set -e
if [ "$rc" -ne 1 ]; then
  echo "perf-audit-self-test: regression.yaml expected exit 1, got $rc" >&2
  failures=$((failures + 1))
fi

# 2. Baseline scenario must exit 0.
set +e
"$DIFF_TOOL" --mode assert --budget "$FIXTURES/baseline.yaml" \
  < "$FIXTURES/observed.csv" > /dev/null 2>&1
rc=$?
set -e
if [ "$rc" -ne 0 ]; then
  echo "perf-audit-self-test: baseline.yaml expected exit 0, got $rc" >&2
  failures=$((failures + 1))
fi

if [ "$failures" -gt 0 ]; then
  echo "perf-audit-self-test: $failures branch(es) failed — assert-logic regressed." >&2
  exit 1
fi

echo "perf-audit-self-test: OK (regression detected, baseline clean)"
exit 0
