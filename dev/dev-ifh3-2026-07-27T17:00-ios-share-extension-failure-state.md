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
- 2026-07-27T18:48:39.865Z — loop iteration 1: Extended the App Group PendingImport schema with a failure block and made UploadService.markFailed persist failure metadata with server-driven retryable classification.
  - Change: PendingImport gained failed/error_code/error_id/retryable/attempted_at fields with snake_case JSON keys, a defaulted memberwise init, a markingFailed(...) copy helper, and a hand-rolled init(from:) so legacy records lacking the failure block still decode instead of failing the whole array
  - Change: UploadService.markFailed now upserts the failure block into the App Group record instead of dropping it, while preserving the existing share_extension_failed telemetry (now also carrying retryable)
  - Change: parseErrorPayload returns a ParsedError struct that reads the server's top-level retryable field with a status-code fallback (408/429/5xx retryable, other 4xx permanent, no-response retryable); PUT failures are classified non-retryable because the file URL cannot survive the App Group
  - Change: Verified via swiftc -typecheck against the iOS simulator SDK plus a throwaway macOS harness asserting legacy-record decode defaults, snake_case encoding, epoch-ms attempted_at, and PendingImports upsert/remove round-trips
  - Learning: There is no Swift test target or CI job for the share extension — RunnerTests.swift is an empty Flutter stub and no workflow runs xcodebuild/swift test. AC 6's unit test cannot rely on existing infrastructure.
  - Learning: The pure-logic extension files (PendingImports, SharedState, Telemetry, UploadService) compile and run fine for macOS with plain swiftc, and UserDefaults(suiteName: 'group.com.palateful.app') works locally — so a runnable Swift test harness for AC 6 is feasible without Xcode/simulator/pods.
  - Learning: The synthesized Codable decoder would have thrown on a missing non-optional `failed` key and taken the entire pending-imports array with it; the additive-schema promise in the spec requires the custom init(from:) that was added.
  - Learning: Swift Date encodes as seconds-since-2001 by default, so attempted_at is stored as epoch millis (matching createdAt) with a computed Date accessor — a deviation from the AC's literal `attemptedAt: Date?` wording that is required for Dart readability.
  - Learning: The server's retryable contract is a top-level boolean on the error body (libraries/utils/utils/api/endpoint.py), alongside error_code — there is no error_id in the server payload, so that field stays nil in practice.
- 2026-07-27T18:56:09.220Z — loop iteration 2: Implemented the permanent-failure UNUserNotification path with a testable notifier seam and an errorCopy(for:) map, then landed a runnable Swift unit-test harness (wired into Xcode Cloud CI) that covers all three ifh-3 test cases plus permission fallbacks.
  - Change: Added app/ios/PalatefulShare/FailureNotifier.swift: a FailureNotifying protocol seam over UNUserNotificationCenter, the collapsed FailureNotificationAuthorization enum (granted/denied/notDetermined, with .provisional and .ephemeral folded into granted and @unknown default treated as not-granted), the SystemFailureNotifier production implementation, the shared notification title, and errorCopy(for:) covering the 11 error codes the Dart importFailureCopy map will ship with a verbatim-code fallback for unknown codes
  - Change: UploadService.markFailed now notifies on permanent failures only: retryable failures return before permission is even queried; non-retryable failures query (never request) permission and post a record-id-keyed notification with deep-link userInfo, or emit a share_extension_failure_notification_skipped telemetry event when permission is denied/notDetermined. The notifier is constructor-injected with a production default
  - Change: Registered FailureNotifier.swift in Runner.xcodeproj (PBXBuildFile + PBXFileReference + PalatefulShare group + Sources phase) and verified the extension target actually builds with it
  - Change: Added app/ios/PalatefulShareTests/UploadServiceFailureTests.swift — a dependency-free @main test binary with a FakeNotifier and a tiny assertion harness covering persistence of the failure block, snake_case/epoch-ms JSON shape, notify-on-permanent, silent-on-retryable, both no-permission fallbacks, legacy-record decode defaults, and errorCopy coverage
  - Change: Added tools/share-extension-tests.sh (compiles the UIKit-free extension sources for the host with swiftc and runs the tests; skips cleanly on non-macOS) and invoked it from app/ios/ci_scripts/ci_post_clone.sh so the extension finally has CI coverage
  - Change: Made SharedState.appGroupId a computed property with a test-only appGroupIdOverride so the harness writes to a throwaway UserDefaults suite instead of the real shared container, and relaxed markFailed from private to internal so tests can drive it without a fake server
  - Learning: The share extension target builds standalone with `xcodebuild -target PalatefulShare -sdk iphonesimulator CODE_SIGNING_ALLOWED=NO` after just `flutter pub get` — no `pod install` needed, since the appex has no Pods dependency. This is a ~1 minute full verification of pbxproj edits that iteration 1 did not have available.
  - Learning: Xcode Cloud's ci_post_clone.sh runs on a macOS host and already hosts the sie-4 memory lint, so it is the natural (and only) CI home for Swift extension tests — no GitHub Actions workflow touches iOS at all.
  - Learning: UserNotifications types (UNUserNotificationCenter, UNMutableNotificationContent, UNAuthorizationStatus.ephemeral) all compile for a plain macOS swiftc target, so the notifier file needs no #if os(iOS) guard; only `UNUserNotificationCenter.current()` would trap at runtime, which the injected fake avoids.
  - Learning: The Dart `importFailureCopy` map the AC says to mirror does not exist yet — it is ifh-5's deliverable. The Swift errorCopy(for:) helper was written against the 11 codes the epic enumerates for that map, so ifh-5 must copy from Swift rather than the reverse.
  - Learning: swiftc rejects top-level code outside main.swift when compiling multiple files, so the test runner uses `@main enum` — worth knowing for any future harness in this style.
