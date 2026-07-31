# E-7 — Deploy freeze becomes visible

- **Priority:** P2 · **Validation type:** human · **Phase:** 8 (FR-6)
- **Status:** RED — observation in progress, **one step owed**. Steps 1, 2, 3,
  4 and 7 are now **fully observed**, including the mechanism: three real
  `workflow_dispatch` runs of the fixed workflow executed in GitHub Actions
  (runs 30652052889 / 30652140468 / 30652190943), with environment-scoped AWS
  credentials, against live prod. Step 5 is measured against live prod by
  simulation with its ECS assumptions verified read-only (A0–A3); only the prod
  mutation itself stays owed, and it is no longer discriminating while prod is
  fresh. The logic plus the dispatch/schedule/credentials wiring is pinned on
  every PR by `tools/deploy-freshness-self-test.sh` (9 cases,
  mutation-verified). **Step 6a — the cron actually firing — is the only thing
  left**, and it is the one thing that genuinely needs a morning; its approval
  gate (G0–G3) and every precondition for the firing (S0–S3) are already
  observed. The owed run has a filed command in `MANUAL.md`.
- **⚠ The 96-day freeze ended at 2026-07-31 11:06 MDT, mid-observation.** Prod
  now runs a same-day image and the check correctly reports `Gap: 0 day(s)` /
  exit 0. Earlier guidance in this file and in `MANUAL.md` said a **green** run
  was the failure signal — that was true only while the freeze was live. It is
  no longer. See "The freeze ended mid-observation" below before interpreting
  any post-merge run.

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
| 1 | `workflow_dispatch` run against current prod | reports the true gap | **PASS — measurement *and* mechanism** (2026-07-31). First dispatch (run 30647079681) died in `configure-aws-credentials` — "Credentials could not be loaded": the AWS secrets are environment-scoped (`production`) and the job deliberately omitted `environment: production`, so it had no credentials at all. Fixed by declaring the environment (safe — see step 6 actual). Before the fix could be dispatched it was measured locally against **live prod** via `tools/deploy-freshness-live-check.sh` (same bash, same extractor): `:62` → `c85e350d…` → `Gap: 96 day(s)` → exit 1, then `:63` → `848311af…` → `Gap: 0 day(s)` → exit **0** after the freeze ended six minutes later — it tracks state, it is not a constant. **The fixed workflow then ran in Actions for real: run [30652052889](https://github.com/LeoTheMighty/palateful/actions/runs/30652052889), `workflow_dispatch` on `feat/dev-7c5cf2`, 17:40:00Z → success in 19 s.** Credentials loaded; `Running task definition: arn:…:task-definition/palateful-api-prod:63` → `Deployed image: …/palateful/api:848311af…` → `Deployed commit: 848311af 2026-07-31 10:24:08 -0600` → `Gap: 0 day(s); threshold: 7 day(s).` → `Prod image is fresh (0d <= 7d)` → exit 0. See "The dispatch did not need the merge" below. |
| 2 | Cross-check step 1 against `bin/prod-status` and `git log -1 --format=%ci <tag>` | all three agree | **PASS, now against the Actions run itself** (2026-07-31). Third and definitive reading, taken around dispatch run 30652052889 (17:40Z): the **Actions** step reported `:63` / `848311af…` / `Gap: 0 day(s)`; `bin/prod-status` reported `848311af83a2… — 0d old (77 minutes ago, chore: claim 7c5cf2 for /devx)` for *both* `palateful-api-prod` and `palateful-worker-prod`; `git log -1 --format='%h %ci %s' 848311af` → `848311af 2026-07-31 10:24:08 -0600`. Three legs, agreeing on tag, age and commit date — and this time the first leg is the shipped workflow running in GitHub, not a local re-execution of its bash. Earlier readings, kept for the record: all three legs measured within the same hour agree at **96d** on `c85e350d…` — the workflow's own step (`Gap: 96 day(s)`, live-check run), `bin/prod-status` (`96d old`, and the same for `palateful-worker-prod`), and `git log -1 --format=%ci c85e350d` → 2026-04-26 10:27:45 -0600. An earlier reading the same day said 95d: the gap is a live floor-divided age, so it ticks up by one each midnight UTC; 95 and 96 are the same observation on either side of a day boundary, not a disagreement. **Cross-checked a second time at 11:08, post-freeze:** workflow step `Gap: 0 day(s)` on `848311af…`, `bin/prod-status` `848311af… — 0d old (45 minutes ago)` for both services, `git log -1 --format=%ci 848311af` → 2026-07-31 10:24:08 -0600. Three legs, agreeing again — this time on a value that *moved*, which is the stronger form of the check. |
| 3 | Synthetic gap > 7 days | run **fails** | **PASS — through the real dispatch** (2026-07-31). Run [30652140468](https://github.com/LeoTheMighty/palateful/actions/runs/30652140468), `-f synthetic-gap-days=8`, 17:41:18Z → **failure** in 29 s. Log: `::warning::SYNTHETIC gap of 8d substituted for the real measurement (test run.)`, `Gap: 8 day(s); threshold: 7 day(s).`, `::error::Prod is running an image 8 days old …`, `Process completed with exit code 1`. Two things this proves that the local run could not: the input crossed GitHub's expression layer into `$SYNTHETIC_GAP_DAYS` (the literal `SYNTHETIC gap of 8d` is in the log, which is the check the wiring assertion was written to protect), and the substitution **displaced** the real measurement — no `Deployed commit:` line, no `Gap: 0`. This is the discriminating dispatch now that prod is fresh: real prod would have passed at 0d, and the run failed on demand. Also pinned offline on every PR by `tools/deploy-freshness-self-test.sh` over a 96d fixture, and previously measured locally against live ECS/ECR/git. |
| 4 | Synthetic gap < 7 days | run passes | **PASS — through the real dispatch** (2026-07-31). Run [30652190943](https://github.com/LeoTheMighty/palateful/actions/runs/30652190943), `-f synthetic-gap-days=1`, 17:42:04Z → **success** in 18 s: `::warning::SYNTHETIC gap of 1d …`, `Gap: 1 day(s); threshold: 7 day(s).`, `Prod image is fresh (1d <= 7d).` Honest caveat: with prod now at 0d a *pass* is not by itself discriminating — a dropped input would also pass — but the run reports `1`, not `0`, so the value did land and it is `1` that was compared. The discriminating half is step 3's on-demand failure against the same fresh prod. Boundary `=7` (== threshold, gate is `-gt`) exercised locally and pinned in the self-test. |
| 5 | Register a newer ACTIVE task-definition revision without deploying it | reported gap is **unchanged** | **Measurement PASS against live prod, registration still owed** (2026-07-31). `tools/deploy-freshness-live-check.sh --simulate-newer-revision` shims the one `describe-task-definition` call that a registration would change — every other call goes to real ECS — and the shipped bash produced a **byte-identical** report before and after (`:62`, `c85e350d…`, `Gap: 96 day(s)`, exit 1). The control in the same run proves the divergence was real and reachable: with the family shortcut reintroduced, that same bash reported the undeployed image at `Gap: 0 day(s)` / "Prod image is fresh" on 96d-frozen prod — green and blind. Precondition at that time: the family had exactly **one** ACTIVE revision, `:62`, which *was* the running one, so the trap was latent and only a divergence could expose it. The assumptions that simulation encodes about ECS were then **verified read-only against live AWS** (`--verify-shim-assumptions`, A0–A3 below), so the step no longer rests on documented-behaviour recall. **The discriminating form of this observation is no longer reproducible** — see "the freeze ended" below. |
| 6 | Wait for the next scheduled 09:00 MDT trigger | fires with **no approval prompt** | **"No approval prompt" PASS (observed), "fires" pending** (2026-07-31). The step is two claims and only one needs a morning. The gate half is discharged by `tools/deploy-freshness-live-check.sh --verify-environment-gate`: `production` has `protection_rules: []` and no branch policy, **and** the 10 most recent real deployments into that environment — 8 of them from today's `deploy-services`/`terraform-prod`/`deploy-web` run 30646967338 — went `queued` → `in_progress` in 1–8 s with **zero** `waiting` states, evidence that postdates the environment's last config change (2026-03-20). Config *and* behaviour, not config alone. What is still owed is only that the `0 15 * * *` cron fires at all — the workflow landed on `main` at 16:24 UTC today, after that day's 15:00 UTC slot, so the first scheduled run is 2026-08-01. Every *precondition* for that firing is now observed too (`--verify-schedule-fires`, S0–S3 below): the workflow is registered and `active`, its cron is on the default branch, and this repo's scheduler produced 54 unattended runs in 94h with no approval and no silence over 3.4h. **The gate half is now witnessed by *this workflow itself*, not only by `ci.yml`'s deploy jobs:** the three dispatch runs above each created a `production` deployment (5695703361 / 5695719549 / 5695728778) that went straight `in_progress` **3–8 s** after the run was created, with **no `waiting` state** on any of them — i.e. the check job, with its new `environment: production`, was never held for a human. The cron and the `environment:` declaration are pinned on every PR by the self-test; a protection rule added later is caught by re-running `--verify-environment-gate` (and, at 09:00, by the run stalling). |
| 7 | `bin/prod-status` | prints the deployed tag and its age | **PASS** (2026-07-31): prints `palateful-api-prod: c85e350dd48b… — 95d old (3 months ago, chore(sprint-status): …)` for both api and worker services. Re-run at 11:08 after the freeze ended: `848311af… — 0d old (45 minutes ago, chore: claim 7c5cf2 for /devx)`, again for both. (It also showed `palateful-api-prod: 0/1 running` and an unhealthy API — the rollout was still `IN_PROGRESS` at that moment, not a defect.) |

### The freeze ended mid-observation (2026-07-31 11:06 MDT)

The 96-day freeze this eval was written against **ended while the eval was
being run**, which handed E-7 the one thing a fixture can never provide: the
same shipped bash, against the same production account, on both sides of a
real deploy.

| Time (MDT) | Event | What the check reported |
|---|---|---|
| ~11:00–11:02 | prod frozen at `palateful-api-prod:62` / `c85e350d…` (2026-04-26) | `Gap: 96 day(s)` → exit **1** |
| 11:06:06–07 | `RegisterTaskDefinition` × 3 (api `:63`, worker `:53`, migrator `:54`) — a real deploy of `848311af` | — |
| 11:06:08 | `UpdateService` on api `:63` and worker `:53` | — |
| 11:08 | re-run, unchanged tooling | `Gap: 0 day(s)` → exit **0** |

Both times were cross-checked against `bin/prod-status` and `git log` and all
three legs agreed (steps 1, 2, 7). Six minutes, one real state change, an
inverted verdict: the check measures prod rather than restating a constant.
That is the core of E-7's expectation, and it is now observed rather than
argued. (Event times are from CloudTrail `lookup-events`, read-only.)

**Two things this invalidates — read before running anything post-merge:**

1. **"A green run is the failure signal" is no longer true.** It was correct
   for the ~96 hours this eval was written in, and it is repeated in earlier
   rows above and in `MANUAL.md`. Prod is now same-day. The post-merge step-1
   dispatch should be expected to **pass**, and the honest instruction is not
   an expected exit code but an expected *agreement*: whatever it reports must
   match `bin/prod-status` and `git log`. Step 3 (synthetic 8d) is now the
   discriminating dispatch, since it forces a failure on demand.
2. **Step 5's discriminating form is no longer reproducible.** The trap is
   "the newest *registered* revision masks an older *running* one", so it can
   only show a gap difference when the running image is stale. Re-running
   `--simulate-newer-revision` against fresh prod still passes, but its control
   now reports `Gap: 0 day(s)` too — the injection is still detectable (a
   different image tag and commit line) yet no longer produces the 96d→0d
   green-and-blind signature. The discriminating observation was taken at
   ~11:00, inside the last hour of the freeze. It cannot be retaken until prod
   goes stale again, which is precisely why the offline self-test — which pins
   a 96d fixture permanently — is the thing that carries this property forward.

Also worth recording, because iteration notes flagged it as a puzzle: the
`PRIMARY` deployment dated 2026-07-27 was **not** a deploy. CloudTrail shows
`UpdateService` on 2026-05-03 and 2026-07-27 both naming the *already-running*
`:62`, with **zero** `RegisterTaskDefinition` events in the 90-day window until
today — i.e. two `--force-new-deployment` bounces of the same stale image. A
service can look freshly deployed and be 96 days stale; `describe-services`
deployment timestamps are not a freshness signal, and a check built on them
would have read green throughout the freeze.

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

### Verifying the simulation's assumptions against live AWS (added 2026-07-31)

A simulation is only as good as its author's memory of the API it imitates.
What the shim asserts is that a `register-task-definition` produces a specific
divergence — new revision becomes the family's newest ACTIVE, while
`describe-services` keeps returning the old one. That was left as "documented
AWS behaviour" and therefore as the last unobserved link in step 5.

It does not have to be. The claim decomposes into four pieces and **every one
of them is readable out of the live account without registering anything**.
`tools/deploy-freshness-live-check.sh --verify-shim-assumptions` checks them
and refuses to pass on any it cannot witness. Measured 2026-07-31 (all four
observed, exit 0):

| # | Assumption | Observed in `592349850338` |
|---|---|---|
| A0 | the family name the shim intercepts is the running task definition's family | running `…/palateful-api-prod:63`; family `palateful-api-prod` == the workflow's `SERVICE`, which is the key the shim matches on |
| A1 | a family-name lookup returns the **newest ACTIVE** revision, even when an older ACTIVE revision exists and the newest runs nowhere | witness family `palateful-migrator-prod`, ACTIVE revisions **34 and 54**: `describe-task-definition --task-definition palateful-migrator-prod` → `:54`, with `:34` still ACTIVE and ignored |
| A2 | `describe-services` returns a revision-pinned ARN that resolves to that exact revision | stored `…/palateful-api-prod:63`, resolves to revision 63 — a registration adds a revision, it cannot rewrite a stored ARN, so only `update-service` moves this pointer |
| A3 | revision numbers are never reused, so a registration lands **above** the running one | family `palateful-api-prod`: 63 revisions, contiguous 1..63, no duplicates → the next registration is `:64` (deregistering spends the number rather than freeing it) |

A1 is the important one, and it was found **in nature** rather than
constructed: `palateful-migrator-prod` genuinely carries an ACTIVE revision
that nothing runs, and the family-name lookup genuinely skips past it to the
newest. That is the exact mechanism by which the family shortcut would report
an undeployed image as "deployed". A0+A3 fix *which* answer a registration
changes (the family name, and `:running+1`) — the two keys the shim
intercepts; A2 is why the correct path stays put. Together they are the shape
of the divergence, measured.

If the account ever stops offering a family with two ACTIVE revisions, the
tool exits **2 — "not observable"** rather than passing: an assumption that
cannot be witnessed is not a confirmed one. It needs live credentials, so it
is an operator tool, not a CI gate.

What remains strictly unobserved for step 5 is now only the composition —
that issuing the real API call produces A1+A3 together in one step. That is
the `RegisterTaskDefinition` contract itself, and today's deploy exercised it
three times (api `:63`, worker `:53`, migrator `:54`, all one above their
predecessors) without any of them touching a running service until
`UpdateService` fired a second later. The `MANUAL.md` entry is kept for the
record but is no longer discriminating while prod is fresh.

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
| **Mechanism** — does it run *in Actions*, with environment-scoped credentials? | **Discharged 2026-07-31** by run 30652052889 — see the next section; the local run supplies its own credentials and its own trigger, which is exactly what failed here |
| **Mechanism** — does it run *on a schedule*, unattended? | **Still owed** — needs a morning (step 6a) |

What the live check changed permanently is that a *measurement* regression is
caught before merge instead of at 09:00 the next day.

### The dispatch did not need the merge (added 2026-07-31)

Four iterations of this eval recorded steps 1/3/4 as "blocked on the merge",
from a gotcha that read: `gh workflow run` resolves the workflow definition
from a **pushed** ref, and pushing is out of bounds. Both halves of that are
true. The conclusion drawn from them was not.

`--ref` takes **any pushed ref**, not just the default branch. The WIP branch
carrying the `environment: production` fix was already pushed — the loop pushes
it every iteration — so the fixed definition was dispatchable the whole time.
The only thing `workflow_dispatch` needs from `main` is that *some* version of
the file be registered there so the trigger exists at all, which it has been
since the parent story merged. (`schedule:` is the trigger that genuinely
honours only the default branch — S1 above. The two were conflated.)

Measured 2026-07-31, three dispatches on `feat/dev-7c5cf2` @ `3ebf00d5`:

| Run | Input | Result | Key log line |
|---|---|---|---|
| [30652052889](https://github.com/LeoTheMighty/palateful/actions/runs/30652052889) | none (real measurement) | **success**, 19 s | `Gap: 0 day(s)` on `:63` / `848311af…`, matching `bin/prod-status` and `git log` |
| [30652140468](https://github.com/LeoTheMighty/palateful/actions/runs/30652140468) | `synthetic-gap-days=8` | **failure**, 29 s | `::warning::SYNTHETIC gap of 8d …` then `::error::Prod is running an image 8 days old` |
| [30652190943](https://github.com/LeoTheMighty/palateful/actions/runs/30652190943) | `synthetic-gap-days=1` | **success**, 18 s | `::warning::SYNTHETIC gap of 1d …`, `Prod image is fresh (1d <= 7d)` |

What only these runs could prove, that no amount of local execution could:

1. **The credentials fix works in the place it failed.** Run 30647079681 died
   in `configure-aws-credentials`; these three, same job, same secrets
   reference, one `environment:` line different, reached ECS. The
   environment-scoped secrets resolve for a **non-default branch**, so no
   branch policy is silently filtering them either.
2. **The dispatch input crosses GitHub's expression layer.** The self-test
   asserts `inputs.synthetic-gap-days` → `$SYNTHETIC_GAP_DAYS` statically
   because it injects that variable itself and is structurally blind to the
   wire. Run 30652140468 printed `SYNTHETIC gap of 8d` — the literal string the
   wiring assertion exists to protect — which is the wire firing end to end.
3. **The gate half of step 6, from this workflow rather than by analogy.** G2
   had to borrow its witnesses from `ci.yml`'s deploy jobs. These three runs are
   the freshness check's *own* deployments into `production`
   (5695703361 / 5695719549 / 5695728778): `in_progress` 3–8 s after creation,
   zero `waiting` states. Re-running `--verify-environment-gate` after the
   dispatches picks them up as the three newest witnesses and still exits 0.

A small artefact from that re-run, so nobody reads it as a defect: these three
deployments carry **no `queued` state**, going straight to `in_progress`, so the
tool reports `queued->in_progress in ?` for each. `ci.yml`'s deployments do
record `queued`. The G2 assertion is on the *absence of `waiting`*, not on the
queue latency, so it is unaffected — but the timing column is blank for
dispatch-triggered deployments and the 3–8 s figures above are measured from
the deployment's `created_at` instead.

The general lesson is the one this eval keeps re-learning: "blocked" was a
property of the first framing, not of the system. Iteration 4 split
measurement from mechanism and recovered four observations; iteration 5 split
"prod mutation" into the answers a shim can supply; this one splits "pushed
ref" from "default branch". Each time the residue got smaller. What is left
after this is a single irreducible wait — a cron slot has to arrive.

### Splitting step 6 into the gate and the calendar (added 2026-07-31)

Step 6 reads as one observation — "the scheduled trigger fires unattended with
no approval prompt" — but it is two independent claims, and only one of them
needs to wait for a morning:

| Half | Needs |
|---|---|
| **(a) the cron fires at all** | calendar time — genuinely owed |
| **(b) nothing holds the job for a human** | nothing; observable right now |

(b) is the half the step-1 credentials fix put at risk, and it is the one that
matters more. Declaring `environment: production` is what gave the job its AWS
secrets, and an environment is exactly where GitHub hangs a required-reviewer
gate. A gated freshness check is worse than no check: it goes quiet at 09:00
waiting for a human who, by the premise of this entire workstream, is not
looking. Earlier this file discharged (b) by reading `protection_rules: []`
off the API — a config read, which says what *should* happen.

`tools/deploy-freshness-live-check.sh --verify-environment-gate` asks what
*did* happen as well. `ci.yml`'s deploy jobs declare the same environment, so
the account carries its own witnesses: a job whose environment requires
approval creates a deployment that sits in the `waiting` state until someone
clicks, so a completed deployment whose states never included `waiting` is a
run that was never gated. Measured 2026-07-31 (GitHub reads only, exit 0):

| # | Claim | Observed in `LeoTheMighty/palateful` |
|---|---|---|
| G0 | the check job declares an environment, and this is the name the rest is about | `environment: production`, read out of the workflow rather than hardcoded |
| G1 | that environment carries no approval gate and no branch policy | `protection_rules: []`, `deployment_branch_policy: null`, last changed 2026-03-20T20:41:42Z |
| G2 | real jobs used it and none ever waited for a human | 10 deployments, **0** in `waiting`; `queued` → `in_progress` in 1–8 s each. Eight are from run 30646967338 — today's real deploy — including `deploy-services`, which started 8 s after `run-migrator` finished. **Since updated with the strongest possible witnesses: the freshness check's own three dispatch deployments** (5695703361 / 5695719549 / 5695728778, 17:40–17:42Z) — `in_progress` 3–8 s after the deployment was created, no `waiting` — so G2 no longer argues by analogy from a *different* job that shares the environment. Note these three record **no `queued` state at all** (states go straight `in_progress` → terminal), so the tool prints `queued->in_progress in ?` for them; the assertion is on the absence of `waiting`, which is unaffected |
| G3 | that evidence postdates the environment's last configuration change | newest witness 2026-07-31T17:07:45Z ≥ 2026-03-20T20:41:42Z |

G3 is the one that is easy to skip and would rot silently: rules added *after*
the newest witness would gate the next run while every past deployment still
looks clean, so behavioural evidence older than the config it claims to
describe proves nothing. The tool exits **2 — not observable** rather than
passing when the environment is unreadable or has no deployments at all.

Mutation-verified 2026-07-31; each of five deliberate regressions was caught by
exactly one check, with the control green before and after:

| Mutation | Caught by | Exit |
|---|---|---|
| `environment:` line deleted from the workflow | G0 — "that is the credentials fix regressing" | 1 |
| environment renamed to one that does not exist | G1 — not observable (and G2 has no witnesses) | 2 |
| `waiting`-state detection looks for the wrong state | G2 — reported 8 of 10 deployments as gated | 1 |
| API forced to report a `required_reviewers` rule | G1 | 1 |
| environment `updated_at` forced past every witness | G3 | 1 |

What this does **not** discharge is (a). The workflow landed on `main` at
16:24 UTC on 2026-07-31, *after* that day's 15:00 UTC slot, so the earliest
scheduled run is 2026-08-01 — and note that the version now on `main` still
predates the `environment:` fix, so that first run will die in
`configure-aws-credentials` until this branch merges. The run that proves
step 6 is the first scheduled one after the merge.

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

### Step 6a: everything except the firing (added 2026-07-31)

The calendar half was left as one indivisible wait — "see if it fires
tomorrow". It is not indivisible. The firing needs a morning; every *condition*
for it is readable now, and each of those conditions fails the same way the
original 92-day freeze did: silently, with nothing red anywhere.
`tools/deploy-freshness-live-check.sh --verify-schedule-fires` reads all four
(GitHub only, no AWS). Measured 2026-07-31, exit 0:

| # | Condition | Observed in `LeoTheMighty/palateful` |
|---|---|---|
| S0 | GitHub still has the workflow in a state it can schedule | `state: active`. This is not a formality: GitHub **auto-disables scheduled workflows in a repo with 60 days of no activity**, and a disabled workflow neither fires nor complains — a freeze detector that dies of the very quiet it is watching for |
| S1 | the cron is on the **default branch** | `main` declares `0 15 * * *`, identical to this working tree. `schedule:` is honoured *only* from the default branch, so a cron edited on a feature branch — and dutifully pinned there by the self-test — schedules nothing |
| S2 | this repo's scheduler actually fires, unattended | **54** `event: schedule` runs over 94h, **0** in `waiting` and 0 `action_required` |
| S3 | it fires often enough for E-7's own 24h threshold | longest silence between firings **3.4h** (2026-07-31 01:13Z → 04:40Z), measured from those 54 runs |

S1 also prints, as a standing note rather than an assertion, that the
default-branch copy currently differs from this working tree in 16 lines and
**does not declare `environment:`** — which is exactly why the first scheduled
run will die in `configure-aws-credentials` until this branch merges. The
scheduled run uses `main`'s copy, never the one you are looking at.

**The finding: firings in this repo do not track the cron that declared them.**
All 54 witnesses belong to `devx-promotion.yml`, whose only live cron is
`0 0 31 2 *` — 31 February, a date that does not exist, deliberately chosen as
a no-op. It predicts **0** firings over the observed window. **54** occurred,
at irregular 1–3.4h intervals, every one `event: schedule`, `head_branch: main`,
conclusion `success`. The file has a single commit in its history, so a stale
definition does not explain it.

That matters for how step 6a gets read tomorrow. E-7's threshold is *frequency*
("within 24h of crossing 7 days"), and frequency is now measured and comfortably
met. *Punctuality* is not established and cannot be inferred from `0 15 * * *`,
so the observer must **record the actual UTC time the run lands** rather than
confirm it "ran at 09:00". Judging the check by the wrong one of those two would
turn a working detector into a phantom bug report, or vice versa.

Worth noting from the same tool: a plain daily cron yields a longest silence of
exactly **24.0h**, which meets E-7's 24h threshold with *zero* margin. If the
threshold is ever tightened, or the scheduler ever lags, the schedule needs a
second slot — the tool will say so rather than leave it to arithmetic.

Mutation-verified 2026-07-31; each of six deliberate regressions was caught by
exactly one check, with the control green before and after:

| Mutation | Caught by | Exit |
|---|---|---|
| workflow state forced to `disabled_inactivity` | S0 — "it will not fire, and it will not say so" | 1 |
| workflow path GitHub has never registered | S0 — not observable | 2 |
| working-tree cron changed to `0 16 * * *` | S1 — pins a schedule that is not the one running | 1 |
| `schedule:` block deleted from the working tree | S1 | 1 |
| one schedule run forced to `status: waiting` | S2 — the scheduler fires but a human gates it | 1 |
| run history thinned to its two endpoints (94h apart) | S3 — silence longer than the threshold | 1 |

Mutations S0/S2/S3 were injected into the **data** (a `gh` shim rewriting one
API answer) rather than into the comparisons, so what they prove is that the
assertions bind to what GitHub actually reports. The cadence analyzer
(`tools/deploy-freshness-cadence.py`) was separately controlled in both
directions, because a fidelity warning that is really a hardcoded string would
be worse than none: runs at 15:00 daily against `0 15 * * *` report
"predicts 4 — matches"; the same runs against `0 3,15 * * *` report a mismatch
(7 predicted, 4 observed) and still exit 0; the same runs against a 12h
threshold exit 1; a single run exits 2.

## Accepted cost

The check shares its fate with the CI system whose silent breakage it exists
to catch. Mitigated only by living in a separate workflow file with its own
trigger, so a red `ci.yml` does not skip it — a push-triggered job would have
been skipped throughout this very incident.

## Result

- **Verdict:** _pending on one observation_ — steps **1, 2, 3, 4 and 7 are
  fully observed**, mechanism included: three real `workflow_dispatch` runs of
  the fixed workflow in GitHub Actions (30652052889 success / 30652140468
  failure-on-demand / 30652190943 success), with environment-scoped credentials
  reaching live prod, cross-checked three ways. Step 5 is measured against live
  prod by simulation with its ECS semantics observed read-only (A0–A3); only
  the prod mutation stays owed and it is no longer discriminating while prod is
  fresh. Step 6's gate half is observed (G0–G3, now including this workflow's
  own three ungated deployments) and every precondition for the cron is
  observed (S0–S3: workflow active, cron on the default branch, 54 unattended
  scheduler firings, longest silence 3.4h vs a 24h threshold). **What remains
  is one thing: the first scheduled run of this workflow (step 6a)**, filed in
  `MANUAL.md`. Everything else about it that can be read has been read; a cron
  slot simply has to arrive.
- **Read the morning run by time as well as verdict.** This repo's scheduler
  fired 54 times against a cron that predicts zero, so the *hour* a run lands
  is not inferable from `0 15 * * *`. Record it. The threshold E-7 actually
  states is about frequency, and frequency is measured (S3).
- **Measured gap vs `git log`:** two readings, one hour apart, three agreeing
  legs each. **96 days** at 11:00 (`c85e350d`, 2026-04-26 10:27:45 -0600,
  exit 1) and **0 days** at 11:08 (`848311af`, 2026-07-31 10:24:08 -0600,
  exit 0), across a real deploy at 11:06.
- **The freeze is over.** Earlier guidance in this file — "a green run is the
  failure signal" — expired at 11:06 MDT on 2026-07-31. Post-merge runs should
  be judged by whether they **agree with `bin/prod-status` and `git log`**, not
  by an expected exit code.
- **Date observed:** 2026-07-31 — measurement (both freeze states) and the
  dispatch mechanism (three Actions runs, 17:40–17:42Z). The scheduled-trigger
  observation is pending the first cron slot after merge.

## Links

- Plan phase 8: `../plan.md`
- Expectation: `../expectations.md` (E-7)
