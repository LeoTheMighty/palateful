#!/usr/bin/env bash
# E-1 (P0) — A deliberate shake opens feedback over the current screen. expectations.md E-1.
# Runs flutter/e1_user_path_test.dart against the real app through
# lib/run_flutter_eval.sh. Exit 0 GREEN, 1 RED (named SHAKE-RED markers
# only), 3 eval broken, blind or tampered. Pins the runner and the test;
# the runner pins the harness. Locked by Gate 4: fix the code, not the eval.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_SHA="736976e5442d7a73c7559a2d92d9f97c51d39632a3ba7715c87d0b8d0b954346"
got="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$HERE/lib/run_flutter_eval.sh" 2>/dev/null)"
if [[ "$got" != "$RUNNER_SHA" ]]; then
  echo "EVAL-TAMPERED E-1: lib/run_flutter_eval.sh sha256 ${got:-missing} != pinned $RUNNER_SHA"; exit 3
fi
exec bash "$HERE/lib/run_flutter_eval.sh" E-1 flutter/e1_user_path_test.dart 7604d8224d70c81b91ea5702c8aeac7d08708b496180a2203582a02f72491f42 6
