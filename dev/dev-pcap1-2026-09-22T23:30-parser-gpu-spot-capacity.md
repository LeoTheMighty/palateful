---
hash: pcap1
type: dev
created: 2026-09-22T23:30:00-06:00
title: Parser GPU capacity — imports die when spot has no GPUs, silently, for months
from: leonidbelyi-41, after palateful-98 flagged `bin/prod-status` reporting "Batch Parser (recent jobs): FAILED: 1"
status: ready
owner: null
branch: null
---

## Goal

Make a user's import either run or fail visibly. Today it can be accepted,
never run, and leave no signal anywhere.

**Do not implement until Leo has answered the cost question in §Options —
on-demand GPU is his money.**

## What happened (measured 2026-09-22, read-only)

Leo submitted an import at **19:10:33 UTC**. It is still, five hours later,
showing as "1 import in progress". It is dead.

| time (UTC) | event |
|---|---|
| 19:10:33.79 | `parser_batches` row `9384da8a…` created, status **`submitted`** |
| 19:10:34.13 | AWS Batch job `parser-batch-84a8e0d3` created |
| 21:48:28 | attempt 1 instance terminated — **never started** |
| 22:10:20 | attempt 2 instance terminated — **never started** |
| 22:17:52 | attempt 3 terminated, job **FAILED** after 187 minutes |

All three spot requests closed with
**`instance-terminated-no-capacity`** — *"no Spot capacity available that
matches your request."* Not a code failure, not the `desired_vcpus` reset
(ruled out: attempt 1 died 16 minutes **before** that apply ran, and #53
had already merged), not today's deploys.

