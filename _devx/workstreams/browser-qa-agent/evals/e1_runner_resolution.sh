#!/usr/bin/env bash
# e1_runner_resolution.sh — E-1: RED gate resolves runners in palateful (P0).
#
# Asserts (plan.md §E-1 eval mechanics — the threshold's intent, positively):
#   1. `devx gate evals 41ee13 --dry-run` JSON: every `planned` entry has a
#      non-null command, and planned + deferred counts equal 6. This
#      satisfies "zero `not-run (no runner)`" a fortiori — the prose verdict
#      strings never appear in dry-run output.
#   2. `grep -c playwright devx.config.yaml` returns 0 — the `qa:` block
#      names no tool that is not installed in the repo.
#
# Exit contract: 0 green · 1 missing behavior (right-reason RED) ·
# 2 + `INFRA:` sentinel on infrastructure failure (never counts as RED).
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "INFRA: not inside a git repository"; exit 2; }
cd "$REPO_ROOT" || { echo "INFRA: cannot cd to repo root"; exit 2; }
command -v devx >/dev/null 2>&1 || { echo "INFRA: devx CLI not on PATH"; exit 2; }
command -v node >/dev/null 2>&1 || { echo "INFRA: node not on PATH"; exit 2; }

if ! DRY_JSON="$(devx gate evals 41ee13 --dry-run 2>&1)"; then
  echo "INFRA: 'devx gate evals 41ee13 --dry-run' exited nonzero:"
  echo "$DRY_JSON"
  exit 2
fi

printf '%s' "$DRY_JSON" | node -e '
  const raw = require("fs").readFileSync(0, "utf8");
  let j;
  try {
    j = JSON.parse(raw);
  } catch (e) {
    console.log("INFRA: dry-run output is not JSON: " + e.message);
    process.exit(2);
  }
  const planned = j.planned ?? [];
  const deferred = j.deferred ?? [];
  if (planned.length + deferred.length !== 6) {
    console.log(`MISSING BEHAVIOR: dry-run resolved ${planned.length} planned + ${deferred.length} deferred expectations; expected 6 total — runner resolution is incomplete`);
    process.exit(1);
  }
  const noCmd = planned.filter((p) => !p.command);
  if (noCmd.length > 0) {
    console.log(`MISSING BEHAVIOR: no \`projects:\` runner resolved a test command for: ${noCmd.map((p) => p.eId).join(", ")}`);
    process.exit(1);
  }
  console.log(`runner resolution OK: ${planned.length} planned (all with commands) + ${deferred.length} deferred`);
' || exit $?

PLAYWRIGHT_COUNT="$(grep -c playwright devx.config.yaml || true)"
if [[ "$PLAYWRIGHT_COUNT" != "0" ]]; then
  echo "MISSING BEHAVIOR: devx.config.yaml still names playwright ${PLAYWRIGHT_COUNT} time(s) — playwright is installed nowhere in this repo; the qa: block must name only installed tools (E-1 threshold)"
  exit 1
fi

echo "E-1 GREEN: all 6 expectations resolve (or legally defer) and the qa: block names no uninstalled tools"
exit 0
