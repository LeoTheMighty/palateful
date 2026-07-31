# E-7 — Deploy freeze becomes visible

- **Priority:** P2 · **Validation type:** human · **Phase:** 8 (FR-6)
- **Status:** RED — observation in progress. All seven steps have now been
  measured against **live prod** (steps 2 and 7 directly; steps 1, 3, 4 and 5
  by running the workflow's own extracted bash via
  `tools/deploy-freshness-live-check.sh`), and the logic plus the
  dispatch/schedule/credentials wiring is pinned on every PR by
  `tools/deploy-freshness-self-test.sh` (9 cases, mutation-verified). What is
  still owed is the **mechanism**: the Actions dispatch and unattended 09:00
  run after merge (steps 1/3/4/6) and one real task-definition registration
  (step 5). Every owed run has a filed command in `MANUAL.md`.

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
| 1 | `workflow_dispatch` run against current prod | reports the true gap | **Measurement PASS, mechanism pending** (2026-07-31). First dispatch (run 30647079681) died in `configure-aws-credentials` — "Credentials could not be loaded": the AWS secrets are environment-scoped (`production`) and the job deliberately omitted `environment: production`, so it had no credentials at all. Fixed by declaring the environment (safe — see step 6 actual). The Actions re-run is still owed (`gh workflow run` resolves the definition from a *pushed* ref), but the same bash, extracted from the same YAML, was run against **live prod** via `tools/deploy-freshness-live-check.sh`: `describe-services` → `…/palateful-api-prod:62` → image `…/palateful/api:c85e350d…` → `Gap: 96 day(s)` → exit 1 with the freeze error. The gap it reports is the true gap. |
| 2 | Cross-check step 1 against `bin/prod-status` and `git log -1 --format=%ci <tag>` | all three agree | **PASS** (2026-07-31): all three legs measured within the same hour agree at **96d** on `c85e350d…` — the workflow's own step (`Gap: 96 day(s)`, live-check run), `bin/prod-status` (`96d old`, and the same for `palateful-worker-prod`), and `git log -1 --format=%ci c85e350d` → 2026-04-26 10:27:45 -0600. An earlier reading the same day said 95d: the gap is a live floor-divided age, so it ticks up by one each midnight UTC; 95 and 96 are the same observation on either side of a day boundary, not a disagreement. |
| 3 | Synthetic gap > 7 days | run **fails** | **Logic PASS on live prod, dispatch pending** (2026-07-31). Against real ECS/ECR/git via the live check: `SYNTHETIC_GAP_DAYS=8` → `::warning::SYNTHETIC gap of 8d`, `Gap: 8 day(s)`, exit **1** — and it never reports 96, so the substitution really displaced the real measurement. Also pinned offline on every PR by `tools/deploy-freshness-self-test.sh` over a 96d fixture. The Actions dispatch is still owed, because only it exercises `inputs.synthetic-gap-days` → `$SYNTHETIC_GAP_DAYS` through GitHub's expression layer (the wire itself is statically asserted — see below). |
| 4 | Synthetic gap < 7 days | run passes | **Logic PASS on live prod, dispatch pending** (2026-07-31). `SYNTHETIC_GAP_DAYS=1` against the same frozen-96d live prod → `Prod image is fresh (1d <= 7d)`, exit **0** — a pass that can only come from the substitution taking effect. Boundary also exercised live: `=7` (== threshold) → exit 0, since the gate is `-gt`. Same offline pin as step 3. |
| 5 | Register a newer ACTIVE task-definition revision without deploying it | reported gap is **unchanged** | **Measurement PASS against live prod, registration still owed** (2026-07-31). `tools/deploy-freshness-live-check.sh --simulate-newer-revision` shims the one `describe-task-definition` call that a registration would change — every other call goes to real ECS — and the shipped bash produced a **byte-identical** report before and after (`:62`, `c85e350d…`, `Gap: 96 day(s)`, exit 1). The control in the same run proves the divergence was real and reachable: with the family shortcut reintroduced, that same bash reported the undeployed image at `Gap: 0 day(s)` / "Prod image is fresh" on 96d-frozen prod — green and blind. Precondition (unchanged): the family has exactly **one** ACTIVE revision, `:62`, which *is* the running one, so the trap is latent and only a divergence can expose it. See below for what the simulation does and does not discharge. |
| 6 | Wait for the next scheduled 09:00 MDT trigger | fires with **no approval prompt** | _pending_ (calendar time; command filed in `MANUAL.md`) — but verified 2026-07-31 via `gh api repos/…/environments/production` that the environment has `protection_rules: []` and no branch policy, so declaring it (step 1 fix) introduces no approval gate. The `0 15 * * *` cron and the `environment:` declaration are now pinned on every PR by the self-test; what only this run can show is a protection rule added on the GitHub side after the fact. |
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

### Observing step 5 without mutating prod (added 2026-07-31)

Registering a revision in the production account is the one thing in this
protocol an agent cannot do, so step 5 — the load-bearing one — was set to
stay owed indefinitely. But the check does not *read the ECS registry as
state*; it reads it through exactly two `aws` calls. A registration changes
what **one** of them returns, for **one** argument: a
`describe-task-definition` on the family name (or on the would-be-next
revision ARN) starts answering with the new, undeployed image.

`--simulate-newer-revision` shims exactly that one answer and passes every
other call through to the real CLI against real prod. The running revision
stays the genuine `:62` from a genuine `describe-services`; the gap is
computed from the genuine deployed tag by the genuine `git log`. Nothing is
written to AWS.

Measured 2026-07-31 (simulating `:63` on tag `602b149f…`, 0 days old):