**Refinement that decides which fix matters (palateful-0e, verified
independently — all four of this spec's measurements matched).** This was
not "Batch never found capacity". 0e read the live environment about an
hour before the failure and saw **desired 4 with the job RUNNABLE**, so
**Batch allocated an instance three times and spot reclaimed each one
before the container started** (`startedAt: null`, `exitCode: null`, three
different instance IDs). Allocation is not the failing step; **surviving
reclamation** is. Therefore:
- the **on-demand fallback is load-bearing** — the only change that
  survives reclamation, because the failure happens *after* allocation;
- **widening the pool helps allocation**, which was never what failed
  here. Kept because it is free and reduces exposure, not because it
  fixes this;
- the **retry policy is a real bug that would not have saved this job** —
  with `evaluateOnExit: []` all three attempts were spent re-entering the
  same spot-only pool. It becomes load-bearing *once the fallback exists*,
  since that is what routes a reclaim-retry to on-demand.
It also narrows 79's permanent-vs-unlucky question: allocation works, so
this is reclamation exposure, not capacity unavailability.

**Downstream:** the batch never fanned out. `import_jobs` under it: **0**.
The Activity tab is empty because its table is empty, while "1 import in
progress" correctly reads the `parser_batches` row. The UI bug
(`impvis1`, palateful-79) and this are the same incident from two ends.

## The five-month silence — the part that matters most

The pipeline **used to work**: 9 succeeded batches, last **2026-04-22**;
43 completed `import_jobs`, last **2026-04-26** — the same date prod froze
on `c85e350`.

**Precisely what is measured, because the obvious phrasing overstates it:**
**tonight is the first `parser_batches` row since 2026-04-22.** There are
no batch rows in between. So for those five months the pipeline was not
failing — **nothing was asking it to run**. What is measured is that the
first attempt after the gap died on capacity. Whether it would also have
failed in June is untested and now untestable.
*(This spec first said "five months dead". That was inference dressed as
measurement; palateful-79 caught the same overstatement in its own spec
and the correction applies here too.)*

**Nothing noticed, for five months:**
- no alarm on a Batch job failing;
- no alarm on a `parser_batches` row stuck in `submitted`;
- no alarm on **14 `parser_jobs` stuck in `running` since April** and 8 in
  `submitted`.

A user-visible feature was unusable, and the one attempt to use it failed
with **zero signal**. That is a stronger example than most of the detection
ranking
(`dev-clidet1`, `dev-obsgap1`): the failure was not mis-reported, it was
never reported.

*(Correction on the record: this spec's author first inferred "the parser
has never run" from three empty Batch log groups. That was wrong — the
logs had expired. The database answered directly and differently. Empty
is not evidence of never.)*

## Current configuration

- compute environment: **SPOT only**, `instanceTypes: [g4dn.xlarge,
  g5.xlarge]`, 2 subnets, `SPOT_PRICE_CAPACITY_OPTIMIZED`, max 32 vCPU,
  **no on-demand fallback**
- job definition `palateful-parser-job-prod:32` — 4 vCPU, 15 GiB, **1
  GPU**, `attempts: 3`, `attemptDurationSeconds: 1800`
- historical successful batches ran **11–13 minutes** end to end

## Options (costs measured from the AWS Pricing API, us-east-1, Linux)

On-demand: **g4dn.xlarge $0.526/hr**, g6.xlarge $0.805/hr, g5.xlarge
$1.006/hr, g4dn.2xlarge $0.752/hr. A 13-minute job on g4dn.xlarge is
**≈ $0.11 on-demand**; spot typically runs 60–70% below that, so the
delta per import is **cents**.

1. **Widen the instance types.** Add `g6.xlarge`, `g4dn.2xlarge`,
   `g5.2xlarge` to the spot pool. More pools, less exhaustion. **No cost
   change** (still spot, capacity-optimised picks cheapest available).
   Lowest risk, smallest benefit — it reduces the odds, doesn't remove
   them.
2. **On-demand fallback.** Add a second compute environment (on-demand,
   same types) **lower** in the job queue's order, so Batch uses spot
   first and falls back only when spot has nothing. Cost is bounded by
   how often spot fails: at 13 min/job, **each fallback job costs ~$0.11**.
   This is the only option that makes an import actually complete tonight.
3. **Retry policy.** `attempts: 3` burned in 30 minutes against a pool
   that was empty for hours. `evaluateOnExit` is empty, so a
   capacity kill and an application crash are retried identically.
   Consider more attempts with backoff **for capacity kills only**, so a
   genuine crash still fails fast.
4. **Do nothing about capacity, fix only visibility.** Legitimate if
   imports are rare and Leo will retry manually — but then `impvis1`
   must say *failed*, not *in progress*.

Recommendation, pending Leo: **1 + 3 unconditionally** (free, reduces
recurrence, stops burning retries in 30 minutes), and **2 if he accepts
~$0.11 per fallen-back import**.

## Acceptance criteria

- [ ] **Record which compute environment ran each attempt** (palateful-0e's
      wording, kept because the last clause is the load-bearing part):
      > When the job is re-submitted, read `describe-jobs →
      > jobs[0].attempts[].container.taskArn` for **every** attempt and
      > record which compute environment ran each one. The ARN embeds the
      > CE name (e.g. `…/palateful-parser-spot-gpu-prod-…_Batch_…`).
      > **A successful import does not discharge this AC** — a job that
      > succeeds on its first spot attempt proves nothing about fallback.
      > The AC is discharged only by an attempt observed running on the
      > **on-demand** CE, or by an explicit note that no reclamation
      > occurred and the assumption is still untested.

      The likeliest outcome now that the pool is wider is that the first
      attempt succeeds — which would read as "the fallback works" while
      leaving the assumption the fix rests on unverified. That is tonight's
      LESSONS entry (#64) landing on this very change, so the escape clause
      stays.
- [ ] **Independent re-confirmation by a session that did not make the
      change** (carried from `debug/debug-parsercap1`; owner palateful-0e).
      One session's read of prod is a strong lead, not a licence — and not
      a self-check.
- [ ] **Settle the open question by re-running**: is the capacity failure
      permanent, or was tonight unlucky? One spot-only pool with no
      fallback fails either way, and a single data point cannot separate
      them. Re-submit a batch and observe — do not infer from tonight.
- [ ] An import that cannot get spot capacity **either** runs on fallback
      capacity **or** reaches a terminal failed state visible to the user.
      No more "accepted, never ran, still says in progress".
- [ ] A Batch job that fails, **and** a `parser_batches` row still
      `submitted` after N minutes, each raise an alert. Wired to the
      alert channel from G1 — note it currently has **0 subscriptions**,
      so this is not done until a confirmed subscriber exists.
- [ ] **The April stale state is resolved explicitly**: 14 `parser_jobs`
      in `running` and 8 in `submitted`, all from April. Decide and
      implement — reconcile against Batch, or mark terminal — and say
      which. Until then, any count the app shows is untrustworthy.
- [ ] Tonight's batch `9384da8a…` is resolved, not left `submitted`.
- [ ] Proven by driving it: submit an import while spot capacity is
      unavailable and show the outcome — **recording which compute
      environment the attempt landed on**, since a success on order 1
      proves the pipeline, not the fallback. Method proposed above;
      needs Leo's approval before running. A capacity fix that has never
      been exercised against an empty pool is a configured fix, not a
      verified one.

## Ownership after reconciling with parsercap1 and prcon1

Three specs described one incident. Merged 2026-09-23 so no AC is silently
dropped when one closes:

| Concern | Owner | State |
|---|---|---|
| Capacity: fallback, wider pool, reclaim-aware retries | **pcap1** (this) | Applied `fb2892d0` |
| Fallback drill — is it permanent or was tonight unlucky? | **pcap1** (this) | **Owed**, proposed below, needs Leo |
| **Independent re-confirmation before/after changing the compute environment** — carried from `debug/debug-parsercap1`'s first AC | **palateful-0e** | **Owed** |
| Write-back: a Batch job dies and the rows stay `submitted` | **`dev/dev-prcon1`** | Ready |
| April stale state: 14 `parser_jobs` `running` + 7 `submitted`, `parser_batch_id IS NULL` | **`dev/dev-prcon1`** | Ready |
| Rendering a dead batch as failed | `impvis1` / #56 (palateful-79) | Merged |

`debug/debug-parsercap1` is closed as **superseded**, pointing here and at
prcon1. It is not deleted: it holds the original investigation.

**This spec does not resurrect Leo's stuck batch `9384da8a…`.** That needs
prcon1's write-back plus a re-submit.

## Correction: "the fallback is load-bearing" is NOT established

palateful-0e proposed that framing and has since walked it back, and the
walk-back is right. The reasoning was: reclamation happens *after*
allocation, so only on-demand survives it. **That does not follow.**

Batch picks a compute environment when it **schedules an attempt**, based
on where it can place work. Reclamation is not a placement failure — so
if the spot environment can still allocate, a retry is likely placed on
**order 1 again**. Order 2 engages when order 1 **cannot allocate**, which
is exactly the condition we did *not* observe on 2026-09-22. In the worst
case all 10 attempts burn on spot.

What rescues it is correlation, not mechanism: reclamation usually happens
*under* capacity pressure, so spot often also fails to allocate and order 2
then engages. That is a probabilistic argument. Neither session found a
documented guarantee.

**How to settle it by measurement, not documentation.** The task ARN
embeds the compute environment name:
`arn:aws:ecs:…:task/palateful-parser-spot-gpu-prod-…_Batch_…/…`
So `describe-jobs → attempts[].container.taskArn` reveals **which
environment ran each attempt**. Verified against the 2026-09-22 failure:
all three attempts report the spot environment. (That job predates the
fallback, so it proves the method, not the behaviour.)

**Therefore, and this matters for the drill below:**
- forcing spot `max_vcpus = 0` proves **order-2 placement works at all** —
  a genuine prerequisite, and it rules out a mis-ordered queue;
- it tests **allocation-failure fallback**, *not* **reclamation fallback**,
  which is the assumption actually in doubt;
- only **per-attempt CE inspection on a real multi-attempt job** discharges
  it. That costs nothing and needs no forcing — it just needs the next
  failure.

Until then, pcap1's honest claim is: the wider pool and the retry policy
are improvements on their own, and the fallback **may or may not** engage
on reclamation.

## Proposed fallback drill — NOT YET RUN, needs Leo's approval

**The problem with waiting.** The fallback only engages when spot cannot
serve. If we wait for that to happen naturally, **the first real test of
this code is an actual user import** — which is how tonight went. A drill
is the alternative: force the condition deliberately, at a chosen moment,
with someone watching.

**Method (controllable, reversible):**
1. Confirm the parser queue is idle (`RUNNING/RUNNABLE/STARTING/SUBMITTED`
   all 0).
2. Set the **spot** compute environment's `max_vcpus` to **0** via
   Terraform and apply. Spot can then allocate nothing, which is a
   stronger condition than a real exhaustion.
3. Submit one parser batch.
4. Expect: the job cannot be placed on order 1, Batch places it on the
   **on-demand** environment at order 2, an instance starts, and the job
   runs to completion. Record the compute environment the attempt landed
   on, not just that the job succeeded.
5. Revert `max_vcpus` and apply.

**Risk, stated plainly: this is a production Terraform change whose whole
purpose is to make production fail over.** Between steps 2 and 5, an
import Leo submits can only run on the 8-vCPU on-demand environment. If
step 5 is forgotten, spot stays disabled and every subsequent import runs
at on-demand price. Mitigations: run it while the queue is idle, keep the
window short, and treat step 5 as part of the drill rather than cleanup.
Same shape as `rsh109`'s rotation drill — a deliberate, attended
production exercise, not a background task.

**What the drill proves that a normal import does not.** A successful
import while spot capacity is *available* proves the pipeline works end
to end. It proves **nothing about the fallback**, because order 1 served
it. Only a placement on order 2 tests the change that pcap1 calls
load-bearing.

**Open assumption this drill also settles** (raised to palateful-0e for
independent confirmation): does Batch actually place a *retry* on the
next compute environment in the queue after a host-level kill, rather
than re-queueing to the environment that owned the previous attempt? The
fallback's value rests on it, and it was reasoned from the queue-order
semantics rather than measured.

## Outcome 2026-09-23: the fallback did not work, and the order is inverted

Leo re-submitted an import at **15:08:09 UTC**. Observed for **88 minutes**:

| | |
|---|---|
| job status | `RUNNABLE`, **0 attempts** |
| spot CE `desiredvCpus` | **4**, held throughout |
| on-demand CE `desiredvCpus` | **0**, never moved |
| container instances | **0** in both clusters |
| spot instance requests today | **0** (last night: 3) |
| EC2 fleets today | **0** |
| both CEs | `VALID`, "ComputeEnvironment Healthy" |

**Nothing was broken.** Batch decided order 1 *could* allocate, set a target
of 4 vCPU, and retried fleet requests that never fulfilled — so **order 2
was never reached**. This is 0e's corrected model confirmed by observation:
order 2 engages when order 1 **cannot allocate**, not when it allocates and
fails to deliver.

Note this is *worse* than 2026-09-22, when three instances at least launched
before being reclaimed. Tonight nothing launched at all, across five
instance types.

**Decision (Leo): on-demand becomes order 1, spot order 2** (`odfirst1`).
Cost at measured April volume — 24 GPU jobs / 12 days, avg 11.9 min, 4.76
GPU-hours: **~$4.36/month**, about 7c per import. The `$0.16/hr` spot figure
is from a **code comment, not a measurement**, so the delta is approximate;
the on-demand side ($0.526/hr) is from the AWS Pricing API.

**The honest counterpoint, recorded because it is the lesson.** This makes
pcap1's on-demand fallback **largely redundant** — it only helps in the case
where spot cannot even be targeted, which is not the case that has occurred
twice. The original design optimised for a saving of **about four dollars a
month** at the cost of a feature that then failed twice, and the fix I built
for it addressed the wrong half of the failure. Spot-first fails open into
*queued forever*; on-demand-first fails into *slightly more expensive*.
**Prefer the failure mode that degrades cost over the one that degrades
function**, especially when the saving is this small.

## The root cause: the account was never permitted to run on-demand G instances

**`L-DB2E81BA` "Running On-Demand G and VT instances" = 0.** Adjustable,
and the quota-change history is **empty** — it has been 0 since the account
was created. Spot is permitted: `L-3819A6DF` = 32.

**Why nobody checked: the adjacent quota is fine.** `L-3819A6DF` is **32**.
Two near-identically named GPU quotas, one healthy and one zero — so anyone
asking *"do we have GPU quota in this account?"* finds a reassuring number
and stops. The reassuring reading was real; it just answered a different
question. `L-DB2E81BA` is `adjustable: true`, so the remedy is a support
request, not a redesign — and **an adjustable quota at 0 with an empty
change history is specifically the signature of "nobody ever asked"**, as
distinct from a hard limit. (Contrast drawn by palateful-0a, who also
re-verified both quotas independently from the live account.)

AZs are ruled out: the CEs use `us-east-1a` and `us-east-1b`, and
`g4dn.xlarge`, `g5.xlarge` and `g6.xlarge` are all offered in 1a, 1b, 1c,
1d and 1f.

**Why a quota of 0 was invisible rather than merely unnoticed: there was no
on-demand path to exercise.** `parser_ondemand_gpu` first entered the module
in `fb2892d0` (#63) on **2026-09-22** — before that commit the queue had
exactly one compute environment and it was spot. So every April import ran on
spot by construction, not by chance. The account has been forbidden to run
on-demand G instances since it was created, and until last night nothing ever
asked it to. The first thing that did was the fallback built to make the
pipeline more reliable.

**So pcap1's on-demand fallback was structurally incapable of launching a
single instance, from the moment it was written.** Not "engages only when
spot cannot allocate" — the account may not run these instances at all.

### The lesson: verified the shape, never the capability

The fallback was checked, and checked again, and both checks passed:
- the author planned it, applied it, and confirmed 5 instance types, `max
  8`, `ENABLED/VALID`, queue order 2;
- **palateful-0e independently re-confirmed all of it from AWS**, including
  catching a real defect (the pool was narrower than spot's);
- a pre-registered plan matched the apply exactly; every post-apply check
  passed.

**Every one of those checks was about the shape of the configuration. None
asked whether the account was permitted to create the resource.** Two
sessions confirmed the wiring; neither confirmed the capability.

**General form: for any resource a change depends on, confirm the account
can actually create it — not merely that the configuration refers to it
correctly.** A service quota of 0 produces a `VALID` / "ComputeEnvironment
Healthy" environment, a standing `desiredvCpus`, and silence.

### Observed: Batch does not fall through an incapable order-1

With on-demand at order 1 and its quota at 0, Batch held `desiredvCpus = 4`
on the incapable environment for **67 minutes** and **never fell through to
order 2**. The whole fallback design assumed it would. Worth knowing
independently of the quota: an order-1 environment that cannot deliver is
not automatically skipped.

### Status

Spot-first restored (`spotback1`) **only because on-demand cannot launch**.
Leo has filed the `L-DB2E81BA` increase. When granted, flip back to
on-demand first — `odfirst1` / #76 holds the reasoning and the costing.

## Correction: the cost model counted only the runs that worked

#76 costed the on-demand fallback from **4.76 GPU-hours** — 24 succeeded
April `parser_jobs` × 11.89 min. That excluded the **16 failed jobs**, which
averaged **12.92 min** and ran as long as **20.1**. Failed jobs occupy the
GPU for their whole run; several fail *because* they ran long.

Real April basis, from `completed_at`: **40 jobs, 8.20 GPU-hours,
2026-04-09 → 04-22** (14 days, not the 12 first written). **+72% on the
basis**, scaling the published $4.36/month to roughly **$7.50** — *scaled
from the published figure, not re-derived from instance pricing*. Leo has
the corrected number; his decision is unchanged.

**The generalisation, which is the actual finding:** *a cost model built
from successful runs understates anything whose failures consume the same
resource.* This is the survivorship shape — reasoning from the healthy
population — and here it is worse than neutral, because **a failure that
runs to the 30-minute timeout costs more than a success.** The population I
dropped was the expensive one.

Same shape as the defect the stale-pointer guard was built to avoid:
counting only stale-*shaped* hits made "nothing is stale" and "I matched
almost nothing" the same output. Whenever a number is derived from a
filtered set, state the filter next to the number.

**Not a correction — a number that looks alarming and means nothing.**
April `import_jobs` show `completed_at - created_at` averaging **290
minutes**, to a maximum of **1247**. That is not pipeline latency:
`import_jobs.created_at` is set **after** parsing finishes, and the interval
from import-job creation to its last `parser_job` completing is **0.0
minutes on all six rows**. It measures the **user's review-and-confirm
phase**. Reported as latency it would send someone hunting a performance
problem that is Leo reading his own recipes.

## For prcon1: the two failure modes are distinguishable in the data

No new instrumentation needed. A sweep can tell them apart today:

| Failure mode | `status` | `completed_at` |
|---|---|---|
| Watcher timed out (90 min) | `failed` | ≈ `created_at` + 90 min |
| Celery worker restarted | `submitted` | **NULL, forever** |

The second is last night's `9384da8a`, which sat `submitted` for 21.7 hours
because the in-process sleep loop died with its worker and nothing ever
wrote a terminal status. This retroactively confirms 0e's account of that
window.

**Paired hazard, and they compound: `updated_at` is not bumped by the
timeout write.** Measured per row — on all 11 April batches
`updated_at - completed_at` is **+0.002 to +0.242 s** (same transaction);
on the two September timeout rows it is **−5383 s**, i.e. `updated_at` sits
90 minutes *before* the row's own terminal write. On `parser_jobs` the
maximum divergence anywhere is 0.23 s.

**So a sweep that looks for "recently changed batches" by `updated_at`
misses precisely the timed-out ones** — the failures most worth finding.
Sweep on `completed_at`, or on `status` directly.

**Mechanism, found by palateful-0e and now owned by `prcon1` (#77).** The
timeout write is not special. `updated_at` is `onupdate=func.now()`
(`joins_base.py:16`), and Postgres `now()` is **transaction start time**,
not statement time — 0e proved this read-only against prod rather than
citing it: across a `pg_sleep(2)` inside one transaction, `now()` moved
**0.000s** while `clock_timestamp()` moved **2.011s**. The watcher holds
**one transaction open for the whole 90 minutes** (the per-poll re-fetch at
`watch_parser_batch_task.py:75` is a SELECT, and the non-terminal path of
`complete_parser_batch` deliberately writes nothing), while `completed_at`
is Python wall-clock (`parser_batch_completion.py:242`). One write, two
columns, two different clocks.

**Why it's believable rather than merely consistent: it predicted my
control.** `_mark_failed` commits, so the `parser_jobs` loop runs in a
*fresh* transaction begun at the real time — their `updated_at` should
track `completed_at` closely. Measured max divergence: **0.23s**. 0e
derived the mechanism before re-reading that measurement, and it is the
observation that would have falsified it.

**Generalisation, which outlives this spec:** *any row written by a
long-running task before its first commit carries an `updated_at` from when
the task started, not from when the row changed.* That holds anywhere in
this codebase a task holds a transaction open — not only here.

## Technical notes

- Evidence gathered read-only via `bin/prod-script` inside
  `SET TRANSACTION READ ONLY`, plus `aws batch` / `aws ec2
  describe-spot-instance-requests` / `aws pricing`.
- The spot-request status is the decisive artefact: `statusReason` on the
  Batch job only says "Host EC2 terminated", which is ambiguous between
  reclamation, capacity exhaustion and a terraform-driven scale-down.
  `describe-spot-instance-requests` disambiguated it.
- `impvis1` (palateful-79) renders this state; it has the joined evidence
  and the recommendation that the string be *dead*, not *in flight*.

## Status log

- 2026-09-22 — filed from the investigation of `bin/prod-status`'s
  "FAILED: 1", which palateful-98 flagged rather than dropping. Root
  cause is spot GPU capacity exhaustion; the five-month silence is the
  larger finding. Not implemented: awaiting Leo's decision on on-demand
  fallback cost.
- 2026-09-22 — corrected: "five months dead" replaced with what is
  measured, that no batch was submitted between 2026-04-22 and tonight.
  Also recorded from palateful-79's pull: the 14 stuck `parser_jobs` have
  `parser_batch_id IS NULL`, so no surface renders them and no count
  includes them — invisible stale state, not merely undisplayed.
- 2026-09-22 — implemented (options 1+2+3) after Leo approved the
  on-demand cost. Framing corrected from 0e's independent verification:
  the failure is reclamation *after* allocation, which makes the fallback
  load-bearing and the wider pool a cheap extra.
- 2026-09-23 — applied to prod (`fb2892d0`, apply run 35803059252):
  3 added, 1 changed, 2 destroyed, matching the pre-registered plan
  exactly; the old spot CE went as a deposed object *after* the new one
  and after the queue was repointed, so `create_before_destroy` is
  verified behaviour rather than an assumption. Configured-correctly pass
  green. **Still owed: the fallback drill (proposed above, not run) and
  0e's independent re-confirmation.** This fix does **not** resurrect
  Leo's stuck batch `9384da8a…`; that needs 0e's write-back spec and a
  re-submit.
- 2026-09-23 — fallback observed NOT engaging on a live import (88 min,
  spot desired 4, on-demand 0, zero instance requests). Leo chose
  on-demand-first; filed as `odfirst1`. pcap1's fallback is largely
  redundant as a result, recorded above rather than quietly superseded.
- 2026-09-23 — root cause found: on-demand G quota is 0 and always has
  been, so the fallback could never launch. Reverted to spot-first
  temporarily (`spotback1`); Leo filed the limit increase. Recorded the
  general lesson — verified the shape, never the capability — and the
  observation that Batch does not fall through an incapable order-1.
