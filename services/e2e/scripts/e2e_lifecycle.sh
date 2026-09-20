#!/usr/bin/env bash
# e2e_lifecycle.sh — the one-command E2E lifecycle.
#
#   stack up → wait for the API to report healthy → run every flow →
#   tear the stack down (in a trap, so teardown survives a failure or a
#   Ctrl-C) → exit 0 iff every flow passed.
#
# This is what `npx nx run e2e:test` invokes. Use scripts/run_all.sh
# directly only when you are managing the stack yourself.
#
# Usage:
#   bash services/e2e/scripts/e2e_lifecycle.sh          # all flows
#   bash services/e2e/scripts/e2e_lifecycle.sh 01 03    # specific flows
#
# Environment overrides:
#   E2E_HEALTH_URL      health endpoint to poll (default http://localhost:8000/v1/health)
#   E2E_HEALTH_TIMEOUT  seconds to wait for healthy (default 180)
#   E2E_KEEP_STACK      set to 1 to skip teardown (debugging a failure)
#
# Exit codes: 0 all flows passed · 1 at least one flow failed ·
#             2 prerequisite missing or the stack never came up healthy.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

HEALTH_URL="${E2E_HEALTH_URL:-http://localhost:8000/v1/health}"
HEALTH_TIMEOUT="${E2E_HEALTH_TIMEOUT:-180}"
KEEP_STACK="${E2E_KEEP_STACK:-0}"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.e2e.yml)

# Compose derives the project name from the working directory. Running this
# from a git worktree (which is exactly what `/devx` local CI does) would
# otherwise create a second, differently-named project — so `stack-down`,
# `ps -q`, and `docker kill palateful-api` from the repo root would all
# miss these containers. Pin it.
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-palateful}"

cd "$REPO_ROOT" || { echo "ERROR: cannot cd to repo root $REPO_ROOT" >&2; exit 2; }

# --- prerequisites --------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found on PATH." >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: the Docker daemon is not running — start Docker Desktop and retry." >&2
  exit 2
fi
# Checked here too, not just in run_all.sh — a mismatch found after
# `docker compose up --build` has already run costs minutes for nothing.
# shellcheck source=services/e2e/scripts/_chromedriver_check.sh
. "$SCRIPT_DIR/_chromedriver_check.sh"
check_chromedriver || exit $?
# docker-compose.yml declares `env_file: .env`, and .env is gitignored — so
# it is absent in a fresh clone and in every git worktree. Compose's own
# error for this is easy to misread as a compose-file problem.
if [[ ! -f .env ]]; then
  echo "ERROR: $REPO_ROOT/.env is missing (docker-compose.yml requires it)." >&2
  echo "       Copy it from .env.example, or from your main checkout if you" >&2
  echo "       are running inside a git worktree (.env is gitignored)." >&2
  exit 2
fi

# --- teardown -------------------------------------------------------------

# Registered before `up` so a failure *during* startup still tears down
# whatever came up. run_all.sh's own EXIT trap (chromedriver kill) is
# process-local and composes with this one — both fire.
teardown() {
  local rc=$?
  trap - EXIT
  if [[ "$KEEP_STACK" == "1" ]]; then
    echo "==> E2E_KEEP_STACK=1 — leaving the stack running."
  else
    echo ""
    echo "==> Tearing down the e2e stack..."
    "${COMPOSE[@]}" down --remove-orphans || \
      echo "WARNING: teardown failed — run 'npx nx run e2e:stack-down' by hand." >&2
  fi
  exit "$rc"
}
trap teardown EXIT
# Without these, a Ctrl-C/SIGTERM would kill the shell before the EXIT trap
# ran, leaving the stack up.
trap 'exit 130' INT
trap 'exit 143' TERM

# --- up -------------------------------------------------------------------

echo "==> Starting the e2e stack (docker compose up --build -d)..."
if ! "${COMPOSE[@]}" up --build -d; then
  echo "ERROR: failed to start the e2e stack." >&2
  exit 2
fi

# --- wait healthy ---------------------------------------------------------

echo "==> Waiting for the API to report healthy at $HEALTH_URL (timeout ${HEALTH_TIMEOUT}s)..."
deadline=$(( SECONDS + HEALTH_TIMEOUT ))
healthy=0
while (( SECONDS < deadline )); do
  if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 2
done

if (( healthy != 1 )); then
  echo "ERROR: the API did not become healthy within ${HEALTH_TIMEOUT}s." >&2
  echo "       Recent api logs:" >&2
  "${COMPOSE[@]}" logs --tail=50 api >&2 || true
  exit 2
fi
echo "==> API healthy."

# --- flows ----------------------------------------------------------------

bash "$SCRIPT_DIR/run_all.sh" "$@"
exit $?
