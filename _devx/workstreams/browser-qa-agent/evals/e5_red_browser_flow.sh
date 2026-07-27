#!/usr/bin/env bash
# e5_red_browser_flow.sh — E-5: interactive expectation goes RED for the
# right reason (P1). Wrapper, per plan.md §E-5 artifact shape.
#
# Asserts the browser-flow eval CONVENTION exists and works:
#   (a) evals/README.md documents it (shape, exit contract, run-eval.sh
#       dispatcher, INFRA: sentinel discipline);
#   (b) evals/demo_browser_flow.sh exists and is right-reason-shaped —
#       running it yields exit 1 with the asserted-behavior banner
#       (`MISSING BEHAVIOR:`), or exit 2 + `INFRA:` when the stack is down
#       (which this wrapper reports and propagates as its own INFRA exit 2).
#
# The demo flow itself targets a deliberately unbuilt behavior, stays red
# by design, and is NOT a Verified-by artifact — it is the reference
# implementation the next workstream copies.
#
# Exit contract: 0 green · 1 missing behavior (right-reason RED) ·
# 2 + `INFRA:` sentinel on infrastructure failure (never counts as RED).
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "INFRA: not inside a git repository"; exit 2; }
cd "$REPO_ROOT" || { echo "INFRA: cannot cd to repo root"; exit 2; }

EVDIR="_devx/workstreams/browser-qa-agent/evals"
README="$EVDIR/README.md"
DEMO="$EVDIR/demo_browser_flow.sh"

if [[ ! -f "$README" ]]; then
  echo "MISSING BEHAVIOR: $README does not exist — the browser-flow eval convention is not documented for reuse"
  exit 1
fi
for term in "Exit contract" "INFRA:" "run-eval.sh" "MISSING BEHAVIOR:"; do
  if ! grep -qF "$term" "$README"; then
    echo "MISSING BEHAVIOR: $README does not document required convention element '$term'"
    exit 1
  fi
done

if [[ ! -f "$DEMO" ]]; then
  echo "MISSING BEHAVIOR: $DEMO does not exist — no reference browser-flow artifact for the next workstream to copy"
  exit 1
fi

DEMO_OUT="$(bash "$DEMO" 2>&1)"
DEMO_RC=$?

case "$DEMO_RC" in
  1)
    if grep -qF "MISSING BEHAVIOR:" <<<"$DEMO_OUT"; then
      echo "E-5 GREEN: convention documented; demo flow is right-reason-shaped (exit 1 + asserted-behavior banner)"
      exit 0
    fi
    echo "MISSING BEHAVIOR: demo flow exited 1 but printed no 'MISSING BEHAVIOR:' banner — convention violated"
    echo "$DEMO_OUT"
    exit 1
    ;;
  2)
    if grep -qF "INFRA:" <<<"$DEMO_OUT"; then
      echo "INFRA: demo flow reports an infrastructure failure (propagating):"
      grep -F "INFRA:" <<<"$DEMO_OUT"
      exit 2
    fi
    echo "MISSING BEHAVIOR: demo flow exited 2 without the INFRA: sentinel — convention violated"
    echo "$DEMO_OUT"
    exit 1
    ;;
  0)
    echo "MISSING BEHAVIOR: demo flow exited 0 — it must stay red by design (it targets a deliberately unbuilt behavior)"
    exit 1
    ;;
  *)
    echo "MISSING BEHAVIOR: demo flow exited ${DEMO_RC} — outside the documented exit contract (0/1/2)"
    echo "$DEMO_OUT"
    exit 1
    ;;
esac
