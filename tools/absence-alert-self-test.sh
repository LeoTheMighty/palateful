#!/usr/bin/env bash
#
# Self-test for .github/workflows/absence-alert.yml (absal1 / U3).
#
# WHY THIS EXISTS
# ---------------
# An absence alert is the one kind of check whose healthy state and whose
# broken state look identical from the outside: both are silence. "It ran and
# said nothing" is indistinguishable from "it would never have said anything".
# The only way to trust it is to drive it into every verdict on purpose.
#
# It asserts DELIVERY, not just exit codes. The premise this check was first
# built on was wrong — GitHub Actions email is switched off for this account,
# so a red run reaches nobody (PR #55) — and a test that only checked exit
# codes would have passed happily against that mistake. So each case also
# asserts what was published, and to which topic.
#
# The bash body is EXTRACTED FROM THE WORKFLOW YAML at run time, never copied,
# so this cannot pass against logic the workflow no longer ships. Same
# mechanism as tools/deploy-freshness-self-test.sh.
#
# Usage: bash tools/absence-alert-self-test.sh
# Exit:  0 all cases pass, 1 any case fails or extraction fails.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/absence-alert.yml"
STEP_NAME="Check expected telemetry and the alert channel"

[ -f "$WORKFLOW" ] || { echo "FAIL: $WORKFLOW not found"; exit 1; }

SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT

python3 "$REPO_ROOT/tools/deploy-freshness-extract.py" \
  "$WORKFLOW" "$STEP_NAME" "$SANDBOX/check.sh"

# Thresholds come from the workflow, so a case can never assert against a
# value the workflow stopped using.
read_env() { sed -n "s/^  $1: *//p" "$WORKFLOW" | head -1; }
LOG_GROUP="$(read_env LOG_GROUP)"
MIRROR_PATH="$(read_env MIRROR_PATH)"
HEALTH_URL="$(read_env HEALTH_URL)"
TOPIC_NAME="$(read_env TOPIC_NAME)"
HEARTBEAT_TOPIC_NAME="$(read_env HEARTBEAT_TOPIC_NAME)"
MAX_SILENCE_DAYS="$(read_env MAX_SILENCE_DAYS)"
BASELINE_DAYS="$(read_env BASELINE_DAYS)"
for v in LOG_GROUP MIRROR_PATH HEALTH_URL TOPIC_NAME HEARTBEAT_TOPIC_NAME \
         MAX_SILENCE_DAYS BASELINE_DAYS; do
  [ -n "${!v}" ] || { echo "FAIL: could not read $v from workflow env"; exit 1; }
done
echo "workflow env: MAX_SILENCE_DAYS=$MAX_SILENCE_DAYS BASELINE_DAYS=$BASELINE_DAYS TOPIC_NAME=$TOPIC_NAME HEARTBEAT=$HEARTBEAT_TOPIC_NAME"

ALERTS_ARN="arn:aws:sns:us-east-1:000000000000:$TOPIC_NAME"
HB_ARN="arn:aws:sns:us-east-1:000000000000:$HEARTBEAT_TOPIC_NAME"

# ── Fakes ────────────────────────────────────────────────────────────────
mkdir -p "$SANDBOX/bin"
cat > "$SANDBOX/bin/aws" <<'FAKE'
#!/usr/bin/env bash
echo "$*" >> "$AWS_CALLS"
case "$1 $2" in
  "logs filter-log-events")
    # Two calls per run: the recent window, then the baseline window.
    n=$(grep -c "logs filter-log-events" "$AWS_CALLS")
    if [ "$n" -le 1 ]; then want="${FAKE_LOGS:-0}"; else want="${FAKE_BASELINE:-0}"; fi
    [ "$want" = "fail" ] && exit 1
    echo "$want"
    ;;
  "sns list-topics")
    case "$*" in
      *"$HEARTBEAT_TOPIC_NAME"*) echo "${FAKE_HB_ARN:-None}" ;;
      *)                         echo "${FAKE_TOPIC_ARN:-$ALERTS_ARN}" ;;
    esac
    ;;
  "sns list-subscriptions-by-topic")
    [ "${FAKE_CONFIRMED:-}" = "fail" ] && exit 1
    echo "${FAKE_CONFIRMED:-1}"
    ;;
  "sns get-topic-attributes")
    echo "${FAKE_PENDING:-0}"
    ;;
  "sns publish")
    exit 0
    ;;
  *)
    echo "unexpected aws call: $*" >&2; exit 64
    ;;
