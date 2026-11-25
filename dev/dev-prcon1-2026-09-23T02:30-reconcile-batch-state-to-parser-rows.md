---
hash: prcon1
type: dev
created: 2026-09-23T02:30:00-06:00
title: Nothing reconciles terminal AWS Batch state back to parser rows — the app believes dead imports are still running
from: dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md
status: ready
owner: null
branch: null
---

## Goal

> **This spec's original premise was WRONG and is corrected below (2026-09-23).**
> It was filed as "nothing reconciles terminal AWS Batch state back to parser
> rows". Reconcilers exist. The defect is different, and worse.

**Two independent defects, both observed live in prod.**

### Defect 1 — the safety net dies with its process

Completion has a primary path and a safety net:
- **Primary:** the Batch container itself POSTs `/parser/batches/{id}/complete`
  on exit (`run_job.py`).
- **Safety net:** `watch_parser_batch_task`, dispatched at
  `create_parser_batch.py:103`, for when the container crashes or is
  Spot-interrupted before it can call back.

**The safety net is an in-process blocking loop** —
`for attempt in range(180)` with `time.sleep(30)` inline
(`watch_parser_batch_task.py:102`), i.e. **one Celery worker blocking for 90
minutes**. It is not a scheduled re-check. **Kill the process and the vigil is
gone; nothing re-arms it**, and the batch stays `submitted` forever.

**Observed (measured):** batch `9384da8a` (2026-09-22 19:10:33Z) was still
`submitted` with `completed_at` NULL **21.7 hours later**, while batch
`49ba1ba6` under identical code *did* time out. The discriminator is a worker
replacement inside the vigil's window — ECS events for
`palateful-worker-prod`:
```
20:05:58  has stopped 1 running tasks: (733963f4…)
20:05:59  has started 1 tasks: (c38fa30a…)
20:07:43  has stopped 1 running tasks: (c38fa30a…)
20:07:44  has started 1 tasks: (7ce79282…)
20:11:30  deployment ecs-svc/5381258920964928019 completed
```
20:05:58 is inside 19:10:33 → 20:40:33, ~35 min before the timeout would have
fired.

**Deploys are one cause, not the cause.** Three separate attributions to a
specific deploy were made and all three were withdrawn: the worker replacement
at 20:05:58 is **eleven minutes before** `fd732fab`'s first ECS-touching leg
(`terraform-prod` 20:17:15, `deploy-services` 20:19:22). **The trigger for the
20:05 replacement is unidentified** — see `wkrst1`.

**That is the argument for the fix.** A mechanism that survives only while one
process stays alive for 90 minutes will be broken by things nobody classified
as a deploy, so **no deploy-scheduling discipline repairs it**. Reconciliation
must be a **periodic sweep over non-terminal rows**, not an in-process vigil.
Lengthening the budget makes a bigger target, not a safer one.

### Defect 2 — the timeout writes a false terminal, and the idempotence guard then protects it

The vigil's expiry writes `failed` **unconditionally**, without re-checking
whether AWS still has the job. Observed live:

| | |
|---|---|
| DB, batch `49ba1ba6` | **`failed`** at **16:38:22Z**, *"Watcher timed out after 90 minutes"* |
| AWS, job `d1945302`, same moment | **`RUNNABLE`**, `attempts: 0`, `startedAt: null` — **never started** |

**Twice in one day.** The resubmit repeated it exactly, and this one was
watched to the second: batch `2ca59c8c` → **`failed` at 18:41:49Z**, same
message, while AWS job `2e878fd3` read **`RUNNABLE`, `attempts: 0`,
`startedAt: null`** at that same instant. Two dated instances, four hours
apart, same mechanism.

**Root cause of *why* neither job started** (palateful-4f): service quota
**`L-DB2E81BA`, "Running On-Demand G and VT instances", is `0`** — the AWS
default, never raised. After the CE reorder put on-demand first, jobs queued
against a pool **the account is not permitted to run at all**. So these jobs
were never going to start, timeout or no timeout.

**That is what makes the false-terminal defect worth fixing independently.**
The quota explains the *stall*; it does not excuse writing `failed` onto work
AWS still has queued, nor discarding the eventual output. Had the quota been
fine and the job merely slow, the same write would have destroyed a genuinely
recoverable import — which is what happened to the 09-22 batch.

The job was *queued*, not failed. Then
`parser_batch_completion.py:49` does its job correctly:

```python
if parser_batch.status in TERMINAL_STATUSES:   # ("succeeded","failed","partial")
    return parser_batch.status                  # no-op
```

So when the container eventually finishes and calls back, it is told `failed`,
**returns HTTP 200**, and exits. **No `ImportJob`, no `ImportItem`, no recipe,
and no record anywhere that a completed parse was discarded.** The user must
resubmit; the GPU work is paid for and thrown away.

