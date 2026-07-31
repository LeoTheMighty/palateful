# E-7 — Deploy freeze becomes visible

- **Priority:** P2 · **Validation type:** human · **Phase:** 8 (FR-6)
- **Status:** RED — observation in progress (steps 2 and 7 recorded 2026-07-31; step 1 caught a credentials bug, fixed, re-run pending merge).

## Expectation

When the deployed prod image is more than 7 days behind `main`, the system
SHALL surface that gap to the operator rather than leaving it silent.

**Threshold:** gap reported within 24h of crossing 7 days.

## Why this is a human eval, not a test

The mechanism is a scheduled GitHub Action reading live ECS state. What
`deploy-freshness.yml` computes can be unit-tested; what it *is for* —
firing unattended, on a schedule, against production, when nobody is
looking — cannot. That property is exactly what failed for 92 days in this
incident, and it is only provable by observation.

## Observation protocol

Run in order. Record the actual, not "as expected".

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | `workflow_dispatch` run against current prod | reports the true gap | **FAIL then fixed** (2026-07-31): run 30647079681 died in `configure-aws-credentials` — "Credentials could not be loaded". The AWS secrets are environment-scoped (`production`), and the job deliberately omitted `environment: production`, so it had no credentials at all. Fixed by declaring the environment (safe — see step 6 actual). Re-run pending merge of the fix. |
| 2 | Cross-check step 1 against `bin/prod-status` and `git log -1 --format=%ci <tag>` | all three agree | Partial (2026-07-31): `bin/prod-status` → `c85e350d…` 95d old; `git log -1 --format=%ci c85e350d` → 2026-04-26 10:27:45 -0600 = 95 days. Two of three agree; workflow measurement pending step 1 re-run. |
| 3 | Synthetic gap > 7 days | run **fails** | _pending_ (blocked on step 1 fix merging) |
| 4 | Synthetic gap < 7 days | run passes | _pending_ (blocked on step 1 fix merging) |
| 5 | Register a newer ACTIVE task-definition revision without deploying it | reported gap is **unchanged** | _pending_ |
| 6 | Wait for the next scheduled 09:00 MDT trigger | fires with **no approval prompt** | _pending_ — but verified 2026-07-31 via `gh api repos/…/environments/production` that the environment has `protection_rules: []` and no branch policy, so declaring it (step 1 fix) introduces no approval gate. |
| 7 | `bin/prod-status` | prints the deployed tag and its age | **PASS** (2026-07-31): prints `palateful-api-prod: c85e350dd48b… — 95d old (3 months ago, chore(sprint-status): …)` for both api and worker services. |

**Step 5 is the load-bearing one.** `deploy-services` resolves the task
definition by *family* (`ci.yml:867-885`), which returns the family's newest
ACTIVE revision. FR-6 asks the opposite question and must go
`describe-services` → `services[0].taskDefinition` → `describe-task-definition`
on that **revision ARN**. Reusing the family shortcut would report the newest
task definition as "deployed" and mask exactly the freeze this check exists to
catch — so a check that passes steps 1–4 and fails step 5 is worse than no
check, because it reads as green while blind.

**Step 6 is the other one.** The original design omitted
`environment: production` to dodge a presumed required-reviewer gate. The
first dispatch run proved the omission fatal instead: the AWS secrets exist
*only* as environment secrets, so the job had no credentials. The gate
turned out to be presumption, not fact — the environment has **no
protection rules** (verified 2026-07-31, `protection_rules: []`) — so the
job now declares the environment and still fires unattended. Step 6 is the
regression canary: if a required-reviewer rule is ever added to the
environment, the morning run stalls waiting for approval, and the check
goes blind to unattended freezes — exempt this job or move the secrets to
repo scope.

## Accepted cost

The check shares its fate with the CI system whose silent breakage it exists
to catch. Mitigated only by living in a separate workflow file with its own
trigger, so a red `ci.yml` does not skip it — a push-triggered job would have
been skipped throughout this very incident.

## Result

- **Verdict:** _pending_
- **Measured gap vs `git log`:** _pending_
- **Date observed:** _pending_

## Links

- Plan phase 8: `../plan.md`
- Expectation: `../expectations.md` (E-7)
