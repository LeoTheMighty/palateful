#!/usr/bin/env bash
# Resolve the image tags production is ACTUALLY running, for all four
# services, so terraform-prod can apply a Terraform-only change without
# moving any image.
#
# Why this exists (tfgate1): terraform-prod used to run only when
# deploy-images succeeded, because resolve-tags pins every tag to HEAD_SHA
# and HEAD_SHA exists in ECR only if deploy-images just built it. So a
# Terraform-only change merged, planned cleanly, and was never applied.
# Pointing it at HEAD_SHA instead would send ECS to images that were never
# built (CannotPullContainerError, run 24534239978). Deployed tags are the
# only safe input when nothing was built.
#
# Sources — each is "what is live", not "what was last registered":
#   api, worker : the task definition the ECS *service* is running now
#   migrator    : latest ACTIVE revision of its family (it has no service;
#                 terraform registers it, run-migrator runs it)
#   parser      : highest ACTIVE Batch job-definition revision (same query
#                 the post-apply drift check in ci.yml uses)
#
# Read-only: describe-* calls only. Fails loudly on anything it can't
# resolve to a 40-hex SHA — a blank tag passed to terraform would plan an
# image change, which is exactly what this script exists to prevent.
#
# Usage: tools/resolve-deployed-image-tags.sh [github-output-file]
#   Writes api_tag=..., worker_tag=..., migrator_tag=..., parser_tag=...
#   to $1 (e.g. "$GITHUB_OUTPUT") and to stdout.
set -euo pipefail

CLUSTER="${CLUSTER:-palateful-prod}"
ENV_SUFFIX="${ENV_SUFFIX:-prod}"
OUT="${1:-/dev/null}"

tag_of() { echo "${1##*:}"; }

service_image() {
  local td
  td=$(aws ecs describe-services --cluster "$CLUSTER" --services "palateful-$1-$ENV_SUFFIX" \
         --query 'services[0].taskDefinition' --output text)
  aws ecs describe-task-definition --task-definition "$td" \
    --query 'taskDefinition.containerDefinitions[0].image' --output text
}

api=$(tag_of "$(service_image api)")
worker=$(tag_of "$(service_image worker)")
migrator=$(tag_of "$(aws ecs describe-task-definition --task-definition "palateful-migrator-$ENV_SUFFIX" \
  --query 'taskDefinition.containerDefinitions[0].image' --output text)")
parser=$(tag_of "$(aws batch describe-job-definitions --job-definition-name "palateful-parser-job-$ENV_SUFFIX" \
  --status ACTIVE --query 'reverse(sort_by(jobDefinitions, &revision))[0].containerProperties.image' --output text)")

fail=0
for pair in "api=$api" "worker=$worker" "migrator=$migrator" "parser=$parser"; do
  name="${pair%%=*}"; val="${pair#*=}"
  if [[ ! "$val" =~ ^[0-9a-f]{40}$ ]]; then
    echo "::error::could not resolve a deployed SHA for $name (got '$val')" >&2
    fail=1
  fi
  echo "${name}_tag=$val" | tee -a "$OUT"
done
exit "$fail"