esac
FAKE
cat > "$SANDBOX/bin/curl" <<'FAKE'
#!/usr/bin/env bash
[ "${FAKE_HEALTH:-ok}" = "unreachable" ] && exit 7
if [ "${FAKE_HEALTH:-ok}" = "ok" ]; then
  echo '{"status":"ok","db":"OK"}'
else
  echo '{"status":"degraded"}'
fi
FAKE
chmod +x "$SANDBOX/bin/aws" "$SANDBOX/bin/curl"

pass=0; fail=0

# run <case> <expected-exit> <expected-text> <alerts-publish: yes|no> <heartbeat: yes|no>
run() {
  local name="$1" want_exit="$2" want_text="$3" want_pub="$4" want_hb="$5"
  local out rc problems=""
  export AWS_CALLS="$SANDBOX/calls.txt"
  : > "$AWS_CALLS"
  set +e
  out="$(PATH="$SANDBOX/bin:$PATH" \
        AWS_CALLS="$AWS_CALLS" ALERTS_ARN="$ALERTS_ARN" \
        LOG_GROUP="$LOG_GROUP" MIRROR_PATH="$MIRROR_PATH" \
        HEALTH_URL="$HEALTH_URL" TOPIC_NAME="$TOPIC_NAME" \
        HEARTBEAT_TOPIC_NAME="$HEARTBEAT_TOPIC_NAME" \
        MAX_SILENCE_DAYS="$MAX_SILENCE_DAYS" BASELINE_DAYS="$BASELINE_DAYS" \
        GITHUB_SERVER_URL="https://github.test" GITHUB_REPOSITORY="o/r" GITHUB_RUN_ID="1" \
        FAKE_LOGS="${FAKE_LOGS:-}" FAKE_BASELINE="${FAKE_BASELINE:-}" \
        FAKE_CONFIRMED="${FAKE_CONFIRMED:-}" FAKE_PENDING="${FAKE_PENDING:-}" \
        FAKE_HEALTH="${FAKE_HEALTH:-}" FAKE_TOPIC_ARN="${FAKE_TOPIC_ARN:-}" \
        FAKE_HB_ARN="${FAKE_HB_ARN:-}" \
        SIMULATE_SILENCE="${SIMULATE_SILENCE:-false}" \
        SIMULATE_NO_SUBSCRIPTIONS="${SIMULATE_NO_SUBSCRIPTIONS:-false}" \
        bash "$SANDBOX/check.sh" 2>&1)"
  rc=$?
  set -e

  [ "$rc" = "$want_exit" ] || problems="$problems exit=$rc(want $want_exit)"
  if [ "$want_text" != "EMPTY" ] && ! grep -qF "$want_text" <<<"$out"; then
    problems="$problems missing-text"
  fi

  local pub=no hb=no
  grep -q "sns publish --topic-arn $ALERTS_ARN" "$AWS_CALLS" && pub=yes
  grep -q "sns publish --topic-arn $HB_ARN" "$AWS_CALLS" && hb=yes
  [ "$pub" = "$want_pub" ] || problems="$problems alerts-publish=$pub(want $want_pub)"
  [ "$hb" = "$want_hb" ] || problems="$problems heartbeat=$hb(want $want_hb)"

  if [ -z "$problems" ]; then
    echo "  [ok] $name (exit $rc, verdict-published=$pub, heartbeat=$hb)"; pass=$((pass+1))
  else
    echo "  [FAIL] $name:$problems"
    sed 's/^/        /' <<<"$out"
    fail=$((fail+1))
  fi
}

echo "cases:"

FAKE_LOGS=3 FAKE_BASELINE=99 FAKE_CONFIRMED=1 FAKE_HEALTH=ok FAKE_HB_ARN="$HB_ARN" \
  run "healthy: mirror active, channel confirmed, heartbeat sent" 0 "Client mirror active" no yes

