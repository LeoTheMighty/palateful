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
- 2026-07-31T16:43:22.078Z — loop iteration 2: Captured E-7 step-5's live preconditions read-only, filed the prod-mutation half as a MANUAL entry with exact commands, and made the load-bearing family-shortcut property permanently CI-guarded via a mutation-verified self-test extracted from the workflow YAML.
  - Change: Added tools/deploy-freshness-self-test.sh: extracts the measure step out of deploy-freshness.yml (never copies it), runs it against a mocked aws and a backdated sandbox git repo, and asserts 6 cases — the step-5 running-vs-newest-ACTIVE resolution, fresh-prod pass, non-commit tag failure, and the synthetic-gap fail/pass/boundary paths
  - Change: Wired the self-test into ci.yml's lint job unconditionally (not nx-affected — nx does not project-map workflow files), verified it adds no new actionlint findings beyond the 3 that pre-exist on HEAD
  - Change: Mutation-verified the guard: reintroducing the family shortcut, flipping -gt to -ge, and disabling the synthetic branch each fail the intended case and only that case; fixed a tally bug where a case could print 'pass' then fail an output assertion
  - Change: Recorded actuals in the E-7 eval file: step 5 precondition (family has exactly one ACTIVE revision, so the trap is latent), steps 3/4 logic-pinned-offline with dispatch still owed, the mutation evidence table, and a note that 95d vs 96d is a day-boundary artifact of a floor-divided age rather than a disagreement
  - Change: Filed the prod-mutation half of step 5 in MANUAL.md with a tested jq/aws command sequence, a deploy-safe image-tag rationale, and an explicit deregister-when-done warning
  - Learning: Registering a task definition against the prod account is blocked by the permission classifier, so AC 3 is not loop-runnable at all — not merely blocked on merge like ACs 1/2/4. Iteration 1's learning that 'dispatch-based steps are loop-runnable' does not extend to prod mutations.
  - Learning: Step 5 cannot be observed passively even with full AWS read access: the family has exactly one ACTIVE revision (:62) which is also the running one, so both resolution paths agree until someone deliberately registers a second revision.
  - Learning: The newest image in ECR is c2f7982c from 2026-05-03 (89 days old) — image builds stopped around the same time deploys did, so there is no genuinely fresh image available to construct a <7-day synthetic revision from.
  - Learning: The service's PRIMARY deployment was created 2026-07-27, only days ago, while its image is from 2026-04-26 — something re-deployed the stale task definition recently. Worth a look: it means the freeze is not simply 'nothing has run since April'.
  - Learning: Extracting the workflow's bash out of the YAML at test time (indentation-based, no PyYAML — the lint job has no guaranteed poetry env) is what makes this guard trustworthy; a copied script would drift and go on passing against code that is no longer shipped.
