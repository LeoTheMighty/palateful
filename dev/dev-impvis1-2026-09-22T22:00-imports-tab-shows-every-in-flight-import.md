---
hash: impvis1
type: dev
created: 2026-09-22T22:00:00-06:00
title: the Imports tab shows every in-flight import, whatever table it lives in
from: dev/dev-authrep1-2026-09-22T19:00-auth-path-error-reporting.md
status: in-progress
owner: /devx-c2872fff
branch: feat/dev-impvis1
---

## Goal

Leo, verbatim in substance: *"Currently the pending import is in a weird
spot. I go to Activity in the imports, nothing, then go to the 'Add Recipe'
button in the recipe books part, and then I see '1 pending import', I click
it, it goes to the empty notification tab again."*

**The count and the list read different tables.** The strip on the Add
Recipe sheet reads **ParserBatch** rows; the Imports tab reads **ImportJob
+ ImportItem**. A photo import lives in the first before it fans out into
the second, so between those two moments the strip counts it and the tab
cannot render it.

Measured on `main`:

- Strip: `'1 import in progress'` / `'$n imports in progress'` —
  `app/lib/features/recipes/add_recipe/widgets/live_import_strip.dart:32-34`.
  (The literal "pending import" appears nowhere in `app/lib`; this is the
  string Leo saw.) Count source
  `app/lib/features/recipes/add_recipe/state/import_batches_provider.dart:105-109`
  → `GET /v1/parser/batches`. Active =
  `{pending, submitted, running, partial}`
  (`app/lib/features/recipes/add_recipe/models/import_batch.dart:48-53`).
- Tab: `app/lib/features/activity/imports_tab.dart:128-147` → `GET
  /v1/import-jobs` + `GET /v1/import-items`. It never queries
  `/v1/parser/batches`.
- The server deliberately keeps a **pre-fan-out** batch visible with no
  ImportJobs attached:
  `services/api/src/api/v1/parser/list_parser_batches.py:56-62`.
- Second, independent hole in the same tab: item statuses `pending`,
  `extracting` and `matching` fall through `default: break`
  (`app/lib/features/activity/imports_tab.dart:196-197`). They are visible
  only via the parent job's Blue row
  (`_inProgressJobStatuses`, `:44-50`), so an item still pending under a
  job that has moved on renders nowhere.

## Acceptance criteria

- [x] An import that exists **only** as a parser batch (pre-fan-out)
      appears in the Imports tab's In Progress section. Either the tab
      reads `/v1/parser/batches` alongside jobs/items, or one server
      endpoint unions them — decide in the spike below, don't assume.
- [x] Counted and listed come from **one** source of truth. After the fix,
      no state exists where the strip's count is non-zero and the Imports
      tab renders nothing. Assert this directly in a test, not by
      inspection.
- [x] An item in `pending` / `extracting` / `matching` whose parent job is
      NOT in `_inProgressJobStatuses` renders somewhere. Today it renders
      nowhere.
- [x] **`partial` cannot park a count as in-progress forever.** It is in
      `isActive` and absent from `isTerminal`
      (`app/lib/features/recipes/add_recipe/models/import_batch.dart:48-58`),
      so a batch that stops there counts as in-progress indefinitely — a
      badge that can never reach zero. Either it becomes terminal, or it
      ages out, or it renders as something the user can act on. A count
      that cannot reach zero is a permanent false badge and will be
      rediscovered as a new bug otherwise.
- [x] Tests close the gap that let this ship: **no existing test covers a
      pending import at all.** `app/test/features/activity/imports_tab_test.dart`
      uses job status `processing` only; nothing covers job `pending` /
      `extracting` / `matching` / `awaiting_parser`, nothing covers item
      `pending` / `extracting` / `matching`, and nothing in `app/test`
      touches `LiveImportStrip` or the parser-batch source
      (`grep LiveImportStrip app/test` → no hits). At minimum: a pending
      job renders, a pending item renders, and a pre-fan-out batch renders.

## Technical notes

- Spike first, one hour: does the union belong on the client (tab fetches
  both) or the server (one endpoint)? The server already owns the join via
  `ImportJob.parser_batch_id`
  (`services/api/src/api/v1/parser/list_parser_batches.py:44-53`), which
  argues for the server; the client already polls both surfaces on
  different timers (5s active / 30s idle for batches,
  `import_batches_provider.dart:10-11`; 30s shared tick for the tab,
  `imports_tab.dart:94-96`), which argues for care about double-polling.
- Bucketing is by `item.status` for a reason — see the comment at
  `imports_tab.dart:51-55` and bug diagnosis 2026-04-20, where keying off
  the parent job's status made most items disappear. Do not undo that;
  the fix is an additional in-flight source, not a re-parenting.
