#!/usr/bin/env bash
# Run all E2E integration tests sequentially via flutter drive.
#
# Prerequisites:
#   1. Backend stack running:
#        docker compose -f docker-compose.yml -f docker-compose.e2e.yml up --build -d
#   2. ChromeDriver installed (brew install chromedriver)
#
# Usage:
#   ./services/e2e/scripts/run_all.sh           # all tests
#   ./services/e2e/scripts/run_all.sh 01 03     # specific tests by number

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../../../app" && pwd)"
DRIVER="test_driver/integration_test.dart"

cd "$APP_DIR"

# Start ChromeDriver if not already running
if ! pgrep -q chromedriver; then
  echo "==> Starting ChromeDriver on port 4444..."
  chromedriver --port=4444 &
  DRIVER_PID=$!
  trap 'kill $DRIVER_PID 2>/dev/null || true' EXIT
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

PASSED=0
FAILED=0
ERRORS=()

for test_file in "${TEST_FILES[@]}"; do
  echo ""
  echo "=== Running: $test_file ==="

  # Kill stale Chrome instances between tests to avoid port conflicts
  pkill -f "flutter_tools_chrome_device" 2>/dev/null || true
  sleep 1

  if flutter drive \
    --driver="$DRIVER" \
    --target="$test_file" \
    -d chrome \
    --dart-define=E2E_MODE=true; then
    PASSED=$((PASSED + 1))
    echo "=== PASS: $test_file ==="
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
