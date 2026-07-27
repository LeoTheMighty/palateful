---
hash: ifh4
type: dev
created: 2026-07-27T17:01:00-06:00
title: Dart Reconciler — exponential backoff + permanent-failure UX
from: _bmad-output/planning-artifacts/epic-import-flow-hardening.md
status: ready
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
