#!/usr/bin/env bash
#
# Run deploy-freshness.yml's image-existence step (imgexist1) against REAL
# prod, from a laptop. Read-only.
#
# The self-test (tools/image-exists-self-test.sh) proves the step's LOGIC
# against a fake `aws`. This proves the step can SEE the real thing: the same
# bash, extracted from the same YAML, against live ECS / Batch / ECR.
#
# Modes:
#   (default)                  measure prod as it is now. Mirrors the step:
#                              0 present, 1 missing or no verdict.
#   --replay-incident          answer the ONE question "what does prod run?"
#                              with what prod ran during the 2026-10-29..11-25
#                              outage — worker :64 / api :74 and the service
#                              revisions that pinned their digests — and let
#                              every other call hit real AWS. Those revisions,
#                              task definitions and (deleted) images are all
#                              still real, so the RED comes from real ECR, not
#                              from the shim. Reports the OBSERVATION:
#                              0 the step went red and named both services
#                              (it can see), 1 it went green (BLIND),
#                              2 no verdict (could not observe).
#   --verify-mock-assumptions  check, against real ECR, the error text the
#                              self-test's fake depends on: a missing tag says
#                              ImageNotFoundException, a missing repository
#                              says RepositoryNotFoundException, a present
#                              digest answers "sha256:...<TAB><pushed-at>".
#                              0 all hold, 1 one is contradicted.
#
# Needs an AWS CLI new enough for `ecs describe-service-revisions` (v2 from
# early 2025, or any recent v1). An older one makes the step fail with no
# verdict, by design; this script says so up front instead (exit 2).
#
# Usage: bash tools/image-exists-live-check.sh [--replay-incident | --verify-mock-assumptions]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/deploy-freshness.yml"
STEP_NAME="Check prod's referenced images still exist in ECR"
MODE="${1:-}"
case "$MODE" in ""|--replay-incident|--verify-mock-assumptions) ;; *) sed -n '2,36p' "$0"; exit 2 ;; esac

aws sts get-caller-identity --query Account --output text >/dev/null 2>&1 \
  || { echo "No usable AWS credentials — cannot observe anything (exit 2)."; exit 2; }