**The guard is correct in isolation** — re-entering a finished batch *should*
be a no-op. It becomes destructive only because a different mechanism can mark
a batch terminal while the work is still queued. **The guard faithfully
protects a lie.** A periodic sweep alone does **not** fix this.

### The trap this sets for the fix: `updated_at` is written at transaction start

The obvious way to write the sweep — "find batches whose `updated_at` is
older than N minutes" — **misses precisely the rows this spec is about.**

palateful-4f measured the divergence: on the 11 April batches
`updated_at - completed_at` is +0.002s to +0.242s, but on the two September
timeout rows it is **-5383s** — `updated_at` sits 90 minutes *before* the
row's own terminal write. My probe reads the same thing on `2ca59c8c`:
`created=17:11:36 upd=17:12:07 done=18:41:49`.

The mechanism is not specific to the timeout path, which is why it belongs
in the spec rather than in a code comment:

1. `updated_at` is `onupdate=func.now()` (`models/joins_base.py:16`), and
   Postgres `now()` is **transaction start**, not statement time. Verified
   against prod, read-only: inside one transaction across a `pg_sleep(2)`,
   `now()` moved `0.000s` while `clock_timestamp()` moved `2.011s`.
2. The watcher holds **one transaction open for the full 90 minutes**. The
   per-poll re-fetch (`watch_parser_batch_task.py:75`) is a SELECT, and the
   non-terminal path of `complete_parser_batch` explicitly leaves the row
   untouched, so nothing commits.
3. `completed_at = datetime.now(UTC)` (`parser_batch_completion.py:242`) is
   Python wall-clock. So the same write records the true time in
   `completed_at` and the transaction's start time in `updated_at`.

**The hypothesis predicts 4f's control measurement, which is why I believe
it rather than merely fitting it**: `_mark_failed` commits, and the
`parser_jobs` are then updated in a *fresh* transaction begun at the real
time — so their `updated_at` should track `completed_at` closely. 4f
measured max divergence 0.23s on `parser_jobs`. That is the prediction.

The generalisation is the part worth carrying: **any row written by a
long-running task before its first commit carries an `updated_at` from when
the task started, not from when the row changed.** Anywhere in this codebase
that a task holds a transaction, `updated_at` is unreliable as a
"recently changed" signal.

Sweep on `status` and `completed_at`. Never on `updated_at`.

**Third instance, 2026-09-24 — and it is the one that generalises the other
two, because it was written by the NORMAL completion path.** Batch
`2d125b0d` (created 15:26:36) had its AWS job fail genuinely; the watcher's
own poll caught it and wrote the terminal status at 16:41:46 with AWS's real
reason. **No timeout was involved at any point.** The divergence is
identical in shape:

| | `updated_at` | `completed_at` | divergence |
|---|---|---|---|
| Timeout path, `49ba1ba6` / `2ca59c8c` (09-23) | transaction start | real | **-5383s** |
| **Normal completion, `2d125b0d` (09-24)** | **15:27:06** | **16:41:46** | **-4480s** |

The original framing — "the timeout write doesn't bump `updated_at`" — is
therefore **too narrow and should not be repeated**. The timeout path is not
special. The watcher holds one transaction across its entire poll loop, so
**every** write it makes carries a transaction-start `updated_at`, whichever
branch produced it. A sweep keyed on `updated_at` misses rows stranded by
any of them.

## What did NOT happen on 2026-09-24, and why it belongs in this spec

