---
hash: rsh108
type: dev
created: 2026-07-27T12:37:00-06:00
title: Deploy-freeze visibility — scheduled freshness check plus prod-status age
from: plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md
status: in-progress
owner: /devx-loop-2026-07-31T15-54-01-442-22311
branch: feat/dev-rsh108
---

## Goal

Make a silent three-month freeze impossible to repeat, on a schedule and on
demand. The only phase that addresses the *meta*-failure rather than the
outage: prod ran a 92-day-old image and nothing said so.

## Acceptance criteria

- [ ] `.github/workflows/deploy-freshness.yml` exists:
      `schedule: cron '0 15 * * *'` (09:00 MDT) plus `workflow_dispatch`,
      checkout with `fetch-depth: 0`, existing static AWS credentials,
      resolves the running task definition, extracts the tag, resolves
      `git log -1 --format=%ct <tag>`, and **fails the run** when the gap
      exceeds 7 days.
- [ ] It resolves the **running** revision: `describe-services` →
      `services[0].taskDefinition` → `describe-task-definition` on that
      **revision ARN**. The family-shortcut trap is commented in the workflow.
- [ ] It deliberately **omits** `environment: production`, with a comment
      explaining why (read-only job; a reviewer gate would make an unattended
      freeze undetectable).
- [ ] `workflow_dispatch` run against current prod reports the true gap,
      cross-checked against `bin/prod-status` and `git log`.
- [ ] A synthetic gap > 7 days **fails** the run; < 7 days passes.
- [ ] Registering a newer ACTIVE task-definition revision without deploying it
      does **not** change the reported gap.
- [ ] The scheduled trigger fires unattended (confirmed the next morning) with
      no approval prompt.
- [ ] `bin/prod-status` prints the deployed tag and its age, reusing the
      `describe-services` call already at `:15-18`.
- [ ] Actuals recorded in
      `_devx/workstreams/rotation-self-heal/evals/E-7_deploy-freeze-visibility.md`.

## Technical notes

- **It must resolve the *running* task definition, not the family.**
  `deploy-services` uses the family shortcut
  (`--task-definition palateful-api-prod`, `ci.yml:867-885`), which returns
  the family's newest ACTIVE revision — correct *there*, because it runs right
  after `terraform-prod` wrote that revision. FR-6 asks the opposite question.
  Using the family shortcut would report the newest task definition as
  "deployed" and mask exactly the freeze this check exists to catch. Reuse
  only the tag-extraction idiom (`containerDefinitions[0].image`,
  `tag="${image##*:}"`). This was caught as a real design bug at the Design
  gate's adversarial coverage pass — the check would have been green and
  blind.
- **Accepted cost, stated plainly**: the check shares its fate with the CI
  system whose silent breakage it exists to catch. Mitigated only by living in
  a **separate workflow file with its own trigger**, so a red `ci.yml` does not
  skip it. This was the deciding argument against putting it inside `ci.yml` —
  a push-triggered job would have been skipped throughout this very incident.
- `fetch-depth: 0` is required: the deployed SHA may be months old (92 days
  when this workstream opened).
- UC-5 folds into `bin/prod-status` rather than a net-new script — one code
  path, one place an operator looks.
- No dependency on any other phase; parallel-safe throughout.
- Verification type: human. RED artifact (stub, deferred):
  `_devx/workstreams/rotation-self-heal/evals/E-7_deploy-freeze-visibility.md`
  (E-7, P2).
- Full context: `_devx/workstreams/rotation-self-heal/plan.md` §Phase 8.

## Status log

- 2026-07-27T12:37 — emitted from plan 462355 at RED-gate PASS. E-7 is a
  deferred human stub (legal for P2); the eval file carries the 7-step
  observation protocol, with the running-vs-family revision check called out
  as the load-bearing step.
- 2026-07-31T10:11:07-06:00 — claimed by /devx in session /devx-loop-2026-07-31T15-54-01-442-22311
- 2026-07-31T16:14:35.346Z — loop iteration 1: Implemented both rsh108 artifacts — deploy-freshness.yml (running-revision resolution, 7-day gap gate, no environment gate, synthetic-gap test input) and the bin/prod-status deployed-tag/age section — with actionlint/shellcheck green and the jq/git logic exercised against a mocked ECS payload and a real 95-day-old SHA.
  - Change: Created .github/workflows/deploy-freshness.yml: daily cron 0 15 * * * plus workflow_dispatch, fetch-depth 0, static AWS creds, describe-services -> revision-ARN describe-task-definition (family-shortcut trap commented in place), git log %ct gap computation failing >7 days, deliberate environment:production omission with rationale comment, and a test-only synthetic-gap-days dispatch input for E-7 steps 3-4
  - Change: Extended bin/prod-status to fetch describe-services JSON once and print a Deployed images section with each service's running tag and age in days, resolved from the revision ARN with a not-a-commit fallback
  - Change: Verified: actionlint clean on the workflow, bash -n + shellcheck clean on prod-status, and the jq extraction/age math proven against a mock ECS payload plus a real 95d-old commit (correctly exceeds the 7d threshold)
  - Learning: Scheduled workflows only run from the default branch, so the scheduled-trigger AC and the whole E-7 observation protocol cannot begin until this branch merges — no local iteration can ever satisfy those ACs
  - Learning: Image tags are pinned to the full git SHA by ci.yml resolve-tags, so git log -1 --format=%ct <tag> dates deployments directly; a synthetic-gap-days workflow_dispatch input lets E-7 prove both fail and pass paths without registering fake revisions
  - Learning: jq is already a dependency of sibling bin scripts (prod-deploy, prod-logs), so using it in prod-status adds no new operator tooling requirement
