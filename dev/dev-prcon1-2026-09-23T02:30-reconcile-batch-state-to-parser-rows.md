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
