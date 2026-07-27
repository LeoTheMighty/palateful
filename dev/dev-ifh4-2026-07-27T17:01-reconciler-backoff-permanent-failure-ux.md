---
hash: ifh4
type: dev
created: 2026-07-27T17:01:00-06:00
title: Dart Reconciler — exponential backoff + permanent-failure UX
from: _bmad-output/planning-artifacts/epic-import-flow-hardening.md
status: in-progress
owner: /devx-loop-2026-07-27T17-03-31-550-87857
branch: feat/dev-ifh4
---

## Goal
Give `PendingImportsReconciler` a real retry policy instead of telemetry-and-drop. Transient failures (5xx/429/network) get bounded exponential backoff (1s, 4s, 16s, 1m, 5m, 30m; max 6 attempts) with silent re-POSTs; permanent failures (server `retryable: false` or 4xx fallback) mark the record `failed: true` immediately with no re-POST. Exhausted retries are treated as permanent so shares are never silently dropped.

## Acceptance criteria
- [ ] `PendingImportsReconciler.reconcile()` honors a `next_attempt_at` timestamp on each record — records whose backoff hasn't elapsed are skipped (left in App Group untouched).
- [ ] On a successful POST, record is dropped (existing behavior).
- [ ] On a transient error (network exception OR server returned `retryable: true` OR fallback heuristic 5xx/429/408): increment `attempt_count`, compute next `next_attempt_at` using the backoff schedule (1s, 4s, 16s, 1m, 5m, 30m), persist updated record. After 6 attempts, mark `failed: true` and stop retrying.
- [ ] On a permanent error (server returned `retryable: false` OR fallback heuristic 4xx other than 408/409/429): mark `failed: true`, set `error_code` from response body, persist record. Do NOT re-POST.
- [ ] Reading the server response — extract `error_code` and `retryable` from the JSON body via the existing `ApiClient` error path (story decides whether `ApiClient.postImportForBook` already exposes the response body on error or whether we need to surface it).
- [ ] New Dart unit tests in `pending_imports_reconciler_backoff_test.dart` cover: (a) transient error increments attempt_count and sets next_attempt_at, (b) permanent error marks failed without retrying, (c) backoff schedule matches the spec, (d) record marked failed after 6 attempts, (e) record skipped while next_attempt_at is in the future.
- [ ] Existing reconciler tests continue to pass.

## Technical notes
- Files: `app/lib/core/services/pending_imports_reconciler.dart` (current failure path at :38–90 reports to ErrorReporter only), new test `app/test/features/imports/pending_imports_reconciler_backoff_test.dart`. See epic "Frontend changes" section.
- Read new `retryable` / `attempt_count` / `next_attempt_at` fields from App Group records; default `retryable=true` for legacy records written by the pre-epic extension (no migration — additive JSON fields).
- Permanent-vs-transient is a server contract: prefer the `retryable` field shipped by ifh-1 (commit 88c04d7); fall back to the status-code heuristic only when the field is missing (older server, bodyless network failure).
- Bounded retries by design: 6 attempts ≈ 36 minutes wall-clock, then failed — no infinite background loops.
- The `failed: true` records this story produces are consumed by ifh-5's `FailedImportsService`/banner; this story only persists state, no UI.
- Original BMAD story key: ifh-4-dart-reconciler-exponential-backoff-and-permanent-failure-ux. Full context: the story's section in the epic file.

## Status log
- 2026-07-27T17:00 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; predecessor stories ifh-1 (88c04d7), ifh-2 (51f76f1) already on main
- 2026-07-27T13:01:58-06:00 — claimed by /devx in session /devx-loop-2026-07-27T17-03-31-550-87857
- 2026-07-27T19:10:42.080Z — loop iteration 1: Implemented the full ifh-4 exponential-backoff + permanent-failure retry policy in PendingImportsReconciler with 28 new unit tests, all passing.
  - Change: PendingImportsReconciler now classifies failures via the server's `retryable` field (read off DioException.response, with a JSON-string body fallback) and falls back to a 5xx/429/408/409-transient vs other-4xx-permanent status heuristic
  - Change: Transient failures increment `attempt_count` and push `next_attempt_at` along the published backoff curve (1s/4s/16s/1m/5m/30m), flipping to `failed: true` with `error_code: retries_exhausted` at 6 attempts; permanent failures set `failed: true` + server `error_code` with no re-POST
  - Change: reconcile() skips both `failed: true` records and records inside an open backoff window, leaving them byte-identical in the App Group; legacy records with no retry fields or a garbled timestamp stay eligible
  - Change: Added an injectable clock to both constructors and exposed `backoffSchedule`/`maxAttempts` as public constants so the schedule is directly assertable
  - Change: New app/test/features/imports/pending_imports_reconciler_backoff_test.dart with 28 tests covering all five AC scenarios plus edge cases
  - Change: Logged 3 pre-existing unrelated imports_tab_test.dart failures in DEBUG.md
  - Learning: ifh-3 has not landed: app/ios/PalatefulShare/PendingImports.swift still has no failed/retryable/attempt_count/next_attempt_at fields, so Dart currently defines the record contract unilaterally. Worse, PendingImport is a strict Codable with fixed CodingKeys — when the extension re-encodes the list it will DROP any Dart-written retry fields. ifh-3 must add matching fields or the backoff state gets wiped on the next share.
  - Learning: The epic's '6 attempts ~= 36 minutes' arithmetic only holds if all six delays elapse (1+4+16+60+300+1800 = 36.4 min), which needs 7 POSTs. Implemented the literal AC instead — failed at attempt_count == 6 — so the last delay actually applied is 5m and the 30m tail is documented as the schedule's kept-but-unreached entry.
  - Learning: error_code on the wire is an INT (libraries/utils/utils/api/endpoint.py failure() defaults to ErrorCode.INTERNAL_ERROR.value), not the snake_case string ifh-5's importFailureCopy map is specced against (`file_too_large`, `unsupported_mime`, ...). ifh-5 will need to key on ints or map them.
  - Learning: app/ has no NX project.json — Flutter tests run via bare `flutter test`, not `npx nx`.
  - Learning: Pre-existing red on this branch: 3 failures in test/features/activity/imports_tab_test.dart (Auto-Imported section renders 0 widgets). Inherited from main, unrelated to the reconciler, but will keep CI red on the merge tail.
