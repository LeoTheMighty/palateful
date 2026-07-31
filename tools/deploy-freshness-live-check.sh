#!/usr/bin/env bash
#
# Run deploy-freshness.yml's measure step against REAL prod, from a laptop.
#
# WHY THIS EXISTS
# ---------------
# `gh workflow run` resolves a workflow definition from a *pushed* ref, so a
# fix to deploy-freshness.yml cannot be exercised until it merges. That left
# E-7 step 1 ("dispatch run reports the true gap") owed for the entire life of
# every change to the check — including the credentials fix that only the first
# dispatch run revealed.
#
# This runs the SAME bash, extracted from the same YAML (never copied — see
# deploy-freshness-extract.py), against the same live ECS/ECR/git, from
# wherever you have AWS credentials. It proves the measurement half of the
# check before merge. It does NOT prove the mechanism half — running in Actions
# with environment-scoped credentials, on a schedule, unattended — which is
# exactly what E-7 steps 1/6 observe and what this script cannot substitute for.
#
# `--simulate-newer-revision` extends the same idea to E-7 step 5, whose live
# form requires registering a task definition in the production account: it
# shims the one `aws` answer a registration would change and leaves every other
# call real. See the block guarding it below for what that does and does not
# discharge.
#
# `--verify-shim-assumptions` closes the loop on that simulation: it checks,
# read-only against live AWS, that ECS really behaves the way the shim pretends
# it does. Without it the simulation is only as good as its author's memory of
# the ECS API.
#
# `--verify-environment-gate` covers E-7 step 6's non-calendar half: declaring
# `environment: production` (the fix that gave the job its AWS credentials) is
# also the one change that could make the check stall waiting for a human — the
# opposite of an unattended freeze detector. It reads GitHub, not AWS.
#
# Usage:
#   bash tools/deploy-freshness-live-check.sh                    # real measurement
#   bash tools/deploy-freshness-live-check.sh --synthetic-gap-days 8   # E-7 step 3
#   bash tools/deploy-freshness-live-check.sh --synthetic-gap-days 1   # E-7 step 4
#   bash tools/deploy-freshness-live-check.sh --simulate-newer-revision  # E-7 step 5
#   bash tools/deploy-freshness-live-check.sh --verify-shim-assumptions  # E-7 step 5 fidelity
#   bash tools/deploy-freshness-live-check.sh --verify-environment-gate  # E-7 step 6 (no wait)
#
# Read-only: describe-services + describe-task-definition only, no mutations
# (--verify-shim-assumptions also lists families/revisions; still read-only.
# --verify-environment-gate touches no AWS at all — GitHub reads only).
# Exit: mirrors the workflow step (0 fresh / 1 stale-or-unknown), 2 on usage
# or credential errors — so a missing AWS session can't be misread as "fresh".
# Under --simulate-newer-revision the codes report the OBSERVATION instead:
# 0 gap unchanged (correct), 1 gap moved (the family-shortcut trap), 2 the
# simulation itself could not be trusted. Under --verify-shim-assumptions:
# 0 every assumption observed, 1 live AWS contradicts one, 2 not observable
# right now (say so rather than pass — an unobservable assumption is not a
# confirmed one). --verify-environment-gate uses the same three: 0 no gate,
# 1 a gate exists (or one already stalled a real run), 2 not observable.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/deploy-freshness.yml"
STEP_NAME="Measure gap between running image and its commit date"

SYNTHETIC=""
SIMULATE_NEWER=0
VERIFY_ASSUMPTIONS=0
VERIFY_ENV_GATE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --synthetic-gap-days) SYNTHETIC="${2:-}"; shift 2 ;;
    --simulate-newer-revision) SIMULATE_NEWER=1; shift ;;
    --verify-shim-assumptions) VERIFY_ASSUMPTIONS=1; shift ;;
    --verify-environment-gate) VERIFY_ENV_GATE=1; shift ;;
    -h|--help) sed -n '2,55p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "usage: $0 [--synthetic-gap-days N] [--simulate-newer-revision] [--verify-shim-assumptions] [--verify-environment-gate]" >&2; exit 2 ;;
  esac
