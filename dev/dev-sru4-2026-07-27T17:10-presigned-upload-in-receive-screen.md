---
hash: sru4
type: dev
created: 2026-07-27T17:10:00-06:00
title: Presigned upload path for PDF / audio / video in the receiving screen
from: _bmad-output/planning-artifacts/epic-share-receiving-ux.md
status: done
owner: /devx-loop-2026-07-27T21-15-34-312-36147
branch: feat/dev-sru4
---

## Goal
Wire the pure-upload branches (PDF, audio, video) of the universal receiving screen to the presigned-upload contract: request `upload-url`, PUT the file to S3, then POST `/import` with `{s3_key, etag, source_type, book_id}`, navigating to the Activity Hub on success. Byte-level progress renders on the receiving card throughout, and a dispose-time `HttpClient.abort()` prevents half-uploaded S3 objects when the user closes mid-upload. This is the last remaining story in the epic — sru-1/2/3/5 landed on main in commit 95b8cab.

## Acceptance criteria
- [ ] Sequence: request `upload-url` → PUT file to S3 (capture `ETag` header) → POST `/import` with `{s3_key, etag, source_type, book_id}`. On `201` navigate to Activity Hub; on `409 object_not_ready` retry `/import` up to 3× with 500 ms backoff before surfacing error.
- [ ] Byte-level progress rendered on the receiving screen during PUT. Progress card covers the full "copy-to-sandbox → uploading → sending" sequence — never black-screen.
- [ ] Screen holds an `HttpClient` that `abort()`s when the screen disposes (user tapped Close or Android back); this prevents half-uploaded S3 objects (lifecycle rule in Epic 1 sweeps them at 24 h as a backstop).
- [ ] Integration test mocks upload-url, S3 PUT, `/import` and asserts the `{s3_key, etag}` body shape + 409-retry path.

## Technical notes
- Upload contract is a locked cross-epic decision (epic file § "Locked cross-epic decisions" item 1) owned by Epic 1 (`epic-share-backend-foundations`): `upload-url` → PUT → `/import {s3_key, etag}` with 3× 500 ms backoff on 409 `object_not_ready`.
- Flows C/D/E in the epic's "End-user flow" section specify the per-type copy and `source_type` values (`pdf`, `audio`, `video_file`); routing logic lives in the epic's "New screen: /recipes/add/receive" section.
- Dedup key `sha256(path+mtime+size)` is used as the s3_key suffix so a double-fire second PUT to the same key is a no-op (epic § "Added by this workshop").
- Progress staging ("Receiving…" → "Uploading… N%" → "Sending to Palateful…" → check flash) and >5 s large-file behavior per epic § "Progress and confirmation UI"; error states (network, 401, 413, 409, generic) keyed on machine-readable `error_code` per epic § "Error states".
- Implementation surface: `app/lib/features/recipes/add_recipe/receive_import_screen.dart`, `state/receive_import_notifier.dart`, `widgets/receive_progress_card.dart` (all landed by sru-1/2); `VideoFileImportScreen` (sru-5) submits through this same upload sequence.
- Risks already mitigated in ACs: 201-before-S3-flush race (HeadObject in Epic 1 + 409 retry handshake here), close-mid-upload leaks (abort on dispose + 24 h lifecycle backstop). See epic § "Risks surfaced in party-mode".
- Original BMAD story key: sru-4-presigned-upload-for-pdf-audio-video-in-receive-screen.

## Status log
- 2026-07-27T17:10 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration
- 2026-07-27T18:10:00-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
- 2026-07-28T00:25:19.329Z — loop iteration 1: Implemented the full presigned-upload sequence (upload-url → S3 PUT → /import with 409 retry) for the PDF/audio/video branches of the receiving screen and the standalone video import screen, with byte-level progress and abort-on-dispose.
  - Change: New PresignedUploader abstraction (app/lib/core/services/presigned_uploader.dart) with a Dio-backed impl that streams a file from disk to a presigned S3 URL, reports byte-level send progress, normalizes the quoted ETag header, and supports abort() via CancelToken on its own Dio instance (the app client's Authorization header would break the SigV4 signature)
  - Change: New ReceiveUploadCoordinator (state/receive_upload_coordinator.dart) implementing the epic-locked contract: upload-url → PUT → POST /import {s3_key, etag, source_type}, with 3x/500ms retry scoped to 409 OBJECT_NOT_READY and terminal handling for DUPLICATE_IMPORT, plus branch→source_type and extension→mime resolution
  - Change: Added ApiClient.getImportUploadUrl(filename, mimeType, sizeBytes) hitting POST /v1/imports/upload-url
  - Change: Replaced ReceiveImportScreen's no-op _uploadAndImport stub with the real coordinator run; screen now owns a PresignedUploader it abort()s in dispose(), threads the sha256 dedup key as idempotency_key, and renders progress throughout
  - Change: Replaced VideoFileImportScreen's 'coming in the next release' UnimplementedError with the same coordinator path, adding a byte-level progress widget, per-error-code copy, and dispose-abort
  - Change: Added ReceivePhase.sending + notifier.enterSending() and made ReceiveProgressCard phase-aware so copy stages detecting → 'Uploading… N%' → 'Sending to Palateful…' instead of parking a determinate bar at 100% during the claim
  - Change: Fixed the error card's Retry silently no-oping: it re-entered _dispatch() and was swallowed by sru-1's 2s double-fire dedup guard; Retry now bypasses that guard while preserving the idempotency key
  - Change: 25 new tests: coordinator (body shape, 409 retry-then-succeed, give-up-after-3, duplicate-is-terminal, error classification, abort propagation, mime resolution), progress card staging, and a screen dispose→abort regression test
  - Learning: AC1's '201' is wrong for the deployed backend — utils.api.endpoint.success() defaults to status 200 and start_import never overrides it, so gating navigation on 201 would never fire. Implemented as any-2xx.
  - Learning: AC3's literal 'HttpClient.abort()' doesn't fit this codebase: the app is Dio-only and package:http's client has no per-request abort. Implemented the same guarantee via a PresignedUploader interface over a Dio CancelToken, which also gave the injection seam the AC4 integration test needs.
  - Learning: Both 409 cases (OBJECT_NOT_READY 292, DUPLICATE_IMPORT 294) share an HTTP status, so retry logic MUST key on the numeric error_code in the body, not the status. Backend lifts `retryable` to the top level too, but error_code is the finer signal.
  - Learning: sru-1's test file documents that File.stat in initState stalls flutter_tester's fake-async zone — so the upload sequence can't be driven end-to-end through the widget. Extracting the sequence into a coordinator is what makes AC4 testable at all; future iterations shouldn't retry the widget-level route.
  - Learning: POST /imports/upload-url 400s on any mime outside its _MIME_EXT table, and Android share intents commonly send application/octet-stream — resolving mime from the extension before the call is required, not defensive.
  - Learning: The Dart PendingImportsReconciler sends a `filename` key while StartImport.Params expects `file_name` — that field is silently dropped on the iOS reconcile path. Pre-existing and out of scope here (the new code sends file_name), but worth a follow-up.
- 2026-07-28T00:33:14.688Z — phase 4: loop-shipped — per-iteration verification (see iteration lines above) stood in for the interactive self-review pass; line appended by the loop merge tail per dvx103
- 2026-07-28T00:33:14.688Z — merged via devx loop — PR https://github.com/LeoTheMighty/palateful/pull/11
