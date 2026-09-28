#!/usr/bin/env bash
# localserve1 — serve the Flutter web app against the LOCAL API.
#
# WHY THIS IS A SCRIPT AND NOT A `flutter run` LINE IN project.json
# =================================================================
# `--dart-define=API_BASE_URL` must not be omittable. `environment.dart:9-12`
# defaults it to `https://api.palateful.app`, so a `flutter run -d chrome`
# with no defines serves a LOCAL app wired to PRODUCTION. SETUP.md told
# people to do exactly that for months.
#
# So the defines live here, the stack is checked before we serve, and a wrong
# invocation is made impossible rather than documented — e2eprod1's rule.
#
# WHAT IS *NOT* THE DANGER HERE, because overstating it costs the real guard
# ------------------------------------------------------------------------
# The E2E bypass token is NOT a production hazard. `dependencies.py:107-110`
# opens it only when BOTH `e2e_test_mode` is true AND `environment` is in
# ("development", "test"). Measured against live prod on 2026-09-27:
#
#     ENVIRONMENT    = "prod"        <- not in the allowed set
#     E2E_TEST_MODE  = (absent)      <- so settings.e2e_test_mode is False
#
# Two independent reasons it fails closed. An E2E_MODE bundle aimed at
# production sends the token and gets a 401.
#
# The real hazard is duller and likelier: a developer pointing a local app at
# production with their OWN credentials and editing live data believing it is
# a sandbox.
#
# Do not "improve" the gate to test only the flag, and do not move the token
# into an env var. A well-known constant that works only when `environment`
# is development is safer than a secret that might work anywhere.
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

case "$API_BASE_URL" in
  http://localhost:*|http://127.0.0.1:*|http://'[::1]':*) ;;
  *)
    echo "ERROR: refusing to serve against a non-local API: $API_BASE_URL" >&2
    echo "  This target exists to make a production target impossible." >&2
    echo "  An allowlist of local hosts, not a denylist of prod ones — so an" >&2
    echo "  unexpected value fails closed." >&2
    exit 2
    ;;
esac

# THE 'dev' vs 'development' TRAP — this cost the e2e author an afternoon and
# the overlay's comment exists because of it.
#
# `config.py:41` defaults `environment` to "dev". The gate requires
# ("development", "test"). "dev" is NOT "development", so a plain
# `docker compose up` accepts the token's shape and REJECTS it silently:
# every request 401s and nothing says the environment string didn't match.
#
# Only `docker-compose.e2e.yml` sets ENVIRONMENT=development (and repoints
# DATABASE_URL at the `test` database, which is why QA can create and destroy
# freely without touching local dev data).
if ! curl -fsS --max-time 3 "$API_BASE_URL/v1/health" >/dev/null 2>&1; then
  echo "ERROR: no API answering at $API_BASE_URL" >&2
  echo "  Start the stack WITH the e2e overlay:" >&2
  echo "      npx nx run e2e:stack-up" >&2
  echo "  A plain 'docker compose up' will 401 every request: it leaves" >&2
  echo "  ENVIRONMENT at config.py's default of \"dev\", and the bypass gate" >&2
  echo "  requires \"development\"." >&2
  exit 3
fi

# `chrome` launches a *fresh* Chrome that the Claude-in-Chrome extension is
# not attached to, so a browser-driven QA session cannot reach the app —
# it was hardcoded, and 0e had to work around it by hand. `web-server`
# instead serves the app and prints a URL, which an already-open,
# already-extended browser can navigate to:
#
#     FLUTTER_DEVICE=web-server npx nx run app:serve-local
#
# Default unchanged, so an interactive run behaves exactly as before.
FLUTTER_DEVICE="${FLUTTER_DEVICE:-chrome}"

echo "serving against $API_BASE_URL (E2E_MODE=true, no credentials needed)"
echo "device: $FLUTTER_DEVICE  (FLUTTER_DEVICE=web-server for automated QA)"
exec flutter run -d "$FLUTTER_DEVICE" \
  --dart-define=API_BASE_URL="$API_BASE_URL" \
  --dart-define=E2E_MODE=true
