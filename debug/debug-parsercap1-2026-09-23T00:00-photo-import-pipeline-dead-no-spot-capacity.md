---
hash: parsercap1
type: debug
created: 2026-09-23T00:00:00-06:00
title: photo import has not completed since April — the parser's Batch jobs die on "no Spot capacity"
from: dev/dev-impvis1-2026-09-22T22:00-imports-tab-shows-every-in-flight-import.md
status: superseded
owner: null
branch: null
---

## Goal

Leo asked whether importing still works end to end at all. For the photo
path the answer appears to be **no, and not since April**.

Measured by palateful-4f against the production database and AWS Batch
(their measurement, relayed — I have not re-run it myself, and it should
be re-confirmed before anyone acts on the infra side):

- `parser_batches` `9384da8a-6435-4839-8cbf-9aaef97c478b`, status
  `submitted`, created 2026-09-22 19:10:33.79 UTC, **zero `import_jobs`
  beneath it**. This is the batch behind Leo's "1 import in progress".
- AWS Batch job `parser-batch-84a8e0d3` created 19:10:34.13 UTC — the same
  second. It **never started** (`startedAt` null on the job and on all
  three attempts), sat for 187 minutes, and reached FAILED at 22:17:52 UTC.
- Cause on all three attempts: **`instance-terminated-no-capacity`** —
  no Spot capacity matching the request. The compute environment asks for
  `g4dn.xlarge` / `g5.xlarge`, **spot only, with no on-demand fallback**.
- Last `parser_batches` row to reach `succeeded`: **2026-04-22** (9 total).
  Last `import_jobs` row to reach `completed`: **2026-04-26** (43 total).
  None of any status since, until tonight's attempt produced none at all.
- **14 `parser_jobs` have been stuck in `running` since April.**

**Correction, 2026-09-23 — the "broken since April" framing was wrong.**
palateful-4f went back and measured it: **tonight's batch is the first
`parser_batches` row created since 2026-04-22.** There are no batch rows
at all in between. So for those five months the pipeline was not failing
— **nothing was asking it to run**. What is measured is that the first
attempt after the gap died on capacity. Whether it would also have failed
in June is untested and now untestable.

The 14 stuck `parser_jobs` do not contradict that: **their
`parser_batch_id` is NULL** (all 14 `running`, 2026-04-09 → 04-11, plus 7
of 8 `submitted`). They are pre-batch-era single jobs with no batch
parent, so they never reach `/v1/parser/batches` and cannot appear on any
client surface. They are real stale state, invisible to this surface and
to any count.

## Why this matters beyond the pipeline

The Activity tab is empty **because its table is empty** — `import_jobs`
has zero rows for tonight. They were never created, because fan-out is
downstream of the Batch job that never ran. The "1 import in progress"
count is reading `parser_batches` and is **correct**.

So `impvis1` must not render this as "In Progress": the batch is dead, not
waiting. See its status log — the ACs were revised on this evidence.

## Acceptance criteria

- [ ] Re-confirm the measurements above independently before changing
      infrastructure. One session's read of prod is a strong lead, not a
      license to change a compute environment.
- [x] Separate "broken since April" from "not attempted since April" —
      done: zero batch rows between 2026-04-22 and tonight, so the gap is
      absence of attempts, not accumulated failure. The open question is
      narrower than first written: **is the capacity failure permanent or
      was tonight unlucky?** One spot-only GPU pool with no fallback can
      fail either way, and one data point cannot tell them apart. Re-run a
      batch and see.
- [ ] The compute environment gets an on-demand fallback, or the
      allocation strategy changes, or the failure is surfaced — a
      spot-only GPU pool with no fallback fails exactly this way under
      capacity pressure, silently.
- [ ] A ParserBatch whose Batch job dies is reconciled to a terminal
      status. Nothing does this today: `sweep_stuck_imports_task` only
      looks at `ImportJob`, so a `submitted` batch stays `submitted`
      forever and no user-visible surface can ever call it failed. This
      is the root of impvis1's "a batch that never fans out" problem.
- [ ] The 14 `parser_jobs` stuck in `running` since April (plus 7
      `submitted`) are resolved or explained. `parser_batch_id IS NULL` on
      all of them — pre-batch-era rows that no surface can show and no
      count includes. Invisible stale state is its own problem even when
      nothing renders it.

## Technical notes

- Worth recording against the rest of this week's collection: while writing
  impvis1's test for these batches I hardcoded a fixture date, and
  `fixture_date_guard_test` failed on it — the guard exists precisely
  because hardcoded fixture dates rot, and it caught its own author. Nearly
  every other detector examined this week was silent, decorative, or
  unheard; this one fired. That is what the working case looks like.

- A better staleness signal than the client's wall-clock grace window, if
  the server ever exposes it: tonight's batch has `updated_at` **24ms**
  after `created_at` and untouched since. A row whose `updated_at` never
  moved off its creation is stale regardless of what its status says.
  `_serialize_batch` does not currently send `updated_at`.

- Related client-side work: `impvis1` (renders aged-out batches honestly),
  `cntlist1` (count/list predicate reconciliation).
- 4f's earlier read of three empty Batch log groups suggested the parser
  had never run; that was wrong — the log groups had expired. The DB
  settled it. Worth remembering before anyone reasons from absent logs
  again.

## Status log
- 2026-09-23T00:00 — filed from palateful-4f's production join while reviewing impvis1; their measurement, relayed, flagged for independent re-confirmation. Blocked-by: —.
- 2026-09-23 — **superseded**, not abandoned. Same incident as `dev/dev-pcap1`,
  filed independently from two sessions during parallel investigation. Split
  by owner so no AC is dropped when one closes:
  * **capacity** (on-demand fallback, wider pool, reclaim-aware retries) →
    **`dev/dev-pcap1`**, applied 2026-09-23 as `fb2892d0`;
  * **the permanent-vs-unlucky question** → **`dev/dev-pcap1`**, answered only
    by its fallback drill, which records *which* compute environment an
    attempt lands on;
  * **independent re-confirmation before touching infrastructure** (this
    spec's first AC) → carried into **`dev/dev-pcap1`**, owner **palateful-0e**.
    Still owed;
  * **write-back reconciliation** (a Batch job dies, the rows stay
    `submitted`) → **`dev/dev-prcon1`**;
  * **April stale state** — 14 `parser_jobs` `running` + 7 `submitted`, all
    `parser_batch_id IS NULL` → **`dev/dev-prcon1`**, which holds the fuller
    measurement.
