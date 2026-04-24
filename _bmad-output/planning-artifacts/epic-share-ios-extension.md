<!-- refined via party-mode 2026-04-18 -->
# Epic: iOS Share Extension — "Save to Palateful" from anywhere

## Locked cross-epic decisions (inherited — do not re-litigate)

Owned by Epic 1 (`epic-share-backend-foundations`), binding on every client:
1. **Single upload contract:** presigned PUT → `/import` with `{s3_key, etag}`. No base64 path.
2. **Intent persistence via Redis** (1 h TTL) — client doesn't need to know this, but the 409 retry handshake does.
3. **ETag handshake:** client captures PUT response `ETag` and sends it to `/import`; on `409 object_not_ready`, retry 3× / 500 ms backoff before error.
4. **Machine-readable `error_code` on every 4xx:** the sheet maps each code to a distinct copy string (see `sie-3` ACs).
5. **Sandbox-first for payload data** (this epic applies it via App Group storage and security-scoped resources; see `sie-4`).

## Added by this workshop

- **Background upload is the default.** Extension uses `URLSessionConfiguration.background` keyed by a pending-import UUID persisted to the App Group. `completeRequest` is called within 100 ms of Save; the OS finishes the PUT after the extension is killed. This is the reliability story for Flow E (no network) and all file shares — the extension's only promise is a persisted intent; the OS completes the upload; the backend finishes the job; the push notification reports the outcome.
- **Size + destination disclosure pre-Save** for files >10 MB. Required for App Store Review (avoids 4.1 / 5.1.1 rejection on unattended upload flows).
- **JWT near-expiry proactive prompt:** if `auth_jwt_expires_at - now < 300s`, sheet shows "Open Palateful to refresh sign-in" before Save is tappable. Avoids the deferred 401.

## Overview

Palateful's iOS app does not currently appear as a target in the iOS share sheet for anything — URLs, photos, PDFs, or videos. The Xcode project has only three targets: `Runner` (main app), `PalatefulWidgets`, and `PalatefulNotificationService`. `receive_sharing_intent ^1.8.0` is installed on the Flutter side, but it has no native iOS bridge without a Share Extension target. This is the literal gap the user hit ("I clicked on a URL and clicked share and I want to have Palateful show up as an option").

This epic adds a new `PalatefulShare` Xcode target: a minimal SwiftUI confirmation sheet, presigned-S3 upload of the shared file directly from inside the extension, and a call to the backend import endpoint. The main app does not need to be running. A push notification — wired from the existing `IMPORT_COMPLETE` / `IMPORT_NEEDS_REVIEW` path — alerts the user when the recipe is ready.

## Goal

User taps Share on any iOS app (Safari on a recipe URL, Photos on a photo of a cookbook page, Files on a PDF, Photos on a video clip) → Palateful appears in the share sheet → user taps it → sees a one-second sheet with an icon, the detected content, an optional recipe-book picker, and Save → extension closes → push notification lands when the backend has a reviewable recipe.

## End-user flow

### Flow A — Authenticated user, URL share

