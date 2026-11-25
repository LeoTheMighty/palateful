#!/usr/bin/env bash
# E-3 (P0) — A shake never interrupts what the user is doing. expectations.md E-3.
# Runs flutter/e3_no_interruption_test.dart against the real app through
# lib/run_flutter_eval.sh. Exit 0 GREEN, 1 RED (named SHAKE-RED markers
# only), 3 eval broken, blind or tampered. Pins the runner and the test;
# the runner pins the harness. Locked by Gate 4: fix the code, not the eval.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_SHA="736976e5442d7a73c7559a2d92d9f97c51d39632a3ba7715c87d0b8d0b954346"
got="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$HERE/lib/run_flutter_eval.sh" 2>/dev/null)"
if [[ "$got" != "$RUNNER_SHA" ]]; then
  echo "EVAL-TAMPERED E-3: lib/run_flutter_eval.sh sha256 ${got:-missing} != pinned $RUNNER_SHA"; exit 3
fi
exec bash "$HERE/lib/run_flutter_eval.sh" E-3 flutter/e3_no_interruption_test.dart c0b202a835acb3d95b599196b7756ec48ee74bf49c40a7688f6d7f200206a96a 9
