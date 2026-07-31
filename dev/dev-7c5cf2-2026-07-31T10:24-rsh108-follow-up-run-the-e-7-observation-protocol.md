---
hash: 7c5cf2
type: dev
created: 2026-07-31T10:24:06-06:00
title: "rsh108 follow-up: run the E-7 observation protocol against live prod"
from: dev/dev-rsh108-2026-07-27T12:37-deploy-freeze-visibility.md
status: in-progress
blocked_by: [rsh108]
branch: feat/dev-7c5cf2
owner: /devx-loop-2026-07-31T15-54-01-442-22311
---

## Goal

Continue rsh108: remaining acceptance criteria split out by devx split (merge-first).

## Acceptance criteria

- [ ] workflow_dispatch run against current prod reports the true gap, cross-checked against bin/prod-status and git log
- [ ] Synthetic gap > 7 days fails the run and < 7 days passes, via the synthetic-gap-days dispatch input
- [ ] Registering a newer ACTIVE task-definition revision without deploying it does not change the reported gap
- [ ] The scheduled 09:00 MDT trigger fires unattended with no approval prompt, confirmed the next morning after merge
- [ ] Actuals recorded in _devx/workstreams/rotation-self-heal/evals/E-7_deploy-freeze-visibility.md

## Carried forward

### State to trust

- parent dev/dev-rsh108-2026-07-27T12:37-deploy-freeze-visibility.md shipped its committed portion at reduced scope through the normal PR/CI/merge tail

### Gotchas (save time — don't rediscover)

- All remaining ACs require the workflow merged to main plus live AWS access and a next-morning check, so they are human-observation work, not loop-iteration work

### Do NOT

- Do not redo ACs already shipped by the parent — audit its PR diff first

## Status log

- 2026-07-31T10:24:06-06:00 — created by devx split from `dev/dev-rsh108-2026-07-27T12:37-deploy-freeze-visibility.md` (merge-first)
- 2026-07-31T10:24:07-06:00 — claimed by /devx in session /devx-loop-2026-07-31T15-54-01-442-22311
- 2026-07-31T16:32:39.243Z — loop iteration 1: Ran the first E-7 observation steps against live prod, caught and fixed a real bug (workflow had no AWS credentials because the secrets are environment-scoped and the job omitted environment: production), and recorded actuals for steps 2 and 7 in the eval file.
  - Change: Fixed .github/workflows/deploy-freshness.yml: added environment: production to the check-freshness job (the AWS secrets are environment-scoped only; first dispatch run 30647079681 failed with 'Credentials could not be loaded' without it) and rewrote the comment block to record that the production environment empirically has no protection rules, so no approval gate is introduced
  - Change: Recorded actuals in _devx/workstreams/rotation-self-heal/evals/E-7_deploy-freeze-visibility.md: step 7 PASS (bin/prod-status prints deployed tag c85e350d, 95d old), step 2 partial (bin/prod-status and git log agree on 95 days; workflow measurement pending re-run), step 1 failure + fix documented, step 6 rationale updated to reflect the environment declaration and its verified zero protection rules
  - Learning: The 'required-reviewer gate on environment: production' that justified omitting the environment was presumption, not fact — gh api shows protection_rules: [] and no branch policy, so declaring the environment costs nothing today; step 6 is now the canary for someone adding rules later
  - Learning: The AWS secrets (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY) exist only in the production environment scope — repo-level secrets are just the two Cloudflare ones — so any workflow needing AWS must declare environment: production
  - Learning: Prod is genuinely frozen at c85e350d (95 days old, both api and worker services), so the post-merge real-measurement run must FAIL to be correct — a green run would indicate the check is broken
  - Learning: gh CLI auth and local AWS admin creds both work from this environment, so dispatch-based protocol steps (1-4) are loop-runnable, not human-only as the spec's gotcha claimed; only step 6 (next-morning wait) truly needs calendar time
  - Learning: The workflow fix cannot be live-tested pre-merge: gh workflow run --ref uses the definition from a pushed ref, and pushing is out of bounds for an iteration — steps 1/3/4 re-run must wait for the loop's merge tail