FAKE_LOGS=0 FAKE_BASELINE=42 FAKE_CONFIRMED=1 FAKE_HEALTH=ok FAKE_HB_ARN="$HB_ARN" \
  run "fires AND delivers: signal died, confirmed subscriber exists" 1 "Verdict published" yes yes

# The measured state of prod on 2026-09-22: the mirror has never reported.
FAKE_LOGS=0 FAKE_BASELINE=0 FAKE_CONFIRMED=1 FAKE_HEALTH=ok FAKE_HB_ARN="$HB_ARN" \
  run "inert, not red: no baseline means silence proves nothing" 0 "no baseline" no yes

FAKE_LOGS=0 FAKE_BASELINE=42 FAKE_CONFIRMED=1 FAKE_HEALTH=unreachable FAKE_HB_ARN="$HB_ARN" \
  run "does not fire: silent mirror while API unhealthy" 0 "the API alarm owns this one" no yes

# The accepted limitation: with no confirmed subscriber the finding cannot be
# delivered, and publishing it into that topic would be the void describing
# itself. It must stay a recorded failure, not a pretend delivery.
FAKE_LOGS=3 FAKE_BASELINE=99 FAKE_CONFIRMED=0 FAKE_PENDING=0 FAKE_HEALTH=ok FAKE_HB_ARN="$HB_ARN" \
  run "fires, does NOT publish: channel has no confirmed subscriber" 1 "no confirmed subscriber" no yes

# PendingConfirmation: reads as coverage in the console, delivers nothing, and
# wants a different action than "nobody subscribed".
FAKE_LOGS=3 FAKE_BASELINE=99 FAKE_CONFIRMED=0 FAKE_PENDING=1 FAKE_HEALTH=ok FAKE_HB_ARN="$HB_ARN" \
  run "names the state: created but never confirmed" 1 "never confirmed" no yes

# Both halves broken: the telemetry verdict must not claim delivery either.
FAKE_LOGS=0 FAKE_BASELINE=42 FAKE_CONFIRMED=0 FAKE_PENDING=0 FAKE_HEALTH=ok FAKE_HB_ARN="$HB_ARN" \
  run "silent mirror + dead channel: reported, not delivered" 1 "Verdict not delivered" no yes

FAKE_LOGS=fail FAKE_BASELINE=99 FAKE_CONFIRMED=1 FAKE_HEALTH=ok FAKE_HB_ARN="$HB_ARN" \
  run "fires: log query failed (cannot see != nothing to see)" 1 "could not see" yes yes

FAKE_LOGS=3 FAKE_BASELINE=99 FAKE_CONFIRMED=fail FAKE_HEALTH=ok FAKE_HB_ARN="$HB_ARN" \
  run "fires: channel query failed" 1 "Channel check could not run" no yes

FAKE_LOGS=3 FAKE_BASELINE=99 FAKE_CONFIRMED=1 FAKE_HEALTH=ok FAKE_TOPIC_ARN=None FAKE_HB_ARN="$HB_ARN" \
  run "fires: alert topic missing entirely" 1 "Alert topic missing" no yes

# Today's real state: the heartbeat topic does not exist yet, so the
# dead-watcher cover is absent and must say so rather than imply cover.
FAKE_LOGS=3 FAKE_BASELINE=99 FAKE_CONFIRMED=1 FAKE_HEALTH=ok FAKE_HB_ARN=None \
  run "says so when dead-watcher cover is missing" 0 "No dead-watcher cover" no no

FAKE_LOGS=9 FAKE_BASELINE=99 FAKE_CONFIRMED=1 FAKE_HEALTH=ok FAKE_HB_ARN="$HB_ARN" SIMULATE_SILENCE=true \
  run "drill: simulate-silence fires and delivers" 1 "Expected telemetry went silent" yes yes

FAKE_LOGS=3 FAKE_BASELINE=99 FAKE_CONFIRMED=1 FAKE_HEALTH=ok FAKE_HB_ARN="$HB_ARN" SIMULATE_NO_SUBSCRIPTIONS=true \
  run "drill: simulate-no-subscriptions fires" 1 "no confirmed subscriber" no yes

echo "absence-alert self-test: $pass passed, $fail failed"
[ "$fail" = 0 ] || exit 1
