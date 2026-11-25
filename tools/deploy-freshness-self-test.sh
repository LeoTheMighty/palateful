#!/usr/bin/env bash
#
# Self-test for .github/workflows/deploy-freshness.yml (E-7 / FR-6).
#
# WHY THIS EXISTS
# ---------------
# The check answers one question: has a change that deploys a new image sat on
# main for longer than MAX_OVERDUE_HOURS without reaching prod? Every way of
# getting that wrong is silent. Answer "no" by mistake and prod freezes under a
# green check; answer "yes" by mistake and the check is red forever and stops
# being read — which is what the image-age predicate did to a quiet backend
# for two months before 2026-11-24. So this drives the shipped bash into each
# answer on purpose, including the two that matter most:
#
#   - a burst of backend merges whose LAST deploy failed, then quiet  -> RED
#   - a quiet backend running a months-old image                      -> GREEN
#
# and E-7's original load-bearing observation (step 5): register a newer
# ACTIVE task-definition revision without deploying it and the verdict must
# not move. A check that resolves the task definition by *family name* reads
# the newest REGISTERED revision, not the one ECS is RUNNING, so a frozen prod
# reads as fresh — green and blind.
#
# HOW
# ---
# The bash body is EXTRACTED FROM THE WORKFLOW YAML at run time, never copied.
# A copy would drift silently and the guard would pass against code that is no
# longer shipped. Extraction fails loudly if the step is renamed or restructured.
#
# "Does this range deploy?" is answered by REAL nx running the REAL
# tools/deploy-affected.sh (the script ci.yml's detect-changes runs) inside a
# sandbox git repo that carries the repo's own nx.json and project.json files,
# with backdated commits. Only AWS is mocked. So a case that says "a utils
# change is overdue" is nx's implicitDependencies saying so, not a path list
# this file made up.
#
# It does NOT replace the live E-7 observation (the workflow firing unattended
# against real ECS is not simulable). It pins the logic; observation pins the
# mechanism. tools/deploy-freshness-live-check.sh runs the same body against
# real prod.
#
# Usage: bash tools/deploy-freshness-self-test.sh   (needs `yarn install` first)
# Exit:  0 all cases pass, 1 any case fails or extraction fails.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/deploy-freshness.yml"
CI_WORKFLOW="$REPO_ROOT/.github/workflows/ci.yml"
STEP_NAME="Measure how long prod has been overdue a deploy"

[ -f "$WORKFLOW" ] || { echo "FAIL: $WORKFLOW not found"; exit 1; }
[ -x "$REPO_ROOT/node_modules/.bin/nx" ] \
  || { echo "FAIL: $REPO_ROOT/node_modules/.bin/nx missing — run 'yarn install --frozen-lockfile' first."; \
       echo "      The cases run real nx; without it they could only pass vacuously."; exit 1; }

SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT

# ── Extract the step body ────────────────────────────────────────────────
# Shared with tools/deploy-freshness-live-check.sh, so the offline guard and
# the live check can never end up running different bash.
python3 "$REPO_ROOT/tools/deploy-freshness-extract.py" \
  "$WORKFLOW" "$STEP_NAME" "$SANDBOX/measure.sh"

# Pull the thresholds from the workflow too, so the test can never assert
# against a threshold the workflow no longer uses.
MAX_OVERDUE_HOURS="$(sed -n 's/^  MAX_OVERDUE_HOURS: *//p' "$WORKFLOW" | head -1)"
CLUSTER="$(sed -n 's/^  CLUSTER: *//p' "$WORKFLOW" | head -1)"
SERVICE="$(sed -n 's/^  SERVICE: *//p' "$WORKFLOW" | head -1)"
[ -n "$MAX_OVERDUE_HOURS" ] && [ -n "$CLUSTER" ] && [ -n "$SERVICE" ] \
  || { echo "FAIL: could not read CLUSTER/SERVICE/MAX_OVERDUE_HOURS from workflow env"; exit 1; }
echo "workflow env: CLUSTER=$CLUSTER SERVICE=$SERVICE MAX_OVERDUE_HOURS=$MAX_OVERDUE_HOURS"
GRACE=$(( MAX_OVERDUE_HOURS * 3600 ))

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

# For the one case that needs nx to be unable to answer.
mkdir -p "$SANDBOX/bin-nx-broken"
cat > "$SANDBOX/bin-nx-broken/npx" <<'MOCK'
#!/usr/bin/env bash
echo "MOCK: nx exploded" >&2
exit 1
MOCK
chmod +x "$SANDBOX/bin-nx-broken/npx"