done

[ -f "$WORKFLOW" ] || { echo "FAIL: $WORKFLOW not found" >&2; exit 2; }

if [ "$VERIFY_ENV_GATE" -eq 1 ]; then
  # ── E-7 step 6, the half that is not calendar time ─────────────────────
  # Step 6 is "the scheduled run fires unattended, with no approval prompt".
  # Two independent things have to hold, and only one of them needs a morning:
  #
  #   (a) the cron fires at all               — calendar time, stays owed
  #   (b) nothing stalls the job for a human  — observable right now
  #
  # (b) is the part the credentials fix put at risk. The job had to declare
  # `environment: production` to see the AWS secrets at all, and an
  # environment is exactly where GitHub hangs a required-reviewer gate. A
  # gated freshness check is worse than none: it goes quiet at 09:00 waiting
  # for a human who, by the premise of this whole workstream, is not looking.
  #
  # Reading `protection_rules: []` off the API says the gate is not configured.
  # This also asks whether real jobs that used the environment ever waited —
  # ci.yml's deploy jobs declare the same environment, so the account carries
  # its own witnesses. Config says what should happen; deployments say what did.
  #
  # GitHub reads only; no AWS, no writes.
  # Exit: 0 no gate, 1 a gate exists or one stalled a real run, 2 not observable.
  command -v gh >/dev/null || { echo "FAIL: gh CLI not on PATH" >&2; exit 2; }
  gh auth status >/dev/null 2>&1 \
    || { echo "FAIL: gh is not authenticated — refusing to report 'no gate'" >&2; exit 2; }

  fails=0
  note_fail() { echo "  FAIL: $1" >&2; fails=$((fails + 1)); }
  # ISO-8601 Z -> epoch. `date -d` is GNU-only and this runs on laptops.
  iso_epoch() {
    python3 -c 'import datetime,sys
print(int(datetime.datetime.strptime(sys.argv[1], "%Y-%m-%dT%H:%M:%SZ")
          .replace(tzinfo=datetime.timezone.utc).timestamp()))' "$1"
  }

  echo "G0 — the check job declares an environment, and this is the name the rest is about"
  # Job-level keys sit at 4 spaces; deploy-freshness.yml has one job. Read the
  # name rather than hardcoding it, so renaming the environment in the YAML
  # moves this check with it instead of silently checking the wrong one.
  env_name="$(sed -n 's/^    environment: *//p' "$WORKFLOW" | head -1)"
  if [ -z "$env_name" ]; then
    echo "  FAIL: no job-level 'environment:' in $(basename "$WORKFLOW") — that is the credentials" >&2
    echo "        fix regressing (run 30647079681: 'Credentials could not be loaded'), not a pass." >&2
    exit 1
  fi
  echo "  OK: environment '$env_name'"

  repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
  [ -n "$repo" ] || { echo "FAIL: could not resolve the repo from gh" >&2; exit 2; }
  echo "  repo: $repo"
  echo

  echo "G1 — the environment carries no approval gate and no branch policy"
  # A 404 leaves the error body on stdout, so blank it explicitly: an error
  # payload parsed as a rule count would report nonsense instead of "unknown".
  env_meta="$(gh api "repos/$repo/environments/$env_name" \
    --jq '[(.protection_rules|length), (.protection_rules|map(.type)|join(",")), (.deployment_branch_policy|tostring), .updated_at] | join("|")' \
    2>/dev/null)" || env_meta=""
  IFS='|' read -r rule_count rule_types branch_policy env_updated <<< "$env_meta"
  case "$rule_count" in ''|*[!0-9]*) env_meta="" ;; esac
  if [ -z "$env_meta" ]; then
    echo "  NOT OBSERVABLE: environment '$env_name' is not readable via the API (missing, or the" >&2
    echo "      token lacks the scope). An unreadable gate is not an absent one." >&2
    exit 2
  fi
  if [ "$rule_count" -eq 0 ] && [ "$branch_policy" = "null" ]; then
    echo "  OK: protection_rules: [] and no deployment_branch_policy (last changed $env_updated)"
  else
    note_fail "environment '$env_name' has $rule_count protection rule(s) [${rule_types:-none}] and branch policy '$branch_policy'"
    echo "        — a scheduled run can stall here, which is precisely the blindness this check exists to remove." >&2
  fi
  echo

  echo "G2 — real jobs used this environment and none of them ever waited for a human"
  # A job whose environment requires approval creates a deployment that sits in
  # the `waiting` state until someone clicks. So a completed deployment whose
  # states never included `waiting` is a run that was never gated — evidence
  # from behaviour rather than from config.
  dep_ids="$(gh api "repos/$repo/deployments?environment=$env_name&per_page=10" \
    --jq '.[].id' 2>/dev/null)" || dep_ids=""
  if [ -z "$dep_ids" ]; then
    echo "  NOT OBSERVABLE: no deployments recorded for environment '$env_name', so there is no" >&2
    echo "      run to witness. Config alone does not discharge this." >&2
    exit 2
  fi
  witnesses=0
  waited=0
  newest_witness=""
  for dep in $dep_ids; do
    states="$(gh api "repos/$repo/deployments/$dep/statuses" \
      --jq '.[] | [.state, .created_at] | join(" ")' 2>/dev/null || true)"
    [ -n "$states" ] || continue
    witnesses=$((witnesses + 1))
    queued_at="$(printf '%s\n' "$states" | awk '$1 == "queued"    { t = $2 } END { print t }')"
    started_at="$(printf '%s\n' "$states" | awk '$1 == "in_progress" { t = $2 } END { print t }')"
    lat="?"
    if [ -n "$queued_at" ] && [ -n "$started_at" ]; then
      lat="$(( $(iso_epoch "$started_at") - $(iso_epoch "$queued_at") ))s"
    fi
    [ -n "$newest_witness" ] || newest_witness="${queued_at:-$started_at}"
    if printf '%s\n' "$states" | grep -q '^waiting '; then
      waited=$((waited + 1))
      echo "  deployment $dep: WAITED for approval ($(printf '%s' "$states" | tr '\n' ',' ))" >&2
    else
      echo "  deployment $dep: queued->in_progress in $lat, states: $(printf '%s\n' "$states" | awk '{print $1}' | tr '\n' ' ')"
    fi
  done
  if [ "$witnesses" -eq 0 ]; then
    echo "  NOT OBSERVABLE: deployments exist but none has readable statuses." >&2
    exit 2
  fi
  if [ "$waited" -eq 0 ]; then
    echo "  OK: $witnesses deployment(s) into '$env_name', zero in the 'waiting' state —"
    echo "      every one went queued -> in_progress in seconds, i.e. runner latency, not a human"
  else
    note_fail "$waited of $witnesses deployment(s) into '$env_name' sat in 'waiting' — the gate is real"
  fi
  echo

  echo "G3 — that evidence postdates the environment's last configuration change"
  # Otherwise G2 witnesses a policy that no longer applies: rules added after
  # the newest witness would gate the next run while every past run looks clean.
  if [ -z "$newest_witness" ]; then
    echo "  NOT OBSERVABLE: no timestamp on the witness deployments." >&2
    exit 2
  fi
  if [ "$(iso_epoch "$newest_witness")" -ge "$(iso_epoch "$env_updated")" ]; then
    echo "  OK: newest witness $newest_witness is at or after the environment's last change $env_updated"
  else
    note_fail "the environment changed at $env_updated, after the newest witness $newest_witness — the behavioural evidence predates the current rules"
  fi

  echo
  if [ "$fails" -eq 0 ]; then
    echo "PASS: declaring '$env_name' introduces no approval gate — config says none is"
    echo "      configured, $witnesses real deployment(s) confirm none was applied, and that"
    echo "      evidence is newer than the last config change."
    echo "STILL OWED (calendar time): that the 0 15 * * * cron fires at all. This says only"
    echo "      that nothing will hold it for a human once it does."
    exit 0
  fi
  echo "FAIL: $fails check(s) failed — a run of $(basename "$WORKFLOW") can stall waiting for" >&2
  echo "      approval, so it cannot detect an unattended freeze. Exempt the job from the" >&2
  echo "      environment or move the AWS secrets to repo scope." >&2
  exit 1
fi

command -v aws >/dev/null || { echo "FAIL: aws CLI not on PATH" >&2; exit 2; }
aws sts get-caller-identity >/dev/null 2>&1 \
  || { echo "FAIL: no usable AWS credentials — refusing to report a gap" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Exit 2, not 1: a structural mismatch must not be readable as "prod is stale".
python3 "$REPO_ROOT/tools/deploy-freshness-extract.py" \
  "$WORKFLOW" "$STEP_NAME" "$TMP/measure.sh" || exit 2

# Pull the workflow's env block rather than restating it, so this script cannot
# check a different cluster/service/threshold than the scheduled run does.
read_env() { sed -n "s/^  $1: *//p" "$WORKFLOW" | head -1; }
AWS_REGION="$(read_env AWS_REGION)"
CLUSTER="$(read_env CLUSTER)"
SERVICE="$(read_env SERVICE)"
MAX_GAP_DAYS="$(read_env MAX_GAP_DAYS)"
[ -n "$AWS_REGION" ] && [ -n "$CLUSTER" ] && [ -n "$SERVICE" ] && [ -n "$MAX_GAP_DAYS" ] \
  || { echo "FAIL: could not read AWS_REGION/CLUSTER/SERVICE/MAX_GAP_DAYS from the workflow env block" >&2; exit 2; }
echo "workflow env: AWS_REGION=$AWS_REGION CLUSTER=$CLUSTER SERVICE=$SERVICE MAX_GAP_DAYS=$MAX_GAP_DAYS"
echo

if [ "$VERIFY_ASSUMPTIONS" -eq 1 ]; then
  # ── Is the step-5 simulation actually faithful? ────────────────────────
  # --simulate-newer-revision proves the check is insensitive to a newer
  # ACTIVE revision *given* that ECS diverges the way the shim pretends. That
  # "given" was the last thing E-7 step 5 took on documentation rather than
  # observation. It decomposes into four claims, and every one of them can be
  # read out of the live account without registering anything:
  #
  #   A0  the family name the shim intercepts is the running task def's family
  #   A1  a family-name lookup returns the highest-numbered ACTIVE revision,
  #       even when an older ACTIVE revision exists and the newest runs nowhere
  #   A2  describe-services returns a revision-pinned ARN that resolves to that
  #       exact revision — the pointer a registration cannot move
  #   A3  revision numbers are never reused, so a registration yields max+1 —
  #       the ARN the shim fabricates
  #
  # Exit: 0 all observed, 1 live AWS contradicts one, 2 not observable now.
  fails=0
  note_fail() { echo "  FAIL: $1" >&2; fails=$((fails + 1)); }

  # Revision numbers of an EXACT family. --family-prefix is a prefix match, so
  # a family named "<x>-extra" would otherwise leak in.
  list_revs() {
    aws ecs list-task-definitions --family-prefix "$1" --status "$2" \
      --output text --query 'taskDefinitionArns[]' \
      | tr '\t' '\n' | sed 's|.*/||' | awk -F: -v f="$1" '$1 == f { print $2 }'
  }

  running_td="$(aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" \
    --query 'services[0].taskDefinition' --output text)"
  case "$running_td" in
    arn:*:task-definition/*:[0-9]*) ;;
    *) echo "FAIL: describe-services returned '$running_td', not a revision-pinned task-definition ARN" >&2
       echo "      — A2 is contradicted at the first hop; the shim's whole model is wrong." >&2
       exit 1 ;;
  esac
  running_rev="${running_td##*:}"
  running_family="${running_td%:*}"; running_family="${running_family##*/}"
  echo "running task definition: $running_family:$running_rev"
  echo

  echo "A0 — the shim intercepts the family the running task definition belongs to"
  if [ "$running_family" = "$SERVICE" ]; then
    echo "  OK: family '$running_family' == the workflow's SERVICE '$SERVICE', which is what the shim keys on"
  else
    note_fail "family is '$running_family' but the shim keys on SERVICE '$SERVICE' — it would intercept nothing"
  fi

  echo "A1 — a family-name lookup returns the newest ACTIVE revision"
  witness=""
  for fam in $(aws ecs list-task-definition-families --status ACTIVE --output text \
                 --query 'families[]' | tr '\t' '\n'); do
    revs="$(list_revs "$fam" ACTIVE)"
    [ "$(printf '%s\n' "$revs" | grep -c .)" -ge 2 ] || continue
    witness="$fam"
    newest="$(printf '%s\n' "$revs" | sort -n | tail -1)"
    oldest="$(printf '%s\n' "$revs" | sort -n | head -1)"
    resolved="$(aws ecs describe-task-definition --task-definition "$fam" \
      --query 'taskDefinition.taskDefinitionArn' --output text)"
    resolved="${resolved##*:}"
    echo "  witness family '$fam': ACTIVE revisions $(printf '%s' "$revs" | tr '\n' ' ')"
    if [ "$resolved" = "$newest" ] && [ "$newest" != "$oldest" ]; then
      echo "  OK: '$fam' (no revision) resolved to :$resolved — the newest ACTIVE, while :$oldest stayed ACTIVE and ignored"
      echo "      that is exactly how the family shortcut goes green-and-blind: newest wins, deployed-or-not"
    else
      note_fail "'$fam' resolved to :$resolved, expected the newest ACTIVE :$newest"
    fi
    break
  done
  if [ -z "$witness" ]; then
    # Refuse to pass on an unobserved claim. This is the one assumption that
    # needs a family carrying an ACTIVE revision nobody runs; if the account
    # no longer has one, say "not observable", not "fine".
    echo "  NOT OBSERVABLE: no family in this account currently has 2+ ACTIVE revisions," >&2
    echo "      so the newest-ACTIVE-wins behaviour cannot be witnessed read-only right now." >&2
    exit 2
  fi

  echo "A2 — the running pointer is a pinned revision, not a floating family reference"
  pinned="$(aws ecs describe-task-definition --task-definition "$running_td" \
    --query 'taskDefinition.revision' --output text)"
  if [ "$pinned" = "$running_rev" ]; then
    echo "  OK: describe-services stores '$running_td' and that ARN resolves to :$pinned"
    echo "      a registration adds a revision; it cannot rewrite a stored ARN, so only update-service moves this"
  else
    note_fail "the running ARN resolved to :$pinned, not :$running_rev"
  fi

  echo "A3 — revision numbers are never reused, so a registration lands above the running one"
  all_revs="$( { list_revs "$running_family" ACTIVE; list_revs "$running_family" INACTIVE; } | sort -n)"
  total="$(printf '%s\n' "$all_revs" | grep -c .)"
  uniq_total="$(printf '%s\n' "$all_revs" | sort -nu | grep -c .)"
  max_rev="$(printf '%s\n' "$all_revs" | tail -1)"
  echo "  family '$running_family': $total revisions, highest :$max_rev, running :$running_rev"
  if [ "$total" -eq "$uniq_total" ] && [ "$max_rev" -eq "$total" ] && [ "$max_rev" -ge "$running_rev" ]; then
    echo "  OK: revisions are 1..$max_rev with no gaps and no duplicates (deregistering leaves the number spent),"
    echo "      so the next register-task-definition is :$((max_rev + 1)) — above the running :$running_rev, which by A1 wins the family lookup"
  else
    note_fail "revisions are not a contiguous 1..N (total=$total unique=$uniq_total max=$max_rev) — the next revision number is not predictable from here"
  fi

  echo
  if [ "$fails" -eq 0 ]; then
    echo "PASS: every assumption behind --simulate-newer-revision is observed in live AWS."
    echo "      A0+A3 fix WHICH answer a registration would change; A1 makes the family"
    echo "      shortcut see it; A2 keeps the correct path on :$running_rev. That is the"
    echo "      divergence the shim injects — and now the shape of it is measured, not assumed."
    exit 0
  fi
  echo "FAIL: $fails assumption(s) contradicted by live AWS — the step-5 simulation models" >&2
  echo "      something this account does not do, so its PASS cannot be trusted." >&2
  exit 1
fi

# The workflow checks out with fetch-depth: 0 because the deployed SHA may be
# months old. A shallow or stale local clone would report "not a commit" and
# look like unknown provenance instead of a fetch problem, so say so up front.
if [ -f "$REPO_ROOT/.git/shallow" ]; then
  echo "WARNING: shallow clone — the deployed SHA may be missing locally; run 'git fetch --unshallow'." >&2
fi

# Runs the extracted step once. $1 = output file, $2 = script, $3 = PATH to use.
# Echoes the exit status.
run_measure() {
  local out="$1" script="$2" path="$3" status=0
  # `|| status=$?` rather than toggling errexit: a function that flips `set -e`
  # leaves it flipped for its caller.
  ( cd "$REPO_ROOT" \
    && env PATH="$path" AWS_REGION="$AWS_REGION" CLUSTER="$CLUSTER" SERVICE="$SERVICE" \
           MAX_GAP_DAYS="$MAX_GAP_DAYS" SYNTHETIC_GAP_DAYS="$SYNTHETIC" \
       bash "$script" ) > "$out" 2>&1 || status=$?
  cat "$out"
  return "$status"
}

if [ "$SIMULATE_NEWER" -eq 1 ]; then
  # ── E-7 step 5, without mutating prod ──────────────────────────────────
  # The observation is "register a newer ACTIVE revision that was never
  # deployed -> the reported gap does not move". Registering one is a
  # production mutation. But the check never *reads* the ECS registry as
  # state: it reads it through exactly two `aws` calls. So shadow `aws` with
  # a shim that passes every call through to the real CLI against real prod,
  # EXCEPT a describe-task-definition on the family name or on the
  # would-be-next revision ARN — which answers as if that revision had been
  # registered, on a fresh image tag. That is the same divergence the
  # registration would create, seen by the same shipped bash, with nothing
  # written to the account.
  #
  # Exit codes here mean the OBSERVATION, not the freshness check:
  #   0 = gap unchanged (correct), 1 = gap moved (the family-shortcut trap),
  #   2 = the simulation itself could not be trusted.
  REAL_AWS="$(command -v aws)"
  NEWER_TAG="$(git -C "$REPO_ROOT" rev-parse HEAD)"

  real_td="$(aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" \
    --query 'services[0].taskDefinition' --output text)"
  real_image="$(aws ecs describe-task-definition --task-definition "$real_td" \
    --query 'taskDefinition.containerDefinitions[0].image' --output text)"
  case "$real_td" in
    *:[0-9]*) FAKE_ARN="${real_td%:*}:$(( ${real_td##*:} + 1 ))" ;;
    *) echo "FAIL: running task definition '$real_td' has no revision suffix" >&2; exit 2 ;;
  esac
  # The fake image is never pulled — the check only splits the tag off and
  # dates it with `git log` — so HEAD needs no built image to exist.
  FAKE_IMAGE="${real_image%:*}:$NEWER_TAG"
  echo "simulating a newer ACTIVE revision: $FAKE_ARN -> $FAKE_IMAGE"
  echo "  (running revision stays the real $real_td; nothing is written to AWS)"
  echo

  mkdir -p "$TMP/bin"
  cat > "$TMP/bin/aws" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
