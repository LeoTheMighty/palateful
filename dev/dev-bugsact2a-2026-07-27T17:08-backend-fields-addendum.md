---
hash: bugsact2a
type: dev
created: 2026-07-27T17:08:00-06:00
title: Backend fields addendum for import-item detail (last_successful_stage, last_retry_at, confidence_score)
from: _bmad-output/planning-artifacts/epic-bugs-activity-hub.md
status: ready
branch: feat/dev-bugsact2a
---

## Goal
Close the backend field gaps found by the bugs-act-2 field audit so the import activity detail view can render every field in its hierarchical order without `MISSING-needs-backend` dispositions. Three schema adds were identified: `last_successful_stage` in the `GetImportItem` response, a `last_retry_at` column on `import_items`, and `confidence_score` on `parsed_recipe` output. Much of this has likely since landed via epic-import-row-rich-detail (irrd-1, irrd-3) — this story verifies each field end-to-end and implements only what is still missing.

## Acceptance criteria
- [ ] `GetImportItem` response includes `last_successful_stage` (verify irrd-1 delivered this; implement if any gap remains, e.g. missing from a list endpoint the detail view consumes).
- [ ] `import_items` has a `last_retry_at` column (migration via the migrator service if not present), populated on retry, and exposed on the import-item response (verify against irrd-1 "backend expose stage and retry fields").
- [ ] `parsed_recipe` output carries `confidence_score` (and its companion `confidence_source`), surfaced at the response root of `GetImportItem` / `list_import_items` / `list_import_jobs` (verify irrd-3 delivered this end-to-end; implement only residual gaps).
- [ ] For each of the three fields: either (a) a test proves it is already served correctly and this spec's Status log records "already landed via irrd-N", or (b) the gap is implemented here with schema, persistence, response exposure, and test coverage.
- [ ] Any new/confirmed fields are nullable/backward-compatible — no breaking change to existing clients.
- [ ] Backend-only scope: no Flutter changes. (The bugs-act-2 field-audit comment block in `app/lib/features/activity/widgets/import_activity_detail.dart` may flip `MISSING-needs-backend` dispositions to `rendered`/available, but rendering work belongs to the UI stories.)
- [ ] API test coverage keeps services/api at the pinned 100% coverage bar.

## Technical notes
- The epic file has no dedicated bugs-act-2a section — the story exists only via bugs-act-2 AC6 ("if the audit reveals a backend field is missing and desirable... a follow-up story is filed as `bugs-act-2a-backend-fields-addendum`") and locked principle 5 ("Missing backend fields → follow-up story, not widened scope"). Goal/ACs above are synthesized from the bugs-act-2 section plus the sprint-status.yaml comment: "Spawned by bugs-act-2 field audit (2026-04-16). Backlog — backend schema adds needed to surface: last_successful_stage in GetImportItem response, last_retry_at column on import_items, confidence_score on parsed_recipe output."
- Likely overlap: sprint-status.yaml's epic-import-row-rich-detail header says the epic "Surfaces backlogged bugs-act-2a fields (last_successful_stage, last_retry_at)" and irrd-3 built confidence_score end-to-end — irrd-1/irrd-2/irrd-3 are all `done`. Start with an audit pass; this story may reduce to verification + closing small residual gaps (that outcome is a valid completion — record it in the Status log).
- Reference files: `services/api/src/api/v1/import_job/get_import_item.py`, `list_import_items.py`, `list_import_jobs.py`; `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`; import-item model/schema under `services/api/src/db/models/` and `services/api/src/schemas/` (bugs-act-2 audited `services/api/src/schemas/import_job.py`, `import_item.py`); migrations via `npx nx run migrator:migrate`.
- Original BMAD story key: bugs-act-2a-backend-fields-addendum.

## Status log
- 2026-07-27T17:08 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration
