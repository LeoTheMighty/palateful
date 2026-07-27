# E-7 — Deploy freeze becomes visible

- **Priority:** P2 · **Validation type:** human · **Phase:** 8 (FR-6)
- **Status:** RED — stub. No observation recorded yet.

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
| 1 | `workflow_dispatch` run against current prod | reports the true gap | _pending_ |
| 2 | Cross-check step 1 against `bin/prod-status` and `git log -1 --format=%ci <tag>` | all three agree | _pending_ |
| 3 | Synthetic gap > 7 days | run **fails** | _pending_ |
| 4 | Synthetic gap < 7 days | run passes | _pending_ |
| 5 | Register a newer ACTIVE task-definition revision without deploying it | reported gap is **unchanged** | _pending_ |
| 6 | Wait for the next scheduled 09:00 MDT trigger | fires with **no approval prompt** | _pending_ |
| 7 | `bin/prod-status` | prints the deployed tag and its age | _pending_ |

**Step 5 is the load-bearing one.** `deploy-services` resolves the task
definition by *family* (`ci.yml:867-885`), which returns the family's newest
ACTIVE revision. FR-6 asks the opposite question and must go
`describe-services` → `services[0].taskDefinition` → `describe-task-definition`
on that **revision ARN**. Reusing the family shortcut would report the newest
task definition as "deployed" and mask exactly the freeze this check exists to
catch — so a check that passes steps 1–4 and fails step 5 is worse than no
check, because it reads as green while blind.

**Step 6 is the other one.** Every deploy-touching job sets
`environment: production` (`ci.yml:463`, `:706`, `:852`), which applies
GitHub's required-reviewer gate. A scheduled job that waits for manual
approval can never detect an unattended freeze. The omission is deliberate
and justified by the job being strictly read-only.

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
