#!/usr/bin/env bash
# E-4 (P0) — Admins get the dev-request form; anyone uncertain gets the user path. expectations.md E-4.
# Runs flutter/e4_role_and_ring_test.dart against the real app through
# lib/run_flutter_eval.sh. Exit 0 GREEN, 1 RED (named SHAKE-RED markers
# only), 3 eval broken, blind or tampered. Pins the runner and the test;
# the runner pins the harness. Locked by Gate 4: fix the code, not the eval.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_SHA="736976e5442d7a73c7559a2d92d9f97c51d39632a3ba7715c87d0b8d0b954346"
got="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$HERE/lib/run_flutter_eval.sh" 2>/dev/null)"
if [[ "$got" != "$RUNNER_SHA" ]]; then
  echo "EVAL-TAMPERED E-4: lib/run_flutter_eval.sh sha256 ${got:-missing} != pinned $RUNNER_SHA"; exit 3
fi
exec bash "$HERE/lib/run_flutter_eval.sh" E-4 flutter/e4_role_and_ring_test.dart 711612c1a9b6c50e8e96a97d5f0e59e4d6a3ab4733ad6fa1b084bd65ac02dd52 12