1. User reads a recipe on Safari and taps the Share button.
2. The iOS share sheet opens. "Palateful" appears in the top-row app list (icon reuses the main-app icon).
3. User taps Palateful. The Share Extension presents a ~300 px tall confirmation sheet.
4. Sheet contents: Palateful icon + title "Save to Palateful"; one-line summary "Recipe URL · allrecipes.com"; optional "Save to" book picker (defaults to the user's most recently used personal book, populated from App Group cache); "Cancel" and "Save" buttons.
5. User taps Save. Button shows a spinner for ≤1 second. Extension calls `POST /v1/recipe-books/{book_id}/import` with `source_type="url"` and the URL — no upload needed, URLs pass through. Endpoint returns 201 with an ImportJob id. Extension stores "last saved" feedback and dismisses.
6. The sheet shows a one-second "Saved ✓" confirmation and closes.
7. Backend processes asynchronously. User gets a push notification (via existing `IMPORT_NEEDS_REVIEW` / `IMPORT_COMPLETE` path) when the recipe is ready.
8. Tapping the push deep-links into the Activity Hub with the new row highlighted.

### Flow B — Authenticated user, large file share

1. User finds a 60 MB recipe PDF in Files.app and taps Share.
2. Palateful appears. User taps it.
3. Sheet loads, shows "Recipe PDF · cookbook.pdf" and a size chip "58 MB".
4. User taps Save. The extension:
    - Calls `POST /v1/imports/upload-url` with `{filename: "cookbook.pdf", mime_type: "application/pdf", size_bytes: 60817408}`.
    - Receives `{upload_url, s3_key}`.
    - Streams the file bytes via `URLSession` `uploadTask(with:fromFile:)` to S3 — never buffers the full file in memory (stays well under the 120 MB extension memory ceiling).
    - Calls `POST /v1/recipe-books/{book_id}/import` with `source_type="pdf"`, `s3_key`, and the selected book id.
5. Progress UI: sheet shows a progress ring + "Uploading 12 / 58 MB" during the PUT; "Saving…" for the import POST.
6. On success: "Saved ✓" for one second, extension closes. Push notification fires when processing completes, as with Flow A.

### Flow C — File over 100 MB

1. User shares a 150 MB video. Palateful appears.
2. User taps Palateful. The sheet loads, detects `size_bytes > 100 * 1024 * 1024`, and instead of the Save button shows a message: "This file is too large to share (150 MB, max 100 MB). Open Palateful and import it from Files."
3. A "Close" button dismisses the extension. No network calls were made. No half-state is persisted anywhere.

### Flow D — Unauthenticated / token expired

1. User shares. Palateful appears.
2. Sheet loads, reads auth state from the shared App Group cache. No valid JWT found (expired or never signed in).
3. Sheet shows: "Open Palateful and sign in to save shared recipes." Single "Close" button.
4. Extension closes. No attempted upload. User can sign in in the main app and retry.

### Flow E — No network

1. User shares. Palateful appears.
2. Sheet loads. User taps Save.
3. `/v1/imports/upload-url` (or the direct URL import POST) fails with a network error.
4. Sheet shows: "Couldn't connect. Try again in a moment." Retry button (up to 2 retries), then a "Close" button. No queuing, no deferred handoff — v1 requires network at share time.

### Flow F — Cold-start (main app not running)

1. User shares while Palateful is not running. Extension runs in its own process (iOS extensions are process-isolated by design).
2. Flow is identical to Flow A / B. The extension upload + import call happens entirely in the extension process; no IPC to a main-app-that-isn't-there.
3. Push notification on completion is the only handoff — the main app doesn't get involved until the user taps that notification.

## Frontend changes

### New Xcode target: `PalatefulShare`

- Location: `app/ios/PalatefulShare/`
- Language: Swift (+ SwiftUI for UI)
- Bundle ID: `com.palateful.app.shareextension`
- Deployment target: same minimum iOS version as the main app (verify from `Runner.xcodeproj`; likely iOS 14 or 15).
- Info.plist:
    - `NSExtensionPointIdentifier`: `com.apple.share-services`
    - `NSExtensionPrincipalClass`: `$(PRODUCT_MODULE_NAME).ShareViewController`
    - `NSExtensionActivationRule` dict with:
        - `NSExtensionActivationSupportsWebURLWithMaxCount`: 1
        - `NSExtensionActivationSupportsImageWithMaxCount`: 1
        - `NSExtensionActivationSupportsFileWithMaxCount`: 1 (catches PDFs, audio, video generic files)
        - `NSExtensionActivationSupportsMovieWithMaxCount`: 1
        - `NSExtensionActivationSupportsText`: true
- Entitlements:
    - `com.apple.security.application-groups`: `[group.com.palateful.app]` (reuse the existing App Group from PalatefulWidgets)

### Files (new, Swift)

- `app/ios/PalatefulShare/Info.plist`
- `app/ios/PalatefulShare/PalatefulShare.entitlements`
- `app/ios/PalatefulShare/ShareViewController.swift` — `UIViewController` host for the SwiftUI sheet; bridges `NSExtensionContext` and the extracted `NSItemProvider` attachments into the view model.
- `app/ios/PalatefulShare/ShareView.swift` — SwiftUI view: icon, title, content summary, book picker, Save / Cancel.
- `app/ios/PalatefulShare/ShareViewModel.swift` — `@MainActor` view model: auth-state read from App Group, content-type detection, presigned upload, import POST, error handling.
- `app/ios/PalatefulShare/SharedState.swift` — App Group read helpers: reads JWT, user id, recipe book list cache, last-used-book from `UserDefaults(suiteName: "group.com.palateful.app")`.
- `app/ios/PalatefulShare/UploadService.swift` — thin URLSession wrapper for presigned PUT + JSON POST with auth header.

### App Group cache population (main app side)

- `PushNotificationService` and/or a new small service in `app/lib/core/services/` writes the following to the shared App Group on auth state change and on a 15-minute cadence:
    - `auth_jwt`, `auth_jwt_expires_at`, `user_id`, `api_base_url`
    - `recipe_books` — `[{id, name, is_personal, is_archived}]`
    - `last_used_book_id`
- iOS native side reads these in `SharedState.swift`. Never writes — only the main app writes.

### Main-app Flutter UI

- No changes to existing add-recipe flows. The extension path is orthogonal.
- The existing `/recipes/add/share?url=...` route continues to work as a secondary handoff if the user opens the main app directly with a shared URL (covered by Epic 3 on Android; iOS relies on the extension).

## Backend changes

None directly owned by this epic. Depends on Epic 1 (`epic-share-backend-foundations`) for:

- `POST /v1/imports/upload-url`
- `s3_key` support on `POST /v1/recipe-books/{id}/import`
- Correct upstream social URL routing

The push notification on completion is the existing `IMPORT_NEEDS_REVIEW` / `IMPORT_COMPLETE` flow — no changes.

## Infrastructure changes

- **App Store Connect:** new App ID `com.palateful.app.shareextension`; provisioning profile (development + distribution); App Group capability enabled and added to both the new App ID and the existing main App ID.
- **Xcode Cloud:** `app/ios/ci_scripts/ci_post_clone.sh` and the build scheme in `Runner.xcworkspace` need the new target added. `pod install` runs automatically; no new CocoaPods dependencies are planned (URLSession + SwiftUI only).
- **Fastlane:** currently not used (no `app/ios/fastlane/` directory exists per research). No Fastlane changes in v1.

## Initial design principles

- **Minimal UI, maximum robustness.** The extension UI is two labels, one picker, and two buttons. Every error path has a user-readable message and a Close button. No silent failures.
- **Stream, don't buffer.** Files always upload via `URLSession.uploadTask(with:fromFile:)`. Never `Data(contentsOf:)` a 100 MB video — that would OOM the 120 MB extension process.
- **Trust the App Group, but verify.** Read auth JWT from the App Group cache; attempt the upload; if the 401 comes back, surface "open Palateful to sign in" — don't try to refresh tokens from inside the extension.
- **One-shot, no retries by default.** If the network call fails, the user retries. We don't queue or persist across extension lifetimes (iOS will kill the process at any time).
- **Shared identity, not shared code.** The extension is pure Swift; it doesn't link any Dart/Flutter code. The only handoff with the main app is the App Group read + the backend API.

## File structure (anticipated)

### iOS native (new)
- `app/ios/PalatefulShare/Info.plist`
- `app/ios/PalatefulShare/PalatefulShare.entitlements`
- `app/ios/PalatefulShare/ShareViewController.swift`
- `app/ios/PalatefulShare/ShareView.swift`
- `app/ios/PalatefulShare/ShareViewModel.swift`
- `app/ios/PalatefulShare/SharedState.swift`
- `app/ios/PalatefulShare/UploadService.swift`

### iOS native (modified)
- `app/ios/Runner.xcodeproj/project.pbxproj` — add the new target, target membership, build phases.
- `app/ios/Runner.xcworkspace/contents.xcworkspacedata` — new target joins the scheme.
- `app/ios/Runner/Runner.entitlements` — confirm `com.apple.security.application-groups` contains `group.com.palateful.app` (already does per research).

### Flutter (modified)
- `app/lib/core/services/shared_state_service.dart` — NEW: writes auth + book cache to the iOS App Group (and Android shared prefs for symmetry).
- `app/lib/features/auth/auth_service.dart` (or equivalent) — MODIFY: trigger a `SharedStateService.sync()` on login / logout / token refresh.
- `app/lib/features/recipe_books/...` — MODIFY: trigger a `SharedStateService.sync()` on book create / rename / archive.

## Stories

### Story 1: `sie-1` — Xcode target skeleton + App Group wiring

**AC:**
- New `PalatefulShare` target in `Runner.xcodeproj` compiles clean in Xcode 16.
- Info.plist declares URL / image / file / movie / text activation, max count 1 per type.
- Entitlements include `group.com.palateful.app`; Associated Domains and Push caps explicitly disabled for the extension (reduces App Review surface).
- Empty SwiftUI "Save to Palateful" placeholder sheet renders when sharing from Safari (no network calls yet).
- Provisioning profile + App Store Connect App ID `com.palateful.app.shareextension` created; build signs clean in Xcode Cloud.
- `ci_post_clone.sh` installs the new provisioning profile; archive step verifies `PalatefulShare.appex` is embedded in `Runner.app/PlugIns/` (grep-based assertion in `ci_post_xcodebuild.sh`).

### Story 2: `sie-2` — Shared state bridge (Flutter → App Group)

**AC:**
- `SharedStateService` writes `auth_jwt`, `auth_jwt_expires_at`, `user_id`, `api_base_url`, `recipe_books` (capped at 50), `last_used_book_id` to App Group on auth change and on book list change.
- `sync()` is debounced (250 ms) and runs off the auth callback's critical path — sync never blocks login UI; failures log via `logError` but don't surface.
- Swift `SharedState.read()` returns a strongly-typed `SharedContext?`.
- Extension sheet reads auth state and books from the App Group; shows "Open Palateful and sign in" when no auth or expiry <300 s away.
- Widget target continues to work (regression-test reading the same App Group).

### Story 3: `sie-3` — Minimal confirmation sheet UI + URL share path

**AC:**
- Extension sheet: icon + "Save to Palateful" + one-line summary + book picker (defaults to `last_used_book_id`) + Cancel + Save.
- For a URL share (Safari): Save button (1) persists the pending import to App Group `pending_imports` keyed by UUID, (2) calls `extensionContext.completeRequest` within 100 ms of tap, (3) fires the `/import` call on the background `URLSessionConfiguration.background(withIdentifier: "com.palateful.app.shareextension.upload")`. The `pending_imports` record is reconciled by the main app on next foreground.
- p50 share-sheet-tap → Saved checkmark < 2.5s on Wi-Fi for URL shares; measured via a `share_extension_latency_ms` telemetry event emitted to `/v1/events`.
- Book picker caps at last 50 books (alphabetical + `last_used` first) to bound App Group storage.
- Cancel dismisses without any network calls or App Group writes. `share_extension_cancelled` event fires.
- Error-state copy is indexed by `error_code`: `file_too_large` → "This file is too large…"; `unsupported_mime` → "Palateful can't read this type yet"; `jwt_expired` → "Open Palateful to refresh sign-in"; `rate_limited` → "You've hit your import limit — try again later"; all unknown → "Something went wrong. Try again." + error id.
- If `auth_jwt_expires_at - now < 300s`, sheet shows sign-in prompt instead of Save; no upload attempted. Covered by `sie-2` bridge.
- Manual test on device: share from Safari, verify ImportJob appears in Activity Hub and push notification fires on completion.

### Story 4: `sie-4` — Presigned upload path for file-based shares

**AC:**
- Sequence (all on the background `URLSession`): fetch `/v1/imports/upload-url` with `{filename, mime_type, size_bytes}` → `URLSession.uploadTask(with:fromFile:)` to presigned URL, injecting every header in the response's `required_headers` map → capture PUT response `ETag` → POST `/import` with `{s3_key, etag, source_type, book_id}`. On 409, retry `/import` up to 3× with 500 ms backoff.
- Peak resident memory stays under 80 MB during a 100 MB video upload on iPhone SE 3rd gen iOS 18, measured by `os_proc_available_memory()` sampled every 500 ms and asserted in an automated XCTest that drives the extension via `XCUIApplication`.
- No `UIImage` decoding of shared photos — the file URL is passed straight to `uploadTask(with:fromFile:)`. Explicitly forbidden via a lint/test.
- iCloud "download on demand" files: show "Downloading from iCloud…" state; prefer `loadInPlaceFileRepresentation` where available to avoid a second duplication.
- Pre-Save disclosure for files >10 MB: sheet shows "Uploading NN MB to Palateful" below the Save button.
- Size check: files >100 MB show the "too large" message before any network call; `share_extension_size_too_large` event fires.
- Failure paths map to `error_code` copy as in `sie-3`.
- Plain-text share >1 MB also hits the size check (not just files).

### Story 5: `sie-5` — Cold-start + iPad + edge cases

**AC:**
- Cold-start (main app never ran this session): extension flow works identically; the background `URLSession` finishes the PUT after extension dismissal even with main app dead.
- iPad: share sheet displays extension as a popover anchored correctly (no crash on `UIActivityViewController` popover constraints).
- Multi-item share: when >1 item is detected, a banner appears **on sheet load, before Save is enabled**, reading "Only the first of N items will be saved." `share_extension_multi_item_truncated` telemetry event fires with `{count, kept_type}` and the skipped items are freed immediately.
- `reduce motion` / `large text` accessibility: sheet scales, animations respect user preference.
- `VoiceOver`: all controls read their labels; sheet announces "Save to Palateful" on open.
- Test matrix: iOS 17 AND iOS 18 (18 tightened extension memory); iPhone SE 3rd gen (smallest current target) AND iPhone 15 Pro; iPad.

## Dependencies

- **Blocked by Epic 1 (`epic-share-backend-foundations`)** — needs `/v1/imports/upload-url` and `s3_key` support on the import endpoint. Can start target skeleton (`sie-1`) and App Group bridge (`sie-2`) in parallel with Epic 1, but `sie-4` (file uploads) requires Epic 1 to be merged.
- App Store Connect access for creating the new App ID + provisioning profile.

## Risks surfaced in party-mode (tracked, mitigated in ACs)

- **App Store review on unattended upload:** mitigated by `sie-4` pre-Save disclosure + `sie-1` disabled Push/Associated caps (reduces review surface).
- **iOS 18 extension memory:** mitigated by the 80 MB ceiling + no `UIImage` decode rule in `sie-4` + explicit iOS 18 matrix in `sie-5`.
- **JWT 2-minutes-from-expiry:** mitigated by the <300s proactive prompt in `sie-2` / `sie-3`.
- **Background upload persistence:** the whole "extension dies mid-upload" class is solved by `URLSessionConfiguration.background` per `sie-3` / `sie-4`. Main app reconciles `pending_imports` on foreground.
- **Missing telemetry:** the `share_extension_*` events above fix the observability blind spot.
- **iCloud dataless files:** handled in `sie-4` (download-in-place + state copy).

## Open questions for the user

None. All UX shape was locked in the PRD addendum (minimal sheet, presigned upload, 100 MB cap, eager upload). Multi-file share behavior is "first item only" per the PRD scope cut; the only variation is the pre-Save banner (added by this workshop).