| Run | Report | Exit |
|---|---|---|
| baseline (real prod) | `:62` → `c85e350d…` → `Gap: 96 day(s)` | 1 |
| with the simulated newer ACTIVE revision | **byte-identical** to baseline | 1 |
| control — same bash, family shortcut reintroduced | `palateful-api-prod` → `602b149f…` → `Gap: 0 day(s)`, "Prod image is fresh" | 0 |

The control is the point. "The gap is unchanged" is worthless if the
simulated revision was never actually visible — an inert shim would satisfy
it trivially. So the tool builds the regression itself (rewrites the
extracted `describe-services` resolution to the family shortcut), runs it
against the same shim, and **refuses to report a pass (exit 2) unless that
regression sees the injected revision**. It did: 96d → 0d, green on frozen
prod, which is precisely the green-and-blind failure step 5 exists to catch.

Verdict/exit codes are inverted from the plain live check and ordered
deliberately: `0` = gap unchanged, `1` = gap moved (the trap), `2` = the
simulation could not be trusted. Two mutations confirmed the attribution —
the family shortcut in the shipped YAML gives exit **1** with the 96d→0d
diff, and an inert shim gives exit **2** rather than a false pass. (The
verdict has to be decided *before* the control is built: when the shipped
bash is already the shortcut, the control cannot be constructed at all, and
an earlier ordering reported that as "untrustworthy" instead of "the trap is
present".)

What remains owed for step 5 is narrow and specific: that a **real**
`register-task-definition` produces the divergence the shim models — i.e.
that ECS makes the new revision the family's newest ACTIVE while
`describe-services` keeps returning `:62`. That is documented AWS behaviour
and it is the assumption the shim encodes, but this run did not observe it.
The `MANUAL.md` entry is now scoped to that assumption alone.

### The wiring layer (added 2026-07-31)

Running the extracted step directly proves the logic and is blind, by
construction, to everything that has to hold for that logic to ever run:
the harness supplies `SYNTHETIC_GAP_DAYS` itself and mocks AWS away. So the
same file also asserts, statically, the three pieces of surrounding YAML —
each of which fails *silently*, leaving a green self-test over a check that
never runs or ignores its input:

| Wiring assertion | Blind spot it closes | Mutation-verified by |
|---|---|---|
| exactly one `0 15 * * *` cron | no schedule ⇒ the check only runs when someone remembers — the exact failure of the original 92-day freeze | cron → `0 16 * * *`, and cron deleted |
| job declares `environment: production` | the AWS secrets are environment-scoped; without it every run dies in `configure-aws-credentials` (run 30647079681), and only at 09:00 where nobody is watching | the `environment:` line deleted |
| `inputs.<x>` → env var the run body actually reads | a dispatch run quietly measures **real** prod instead of the synthetic gap, so step 4 fails and reads as "the check is broken" | `env:` mapping deleted; input renamed; env var renamed |

Each of the six mutations was caught by exactly one assertion (8 pass / 1
fail), so attribution stays sharp. The env-var-rename mutation is the
telling one: the six behavioural cases stayed **green** under it, because
they inject the old name themselves — that hole was real until now.
Self-test total: 9 cases.

### Splitting step 1 into measurement and mechanism (added 2026-07-31)

Step 1 was stuck behind a merge for a structural reason, not a technical one:
`gh workflow run` resolves a workflow definition from a **pushed** ref, so any
change to `deploy-freshness.yml` — including the credentials fix that only the
first dispatch revealed — cannot be exercised until it is already on `main`.
That is a bad loop for a check whose whole job is to not be silently broken.

`tools/deploy-freshness-live-check.sh` breaks it. It runs the *same* bash,
extracted from the *same* YAML by the *same* extractor the CI self-test uses
(`tools/deploy-freshness-extract.py` — shared on purpose, so the offline guard
and the live check can never diverge), against the *same* live ECS/ECR/git,
from anywhere with AWS credentials. It reads the cluster/service/threshold out
of the workflow's own `env:` block rather than restating them, is read-only
(`describe-services` + `describe-task-definition`), and exits **2** — never 1 —
on an extraction or credentials failure, so a broken session can't be misread
as "prod is stale".

What that discharges and what it does not:

| Half of step 1 | Status |
|---|---|
| **Measurement** — does the shipped bash, against real prod, report the true gap? | **Discharged 2026-07-31**: 96d, exit 1, agreeing with `bin/prod-status` and `git log` |
| **Mechanism** — does it run *in Actions*, with environment-scoped credentials, on a schedule, unattended? | **Still owed** — the local run supplies its own credentials and its own trigger, which is exactly what failed here |

So the dispatch and the next-morning schedule check stay owed (steps 1/3/4/6 in
`MANUAL.md`). What changed is that a *measurement* regression can now be caught
before merge instead of at 09:00 the next day.

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

- **Verdict:** _pending_ — the measurement is proven for **every** step
  against live prod (1, 2, 3, 4, 5, 7), and CI-guarded offline against
  regression. What remains is the mechanism: the Actions dispatch after merge
  (steps 1/3/4), the unattended 09:00 MDT run (step 6), and one real
  `register-task-definition` to confirm ECS diverges the way step 5's
  simulation assumes. All four are filed in `MANUAL.md`.
- **Measured gap vs `git log`:** **96 days** — workflow step, `bin/prod-status`
  and `git log -1 --format=%ci c85e350d` (2026-04-26 10:27:45 -0600) all agree.
  Prod is genuinely frozen, so a **green** run is the failure signal here.
- **Date observed:** 2026-07-31 (measurement); mechanism observation pending merge.

## Links

- Plan phase 8: `../plan.md`
- Expectation: `../expectations.md` (E-7)
