#!/usr/bin/env bash
# Run all E2E integration tests sequentially via flutter drive.
#
# This is the *inner* runner: it assumes the backend stack is already up.
# For the full lifecycle (stack up → wait-healthy → flows → teardown) use
# `npx nx run e2e:test`, which invokes scripts/e2e_lifecycle.sh.
#
# Prerequisites:
#   1. Backend stack running:
#        docker compose -f docker-compose.yml -f docker-compose.e2e.yml up --build -d
#   2. ChromeDriver installed (brew install chromedriver)
#
# Usage:
#   ./services/e2e/scripts/run_all.sh           # all tests
#   ./services/e2e/scripts/run_all.sh 01 03     # specific tests by number
#
# Exit codes: 0 all flows passed · 1 at least one flow failed ·
#             2 prerequisite missing (chromedriver).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../../../app" && pwd)"
DRIVER="test_driver/integration_test.dart"

# The Flutter build defaults API_BASE_URL to https://api.palateful.app
# (app/lib/core/config/environment.dart). Without this define a "local"
# e2e run compiles a bundle that talks to PRODUCTION with the fixed e2e
# token. Every browser build launched from this repo pins it to localhost.
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

# Retry signature: `flutter drive -d chrome` intermittently fails to attach
# to the freshly launched Chrome device between consecutive tests. Exactly
# one retry, only on this signature — a blanket retry would mask real
# regressions.
RETRY_SIGNATURE="AppConnectionException"

# Hard ceiling per flow attempt, in seconds. Generous — the first flow of a
# run pays for the web compile — but finite, because a wedged `flutter
# drive` never exits on its own.
FLOW_TIMEOUT="${E2E_FLOW_TIMEOUT:-900}"

cd "$APP_DIR" || { echo "ERROR: cannot cd to $APP_DIR" >&2; exit 2; }

# Fail fast on a missing or version-mismatched chromedriver.
# shellcheck source=services/e2e/scripts/_chromedriver_check.sh
. "$SCRIPT_DIR/_chromedriver_check.sh"
check_chromedriver || exit $?

DRIVER_PID=""
LOG_FILE=""

# One trap for both the chromedriver we may have started and the temp log
# of whichever flow is in flight — otherwise an interrupt mid-suite leaks
# both.
cleanup() {
  [[ -n "$DRIVER_PID" ]] && kill "$DRIVER_PID" 2>/dev/null
  [[ -n "$LOG_FILE" ]] && rm -f "$LOG_FILE"
  return 0
}
trap cleanup EXIT

# Start ChromeDriver if not already running
if ! pgrep -q chromedriver; then
  echo "==> Starting ChromeDriver on port 4444..."
  chromedriver --port=4444 &
  DRIVER_PID=$!
  sleep 2
else
  echo "==> ChromeDriver already running"
fi

# Collect test files to run
if [[ $# -gt 0 ]]; then
  # Run specific tests by number (e.g., 01 03 07)
  TEST_FILES=()
  for num in "$@"; do
    pattern="integration_test/${num}*_test.dart"
    # Unquoted on purpose — this is the glob expansion. An unmatched glob
    # stays literal, which the -f test below rejects.
    # shellcheck disable=SC2206
    matches=( $pattern )
    if [[ -f "${matches[0]}" ]]; then
      TEST_FILES+=("${matches[0]}")
    else
      echo "WARNING: no test matching $pattern" >&2
    fi
  done
else
  # Run all numbered test files in order
  TEST_FILES=(integration_test/0*_test.dart)
fi

# Guard the empty case explicitly — expanding an empty array under `set -u`
# is an error on older bash, and "0 passed, 0 failed" must never read green.
if [[ ${#TEST_FILES[@]} -eq 0 ]]; then
  echo "ERROR: no test files matched — nothing to run." >&2
  exit 2
fi

# Kill stale Chrome instances to avoid port conflicts / stale-device attach
# failures. Run before every attempt, including retries — retrying against
# the same stale device adds nothing.
reset_chrome_device() {
  pkill -f "flutter_tools_chrome_device" 2>/dev/null || true
  sleep 1
}

# Run one flow, streaming output while also capturing it so the retry
# decision can inspect the failure signature. `tee` is last in the pipe, so
# the drive exit code comes from PIPESTATUS[0], not the pipeline status.
#
# `perl alarm` bounds each attempt. `flutter drive` can wedge indefinitely
# when the dwds debug service fails to attach to Chrome, and a wedged flow
# hangs the whole suite forever rather than failing it. A pending alarm
# survives exec, so this fires even though perl has replaced itself with
# flutter. SIGALRM kills it -> nonzero exit -> counted as a failure, and an
# AppConnectionException in the captured log still routes to a retry.
#
# Note: with stdout a pipe, Dart block-buffers, so output can arrive in
# bursts rather than smoothly — a slow flow and a wedged one look alike
# while in progress. Allocating a pty via `script` would fix that but needs
# a tty on stdin, which does not exist under nx, CI, or any background run
# (`tcgetattr/ioctl: Operation not supported on socket`). The timeout is
# what makes the difference observable instead: a wedge now ends.
run_flow() {
  local test_file="$1"
  local log_file="$2"

  perl -e 'alarm shift @ARGV; exec @ARGV or die "exec failed: $!\n"' "$FLOW_TIMEOUT" \
    flutter drive \
      --driver="$DRIVER" \
      --target="$test_file" \
      -d chrome \
      --dart-define=E2E_MODE=true \
      --dart-define=API_BASE_URL="$API_BASE_URL" 2>&1 | tee "$log_file"

  return "${PIPESTATUS[0]}"
}

PASSED=0
FAILED=0
ERRORS=()

for test_file in "${TEST_FILES[@]}"; do
  echo ""
  echo "=== Running: $test_file ==="

  [[ -n "$LOG_FILE" ]] && rm -f "$LOG_FILE"
  LOG_FILE="$(mktemp)"
  reset_chrome_device

  if run_flow "$test_file" "$LOG_FILE"; then
    PASSED=$((PASSED + 1))
    echo "=== PASS: $test_file ==="
  elif grep -q "$RETRY_SIGNATURE" "$LOG_FILE"; then
    echo "=== RETRY: $test_file ($RETRY_SIGNATURE — retrying once) ==="
    reset_chrome_device
    if run_flow "$test_file" "$LOG_FILE"; then
      PASSED=$((PASSED + 1))
      echo "=== PASS (on retry): $test_file ==="
    else
      FAILED=$((FAILED + 1))
      ERRORS+=("$test_file")
      echo "=== FAIL (after retry): $test_file ==="
    fi
  else
    FAILED=$((FAILED + 1))
    ERRORS+=("$test_file")
    echo "=== FAIL: $test_file ==="
  fi
done

echo ""
echo "========================================="
echo "  Results: $PASSED passed, $FAILED failed"
echo "========================================="

if [[ ${#ERRORS[@]} -gt 0 ]]; then
  echo "  Failed tests:"
  for f in "${ERRORS[@]}"; do
    echo "    - $f"
  done
  exit 1
fi

exit 0
