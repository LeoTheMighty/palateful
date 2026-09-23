---
hash: impprog1
type: debug
created: 2026-09-22T23:00:00-06:00
title: every In Progress row reads "Importing 0 of N" — the list endpoint never sends processed_items
from: dev/dev-impvis1-2026-09-22T22:00-imports-tab-shows-every-in-flight-import.md
status: ready
owner: null
branch: null
---

## Goal

`_JobView.fromJson` reads `j['processed_items']`
(`app/lib/features/activity/imports_tab.dart`), and
`ListImportJobs.JobSummary`
(`services/api/src/api/v1/import_job/list_import_jobs.py`) has no such
field. It is therefore always null → 0, so the Imports tab's progress
label reads **"Importing 0 of N" for every in-progress row, always**, no
matter how far along the import is. The `CompactStagePill` synthesized
from the same numbers (`_synthesizeJobTelemetry`) is wrong in the same
direction.

Pre-existing; not introduced by impvis1. Found while reviewing it: the
existing widget-test fixtures invent `processed_items`, so the tests
render a response shape the API never produces and the defect was
invisible to them. impvis1's own fixtures were corrected to match the
real shape, which is what makes the "0 of N" visible in the test output.

## Acceptance criteria

- [ ] Reproduce first: assert against a fixture built from the ACTUAL
      `JobSummary` field list, not a hand-written map. A test that invents
      fields is how this survived.
- [ ] Either `JobSummary` carries `processed_items` (the `ImportJob` model
      already has the column), or the client stops claiming a count it
      cannot know and shows an indeterminate label.
- [ ] `source_url` has the same shape of problem on the straggler row path
      — check it in the same pass.
- [ ] Audit the other fixtures in
      `app/test/features/activity/imports_tab_test.dart` for invented
      fields while here.

## Technical notes

- The per-job endpoint (`GET /v1/import-jobs/{id}`) may well send it; this
  is specifically the LIST shape the tab uses.
- Low user harm, high confusion: a user watching an import sees a
  progress ring that never moves.

## Status log
- 2026-09-22T23:00 — filed from the impvis1 review; pre-existing, hidden by fixtures that invented the field. Blocked-by: —.
