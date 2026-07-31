#!/usr/bin/env bash
#
# Run deploy-freshness.yml's measure step against REAL prod, from a laptop.
#
# WHY THIS EXISTS
# ---------------
# `gh workflow run` resolves a workflow definition from a *pushed* ref, so a
# fix to deploy-freshness.yml cannot be exercised until it merges. That left
# E-7 step 1 ("dispatch run reports the true gap") owed for the entire life of
# every change to the check — including the credentials fix that only the first
# dispatch run revealed.
#
# This runs the SAME bash, extracted from the same YAML (never copied — see
# deploy-freshness-extract.py), against the same live ECS/ECR/git, from
# wherever you have AWS credentials. It proves the measurement half of the
# check before merge. It does NOT prove the mechanism half — running in Actions
# with environment-scoped credentials, on a schedule, unattended — which is
# exactly what E-7 steps 1/6 observe and what this script cannot substitute for.
#
# Usage:
#   bash tools/deploy-freshness-live-check.sh                    # real measurement
#   bash tools/deploy-freshness-live-check.sh --synthetic-gap-days 8   # E-7 step 3
#   bash tools/deploy-freshness-live-check.sh --synthetic-gap-days 1   # E-7 step 4
#
# Read-only: describe-services + describe-task-definition only, no mutations.
# Exit: mirrors the workflow step (0 fresh / 1 stale-or-unknown), 2 on usage
# or credential errors — so a missing AWS session can't be misread as "fresh".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/deploy-freshness.yml"
STEP_NAME="Measure gap between running image and its commit date"

SYNTHETIC=""
while [ $# -gt 0 ]; do
  case "$1" in
    --synthetic-gap-days) SYNTHETIC="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "usage: $0 [--synthetic-gap-days N]" >&2; exit 2 ;;
  esac
done

[ -f "$WORKFLOW" ] || { echo "FAIL: $WORKFLOW not found" >&2; exit 2; }
command -v aws >/dev/null || { echo "FAIL: aws CLI not on PATH" >&2; exit 2; }
aws sts get-caller-identity >/dev/null 2>&1 \
  || { echo "FAIL: no usable AWS credentials — refusing to report a gap" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Exit 2, not 1: a structural mismatch must not be readable as "prod is stale".
python3 "$REPO_ROOT/tools/deploy-freshness-extract.py" \
  "$WORKFLOW" "$STEP_NAME" "$TMP/measure.sh" || exit 2

# Pull the workflow's env block rather than restating it, so this script cannot
# check a different cluster/service/threshold than the scheduled run does.
read_env() { sed -n "s/^  $1: *//p" "$WORKFLOW" | head -1; }
AWS_REGION="$(read_env AWS_REGION)"
CLUSTER="$(read_env CLUSTER)"
SERVICE="$(read_env SERVICE)"
MAX_GAP_DAYS="$(read_env MAX_GAP_DAYS)"
[ -n "$AWS_REGION" ] && [ -n "$CLUSTER" ] && [ -n "$SERVICE" ] && [ -n "$MAX_GAP_DAYS" ] \
  || { echo "FAIL: could not read AWS_REGION/CLUSTER/SERVICE/MAX_GAP_DAYS from the workflow env block" >&2; exit 2; }
echo "workflow env: AWS_REGION=$AWS_REGION CLUSTER=$CLUSTER SERVICE=$SERVICE MAX_GAP_DAYS=$MAX_GAP_DAYS"
echo

# The workflow checks out with fetch-depth: 0 because the deployed SHA may be
# months old. A shallow or stale local clone would report "not a commit" and
# look like unknown provenance instead of a fetch problem, so say so up front.
if [ -f "$REPO_ROOT/.git/shallow" ]; then
  echo "WARNING: shallow clone — the deployed SHA may be missing locally; run 'git fetch --unshallow'." >&2
fi

set +e
( cd "$REPO_ROOT" \
  && env AWS_REGION="$AWS_REGION" CLUSTER="$CLUSTER" SERVICE="$SERVICE" \
         MAX_GAP_DAYS="$MAX_GAP_DAYS" SYNTHETIC_GAP_DAYS="$SYNTHETIC" \
     bash "$TMP/measure.sh" )
STATUS=$?
set -e

echo
echo "measure step exit: $STATUS  ($([ "$STATUS" -eq 0 ] && echo 'PASS — fresh' || echo 'FAIL — stale or undatable'))"
if [ -n "$SYNTHETIC" ]; then
  echo "NOTE: synthetic gap ${SYNTHETIC}d was substituted — this exercised the threshold, NOT prod's real age."
fi
exit "$STATUS"
