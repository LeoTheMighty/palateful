---
hash: ifh5
type: dev
created: 2026-07-27T17:02:00-06:00
title: Frontend — FailedImportsBanner + FailedImportsSheet wired into Import Activity Hub
from: _bmad-output/planning-artifacts/epic-import-flow-hardening.md
status: ready
blocked-by: [ifh3, ifh4]
branch: feat/dev-ifh5
---

## Goal
Give failed imports a user-visible, actionable surface. A new `FailedImportsService` consolidates server-side failed `import_items` with local App Group records that never made it past reconciliation; a persistent `FailedImportsBanner` in the Import Activity Hub shows "N imports couldn't be processed", and tapping it opens a sheet with per-row friendly error copy plus Dismiss / Retry actions.

## Acceptance criteria
- [ ] New `FailedImportsService` exposes a stream of failed import records sourced from (a) the App Group via `PendingImports.list().where(failed)` and (b) server-side `import_items` in `failed`/`unrecoverable` state. De-dup by `idempotency_key` if both sides have the same record (server wins).
- [ ] `FailedImportsBanner` widget shows count + "tap to review" affordance; mounts at the top of the Import Activity Hub when the count is > 0; hides when count is 0.
- [ ] Tap opens `FailedImportsSheet` listing each failed record with: source-type icon, user-visible filename/URL, friendly error message (from `importFailureCopy`), per-row Dismiss + Retry buttons. Retry calls reconciler with attempt_count reset to 0; Dismiss removes the record from the App Group / archives the server-side import item.
- [ ] Reactivity: emits / subscribes via the existing MutationBus per `app/lib/core/state/README.md`; banner state updates in real time as failures clear or new ones arrive.
- [ ] New `import_failure_copy.dart` map ships at least: `network`, `unknown`, `jwt_expired`, `file_too_large`, `unsupported_mime`, `rate_limited`, `s3_put_failed`, `object_not_ready`, `cross_user_key`, `recipe_book_access_denied`, `recipe_book_not_found`. Default fallback uses `error_code` verbatim.
- [ ] Widget tests cover: (a) banner hidden when no failures, (b) banner shown with correct count, (c) sheet renders multiple failure rows, (d) Retry resets attempt_count and triggers reconciler, (e) Dismiss removes record from list.

## Technical notes
- New files: `app/lib/core/services/failed_imports_service.dart`, `app/lib/core/state/import_failure_copy.dart`, `app/lib/features/imports/widgets/failed_imports_banner.dart`, `app/lib/features/imports/widgets/failed_imports_sheet.dart`, `app/test/features/imports/failed_imports_banner_test.dart`. See epic "File structure" section.
- `importFailureCopy` sits alongside `mutationFailureCopy` (convention in `app/lib/core/state/README.md`) — one error_code → user-message map spanning imports and mutations; use `pumpWithMutation` test helper for reactivity tests.
- Consumes `failed: true` App Group records written by ifh-3 (Swift extension) and ifh-4 (Dart reconciler) — hence blocked-by. Retry action depends on ifh-4's reconciler exposing attempt_count reset.
- Placement: banner mounts above the per-import-item UI shipped by `epic-import-row-rich-detail` / `epic-import-activity-nav` — no coupling beyond placement (soft dependency per epic).
- Telemetry: log banner impression + per-row tap-Retry / tap-Dismiss for product feedback (epic "Frontend changes" section).
- Original BMAD story key: ifh-5-frontend-failed-imports-banner-and-sheet-in-activity-hub. Full context: the story's section in the epic file.

## Status log
- 2026-07-27T17:00 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; predecessor stories ifh-1 (88c04d7), ifh-2 (51f76f1) already on main