The same run is the clearest evidence of where this defect's boundary lies.
AWS reported `FAILED`; the watcher's own poll detected it; the database
recorded a terminal status carrying AWS's real reason (`Essential container
in task exited`) **14m50s inside the 90-minute mark**. No false terminal, no
discarded result, no idempotence-guard collision.

**When the container's outcome reaches AWS and the watcher is alive to see
it, the existing path works.** The defects in this spec are what happens
when one of those two conditions fails — the vigil dies with its worker, or
the deadline expires while AWS still holds the job. Whoever implements the
sweep should know they are covering those gaps, **not** replacing a path
that is broken in the normal case. Recording the success as precisely as the
failures is what makes that boundary legible.

(Separately: that container lived **34 seconds** against an April baseline
of 11.89 min succeeded / 12.92 min failed. That is a different defect,
filed as `ocrload1` — a model-load crash — and is explicitly not in scope
here.)

## Acceptance criteria

- [ ] **Reconciliation is a periodic sweep over non-terminal rows**, not an
      in-process vigil. It must survive worker replacement, because worker
      replacement is routine and not always a deploy.
- [ ] **The timeout stops writing terminal states for work AWS still holds.**
      Before marking anything failed, re-query Batch: if the job is
      `SUBMITTED`/`PENDING`/`RUNNABLE`/`STARTING`/`RUNNING`, it is **not**
      failed. Prefer leaving it non-terminal for the sweep over writing a
      false terminal.
- [ ] **A callback arriving at an already-terminal batch is recorded, not
      silently dropped.** Today it returns 200 and vanishes. At minimum log +
      alert; ideally, a batch marked failed *only* by timeout should be
      recoverable when real output later arrives.
- [ ] **Decide explicitly what happens to the stranded rows, before
      implementing** — `9384da8a` and the 14 April `parser_jobs` stuck
      `running` with `parser_batch_id IS NULL` (2026-04-09 → 04-11). Their
      Batch jobs are long past retention, so a sweep that only reads live
      Batch cannot resolve them. Reconcile or mark terminal, but **say which
      in the spec**.
- [ ] Rows awaiting a **human** (`awaiting_review`) are never swept. The test
      is "is the system still going to act on this?", not "is it
      non-terminal?".
- [ ] **Divergence is surfaced, not just repaired** — otherwise the sweep is
      another silent detector. Ties to `absal1`.
- [ ] Proven by driving a job to each outcome and watching the rows follow,
      not by reading the sweep.
- [ ] **The sweep's own success case is asserted, not assumed.** A test must
      cover the 2026-09-24 shape: AWS reports terminal, the watcher is alive,
      and the existing path records it correctly **without** the sweep acting.
      A sweep that "fixes" rows the normal path already handled is a
      regression, and nothing currently distinguishes the two.
- [ ] **The sweep does not key on `updated_at`.** It is written at
      transaction start, so on exactly the timed-out rows it predates the
      row's own terminal write by 90 minutes. Key on `status` +
      `completed_at`, and assert it in a test rather than a comment.

## Technical notes

- **Coordinate before implementing:** `pcap1` (palateful-4f, parser capacity)
  and palateful-79's stranded-state work overlap this. This spec is
  deliberately scoped to **reconciliation and stale state**, not to capacity.
  Agree the boundary so it isn't specced twice.
- Batch retains job detail for a limited window, so a reconciler that only
  ever reads live Batch cannot fix history. That is exactly why the 14 April
  rows need a decision rather than a lookup.
- Related: `parser_jobs.batch_job_id` exists, which is the join key a
  reconciler needs; check it is populated for today's row before relying on it.

## Status log
- 2026-09-23T02:30 — filed at palateful-41's request after independently
  verifying palateful-4f's parser-capacity evidence. All four of 4f's points
  matched exactly; this divergence is what that check turned up that its
  scope did not cover.
- 2026-09-23 — reconciliation note (added by the pcap1 owner; palateful-0e
  please adjust if you disagree): **prcon1 owns the write-back AND the April
  stale state** (14 `parser_jobs` `running` + 7 `submitted`, `parser_batch_id
  IS NULL`), since it holds the fuller measurement. `debug/debug-parsercap1`
  is superseded and points here for both. Capacity and the fallback drill are
  `dev/dev-pcap1`; its independent re-confirmation AC is yours.
- 2026-09-23 — **rewritten; original premise refuted.** Reconcilers exist
  (`watch_parser_batch_task`, 90 min; `watch_parser_job_task`, 20 min) and the
  primary path is the container's own callback. The defects are (1) the safety
  net is an in-process vigil that dies with its worker and is never re-armed,
  and (2) its timeout writes a false terminal that the idempotence guard then
  protects, discarding a real result. Both observed live in prod today.
  Three attributions of the worker replacement to a specific deploy were made
  and withdrawn; the trigger remains unidentified (`wkrst1`). What survived
  every correction is the process-lifetime dependency, which is what the fix
  must remove.
- 2026-09-23T18:55 — added the `updated_at` trap section + its AC. 4f measured
  the divergence (-5383s on the two September timeout rows vs +0.002..0.242s
  on the April rows) and addressed it here from `pcap1`; I confirmed it from
  my own probe (`2ca59c8c`: upd=17:12:07, done=18:41:49) and then established
  the mechanism rather than the correlation: Postgres `now()` is
  transaction-start, proven read-only against prod (`now()` +0.000s across a
  `pg_sleep(2)` while `clock_timestamp()` moved +2.011s), and the watcher
  holds one transaction open for the full 90 minutes. The mechanism predicts
  4f's control — `parser_jobs`, written after `_mark_failed` commits, should
  track closely, and they do (max 0.23s). Generalised in the spec: any row
  written by a long-running task before its first commit carries an
  `updated_at` from when the task started.
- 2026-09-24T16:50 — added the third `updated_at` instance, measured on batch
  `2d125b0d`. It is the one that generalises: the write came from the normal
  completion path with no timeout involved (`updated_at` 15:27:06,
  `completed_at` 16:41:46, -4480s), so "the timeout write doesn't bump
  `updated_at`" is too narrow and the transaction-holding mechanism is the
  cause. Also recorded what did NOT happen in that run — AWS reported FAILED,
  the watcher caught it, the DB recorded the real reason 14m50s inside the
  90-minute mark — because it marks the boundary of what this spec is fixing.
  The container's 34-second life is `ocrload1`, not this.
