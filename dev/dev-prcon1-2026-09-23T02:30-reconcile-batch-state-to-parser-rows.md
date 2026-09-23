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

**A parser job can fail in AWS Batch and the database never hears about it.**
The app then believes the import is still in progress — permanently.

This is the week's pattern in the **data layer** rather than the alerting
layer, and it is the part that survives `pcap1`: widening the instance pool
and adding an on-demand fallback make failures rarer, they do not make a
failure visible.

## Measured 2026-09-23 (read-only prod)

**A — a live divergence, created today:**

| Where | State |
|---|---|
| AWS Batch job `parser-batch-84a8e0d3` (`4875e2e1-…`) | **FAILED**, 3 attempts, all `startedAt: null` (spot reclaimed each host) |
| `parser_batches` row (2026-09-22 19:10:33) | **`submitted`** |
| `parser_jobs` row (2026-09-22 19:10:33) | **`submitted`** |

The Batch job reached a terminal state; both rows still say `submitted`.
**Nothing writes the failure back**, so this will recur on every failure.

**B — April strandings, five months old:**

| `parser_jobs` status | `parser_batch_id` | count | window |
|---|---|---|---|
| **`running`** | **NULL** | **14** | 2026-04-09 → 04-11 |
| `submitted` | NULL | 7 | 2026-04-09 → 04-10 |
| `failed` | NULL | 12 | 2026-04-09 → 04-11 |
| `succeeded` | NULL | 11 | 2026-04-10 → 04-11 |

The 14 `running` rows are the ones that matter: **stuck in a non-terminal
state since April, with no batch to join to**, so they are invisible to any
surface that counts by batch. The NULL-batch rows all predate `parser_batches`
(first row 2026-04-15), i.e. they are pre-batch-era.

Last `parser_batches` success: **2026-04-22**. Last `import_jobs` row:
**2026-04-26**.

**Not stuck, do not touch:** `import_jobs` has 2 `awaiting_review` and
`import_items` 4 `awaiting_review` (last 2026-04-26). Those are waiting on a
*person*, which is a legitimate non-terminal state.

## Acceptance criteria

- [ ] A reconciler maps terminal AWS Batch state onto `parser_batches` /
      `parser_jobs`: a FAILED job marks its rows failed, with the reason
      (`Host EC2 … terminated` is different from an app error and should
      survive into `error_message`).
- [ ] **Decide explicitly what happens to the 14 stranded `running` rows, and
      say which in the spec before implementing:** reconcile them against
      Batch (their jobs are long gone from Batch's retention, so this will
      likely fail), or **mark them terminal** with a reason recording that
      they were stranded by a pre-`parser_batches` code path. **Do not leave
      the decision to the implementation.**
- [ ] Rows awaiting a human (`awaiting_review`) are never touched. The test
      is "is the system still going to act on this?", not "is it
      non-terminal?".
- [ ] Idempotent and safe to re-run; it must not resurrect archived rows.
- [ ] **Divergence is surfaced, not just repaired.** A row non-terminal for
      longer than the Batch timeout (1800 s) plus a margin, with no
      corresponding live Batch job, should reach the alert topic — otherwise
      the reconciler becomes another silent detector. Ties to `absal1`.
- [ ] Proven by driving a job to FAILED and watching the rows reach a terminal
      state, not by reading the reconciler.

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
