#!/usr/bin/env bash
# E-5 eval (admin-request-intake, 1e84ad) — what Leo reads is what an agent reads.
#
# Gate 4 stamps this file's sha256. It pins the shared runner below, the
# runner pins services/api/tests/devreq_harness.py, and the test file is
# pinned here, so the lock covers everything this eval runs. Make the code
# pass it; a genuinely wrong eval is 'devx revise', not an edit.
#
# Exit 0 GREEN · 1 RED (a test failed) · 3 EVAL-TAMPERED / EVAL-WRONG-REASON.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="$HERE/lib/run_pytest_eval.sh"
RUNNER_SHA="c847e4d42dea56e045f28ebd4c005ed3fc2f9c106fe0f561d3a663d4980a152b"
got="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$RUNNER" 2>/dev/null)"
if [[ "$got" != "$RUNNER_SHA" ]]; then
  echo "EVAL-TAMPERED E-5: $RUNNER sha256 ${got:-missing} != pinned $RUNNER_SHA"
  exit 3
fi
exec bash "$RUNNER" E-5 services/api/tests/test_dev_requests_normalization.py 4c1d54671235be185a26b513f8f7471982f72ce1f248f66a2337dda158dfde65 12