- Sibling defects filed separately, deliberately not in scope here:
  `acttab1` (an explicit `?tab=` must win) and `cntlist1` (server-side
  count/list predicate reconciliation).
- Leo also asked for a check that importing still works end to end. That
  is attached to `ifh6`'s regression sweep rather than duplicated here.

## Status log
- 2026-09-22T22:00 — filed from the scoping pass on Leo's report; count/list table mismatch measured on main, split into impvis1 / acttab1 / cntlist1 with leonidbelyi-41, Leo chose to file all three and start here. Blocked-by: —.
- 2026-09-22T22:20 — claimed for /devx (hand-claim: main is a serialized deploy lane, so the claim commit lands on feat/dev-impvis1, not main — coordinator leonidbelyi-41). Base: 2afd622e.
- 2026-09-22T22:50 — phase 2: spec ACs direct (v2 native); 5 ACs; workstream=none; red-artifacts=none.
- 2026-09-22T23:10 — phase 3: client-side union (spike outcome — the batches endpoint already returns each batch with its ImportJobs, so no new endpoint and no API deploy). Tab reads active batches, synthesises In Progress rows for pre-fan-out ones, dedups against listed jobs; stragglers collapse per job; `isInFlightAt` adds a 2h grace so a batch that never fans out stops counting.
- 2026-09-22T23:30 — phase 4: single-agent adversarial review (read-only, diff 357 lines); 7 findings (2 HIGH, 1 MED-HIGH, 2 MED, 2 LOW); ALL fixed in-place. Load-bearing fix: the straggler branch fired on `awaiting_review`, which `create_recipe_task.py:465-483` sets while a job is STILL RUNNING, so a 50-URL bulk import would have rendered 48 separate rows — it now collapses to one row per job and skips cancelled imports. Second: synthetic `batch:`/`item:` ids were being pushed at a UUID-typed route (500 + an error_logs row per tap, on the row the user is most likely to tap); batch rows are now non-openable and straggler rows carry the real job id. Re-review of the changed hunks clean.
- 2026-09-22T23:35 — RED honesty: of the 5 original tests, 2 fail without the fix (pre-fan-out batch, pending item under a finished job); the other 3 are guards that passed before. The 4 added in review (grace expiry, straggler collapse, cancelled leftovers, fixture-shape correction) all fail without their fixes.
- 2026-09-22T23:40 — phase 5: flutter test 1639 passed, flutter analyze 0 errors, no-silent-catch-check OK. Filed debug/debug-impprog1 (blue rows always read "Importing 0 of N" — the list endpoint never sends `processed_items`, and the old fixtures invented it).
- 2026-09-23T00:20 — **AC revision on new evidence.** palateful-4f joined the batch behind Leo's report to a specific AWS Batch job: `parser_batches` 9384da8a (status `submitted`, 0 import_jobs) → Batch job `parser-batch-84a8e0d3`, created the same second, never started, three attempts dead on `instance-terminated-no-capacity`, terminal FAILED 22:17Z. The state this story renders is DEAD, not in flight. The Activity tab was empty because `import_jobs` has zero rows for tonight — they were never created — so the emptiness was never a rendering bug, and "1 import in progress" was reading the batch row correctly. Changed accordingly: a batch past the grace window with no ImportJobs now renders in **Failed** as "Import failed — the parser never started" instead of being hidden. Hiding it would have left Leo with silence; rendering it In Progress would have been a spinner that never stops. Copy says what is known (it never started), not the cause — the client cannot distinguish capacity from crash, and nothing server-side marks the batch failed at all. Filed `debug/debug-parsercap1` for the pipeline itself (nothing has completed since April; 14 parser_jobs stuck `running`), flagged for independent re-confirmation since the measurement is another session's.
- 2026-09-23T00:30 — phase 5 (re-run): flutter test 1640 passed, flutter analyze 0 errors. 12 impvis1 tests now, incl. the stalled-batch row and its non-interactivity.
- 2026-09-23T00:50 — pile risk checked and closed [M, palateful-4f]: only 3 batches in the whole table have zero ImportJobs — tonight's (`submitted`, active) and two from April (`failed`, terminal). So the fixed tab shows Leo ONE "never started" row, not five months of them; no capping or grouping needed. The two April rows do reach the client but the tab asks for active batches only, so they render nowhere; pinned by a test, because applying tonight's copy to them would be inventing a cause for a five-month-old failure nobody diagnosed. The 14 stuck `parser_jobs` cannot render at all — `parser_batch_id IS NULL` on every one, so they never reach `/v1/parser/batches`.
