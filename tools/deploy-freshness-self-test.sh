#!/usr/bin/env bash
#
# Self-test for .github/workflows/deploy-freshness.yml (E-7 / FR-6).
#
# WHY THIS EXISTS
# ---------------
# E-7's load-bearing observation is step 5: "register a newer ACTIVE
# task-definition revision without deploying it -> the reported gap is
# unchanged". A check that resolves the task definition by *family name*
# returns the newest REGISTERED revision, not the one ECS is RUNNING, so a
# frozen prod would read as fresh — green and blind, masking exactly the
# freeze the check exists to catch.
#
# Observing that against live prod means registering a revision in the
# production account, which is a prod mutation that cannot be automated. This
# harness proves the same property offline and on every PR, so the trap cannot
# be reintroduced by a "simplification" between one manual observation and the
# next.
#
# It does NOT replace the live E-7 observation (the workflow firing unattended
# against real ECS is not simulable). It pins the logic; observation pins the
# mechanism.
#
# HOW
# ---
# The bash body is EXTRACTED FROM THE WORKFLOW YAML at run time, never copied.
# A copy would drift silently and the guard would pass against code that is no
# longer shipped. Extraction fails loudly if the step is renamed or restructured.
#
# Usage: bash tools/deploy-freshness-self-test.sh
# Exit:  0 all cases pass, 1 any case fails or extraction fails.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/deploy-freshness.yml"
STEP_NAME="Measure gap between running image and its commit date"

[ -f "$WORKFLOW" ] || { echo "FAIL: $WORKFLOW not found"; exit 1; }

SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT

# ── Extract the step body ────────────────────────────────────────────────
# Deliberately dependency-free (no PyYAML): this runs in the `lint` job before
# any poetry env is guaranteed. Indentation-based, and strict — a structural
# change to the workflow must break this loudly rather than silently test a
# stale script.
python3 - "$WORKFLOW" "$STEP_NAME" "$SANDBOX/measure.sh" <<'PY'
import sys

path, step_name, out = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(path).read().splitlines()

# Find "- name: <step_name>", then the "run: |" that follows it, then take the
# block of lines indented deeper than the "run:" key.
try:
    i = next(n for n, l in enumerate(lines) if l.strip() == f"- name: {step_name}")
except StopIteration:
    sys.exit(f"EXTRACT FAIL: no step named {step_name!r} in {path}")

try:
    j = next(n for n in range(i + 1, len(lines)) if lines[n].strip() in ("run: |", "run: |-"))
except StopIteration:
    sys.exit(f"EXTRACT FAIL: step {step_name!r} has no literal-block `run:`")

run_indent = len(lines[j]) - len(lines[j].lstrip())
body, body_indent = [], None
for line in lines[j + 1:]:
    if not line.strip():
        body.append("")
        continue
    indent = len(line) - len(line.lstrip())
    if indent <= run_indent:
        break
    if body_indent is None:
        body_indent = indent
    body.append(line[body_indent:])

if not [b for b in body if b.strip()]:
    sys.exit(f"EXTRACT FAIL: empty run block for {step_name!r}")

open(out, "w").write("\n".join(body).rstrip() + "\n")
print(f"extracted {len([b for b in body if b.strip()])} lines from {path}")
PY

# Pull the thresholds from the workflow too, so the test can never assert
# against a threshold the workflow no longer uses.
MAX_GAP_DAYS="$(sed -n 's/^  MAX_GAP_DAYS: *//p' "$WORKFLOW" | head -1)"
CLUSTER="$(sed -n 's/^  CLUSTER: *//p' "$WORKFLOW" | head -1)"
SERVICE="$(sed -n 's/^  SERVICE: *//p' "$WORKFLOW" | head -1)"
[ -n "$MAX_GAP_DAYS" ] && [ -n "$CLUSTER" ] && [ -n "$SERVICE" ] \
  || { echo "FAIL: could not read CLUSTER/SERVICE/MAX_GAP_DAYS from workflow env"; exit 1; }
echo "workflow env: CLUSTER=$CLUSTER SERVICE=$SERVICE MAX_GAP_DAYS=$MAX_GAP_DAYS"

# ── Fake `aws` ───────────────────────────────────────────────────────────
# Answers only the two calls the workflow makes, and records every invocation
# so a case can assert *which* resolution path was taken, not just the number
# that came out.
mkdir -p "$SANDBOX/bin"
cat > "$SANDBOX/bin/aws" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$MOCK_CALL_LOG"

if [ "${1:-}" = "ecs" ] && [ "${2:-}" = "describe-services" ]; then
  printf '%s\n' "$MOCK_RUNNING_TD"
  exit 0
