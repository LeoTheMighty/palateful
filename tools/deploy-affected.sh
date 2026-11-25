#!/usr/bin/env bash
#
# THE definition of "this range of main deploys a new image".
#
# Usage: tools/deploy-affected.sh <base> <head>
# Prints GITHUB_OUTPUT-style lines on stdout (the log line goes to stderr):
#
#   api=true|false  worker=…  migrator=…  parser=…  terraform=…
#   services_to_build=["api","worker","migrator","parser"]  |  services_to_build=[]
#
# TWO CALLERS, ONE DEFINITION — that is the whole reason this is a file:
#
#   - ci.yml `detect-changes` feeds these outputs to deploy-images,
#     terraform-prod, run-migrator and deploy-services. It decides what
#     DEPLOYS.
#   - deploy-freshness.yml asks the same question of (running image .. main)
#     to decide whether prod is OVERDUE a deploy. It decides what SHOULD
#     HAVE deployed.
#
# If those two ever disagree, the freeze check either cries wolf over changes
# that never deploy (the 61-days-red-for-a-quiet-backend failure that moved
# this logic here) or, worse, sleeps through ones that should have. So neither
# workflow restates the project list or the nx call; both run this.
# tools/deploy-freshness-self-test.sh asserts statically that both call it and
# that neither carries its own `nx show projects --affected`.
#
# "Affected" is nx's answer, not a path list: `nx show projects --affected`
# diffs merge-base(<base>, <head>)..<head> and maps the changed files through
# the CURRENT working tree's project graph — project roots plus
# implicitDependencies (api/worker depend on utils+agent, migrator on utils).
# That is why there is no services/|libraries/ glob anywhere in this repo to
# keep in sync.

set -euo pipefail

if [ $# -ne 2 ] || [ -z "$1" ] || [ -z "$2" ]; then
  echo "usage: $0 <base> <head>" >&2
  exit 2
fi
base="$1"
head="$2"

# A failing nx call must fail the caller, never read as "nothing affected":
# an empty list here means "deploy nothing", which in detect-changes skips
# every deploy job and in deploy-freshness reports green.
affected="$(npx nx show projects --affected --base="$base" --head="$head")"
echo "Affected projects (${base:0:12}..${head:0:12}): $(printf '%s' "$affected" | tr '\n' ' ')" >&2

has() { printf '%s\n' "$affected" | grep -qx "$1"; }

for p in api worker migrator parser terraform; do
  if has "$p"; then echo "$p=true"; else echo "$p=false"; fi
done

# Compose the deploy-images matrix. Two valid states:
#   - At least one service affected → build ALL FOUR services so
#     every task-def reference (`<repo>:<github.sha>`) exists in ECR.
#     This intentionally bloats CI for unaffected services to break
#     a cross-workflow race (see the resolve-tags comment in ci.yml):
#     under parallel pushes, terraform-prod from one run can land
#     after another run's terraform-prod, leaving the ECS service
#     pointing at <unaffected-service>:<github.sha> from a workflow
#     whose deploy-images never pushed that tag. The cure is to
#     guarantee every push that deploys ANYTHING re-pushes ALL
#     four images under HEAD_SHA. NX/Docker layer caching makes
#     unaffected rebuilds cheap.
#   - No service affected (docs / app-only / pure infra) → empty
#     array. deploy-images and deploy-services skip; terraform-prod
#     applies only if the terraform project is affected (tfgate1), and
#     then against the tags prod is already running — no image moves.
#
# The consequence deploy-freshness depends on: a non-empty array is exactly
# the set of pushes that move the running image tag to HEAD_SHA. An empty one
# never moves it, however much else changed.
deploy_anything=false
for s in api worker migrator parser; do
  if has "$s"; then
    deploy_anything=true
    break
  fi
done
if [ "$deploy_anything" = "true" ]; then
  echo 'services_to_build=["api","worker","migrator","parser"]'
else
  echo 'services_to_build=[]'
fi
