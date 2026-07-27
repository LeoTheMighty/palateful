#!/usr/bin/env bash
# run-eval.sh — dispatcher for workstream eval artifacts.
#
# Committed at browser-qa-agent RED (plan.md §RED-stage prerequisites).
# `devx gate evals` invokes this with one argument (the eval artifact path
# relative to _devx/workstreams). `/devx` local CI may invoke the project
# `test` command bare — with no artifact there is nothing to run, so the
# no-arg path is a successful no-op rather than a hang on stdin.
set -uo pipefail

if [[ $# -eq 0 ]]; then
  echo "run-eval.sh: no artifact given — workstream evals run only via 'devx gate evals' (skipping)"
  exit 0
fi

exec bash "$1"
