---
hash: parsercap1
type: debug
created: 2026-09-23T00:00:00-06:00
title: photo import has not completed since April — the parser's Batch jobs die on "no Spot capacity"
from: dev/dev-impvis1-2026-09-22T22:00-imports-tab-shows-every-in-flight-import.md
status: ready
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

Inference, not measurement: the pipeline has been broken since roughly
late April. What is measured is that nothing has succeeded since then and
that tonight failed on capacity; nobody has yet separated "broken" from
"not attempted" for the months in between. The 14 stuck-`running` rows
argue for attempts that hung rather than an absence of attempts.

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
- [ ] Separate "broken since April" from "not attempted since April":
      count `parser_batches` rows created per month since 2026-04, and
      how many reached a terminal status.
- [ ] The compute environment gets an on-demand fallback, or the
      allocation strategy changes, or the failure is surfaced — a
      spot-only GPU pool with no fallback fails exactly this way under
      capacity pressure, silently.
- [ ] A ParserBatch whose Batch job dies is reconciled to a terminal
      status. Nothing does this today: `sweep_stuck_imports_task` only
      looks at `ImportJob`, so a `submitted` batch stays `submitted`
      forever and no user-visible surface can ever call it failed. This
      is the root of impvis1's "a batch that never fans out" problem.
- [ ] The 14 `parser_jobs` stuck in `running` since April are resolved or
      explained.

## Technical notes

- Related client-side work: `impvis1` (renders aged-out batches honestly),
  `cntlist1` (count/list predicate reconciliation).
- 4f's earlier read of three empty Batch log groups suggested the parser
  had never run; that was wrong — the log groups had expired. The DB
  settled it. Worth remembering before anyone reasons from absent logs
  again.

## Status log
- 2026-09-23T00:00 — filed from palateful-4f's production join while reviewing impvis1; their measurement, relayed, flagged for independent re-confirmation. Blocked-by: —.
