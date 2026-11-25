---
hash: cntlist1
type: dev
created: 2026-09-22T22:10:00-06:00
title: reconcile the import count and list predicates so "badge N, tab empty" cannot recur in a new shape
from: dev/dev-impvis1-2026-09-22T22:00-imports-tab-shows-every-in-flight-import.md
status: ready
owner: null
branch: null
---

## Goal

`impvis1` fixes the instance Leo hit. This fixes the class: the badge and
the list are computed by **different queries with different predicates**,
so they can disagree in at least four more ways that nobody has reported
yet. `BUGS.md:224` — *"Import activity shows a (1) but then has 'All
Set'"* — is the same class, reported before and fixed narrowly.

Measured on `main`. COUNT is `imports_actionable` from
`services/api/src/api/v1/user_activity/unread_count.py:47-57`; LIST is
`services/api/src/api/v1/import_job/list_import_jobs.py:67-75` plus
`services/api/src/api/v1/import_job/list_import_items_batch.py:106-112`.

| predicate | COUNT | LIST |
|---|---|---|
| `ImportJob.archived_at` | not filtered | `IS NULL` (jobs, `:75`) |
| `ImportItem.dismissed_at` | `IS NULL` (`:54`) | not filtered (items) |
| `ImportItem.status` | `IN ACTIONABLE_IMPORT_STATUSES` (`:55`) | no filter |
| row cap | none | 100 jobs, app never paginates (`imports_tab.dart:129`) |

Each row is a way to disagree:

1. **Counted, never listed.** An actionable item under an **archived**
   parent job counts, but the job never reaches the client, so the item is
   never fetched. Badge N, tab empty.
2. **Counted, never listed (volume).** More than 100 non-archived jobs and
   the app fetches page 1 only — older jobs' items count and never list.
3. **Listed, never counted.** A dismissed `failed` item is still returned
   by the batch endpoint and still rendered
   (`imports_tab.dart:182`), while contributing 0 to the badge. The
   response model omits `dismissed_at`
   (`list_import_items_batch.py:170-188`), so the client cannot filter it
   either — and `dismiss_import_item.py:3` claims list endpoints hide it.
4. **Neither counted nor listed.** `approved` is a live item status
   (`services/api/src/api/v1/import_job/approve_import_item.py:83`) that is
   absent from `ACTIONABLE_IMPORT_STATUSES`
   (`libraries/utils/utils/models/import_item.py:24-30`) AND from the
   client's render switch (`imports_tab.dart:178-197`). An item parked
   there is invisible in both directions.

Adjacent, same family, found while scoping:

5. `ImportJob.dismissed_at`'s comment (`import_job.py:78-80`) asserts
   "List endpoints filter these out". **No list endpoint filters it.**
6. The stuck-import sweeper only rescues jobs in `processing`
   (`libraries/utils/utils/tasks/import_tasks/sweep_stuck_imports_task.py:51-55`),
   and `started_at` is set in the same statement that flips the status
   (`parse_source_task.py:53-54`). A job whose task never ran stays
   `pending` with `started_at IS NULL`, is invisible to the sweeper
   forever, and its items keep incrementing the badge forever.
7. `sweep_stuck_imports_task.py:95` assigns `job.error_message`, a column
   `ImportJob` does not have. SQLAlchemy accepts the attribute and never
   persists it, so the stall reason is silently lost. Same at
   `retry_import_item.py:130`.

## Acceptance criteria

- [ ] Count and list agree by construction, not by coincidence: one shared
      predicate definition both paths use, so a change to "what counts"
      cannot land without changing "what lists".
- [ ] Each of (1)–(4) above has a test that fails before the fix.
- [ ] `approved` is either actionable-and-rendered or deliberately
      terminal-and-hidden — decided explicitly and written down, not left
      to fall through two separate `default` branches.
- [ ] Either `dismissed_at` is filtered by the list endpoints (matching
      their own docstrings) or the docstrings are corrected and the field
      is exposed so the client can filter. Not both silent.
- [ ] (6) is fixed or filed with a deadline: a job that never started is
      the one that most looks like Leo's "pending import that goes
      nowhere", and today nothing on the server ever notices it.
- [ ] (7) is fixed — a write to a non-existent column that silently
      succeeds is its own hazard, independent of imports.

## Technical notes

- There is **no enum** for either status column: both are `String(20)`
  with the legal values in a code comment and no CHECK constraint
  (`libraries/utils/utils/models/import_job.py:37-38`,
  `import_item.py:90-91`). `matching` is documented and never written;
  `awaiting_parser` is referenced as a job status and never assigned. A
  shared enum is arguably the root fix and is a bigger change than this
  story — decide, don't drift into it.
- `libraries/utils/utils/models/import_item.py:24-30`
  (`ACTIONABLE_IMPORT_STATUSES`) is the closest thing to a shared
  definition today and is used by exactly one query.

## Status log
- 2026-09-22T22:10 — filed from the scoping pass on Leo's report; the four disagreements are measured, (5)–(7) turned up in the same read. Blocked-by: —.
