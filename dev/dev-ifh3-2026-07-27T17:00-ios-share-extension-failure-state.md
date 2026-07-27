---
hash: ifh3
type: dev
created: 2026-07-27T17:00:00-06:00
title: iOS Share Extension — persist failure state + system notification on permanent failures
from: _bmad-output/planning-artifacts/epic-import-flow-hardening.md
status: in-progress
owner: /devx-loop-2026-07-27T17-03-31-550-87857
branch: feat/dev-ifh3
---

## Goal
Stop the iOS share extension from silently dropping failed imports. `UploadService.markFailed` currently emits telemetry only (UploadService.swift:265–279); instead it must persist failure metadata into the App Group `PendingImport` record so the main-app reconciler and failed-imports UI can see it, and fire a `UNUserNotification` when the failure is permanent (`retryable == false`) so the user learns about the failure even though the share sheet has already dismissed.

## Acceptance criteria
- [ ] `PendingImport` Swift struct gains optional fields: `failed: Bool`, `errorCode: String?`, `errorId: String?`, `retryable: Bool?`, `attemptedAt: Date?`. JSON encoding of the App Group record includes these (snake_case keys) so the Dart side can read them.
- [ ] `UploadService.markFailed` writes the failure metadata back into the persisted `PendingImport` record (via `PendingImports.upsert`) instead of dropping the record. Telemetry emission is preserved.
- [ ] `markFailed` schedules a `UNUserNotification` when `retryable == false`. Notification permission is queried (not requested) — if permission is `notDetermined` or `denied`, fall back to telemetry-only and skip the notification (extensions cannot prompt for permission). Notification body is keyed off `errorCode` via a small Swift `errorCopy(for:)` helper that mirrors the Dart `importFailureCopy` map.
- [ ] For the `submitImport` path, classification of `retryable` reads the new server response field if present; falls back to status code (`4xx` → false except 408/429/5xx → true) when the field is absent.
- [ ] Existing 409-with-3-retries logic is unchanged.
- [ ] Swift unit test covers: (a) markFailed persists fields into the App Group record, (b) markFailed with retryable=false schedules a notification when permission is granted, (c) markFailed with retryable=true does NOT schedule a notification.

## Technical notes
- Files: `app/ios/PalatefulShare/UploadService.swift` (markFailed at :265–279; PUT-failure URLSession delegate at :299–305), `app/ios/PalatefulShare/PendingImports.swift` (record schema gains failed/error_code/retryable/attempt_count/next_attempt_at). See epic "Frontend changes" section.
- For PUT failures, preserve the failure record but DO NOT attempt to re-PUT from the extension — the file URL doesn't survive App Group; the difference vs. today is the user now sees the failure surface in-app.
- Hard constraint: no in-memory PUT refactor — 80 MB RSS budget guard (UploadService.swift:21–25 + ci_post_clone.sh lint) must stay intact.
- Server `retryable` field on error responses already shipped in ifh-1 (commit 88c04d7); the fallback heuristic covers older servers / bodyless network failures.
- App Group schema change is additive — Swift writes and Dart reads both default missing fields to safe values (no migration).
- Notification title: "Couldn't import to Palateful"; body keyed off `error_code`. Only fires if permission already granted.
- Original BMAD story key: ifh-3-ios-share-extension-persist-failure-state-and-system-notification. Full context: the story's section in the epic file.

## Status log
- 2026-07-27T17:00 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; predecessor stories ifh-1 (88c04d7), ifh-2 (51f76f1) already on main
- 2026-07-27T12:43:19-06:00 — claimed by /devx in session /devx-loop-2026-07-27T17-03-31-550-87857