# ── Sandbox nx workspace with backdated commits ──────────────────────────
# The repo's own nx.json and every tracked project.json, read fresh on each
# run (a stale copy would let the project graph drift from the real one), plus
# node_modules and tools/ symlinked from the repo — so `bash
# tools/deploy-affected.sh` inside the sandbox is the shipped script.
#
# The workflow dates commits by COMMITTER date, so both date envs are set or
# the fixture ages wrong.
REPO="$SANDBOX/repo"
NOW="$(date +%s)"
DAY=86400
HOUR=3600
new_repo() {
  rm -rf "$REPO"
  mkdir -p "$REPO"
  git -C "$REPO" init -q
  git -C "$REPO" config user.email t@t.t
  git -C "$REPO" config user.name t
  git -C "$REPO" config commit.gpgsign false
  cp "$REPO_ROOT/nx.json" "$REPO/nx.json"
  [ ! -f "$REPO_ROOT/.nxignore" ] || cp "$REPO_ROOT/.nxignore" "$REPO/.nxignore"
  printf '{"name":"deploy-freshness-sandbox","private":true}\n' > "$REPO/package.json"
  git -C "$REPO_ROOT" ls-files '*project.json' | while IFS= read -r f; do
    mkdir -p "$REPO/$(dirname "$f")"
    cp "$REPO_ROOT/$f" "$REPO/$f"
  done
  ln -s "$REPO_ROOT/node_modules" "$REPO/node_modules"
  ln -s "$REPO_ROOT/tools" "$REPO/tools"
  printf 'node_modules\ntools\n.nx\n' > "$REPO/.gitignore"
  git -C "$REPO" add -A
  commit_at $(( 400 * DAY )) 'workspace'
}
commit_at() {  # $1 = age in seconds, $2 = message (changes already staged)
  local ts=$(( NOW - $1 ))
  GIT_AUTHOR_DATE="$ts +0000" GIT_COMMITTER_DATE="$ts +0000" \
    git -C "$REPO" commit -q --allow-empty -m "$2"
}
mk() {  # $1 = age in seconds, $2 = file to change, $3 = message -> prints sha
  # tools/ and node_modules/ are symlinks into the REAL repo: writing through
  # them would edit the working tree this test is checking.
  case "$2" in
    tools/*|node_modules/*|*..*) echo "mk: refusing fixture path '$2' (escapes the sandbox)" >&2; exit 1 ;;
  esac
  mkdir -p "$REPO/$(dirname "$2")"
  printf '%s\n' "$3" >> "$REPO/$2"
  git -C "$REPO" add "$2"
  commit_at "$1" "$3"
  git -C "$REPO" rev-parse HEAD
}
revert_head() {  # $1 = age in seconds -> prints sha
  local ts=$(( NOW - $1 ))
  GIT_AUTHOR_DATE="$ts +0000" GIT_COMMITTER_DATE="$ts +0000" \
    git -C "$REPO" revert --no-edit HEAD >/dev/null
  git -C "$REPO" rev-parse HEAD
}
# main is read as origin/main, never HEAD (a dispatch checks out a branch).
set_main() { git -C "$REPO" update-ref refs/remotes/origin/main "${1:-HEAD}"; }

ECR=592349850338.dkr.ecr.us-east-1.amazonaws.com/palateful/api
RUNNING_ARN="arn:aws:ecs:us-east-1:592349850338:task-definition/${SERVICE}:62"
NEWER_ARN="arn:aws:ecs:us-east-1:592349850338:task-definition/${SERVICE}:63"
export MOCK_TD_MAP="$SANDBOX/td_map.tsv"
# prod_runs <image-tag> [<tag the family name resolves to>]: the running
# revision serves the first; the family name serves the second (default: the
# same), so only the step-5 case can tell the two resolution paths apart.
prod_runs() {
  printf '%s\t%s\n' \
    "$RUNNING_ARN" "$ECR:$1" \
    "$SERVICE"     "$ECR:${2:-$1}" \
    > "$MOCK_TD_MAP"
  export MOCK_RUNNING_TD="$RUNNING_ARN"
}

# ── Runner ───────────────────────────────────────────────────────────────
PASS=0
FAIL=0
CASE_FAIL_MARK=0
OUT="$SANDBOX/out.txt"
GH_OUT="$SANDBOX/github_output.txt"
run_case() {  # $1 = name, $2 = expected exit; $3 = PATH prefix (optional)
  local name="$1" want="$2" pathpre="${3:-$SANDBOX/bin}" got=0
  CASE_FAIL_MARK="$FAIL"
  MOCK_CALL_LOG="$SANDBOX/calls.log"
  : > "$MOCK_CALL_LOG"
  : > "$GH_OUT"
  export MOCK_CALL_LOG
  set +e
  (
    cd "$REPO"
    PATH="$pathpre:$SANDBOX/bin:$PATH" \
    CLUSTER="$CLUSTER" SERVICE="$SERVICE" MAX_OVERDUE_HOURS="$MAX_OVERDUE_HOURS" \
    GITHUB_OUTPUT="$GH_OUT" NX_DAEMON=false NX_NO_CLOUD=true \
      bash "$SANDBOX/measure.sh"
  ) > "$OUT" 2>&1
  got=$?
  set -e
  if [ "$got" -ne "$want" ]; then
    echo "FAIL [$name]: exit $got, want $want"
    sed 's/^/    | /' "$OUT"
    FAIL=$((FAIL + 1))
    return 1
  fi
  return 0
}

# Called after a case's output assertions, so a case cannot report "pass" and
# then fail an assertion on the next line.
end_case() {  # $1 = name
  # SELFTEST_VERBOSE=1 prints each case's full step output: the evidence,
  # not just the verdict.
  [ -z "${SELFTEST_VERBOSE:-}" ] || sed 's/^/    | /' "$OUT"
  if [ "$FAIL" -eq "$CASE_FAIL_MARK" ]; then
    echo "pass [$1]"
    PASS=$((PASS + 1))
  fi
}

expect_out() {  # $1 = case name, $2 = substring that must appear
  if ! grep -qF -- "$2" "$OUT"; then
    echo "FAIL [$1]: output missing: $2"
    sed 's/^/    | /' "$OUT"
    FAIL=$((FAIL + 1))
    return 1
  fi
  return 0
}

refute_out() {  # $1 = case name, $2 = substring that must NOT appear
  if grep -qF -- "$2" "$OUT"; then
    echo "FAIL [$1]: output contains forbidden string: $2"
    sed 's/^/    | /' "$OUT"
    FAIL=$((FAIL + 1))
    return 1
  fi
  return 0
}

# The verdict the notify steps act on, read from $GITHUB_OUTPUT — not the
# exit code, which cannot tell "stale" from "died before measuring".
expect_verdict() {  # $1 = case name, $2 = stale|fresh|unknown|none
  local got
  got="$(sed -n 's/^verdict=//p' "$GH_OUT" | tail -1)"
  [ -n "$got" ] || got=none
  if [ "$got" != "$2" ]; then
    echo "FAIL [$1]: verdict '$got', want '$2'"
    sed 's/^/    | /' "$OUT"
    FAIL=$((FAIL + 1))
    return 1
  fi
  return 0
}

short() { git -C "$REPO" rev-parse --short "$1"; }

# ── Wiring assertions (static, on the YAML *around* the extracted body) ──
# The behavioural cases below run the measure step directly, with the
# synthetic input set by this harness and AWS mocked out. That proves the
# LOGIC and is deliberately blind to everything that has to be true for the
# logic to ever run: a schedule to fire on, credentials to reach ECS with, an
# actual wire from the dispatch input to the env var the body reads, and the
# one shared definition of "deploys". Each of those fails *silently* — the
# self-test stays green, the live check does not run or measures something
# else — which is the same green-and-blind failure mode step 5 exists to
# catch. So assert them too.
python3 - "$WORKFLOW" "$STEP_NAME" "$SANDBOX/measure.sh" "$CI_WORKFLOW" > "$SANDBOX/wiring.txt" <<'PY'
import re
import sys

wf, step_name, measured, ci_wf = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
lines = open(wf).read().splitlines()
body = open(measured).read()

out = []
ok = lambda name: out.append("OK " + name)
bad = lambda name, why: out.append("FAIL " + name + ": " + why)
ind = lambda l: len(l) - len(l.lstrip())


def block(start, src=None):
    """Lines strictly nested inside the mapping opened on line `start`."""
    src = lines if src is None else src
    own, res = ind(src[start]), []
    for line in src[start + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ind(line) <= own:
            break
        res.append(line)
    return res


def find(pred, src=None):
    src = lines if src is None else src
    return next((n for n, l in enumerate(src) if pred(l)), -1)


def keys_of(start):
    """Top-level keys of the mapping opened on line `start`."""
    b = block(start)
    if not b:
        return []
    depth = ind(b[0])
    return [l.strip().rstrip(":") for l in b
            if ind(l) == depth and l.strip().endswith(":")]


def run_body(src, name):
    """The `run: |` body of the step called `name` in `src`, or None."""
    i = find(lambda l: l.strip() == "- name: " + name, src)
    if i < 0:
        return None
    for n in range(i + 1, len(src)):
        if src[n].strip() and ind(src[n]) <= ind(src[i]):
            return None
        if src[n].strip() in ("run: |", "run: |-"):
            return "\n".join(block(n, src))
        if src[n].strip().startswith("run: "):
            return src[n].strip()[len("run: "):]
    return None


# 1. The unattended trigger (AC-4 / E-7 step 6). A check with no schedule is
#    only ever as good as someone remembering to press the button — which is
#    precisely what did not happen for 92 days.
#
#    Asserted as a PROPERTY, not a literal: what E-7 needs is "a gap is
#    reported within 24h", so what must hold is the worst-case wait between
#    firings, not any particular cron string. Pinning the literal
#    '0 15 * * *' is what let a zero-margin daily schedule sit under a 24h
#    threshold unnoticed — and this workflow's own first 50 firings then
#    ranged 18.3h-31.9h, breaching it. The bound below leaves >=12h of
#    headroom for GitHub's scheduler drift.
MAX_NOMINAL_GAP_H = 12

name = "schedule: daily slots leave <= %dh nominal gap (E-7 threshold 24h)" % MAX_NOMINAL_GAP_H
crons = re.findall(r"^\s*-\s*cron:\s*['\"]?([^'\"#]*?)['\"]?\s*$", "\n".join(lines), re.M)
if not crons:
    bad(name, "no cron trigger at all — the check would only ever run by hand")
else:
    mins = []
    for c in crons:
        f = c.split()
        # Only plain daily slots are understood here; anything fancier (step
        # values, day-of-week narrowing) must not be silently read as daily.
        if len(f) != 5 or f[2:] != ["*", "*", "*"] or not f[0].isdigit() or not f[1].isdigit():
            mins = None
            bad(name, "cron %r is not a plain daily slot — cannot bound the gap" % c)
            break
        mins.append(int(f[1]) * 60 + int(f[0]))
    if mins:
        mins = sorted(set(mins))
        # Largest wait between consecutive firings, wrapping past midnight.
        gaps = [b - a for a, b in zip(mins, mins[1:])] + [mins[0] + 1440 - mins[-1]]
        worst = max(gaps) / 60.0
        if worst <= MAX_NOMINAL_GAP_H:
            ok("%s [%d slot(s), worst %.1fh]" % (name, len(mins), worst))
        else:
            bad(name, "worst nominal gap is %.1fh across %r — at or over E-7's "
                      "24h threshold once scheduler drift is added" % (worst, crons))

# 2. The credentials fix (first dispatch run 30647079681 died without it —
#    the AWS secrets exist ONLY at `production` environment scope). Dropping
#    this line breaks nothing until the next scheduled run, silently.
name = "job declares environment: production (AWS secrets are env-scoped)"
j = find(lambda l: l.strip() == "check-freshness:")
if j < 0:
    bad(name, "no check-freshness job")
elif any(l.strip() == "environment: production" for l in block(j)):
    ok(name)
else:
    bad(name, "job has no `environment: production` — the AWS secrets are not "
              "repo-scoped, so the run would fail in configure-aws-credentials")

# 3. The dispatch input actually reaches the body (E-7 steps 3-4). If the
#    env: mapping is dropped or the input renamed, a dispatch run quietly
#    measures REAL prod instead of the synthetic value, which reads as "the
#    check is broken" rather than "the wiring is broken".
name = "workflow_dispatch input is wired to the env var the body reads"
wd = find(lambda l: l.strip() == "workflow_dispatch:")
declared = []
if wd >= 0:
    for n, l in enumerate(lines[wd + 1:], wd + 1):
        if l.strip() and ind(l) <= ind(lines[wd]):
            break
        if l.strip() == "inputs:":
            declared = keys_of(n)
            break

i = find(lambda l: l.strip() == "- name: " + step_name)
step_env = {}
if i >= 0:
    for n, l in enumerate(lines[i + 1:], i + 1):
        if l.strip() and ind(l) <= ind(lines[i]):
            break
        if l.strip() == "env:":
            for e in block(n):
                if ":" in e:
                    k, v = e.strip().split(":", 1)
                    step_env[k] = v.strip()
            break

wired = [(k, v) for k, v in step_env.items() if "inputs." in v]
if i < 0:
    bad(name, "step %r not found" % step_name)
elif not wired:
    bad(name, "the measure step's env: block maps no ${{ inputs.* }} value, so "
              "a dispatch run would ignore the input and measure real prod")
else:
    key, val = wired[0]
    inp = re.search(r"inputs\.([A-Za-z0-9_-]+)", val).group(1)
    if inp not in declared:
        bad(name, "env %s reads inputs.%s, not a declared workflow_dispatch "
                  "input (declared: %r)" % (key, inp, declared))
    elif not re.search(r"\b%s\b" % re.escape(key), body):
        bad(name, "env %s is set from inputs.%s but the run body never reads it"
                  % (key, inp))
    else:
        ok(name + " [%s -> $%s]" % (inp, key))

# 4. ONE definition of "deploys a new image". ci.yml's detect-changes decides
#    what deploys; this check decides what should have. If either grows its
#    own nx call or project list, they can disagree, and that disagreement is
#    exactly the drift that made this check red for two months over a
#    backend that had not changed. Both must call tools/deploy-affected.sh.
name = "ci.yml detect-changes and this check share tools/deploy-affected.sh"
ci_lines = open(ci_wf).read().splitlines()
ci_body = run_body(ci_lines, "Determine affected projects")
problems = []
for where, b in (("ci.yml 'Determine affected projects'", ci_body),
                 ("deploy-freshness measure step", body)):
    if b is None:
        problems.append("%s: step not found" % where)
        continue
    if "tools/deploy-affected.sh" not in b:
        problems.append("%s does not call tools/deploy-affected.sh" % where)
    if re.search(r"show projects|nx affected|--affected", b):
        problems.append("%s runs its own nx affected query" % where)
if problems:
    bad(name, "; ".join(problems))
else:
    ok(name)

# 5. Order of the job's steps. nx needs node_modules, so the install comes
#    before the measure step. The install also comes BEFORE the AWS
#    credentials, which are exported to every later step: a yarn install runs
#    every dependency's install scripts, and prod keys must not be in that
#    environment. And the credentials step must survive an install failure
#    (`!cancelled()` / `always()`), or the no-verdict notifier cannot reach
#    SNS and a registry outage goes silent.
name = "job steps: yarn install -> AWS credentials (survives a failed install) -> measure"
creds = find(lambda l: "aws-actions/configure-aws-credentials" in l)
yarn = find(lambda l: l.strip().startswith("run: yarn install"))
meas = find(lambda l: l.strip() == "- name: " + step_name)
creds_if = ""
if creds >= 0:
    for l in lines[creds + 1:]:
        if l.strip().startswith("- "):
            break
        if l.strip().startswith("if:"):
            creds_if = l.strip()
if min(creds, yarn, meas) < 0:
    bad(name, "missing step (creds=%d yarn=%d measure=%d)" % (creds, yarn, meas))
elif not (yarn < creds < meas):
    bad(name, "order is yarn@%d creds@%d measure@%d" % (yarn, creds, meas))
elif not re.search(r"!cancelled\(\)|always\(\)", creds_if):
    bad(name, "credentials step has no `if: ${{ !cancelled() }}` (got %r): a failed "
              "install would skip it and silence the no-verdict notifier" % creds_if)
else:
    ok(name)

print("\n".join(out))
PY
while IFS= read -r wire_line; do
  case "$wire_line" in
    "OK "*)   echo "pass [wiring: ${wire_line#OK }]"; PASS=$((PASS + 1)) ;;
    "FAIL "*) echo "FAIL [wiring: ${wire_line#FAIL }]"; FAIL=$((FAIL + 1)) ;;
    *)        echo "FAIL [wiring]: unparseable result: $wire_line"; FAIL=$((FAIL + 1)) ;;
  esac
done < "$SANDBOX/wiring.txt"

# ── The shared definition itself (what detect-changes consumes) ──────────
# detect-changes appends this script's stdout to $GITHUB_OUTPUT and four
# deploy jobs read those keys, so pin the contract on real nx: a utils change
# reaches api/worker/migrator through implicitDependencies and deploys all
# four images; a terraform-only change deploys none.
new_repo
U0="$(git -C "$REPO" rev-parse HEAD)"
U1="$(mk $(( 2 * DAY )) libraries/utils/u.py 'utils change')"
T1="$(mk $(( 1 * DAY )) terraform/main.tf 'terraform-only change')"
name='deploy-affected.sh: utils change -> api/worker/migrator, all four images'
got="$(cd "$REPO" && NX_DAEMON=false bash tools/deploy-affected.sh "$U0" "$U1" 2>/dev/null)" || got="(exit $?)"
want='api=true
worker=true
migrator=true
parser=false
terraform=false
services_to_build=["api","worker","migrator","parser"]'
if [ "$got" = "$want" ]; then echo "pass [$name]"; PASS=$((PASS + 1)); else
  echo "FAIL [$name]:"; printf '%s\n' "$got" | sed 's/^/    | /'; FAIL=$((FAIL + 1)); fi
name='deploy-affected.sh: terraform-only change -> terraform=true, no images'
got="$(cd "$REPO" && NX_DAEMON=false bash tools/deploy-affected.sh "$U1" "$T1" 2>/dev/null)" || got="(exit $?)"
want='api=false
worker=false
migrator=false
parser=false
terraform=true
services_to_build=[]'
if [ "$got" = "$want" ]; then echo "pass [$name]"; PASS=$((PASS + 1)); else
  echo "FAIL [$name]:"; printf '%s\n' "$got" | sed 's/^/    | /'; FAIL=$((FAIL + 1)); fi
name='deploy-affected.sh: nx failure fails the script (never reads as "nothing")'
set +e
(cd "$REPO" && PATH="$SANDBOX/bin-nx-broken:$PATH" bash tools/deploy-affected.sh "$U0" "$U1" > "$OUT" 2>&1)
rc=$?
set -e
if [ "$rc" -ne 0 ] && ! grep -q '^services_to_build=' "$OUT"; then echo "pass [$name]"; PASS=$((PASS + 1)); else
  echo "FAIL [$name]: exit $rc"; sed 's/^/    | /' "$OUT"; FAIL=$((FAIL + 1)); fi

# ── Case: a burst whose LAST deploy failed, then quiet → RED ─────────────
# The case this check exists for, and the one wall-clock image age could not
# see: prod got the burst's second merge, the third never deployed, and the
# commits after it touch nothing that deploys. Prod's image is only hours
# old — the old 7-day predicate stayed GREEN here for a week. The oldest
# undeployed deploy-triggering commit, not the newest commit, sets the clock.
new_repo
mk $(( 9 * HOUR ))      services/api/a.py    'burst 1: api'           >/dev/null
B2="$(mk $(( 8 * HOUR )) services/worker/w.py 'burst 2: worker (deployed)')"
B3="$(mk $(( 7 * HOUR )) services/api/a.py    'burst 3: api (deploy failed)')"
mk $(( 6 * HOUR ))      docs/notes.md        'docs after the burst'   >/dev/null
mk $(( 2 * HOUR ))      app/lib/x.dart       'app-only change'        >/dev/null
mk $(( 10 * 60 ))       docs/notes.md        'docs, just now'         >/dev/null
set_main
prod_runs "$B2"
name='burst ends in a failed deploy, then quiet: RED, oldest undeployed named'
if run_case "$name" 1; then
  expect_verdict "$name" stale || true
  expect_out "$name" "Deployed image: $ECR:$B2" || true
  expect_out "$name" "Oldest undeployed: $(short "$B3")" || true
  expect_out "$name" "Overdue: 7h" || true
  refute_out "$name" "Oldest undeployed: $(short "$B2")" || true
fi
end_case "$name"

# ── Case: the same burst much later — still RED, clock unchanged ─────────
new_repo
mk $(( 40 * DAY ))      services/api/a.py    'burst 1: api'           >/dev/null
B2="$(mk $(( 40 * DAY - HOUR )) services/worker/w.py 'burst 2: worker (deployed)')"
B3="$(mk $(( 40 * DAY - 2 * HOUR )) services/parser/Dockerfile 'burst 3: parser (deploy failed)')"
for k in 30 20 10 5 1; do mk $(( k * DAY )) docs/notes.md "docs $k days ago" >/dev/null; done
set_main
prod_runs "$B2"
name='burst ended 40 days ago in a failed deploy: RED, 39d overdue'
if run_case "$name" 1; then
  expect_verdict "$name" stale || true
  expect_out "$name" "Oldest undeployed: $(short "$B3")" || true
  expect_out "$name" "Overdue: 39d 22h" || true
fi
end_case "$name"

# ── Case: quiet backend, months-old image → GREEN ────────────────────────
# The state that kept the image-age check red for two months: prod runs the
# last backend commit, 96 days old, and everything since is app/docs/tools/CI.
new_repo
D="$(mk $(( 96 * DAY )) services/api/a.py 'last backend change (deployed)')"
for k in 90 60 30 7 1; do mk $(( k * DAY )) docs/notes.md "docs $k days ago" >/dev/null; done
mk $(( 3 * DAY )) app/lib/x.dart 'app change' >/dev/null
mk $(( 2 * DAY )) .github/workflows/x.yml 'workflow change' >/dev/null
mk $(( 30 * 60 )) scripts/s.sh 'scripts change' >/dev/null
set_main
prod_runs "$D"
name='quiet backend, 96-day-old image, 8 non-deploying commits since: GREEN'
if run_case "$name" 0; then
  expect_verdict "$name" fresh || true
  expect_out "$name" "Image age: 96d" || true
  expect_out "$name" "quiet: 8 commit(s) on main since the deployed commit" || true
fi
end_case "$name"

# ── Case: prod runs main's tip → GREEN ───────────────────────────────────
new_repo
D="$(mk $(( 50 * DAY )) services/api/a.py 'deployed tip')"
set_main
prod_runs "$D"
name="prod runs main's tip: GREEN"
if run_case "$name" 0; then
  expect_verdict "$name" fresh || true
  expect_out "$name" "prod runs main's tip" || true
fi
end_case "$name"

# ── Cases: the grace window, both sides of the boundary ──────────────────
new_repo
D="$(mk $(( 2 * DAY )) services/api/a.py 'deployed')"
X="$(mk $(( GRACE - 10 * 60 )) services/api/a.py 'api change, deploy in flight')"
set_main
prod_runs "$D"
name="deploy-triggering merge $(( MAX_OVERDUE_HOURS * 60 - 10 ))m ago (inside ${MAX_OVERDUE_HOURS}h grace): GREEN, says when it turns red"
if run_case "$name" 0; then
  expect_verdict "$name" fresh || true
  expect_out "$name" "inside the grace window" || true
  expect_out "$name" "Oldest undeployed: $(short "$X")" || true
fi
end_case "$name"

new_repo
D="$(mk $(( 2 * DAY )) services/api/a.py 'deployed')"
X="$(mk $(( GRACE + 10 * 60 )) services/api/a.py 'api change, never deployed')"
mk $(( 5 * 60 )) docs/notes.md 'docs, just now' >/dev/null
set_main
prod_runs "$D"
name="deploy-triggering merge $(( MAX_OVERDUE_HOURS * 60 + 10 ))m ago (past ${MAX_OVERDUE_HOURS}h grace): RED"
if run_case "$name" 1; then
  expect_verdict "$name" stale || true
  expect_out "$name" "Oldest undeployed: $(short "$X")" || true
fi
end_case "$name"

# ── Case: a shared-library change is a deploy, with no path list anywhere ─
new_repo
D="$(mk $(( 5 * DAY )) services/api/a.py 'deployed')"
X="$(mk $(( 1 * DAY )) libraries/utils/u.py 'utils change')"
set_main
prod_runs "$D"
name='libraries/utils change, 1 day undeployed: RED via nx implicitDependencies'
if run_case "$name" 1; then
  expect_verdict "$name" stale || true
  expect_out "$name" "Oldest undeployed: $(short "$X")" || true
fi
end_case "$name"

# ── Case: terraform-only change → GREEN (it never moves the image) ───────
# Scope limit, pinned so it is a decision and not an accident: a
# Terraform-only apply runs against the tags prod already has (tfgate1), so
# the running image cannot show whether it applied. This check cannot see a
# stuck Terraform-only apply, and must not pretend to by going red forever.
new_repo
D="$(mk $(( 5 * DAY )) services/api/a.py 'deployed')"
mk $(( 2 * DAY )) terraform/main.tf 'terraform-only change' >/dev/null
set_main
prod_runs "$D"
name='terraform-only change, 2 days old: GREEN (moves no image)'
if run_case "$name" 0; then
  expect_verdict "$name" fresh || true
  expect_out "$name" "quiet:" || true
fi
end_case "$name"

# ── Case: change + revert, both undeployed → GREEN ───────────────────────
# Net diff from prod is empty, which is also what ci.yml would deploy.
new_repo
D="$(mk $(( 5 * DAY )) services/api/a.py 'deployed')"
mk $(( 2 * DAY )) services/api/b.py 'api change' >/dev/null
revert_head $(( 1 * DAY )) >/dev/null
set_main
prod_runs "$D"
name='an api change and its revert, both undeployed: GREEN (net diff empty)'
if run_case "$name" 0; then
  expect_verdict "$name" fresh || true
fi
end_case "$name"

# ── Case: main is origin/main, not HEAD ──────────────────────────────────
# A dispatch from a branch checks the branch out. The branch's own backend
# commit must not count; only main deploys.
new_repo
D="$(mk $(( 5 * DAY )) services/api/a.py 'deployed')"
mk $(( 2 * DAY )) docs/notes.md 'docs on main' >/dev/null
set_main
mk $(( 1 * DAY )) services/api/a.py 'branch-only api change' >/dev/null
prod_runs "$D"
name='HEAD has an undeployed api change that is not on origin/main: GREEN'
if run_case "$name" 0; then
  expect_verdict "$name" fresh || true
fi
end_case "$name"

# ── Case 1 (E-7 step 5, the load-bearing one) ────────────────────────────
# Prod is frozen on revision :62 at D. A NEWER revision :63, built from X (a
# backend change 5 days ago), is registered as the family's newest ACTIVE but
# was never deployed. The family-name shortcut resolves to :63 — X..main is
# docs only, so it would report green. The running-revision path resolves to
# :62 — D..main includes X, 5 days past the grace window, so RED.
new_repo
D="$(mk $(( 96 * DAY )) services/api/a.py 'the deployed commit')"
X="$(mk $(( 5 * DAY )) services/api/a.py 'built and registered, never deployed')"
mk $(( 1 * DAY )) docs/notes.md 'newest main' >/dev/null
set_main
prod_runs "$D" "$X"
printf '%s\t%s\n' "$NEWER_ARN" "$ECR:$X" >> "$MOCK_TD_MAP"
name='step5: newer ACTIVE revision registered but not deployed'
if run_case "$name" 1; then
  expect_verdict "$name" stale || true
  expect_out "$name" "Running task definition: $RUNNING_ARN" || true
  expect_out "$name" "Deployed image: $ECR:$D" || true
  expect_out "$name" "Oldest undeployed: $(short "$X")" || true
  # The tell-tale of a family-shortcut regression: the undeployed revision's
  # image reported as the deployed one.
  refute_out "$name" "Deployed image: $ECR:$X" || true
  # And prove the resolution actually went through describe-services rather
  # than reaching a correct verdict by luck.
  if ! grep -qF "ecs describe-services" "$SANDBOX/calls.log"; then
    echo "FAIL [$name]: never called describe-services"; FAIL=$((FAIL + 1))
  fi
  if grep -qE "describe-task-definition --task-definition ${SERVICE}( |$)" "$SANDBOX/calls.log"; then
    echo "FAIL [$name]: resolved by family name — the shortcut trap"; FAIL=$((FAIL + 1))
  fi
fi
end_case "$name"

# ── Case: unknown provenance fails ───────────────────────────────────────
prod_runs latest
name='deployed tag is not a commit in this repo'
if run_case "$name" 1; then
  expect_verdict "$name" unknown || true
  expect_out "$name" "is not a commit in this repository" || true
fi
end_case "$name"

# ── Case: nx cannot answer → no verdict, never "fresh" ───────────────────
# The silent-to-loud property: a broken nx must reach the no-verdict
# notifier, not read as "nothing deploys" (which is green).
new_repo
D="$(mk $(( 5 * DAY )) services/api/a.py 'deployed')"
mk $(( 2 * DAY )) docs/notes.md 'docs' >/dev/null
set_main
prod_runs "$D"
name='nx fails mid-measurement: step fails with NO verdict'
if run_case "$name" 1 "$SANDBOX/bin-nx-broken"; then
  expect_verdict "$name" none || true
  refute_out "$name" "Prod is not overdue" || true
fi
end_case "$name"

# ── Cases (E-7 steps 3-4): the synthetic dispatch input ──────────────────
# Run against fixtures whose REAL answer is the opposite, so a synthetic
# verdict can only come from the substitution taking effect.
new_repo
D="$(mk $(( 5 * DAY )) services/api/a.py 'deployed')"
mk $(( 2 * DAY )) docs/notes.md 'docs' >/dev/null
set_main
prod_runs "$D"   # really: quiet, green
export SYNTHETIC_OVERDUE_HOURS=$(( MAX_OVERDUE_HOURS + 1 ))
name="synthetic ${SYNTHETIC_OVERDUE_HOURS}h (> ${MAX_OVERDUE_HOURS}h) fails on a quiet fixture"
if run_case "$name" 1; then
  expect_verdict "$name" stale || true
  expect_out "$name" "SYNTHETIC overdue of ${SYNTHETIC_OVERDUE_HOURS}h" || true
  expect_out "$name" "says nothing about prod" || true
  refute_out "$name" "quiet:" || true
fi
end_case "$name"

new_repo
D="$(mk $(( 5 * DAY )) services/api/a.py 'deployed')"
mk $(( 2 * DAY )) services/api/a.py 'undeployed api change' >/dev/null
set_main
prod_runs "$D"   # really: 2 days overdue, red
export SYNTHETIC_OVERDUE_HOURS=0
name="synthetic 0h passes despite a really-overdue fixture"
if run_case "$name" 0; then
  expect_verdict "$name" fresh || true
  refute_out "$name" "Oldest undeployed" || true
fi
end_case "$name"

export SYNTHETIC_OVERDUE_HOURS="$MAX_OVERDUE_HOURS"
name="synthetic ${MAX_OVERDUE_HOURS}h == grace passes (boundary is inclusive)"
run_case "$name" 0 || true
end_case "$name"

export SYNTHETIC_OVERDUE_HOURS=1.5
name="synthetic non-integer is refused with no verdict"
if run_case "$name" 1; then
  expect_verdict "$name" none || true
fi
end_case "$name"
unset SYNTHETIC_OVERDUE_HOURS

echo
echo "deploy-freshness self-test: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