if [ "${1:-}" = "ecs" ] && [ "${2:-}" = "describe-task-definition" ]; then
  argv=("$@"); key=""
  for ((n = 0; n < ${#argv[@]} - 1; n++)); do
    if [ "${argv[n]}" = "--task-definition" ]; then key="${argv[n + 1]}"; break; fi
  done
  if [ "$key" = "$SHIM_FAMILY" ] || [ "$key" = "$SHIM_FAKE_ARN" ]; then
    printf '%s\n' "$SHIM_FAKE_IMAGE"
    exit 0
  fi
fi
exec "$SHIM_REAL_AWS" "$@"
SHIM
  chmod +x "$TMP/bin/aws"
  export SHIM_REAL_AWS="$REAL_AWS" SHIM_FAMILY="$SERVICE" \
         SHIM_FAKE_ARN="$FAKE_ARN" SHIM_FAKE_IMAGE="$FAKE_IMAGE"
  SHIM_PATH="$TMP/bin:$PATH"

  echo "── baseline (real prod, no simulated revision) ──"
  set +e; run_measure "$TMP/base.txt" "$TMP/measure.sh" "$PATH"; BASE_STATUS=$?; set -e
  echo
  echo "── with the simulated newer ACTIVE revision ──"
  set +e; run_measure "$TMP/sim.txt" "$TMP/measure.sh" "$SHIM_PATH"; SIM_STATUS=$?; set -e
  echo

  # The verdict comes first, so a real regression is attributed as one. A
  # control that cannot even be built (below) must only ever downgrade a
  # would-be PASS to "untrustworthy" — never mask a FAIL, which is what
  # happens if the control runs first and the shipped bash is already the
  # shortcut.
  echo "baseline exit $BASE_STATUS / simulated exit $SIM_STATUS"
  if [ "$BASE_STATUS" -ne "$SIM_STATUS" ] || ! diff -q "$TMP/base.txt" "$TMP/sim.txt" >/dev/null; then
    echo "FAIL: a newer ACTIVE revision that was never deployed CHANGED the report" >&2
    echo "      — the check resolves by family name, so a frozen prod reads as fresh." >&2
    diff "$TMP/base.txt" "$TMP/sim.txt" | sed 's/^/    | /' >&2 || true
    exit 1
  fi

  # The control. A shim that silently failed to inject anything would make
  # "unchanged" trivially true, so prove the injected revision is reachable:
  # the family-name shortcut — the exact regression this step guards against —
  # must see it. Verifying the simulation is what makes the observation mean
  # something.
  python3 - "$TMP/measure.sh" "$TMP/shortcut.sh" <<'PY' || exit 2
import re
import sys

src = open(sys.argv[1]).read()
mutated, n = re.subn(
    r"running_td=\$\(aws ecs describe-services.*?--output text\)\n",
    'running_td="$SERVICE"\n',
    src,
    flags=re.S,
)
if n != 1:
    sys.exit(
        "SIMULATION FAIL: could not build the family-shortcut control "
        "(matched the describe-services resolution %d times, want 1). The "
        "report was unchanged, but with no working control that is vacuous."
    )
open(sys.argv[2], "w").write(mutated)
PY
  echo
  echo "── control: the same bash with the family-name shortcut reintroduced ──"
  set +e; run_measure "$TMP/ctl.txt" "$TMP/shortcut.sh" "$SHIM_PATH"; CTL_STATUS=$?; set -e
  echo

  if ! grep -qF "$NEWER_TAG" "$TMP/ctl.txt"; then
    echo "FAIL: the control never saw the simulated revision — the shim did not" >&2
    echo "      take effect, so 'gap unchanged' would be vacuous. Not reporting a pass." >&2
    exit 2
  fi

  echo "observation:"
  echo "  control (family shortcut) exit $CTL_STATUS — sees the undeployed image, so the divergence is real"
  echo "  shipped bash: byte-identical report before and after"
  echo "PASS: the reported gap is unchanged by a newer registered-but-undeployed revision."
  exit 0
fi

set +e
run_measure "$TMP/run.txt" "$TMP/measure.sh" "$PATH"
STATUS=$?
set -e

echo
echo "measure step exit: $STATUS  ($([ "$STATUS" -eq 0 ] && echo 'PASS — fresh' || echo 'FAIL — stale or undatable'))"
if [ -n "$SYNTHETIC" ]; then
  echo "NOTE: synthetic gap ${SYNTHETIC}d was substituted — this exercised the threshold, NOT prod's real age."
fi
exit "$STATUS"