aws ecs describe-service-revisions help >/dev/null 2>&1 \
  || { echo "This AWS CLI ($(aws --version 2>&1)) has no 'ecs describe-service-revisions' — the step would fail with no verdict. Use a newer CLI (exit 2)."; exit 2; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
python3 "$REPO_ROOT/tools/deploy-freshness-extract.py" "$WORKFLOW" "$STEP_NAME" "$WORK/images.sh" >/dev/null
wf_env() { sed -n "s/^  $1: *//p" "$WORKFLOW" | head -1; }
CLUSTER="$(wf_env CLUSTER)"
IMAGE_SERVICES="$(wf_env IMAGE_SERVICES)"
IMAGE_JOB_DEFINITIONS="$(wf_env IMAGE_JOB_DEFINITIONS)"
export CLUSTER IMAGE_SERVICES IMAGE_JOB_DEFINITIONS
REGISTRY_ACCT="$(aws sts get-caller-identity --query Account --output text)"
REAL_AWS="$(command -v aws)"

if [ "$MODE" = --verify-mock-assumptions ]; then
  bad=0
  try() {  # $1 = label, $2 = substring expected on stderr (or stdout for 'ok:'), rest = aws args
    local label="$1" want="$2" rc=0; shift 2
    "$REAL_AWS" "$@" > "$WORK/o" 2> "$WORK/e" || rc=$?
    case "$want" in
      ok:*) if [ "$rc" -eq 0 ] && grep -qE "${want#ok:}" "$WORK/o"; then echo "holds  $label"; else echo "BROKEN $label (rc=$rc): $(cat "$WORK/o" "$WORK/e")"; bad=1; fi ;;
      *)    if [ "$rc" -ne 0 ] && grep -qF "$want" "$WORK/e"; then echo "holds  $label"; else echo "BROKEN $label (rc=$rc): $(cat "$WORK/e")"; bad=1; fi ;;
    esac
  }
  # The incident's own image: rule 3 expired it 2026-10-24 23:48Z.
  try "deleted tag -> ImageNotFoundException" ImageNotFoundException \
    ecr describe-images --registry-id "$REGISTRY_ACCT" --repository-name palateful/worker \
    --image-ids imageTag=cd6a3c3efdcd8b6a0b0e8f594a766dc2b5a84896
  try "deleted digest -> ImageNotFoundException" ImageNotFoundException \
    ecr describe-images --registry-id "$REGISTRY_ACCT" --repository-name palateful/worker \
    --image-ids imageDigest=sha256:e7993fd42e4749b29ad0074cd68e858b20b31cfeae9f87aca6b71afd0be5cfeb
  try "missing repository -> RepositoryNotFoundException" RepositoryNotFoundException \
    ecr describe-images --registry-id "$REGISTRY_ACCT" --repository-name palateful/imgexist1-no-such-repo \
    --image-ids imageTag=x
  cur="$("$REAL_AWS" ecs describe-services --cluster "$CLUSTER" --services palateful-worker-prod --query 'services[0].taskDefinition' --output text)"
  img="$("$REAL_AWS" ecs describe-task-definition --task-definition "$cur" --query 'taskDefinition.containerDefinitions[0].image' --output text)"
  # Only the digest and the tab are load-bearing; pushed-at is ISO under CLI
  # v2 and epoch under v1 (both observed), and the step only prints it.
  try "present tag -> 'sha256:<64 hex><TAB><pushed-at>'" "ok:^sha256:[0-9a-f]{64}"$'\t'"." \
    ecr describe-images --registry-id "$REGISTRY_ACCT" --repository-name "$(echo "${img#*/}" | cut -d: -f1)" \
    --image-ids "imageTag=${img##*:}" --query 'imageDetails[0].[imageDigest,imagePushedAt]' --output text
  exit "$bad"
fi

if [ "$MODE" = --replay-incident ]; then
  # Shim exactly one answer: describe-services. Everything else is real.
  mkdir -p "$WORK/bin"
  cat > "$WORK/bin/aws" <<SHIM
#!/usr/bin/env bash
if [ "\$1 \$2" = "ecs describe-services" ]; then
  svc=""; q=""
  for a in "\$@"; do case "\$prev" in --services) svc="\$a" ;; --query) q="\$a" ;; esac; prev="\$a"; done
  case "\$svc" in
    palateful-worker-prod) td=palateful-worker-prod:64; rev=9138326545670638105 ;;
    palateful-api-prod)    td=palateful-api-prod:74;    rev=8716069100883793532 ;;
    *) exec "$REAL_AWS" "\$@" ;;
  esac
  case "\$q" in
    *currentServiceRevisions*) echo "arn:aws:ecs:us-east-1:${REGISTRY_ACCT}:service-revision/${CLUSTER}/\$svc/\$rev" ;;
    *) echo "arn:aws:ecs:us-east-1:${REGISTRY_ACCT}:task-definition/\$td" ;;
  esac
  exit 0
fi
exec "$REAL_AWS" "\$@"
SHIM
  chmod +x "$WORK/bin/aws"
  export PATH="$WORK/bin:$PATH"
  echo "REPLAY: describe-services answers with the outage-era revisions; every other call is real."
fi

rc=0
GITHUB_OUTPUT="$WORK/gh_out" bash "$WORK/images.sh" || rc=$?
verdict="$(sed -n 's/^verdict=//p' "$WORK/gh_out" 2>/dev/null | tail -1)"
echo
echo "step exit=$rc verdict=${verdict:-none}"
[ "$verdict" != missing ] || { echo "detail:"; awk '/^detail<<__IMGEXIST_DETAIL__$/{on=1;next} /^__IMGEXIST_DETAIL__$/{on=0} on' "$WORK/gh_out" | sed 's/^/  /'; }

if [ "$MODE" = --replay-incident ]; then
  case "$verdict" in
    missing)
      d="$(cat "$WORK/gh_out")"
      case "$d" in
        *"palateful-worker-prod: revision 9138326545670638105 pinned digest"*"palateful-api-prod"*|*"palateful-api-prod"*"palateful-worker-prod: revision 9138326545670638105 pinned digest"*)
          echo "OBSERVED: the step can see the incident — RED, from real ECR, naming both services."; exit 0 ;;
      esac
      echo "RED, but not naming both outage services — inspect the detail above."; exit 1 ;;
    present) echo "BLIND: the step went GREEN on the outage's state."; exit 1 ;;
    *)       echo "NOT OBSERVED: the step reached no verdict."; exit 2 ;;
  esac
fi
exit "$rc"