fi

if [ "${1:-}" = "ecs" ] && [ "${2:-}" = "describe-task-definition" ]; then
  key=""
  while [ $# -gt 0 ]; do
    if [ "$1" = "--task-definition" ]; then key="$2"; break; fi
    shift
  done
  image="$(awk -F'\t' -v k="$key" '$1 == k { print $2 }' "$MOCK_TD_MAP")"
  if [ -z "$image" ]; then
    echo "MOCK: no task definition '$key'" >&2
    exit 254
  fi
  printf '%s\n' "$image"
  exit 0
fi

echo "MOCK: unexpected aws call: $*" >&2
exit 253
MOCK
chmod +x "$SANDBOX/bin/aws"

# ── Sandbox git repo with backdated commits ──────────────────────────────
# The workflow dates a deployment with `git log -1 --format=%ct <tag>`, i.e.
# COMMITTER date — so both date envs must be set or the fixture ages wrong.
FROZEN_DAYS=96
FRESH_DAYS=1
now="$(date +%s)"
mk_commit() {  # $1 = age in days, $2 = message -> prints full sha
  local ts=$(( now - $1 * 86400 ))
  GIT_AUTHOR_DATE="$ts +0000" GIT_COMMITTER_DATE="$ts +0000" \
    git -C "$SANDBOX/repo" commit --allow-empty -q -m "$2"
  git -C "$SANDBOX/repo" rev-parse HEAD
}
git init -q "$SANDBOX/repo"
git -C "$SANDBOX/repo" config user.email t@t.t
git -C "$SANDBOX/repo" config user.name t
FROZEN_SHA="$(mk_commit "$FROZEN_DAYS" 'the deployed commit')"
FRESH_SHA="$(mk_commit "$FRESH_DAYS" 'newest main')"

ECR=592349850338.dkr.ecr.us-east-1.amazonaws.com/palateful/api
RUNNING_ARN="arn:aws:ecs:us-east-1:592349850338:task-definition/${SERVICE}:62"
NEWER_ARN="arn:aws:ecs:us-east-1:592349850338:task-definition/${SERVICE}:63"

# ── Runner ───────────────────────────────────────────────────────────────
PASS=0
FAIL=0
CASE_FAIL_MARK=0
run_case() {  # $1 = name, $2 = expected exit; body configured via env
  local name="$1" want="$2" got=0
  CASE_FAIL_MARK="$FAIL"
  MOCK_CALL_LOG="$SANDBOX/calls.log"
  : > "$MOCK_CALL_LOG"
  export MOCK_CALL_LOG
  set +e
  (
    cd "$SANDBOX/repo"
    PATH="$SANDBOX/bin:$PATH" \
    CLUSTER="$CLUSTER" SERVICE="$SERVICE" MAX_GAP_DAYS="$MAX_GAP_DAYS" \
      bash "$SANDBOX/measure.sh"
  ) > "$SANDBOX/out.txt" 2>&1
  got=$?
  set -e
  if [ "$got" -ne "$want" ]; then
    echo "FAIL [$name]: exit $got, want $want"
    sed 's/^/    | /' "$SANDBOX/out.txt"
    FAIL=$((FAIL + 1))
    return 1
  fi
  return 0
}

# Called after a case's output assertions, so a case cannot report "pass" and
# then fail an assertion on the next line.
end_case() {  # $1 = name
  if [ "$FAIL" -eq "$CASE_FAIL_MARK" ]; then
    echo "pass [$1]"
    PASS=$((PASS + 1))
  fi
}

expect_out() {  # $1 = case name, $2 = substring that must appear
  if ! grep -qF -- "$2" "$SANDBOX/out.txt"; then
    echo "FAIL [$1]: output missing: $2"
    sed 's/^/    | /' "$SANDBOX/out.txt"
    FAIL=$((FAIL + 1))
    return 1
  fi
  return 0
}

refute_out() {  # $1 = case name, $2 = substring that must NOT appear
  if grep -qF -- "$2" "$SANDBOX/out.txt"; then
    echo "FAIL [$1]: output contains forbidden string: $2"
    sed 's/^/    | /' "$SANDBOX/out.txt"
    FAIL=$((FAIL + 1))
    return 1
  fi
  return 0
}

export MOCK_TD_MAP="$SANDBOX/td_map.tsv"

# ── Case 1 (E-7 step 5, the load-bearing one) ────────────────────────────
# Prod is frozen on revision :62. A NEWER revision :63 exists as the family's
# newest ACTIVE but was never deployed. The family-name shortcut resolves to
# :63 (fresh, gap 1d, would exit 0 and report green); the correct
# running-revision path resolves to :62 (gap 96d, exits 1).
printf '%s\t%s\n' \
  "$RUNNING_ARN" "$ECR:$FROZEN_SHA" \
  "$NEWER_ARN"   "$ECR:$FRESH_SHA" \
  "$SERVICE"     "$ECR:$FRESH_SHA" \
  > "$MOCK_TD_MAP"
export MOCK_RUNNING_TD="$RUNNING_ARN"
unset SYNTHETIC_GAP_DAYS
name='step5: newer ACTIVE revision registered but not deployed'
if run_case "$name" 1; then
  expect_out "$name" "Running task definition: $RUNNING_ARN" || true
  expect_out "$name" "Deployed image: $ECR:$FROZEN_SHA" || true
  expect_out "$name" "Gap: ${FROZEN_DAYS} day(s)" || true
  # The tell-tale of a family-shortcut regression: the undeployed revision's
  # image or its 1-day gap showing up in the report.
  refute_out "$name" "$FRESH_SHA" || true
  refute_out "$name" "Gap: ${FRESH_DAYS} day(s)" || true
  # And prove the resolution actually went through describe-services rather
  # than reaching a correct number by luck.
  if ! grep -qF "ecs describe-services" "$SANDBOX/calls.log"; then
    echo "FAIL [$name]: never called describe-services"; FAIL=$((FAIL + 1))
  fi
  if grep -qE "describe-task-definition --task-definition ${SERVICE}( |$)" "$SANDBOX/calls.log"; then
    echo "FAIL [$name]: resolved by family name — the shortcut trap"; FAIL=$((FAIL + 1))
  fi
fi
end_case "$name"

# Cases 2-6 map the family name to the SAME image as the running revision, so
# a family-shortcut regression cannot fail them. Only case 1 discriminates on
# the resolution path, which keeps the failure attribution sharp.

# ── Case 2: fresh prod passes ────────────────────────────────────────────
printf '%s\t%s\n' \
  "$NEWER_ARN" "$ECR:$FRESH_SHA" \
  "$SERVICE"   "$ECR:$FRESH_SHA" \
  > "$MOCK_TD_MAP"
export MOCK_RUNNING_TD="$NEWER_ARN"
name='real measurement: freshly deployed prod passes'
if run_case "$name" 0; then
  expect_out "$name" "Gap: ${FRESH_DAYS} day(s)" || true
  expect_out "$name" "Prod image is fresh" || true
fi
end_case "$name"

# ── Case 3: unknown provenance fails ─────────────────────────────────────
printf '%s\t%s\n' \
  "$NEWER_ARN" "$ECR:latest" \
  "$SERVICE"   "$ECR:latest" \
  > "$MOCK_TD_MAP"
name='deployed tag is not a commit in this repo'
if run_case "$name" 1; then
  expect_out "$name" "is not a commit in this repository" || true
fi
end_case "$name"

# ── Cases 4-6 (E-7 steps 3-4): the synthetic-gap dispatch input ──────────
# Frozen fixture throughout, so a synthetic PASS can only come from the
# substitution actually taking effect — not from the fixture being fresh.
printf '%s\t%s\n' \
  "$RUNNING_ARN" "$ECR:$FROZEN_SHA" \
  "$SERVICE"     "$ECR:$FROZEN_SHA" \
  > "$MOCK_TD_MAP"
export MOCK_RUNNING_TD="$RUNNING_ARN"

export SYNTHETIC_GAP_DAYS=$(( MAX_GAP_DAYS + 1 ))
name="synthetic gap ${SYNTHETIC_GAP_DAYS}d (> ${MAX_GAP_DAYS}) fails"
if run_case "$name" 1; then
  expect_out "$name" "SYNTHETIC gap of ${SYNTHETIC_GAP_DAYS}d" || true
  expect_out "$name" "Gap: ${SYNTHETIC_GAP_DAYS} day(s)" || true
  refute_out "$name" "Gap: ${FROZEN_DAYS} day(s)" || true
fi
end_case "$name"

export SYNTHETIC_GAP_DAYS=1
name="synthetic gap 1d (< ${MAX_GAP_DAYS}) passes despite a ${FROZEN_DAYS}d-old fixture"
if run_case "$name" 0; then
  expect_out "$name" "Prod image is fresh (1d" || true
fi
end_case "$name"

export SYNTHETIC_GAP_DAYS="$MAX_GAP_DAYS"
name="synthetic gap ${MAX_GAP_DAYS}d == threshold passes (boundary is inclusive)"
run_case "$name" 0 || true
end_case "$name"
unset SYNTHETIC_GAP_DAYS

echo
echo "deploy-freshness self-test: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
