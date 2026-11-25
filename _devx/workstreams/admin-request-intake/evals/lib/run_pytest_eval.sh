#!/usr/bin/env bash
# run_pytest_eval.sh — shared runner for admin-request-intake's pytest-backed
# evals (plan 1e84ad). Each evals/E-*.sh wrapper pins this file's sha256, and
# this file pins the harness's, so Gate 4's lock on a wrapper covers
# everything the wrapper runs.
#
# Usage: run_pytest_eval.sh <E-id> <test path, repo-relative> <test sha256> <min tests>
#
# Exit codes — what Gate 4 and a human must read:
#   0  GREEN — every test passed, and at least <min tests> ran.
#   1  RED   — at least one test FAILED (an assertion, or a RED: pytest.fail).
#   3  EVAL-TAMPERED or EVAL-WRONG-REASON — the eval itself is broken or
#      edited, or the environment is: a collection error, a fixture error
#      (e.g. Postgres unreachable), a skip, or fewer tests than declared.
#      Nonzero, so Gate 4 counts it — which is why every RED-report quote is
#      read, and why this runner prints which kind of nonzero it is.
#
# Why not `poetry run pytest <file>` directly: services/api's addopts carry
# --cov with fail_under = 100, so a single-file run exits 1 even when every
# test passes (measured 2026-11-24). `-o addopts=""` removes that.
#
# Needs a reachable Postgres for the throwaway database
# (DEVREQ_EVAL_ADMIN_URL, default postgres:postgres@localhost:5432/postgres):
# `docker compose up -d db` locally; CI's test job provides one.
set -uo pipefail

EID="${1:?E-id}"; TEST_REL="${2:?test path}"; TEST_SHA="${3:?test sha256}"; MIN_TESTS="${4:?min tests}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
HARNESS_REL="services/api/tests/devreq_harness.py"
HARNESS_SHA="fc42afd49782a60ac759fa0165bd46d510bdd2f1b37690ada0f4b70aaaf779c8"

sha256_of() { python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }

for pair in "$TEST_REL=$TEST_SHA" "$HARNESS_REL=$HARNESS_SHA"; do
  rel="${pair%%=*}"; want="${pair#*=}"
  if [[ ! -f "$REPO/$rel" ]]; then
    echo "EVAL-TAMPERED $EID: $rel is missing"; exit 3
  fi
  got="$(sha256_of "$REPO/$rel")"
  if [[ "$got" != "$want" ]]; then
    echo "EVAL-TAMPERED $EID: $rel sha256 $got != pinned $want — fix the code, not the eval; a genuinely wrong eval is 'devx revise'"
    exit 3
  fi
done

cd "$REPO/services/api" || { echo "EVAL-WRONG-REASON $EID: cannot cd to services/api"; exit 3; }
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/test}"
JUNIT="$(mktemp "${TMPDIR:-/tmp}/devreq-eval-XXXXXX")"
trap 'rm -f "$JUNIT"' EXIT

poetry run pytest -o addopts="" -p no:cacheprovider -q -rfEs -W ignore::DeprecationWarning \
  --junitxml="$JUNIT" "${TEST_REL#services/api/}"
PYTEST_RC=$?

python3 - "$EID" "$JUNIT" "$PYTEST_RC" "$MIN_TESTS" <<'PY'
import sys
import xml.etree.ElementTree as ET

eid, junit, rc, min_tests = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
try:
    root = ET.parse(junit).getroot()
except Exception as exc:  # no report at all: pytest never got going
    print(f"EVAL-WRONG-REASON {eid}: no junit report (pytest exit {rc}): {exc}")
    sys.exit(3)
cases = root.iter("testcase")
tests = failed = errored = skipped = 0
red, broken = [], []
for case in cases:
    tests += 1
    name = case.get("name")
    if case.find("failure") is not None:
        failed += 1
        red.append(name)
    elif case.find("error") is not None:
        errored += 1
        broken.append(name)
    elif case.find("skipped") is not None:
        skipped += 1
        broken.append(name + " (skipped)")
passed = tests - failed - errored - skipped
print(f"EVAL {eid}: tests={tests} passed={passed} failed={failed} errors={errored} skipped={skipped} pytest_exit={rc}")
if rc not in (0, 1):
    print(f"EVAL-WRONG-REASON {eid}: pytest exit {rc} (collection or usage error), not a test failure")
    sys.exit(3)
if errored or skipped:
    print(f"EVAL-WRONG-REASON {eid}: errors or skips mean the eval did not run as written: {broken}")
    sys.exit(3)
if tests < min_tests:
    print(f"EVAL-WRONG-REASON {eid}: {tests} tests ran, the eval declares {min_tests}")
    sys.exit(3)
if failed:
    print(f"EVAL-RED {eid}: {failed} failing: {red}")
    sys.exit(1)
print(f"EVAL-GREEN {eid}")
sys.exit(0)
PY
