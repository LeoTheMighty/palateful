#!/usr/bin/env bash
# e2_e2e_one_command.sh — E-2: one-command e2e suite green (P0).
#
# Asserts (expectations.md E-2 + plan.md Phase 2 Context):
#   - `npx nx run e2e:test` is a full lifecycle (stack up → wait-healthy →
#     flows → teardown-in-trap), wired through
#     services/e2e/scripts/e2e_lifecycle.sh;
#   - two consecutive runs exit 0 with pass count == glob count
#     (`app/integration_test/0*_test.dart`) — the flake bar, and the guard
#     that a silently dropped/added flow fails rather than hiding under ≥.
#
# The missing-feature checks run BEFORE the infra checks: at RED the
# lifecycle wrapper does not exist, which is the missing behavior itself —
# no Docker/chromedriver needed to observe it (right-reason, cheap).
#
# Exit contract: 0 green · 1 missing behavior (right-reason RED) ·
# 2 + `INFRA:` sentinel on infrastructure failure (never counts as RED).
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "INFRA: not inside a git repository"; exit 2; }
cd "$REPO_ROOT" || { echo "INFRA: cannot cd to repo root"; exit 2; }

WRAPPER="services/e2e/scripts/e2e_lifecycle.sh"
if [[ ! -f "$WRAPPER" ]]; then
  echo "MISSING BEHAVIOR: $WRAPPER does not exist — 'npx nx run e2e:test' has no stack lifecycle (up → wait-healthy → flows → teardown-in-trap); the one-command e2e suite is not built yet"
  exit 1
fi
if ! grep -q "e2e_lifecycle.sh" services/e2e/project.json; then
  echo "MISSING BEHAVIOR: the e2e:test target in services/e2e/project.json does not invoke e2e_lifecycle.sh — the one-command lifecycle is not wired"
  exit 1
fi

GLOB_COUNT="$(ls app/integration_test/0*_test.dart 2>/dev/null | wc -l | tr -d ' ')"
if [[ "$GLOB_COUNT" -lt 8 ]]; then
  echo "MISSING BEHAVIOR: flow population is ${GLOB_COUNT}, expected 8 — the hmp-5 flow (meals_home_promotion) has not been renamed into the 0* glob"
  exit 1
fi

# Infra preconditions — only meaningful once the feature exists.
command -v docker >/dev/null 2>&1 || { echo "INFRA: docker not installed"; exit 2; }
docker info >/dev/null 2>&1 || { echo "INFRA: docker daemon not running"; exit 2; }
command -v chromedriver >/dev/null 2>&1 || { echo "INFRA: chromedriver not installed (brew install chromedriver)"; exit 2; }
command -v npx >/dev/null 2>&1 || { echo "INFRA: npx not on PATH"; exit 2; }
command -v flutter >/dev/null 2>&1 || { echo "INFRA: flutter not on PATH"; exit 2; }

for run in 1 2; do
  LOG="$(mktemp)"
  echo "=== e2 eval: suite run #${run}/2 ==="
  if ! npx nx run e2e:test 2>&1 | tee "$LOG"; then
    echo "MISSING BEHAVIOR: suite run #${run} of 'npx nx run e2e:test' exited nonzero — one-command green not achieved"
    exit 1
  fi
  if ! grep -q "Results: ${GLOB_COUNT} passed, 0 failed" "$LOG"; then
    echo "MISSING BEHAVIOR: suite run #${run} did not report 'Results: ${GLOB_COUNT} passed, 0 failed' — pass count must equal the flow-glob count"
    exit 1
  fi
done

echo "E-2 GREEN: two consecutive one-command runs, ${GLOB_COUNT}/${GLOB_COUNT} flows each"
exit 0
