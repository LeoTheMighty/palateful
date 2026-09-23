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
      unavailable and show the outcome. A capacity fix that has never
      been exercised against an empty pool is a configured fix, not a
      verified one.

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
