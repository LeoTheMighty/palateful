#!/usr/bin/env bash
# e3_walkthrough_emission.sh — E-3: walkthrough template emission with
# executed checks (P1).
#
# Contract this eval pins for the Phase 3 template + /devx emission wiring
# (the template is authored to satisfy THIS script, not vice versa):
#   - the template installs at _devx/templates/engine/qa-walkthrough.md;
#   - emitted walkthroughs are test/test-*-qa-walkthrough.md;
#   - machine-checkable items are checkbox lines tagged `machine`; at
#     emission every one is executed → checked `[x]`, with fenced evidence
#     blocks pasted (≥ one fence pair per machine item, file-wide);
#   - human items are checkbox lines tagged `human`; each stays unchecked
#     and carries an inline "verify" hint (e.g. "how to verify: …").
#
# Exit contract: 0 green · 1 missing behavior (right-reason RED) ·
# 2 + `INFRA:` sentinel on infrastructure failure (never counts as RED).
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "INFRA: not inside a git repository"; exit 2; }
cd "$REPO_ROOT" || { echo "INFRA: cannot cd to repo root"; exit 2; }

TEMPLATE="_devx/templates/engine/qa-walkthrough.md"
if [[ ! -f "$TEMPLATE" ]]; then
  echo "MISSING BEHAVIOR: $TEMPLATE does not exist — the QA-walkthrough template is not installed"
  exit 1
fi

shopt -s nullglob
WALKTHROUGHS=(test/test-*-qa-walkthrough.md)
if [[ ${#WALKTHROUGHS[@]} -eq 0 ]]; then
  echo "MISSING BEHAVIOR: no test/test-*-qa-walkthrough.md exists — no walkthrough has been emitted from the template"
  exit 1
fi

FAILED=0
for f in "${WALKTHROUGHS[@]}"; do
  MACHINE_TOTAL="$(grep -cE '^[[:space:]]*[-*][[:space:]]\[.\].*\bmachine\b' "$f" || true)"
  MACHINE_UNCHECKED="$(grep -cE '^[[:space:]]*[-*][[:space:]]\[ \].*\bmachine\b' "$f" || true)"
  HUMAN_NO_HINT="$(grep -E '^[[:space:]]*[-*][[:space:]]\[.\].*\bhuman\b' "$f" | { grep -cvi 'verify' || true; })"
  FENCE_LINES="$(grep -c '^[[:space:]]*```' "$f" || true)"

  if [[ "$MACHINE_TOTAL" -eq 0 ]]; then
    echo "MISSING BEHAVIOR: $f has no machine-tagged checkbox items — emission did not follow the template contract"
    FAILED=1
    continue
  fi
  if [[ "$MACHINE_UNCHECKED" -ne 0 ]]; then
    echo "MISSING BEHAVIOR: $f has ${MACHINE_UNCHECKED} unchecked machine item(s) — every machine item must be executed (checked) at emission"
    FAILED=1
  fi
  if [[ $((FENCE_LINES / 2)) -lt "$MACHINE_TOTAL" ]]; then
    echo "MISSING BEHAVIOR: $f has $((FENCE_LINES / 2)) fenced evidence block(s) for ${MACHINE_TOTAL} machine item(s) — every machine item needs pasted fenced evidence"
    FAILED=1
  fi
  if [[ "$HUMAN_NO_HINT" -ne 0 ]]; then
    echo "MISSING BEHAVIOR: $f has ${HUMAN_NO_HINT} human item(s) without a 'verify' hint line"
    FAILED=1
  fi
done

[[ "$FAILED" -eq 0 ]] || exit 1
echo "E-3 GREEN: template installed; ${#WALKTHROUGHS[@]} walkthrough(s) with 100% machine items executed+evidenced and hints on every human item"
exit 0
