# E-7 — Deploy freeze becomes visible

- **Priority:** P2 · **Validation type:** human · **Phase:** 8 (FR-6)
- **Status:** RED — observation in progress (steps 2 and 7 recorded 2026-07-31; step 1 caught a credentials bug, fixed, re-run pending merge; steps 3-5 logic pinned offline 2026-07-31 by `tools/deploy-freshness-self-test.sh`, live runs still owed).

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
| 2 | Cross-check step 1 against `bin/prod-status` and `git log -1 --format=%ci <tag>` | all three agree | Partial (2026-07-31): `bin/prod-status` → `c85e350d…` 95d old; `git log -1 --format=%ci c85e350d` → 2026-04-26 10:27:45 -0600 = 95 days. Two of three agree; workflow measurement pending step 1 re-run. Re-measured later the same day: **96d** — the gap is a live floor-divided age, so it ticks up by one each midnight UTC; 95 and 96 are the same observation on either side of a day boundary, not a disagreement. |
| 3 | Synthetic gap > 7 days | run **fails** | _dispatch pending_ (blocked on step 1 fix merging). Logic pinned offline 2026-07-31: `tools/deploy-freshness-self-test.sh` runs the workflow's own measure step with `SYNTHETIC_GAP_DAYS=8` over a 96d-old fixture → exits 1, reports `Gap: 8 day(s)`, and never reports 96 (so the substitution really took effect). |
| 4 | Synthetic gap < 7 days | run passes | _dispatch pending_ (blocked on step 1 fix merging). Logic pinned offline 2026-07-31: `SYNTHETIC_GAP_DAYS=1` over the same 96d-old fixture → exits 0. Boundary also pinned: `=7` (== threshold) passes, since the gate is `-gt`. |
| 5 | Register a newer ACTIVE task-definition revision without deploying it | reported gap is **unchanged** | _live observation still owed_ (see below). Precondition captured 2026-07-31: family `palateful-api-prod` has exactly **one** ACTIVE revision, `:62`, which *is* the running revision — so the shortcut and the correct path currently coincide and the trap is latent, not observable passively. Property proven offline the same day and now CI-guarded (`tools/deploy-freshness-self-test.sh`). |
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

Observing step 5 live means **registering a task-definition revision in the
production account**. That is a prod mutation, so it is human-only and stays
owed. But leaving the property verified once, by hand, and unguarded after
that is the real risk: the trap is a one-line "simplification" away, and prod
currently has only one ACTIVE revision, so a regression would look identical
to a healthy check until the next freeze.

So the property is also pinned offline, on every PR, by
`tools/deploy-freshness-self-test.sh` (wired into `ci.yml`'s `lint` job). It
**extracts the measure step out of the workflow YAML** rather than copying it
— a copy would drift and the guard would pass against code no longer shipped
— and runs it against a mocked `aws` plus a sandbox git repo with backdated
commits. Its step-5 case models exactly the scenario: running revision `:62`
on a 96-day-old image, a newer ACTIVE `:63` on a 1-day-old image that was
never deployed. The correct code reports 96 and exits 1; it asserts the
report never mentions the undeployed image or its 1-day gap, and that the
resolution actually went through `describe-services`.

Verified 2026-07-31 by mutation, not just by passing — three deliberate
regressions were introduced into the workflow and each was caught by the
intended case:

| Mutation | Caught by |
|---|---|
| `running_td="$SERVICE"` (the family shortcut) | step-5 case — reported `Gap: 1 day(s)` / "Prod image is fresh", i.e. green and blind on a 96d-frozen fixture |
| `-gt` → `-ge` on the threshold | the `=7` boundary case |
| synthetic-gap branch made unreachable | all three synthetic cases |

This does **not** discharge step 5. It bounds the window in which a
regression can hide to zero; the live observation still proves the mechanism
against real ECS.

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
