<!-- created 2026-05-03 from /audit triage handoff -->
# Epic: Import Flow Hardening — Make the Whole Pipeline Error-Proof

## Overview

The recipe-import pipeline has structural fragility that lets failures vanish silently. The user's recent week of broken image-share imports revealed a pattern that cuts across all source types: when something goes wrong (server 4xx, S3 PUT failure, transient network blip), the share extension and Flutter reconciler both fall off into telemetry-only paths and the user sees nothing — the share sheet has already dismissed, no banner appears in the app, no notification fires. On top of that, the server-side error_logs that would let us debug have null `request_id` because the import router never forwards the FastAPI `Request` to the endpoint, so the correlation handle that triage scripts depend on was missing.

This epic hardens the four structural gaps surfaced by `/audit` on 2026-05-03:

1. **Silent extension failure** — `UploadService.markFailed` (UploadService.swift:265–279) emits Telemetry only.
2. **Reconciler doesn't surface failures** — `PendingImportsReconciler` (pending_imports_reconciler.dart:38–90) reports to ErrorReporter, with no UI surface.
3. **No retry-policy distinction** — 400 (permanent) and 502 (transient) currently end the same way: telemetry + dropped record.
4. **Observability gaps** — `import_router.py` doesn't pass `Request` to `StartImport.call(...)`, so every error_logs row from the import path has `request_id=null`.

The Decimal-serialization bug class that bit the cart yesterday (commit a5c8438) recurs on `recipe.quantity_normalized` and is folded in here as AC 6 — same Pydantic v2 default-serializes-Decimal-as-string footgun, same Dart `as num?` cast crash if a recipe has a non-null normalized quantity.

## Goal

Turn every failure mode in the import pipeline into either (a) a silent successful retry within seconds when the cause is transient, or (b) a clear, actionable user-visible failure surface when the cause is permanent — and make every server-side failure carry the `request_id` that triage scripts already display. Stop losing shares.

## End-user flow (post-epic)

1. **User shares a recipe via the iOS Share Extension** (or via in-app URL/text/photo import).
2. **Server returns 200/201** → existing happy path runs unchanged. Activity Hub shows the import progressing.
3. **Server returns a transient error (5xx, 429, network blip)** → reconciler does exponential backoff (1s, 4s, 16s, 1m, 5m, 30m cap; max 6 attempts) and re-POSTs. UI shows nothing intermediate — the user doesn't need to know about a 502 that resolves itself.
4. **Server returns a permanent error (400/403/415/422)** → reconciler stops retrying immediately, the App Group record is marked `failed`, the Import Activity Hub shows a persistent "1 import couldn't be processed" banner, tap → list → per-row friendly error message + Dismiss / Retry-once actions.
5. **iOS extension dies before /import fires** → main app's reconciler picks up the App Group record on next foreground, identical retry policy applies.
6. **iOS extension hits a permanent failure (e.g. 415 from upload-url because the file type is rejected)** while the share sheet is dismissed → a `UNUserNotification` fires ("Couldn't import — open Palateful for details"), the App Group record is marked `failed` so the in-app surface is consistent on next foreground.
7. **Recipe with non-null `quantity_normalized` is fetched** → JSON wire payload is a number, Dart parser cast succeeds, recipe screen renders normally (no recurrence of the cart bug).

## Frontend changes

- **`UploadService.swift`** (iOS share extension):
  - `markFailed` writes failure metadata back into the App Group record (`failed: true`, `error_code`, `error_id`, `attempted_at`, `retryable: bool`) instead of dropping it. Persistent record so the main-app reconciler and the failed-imports UI both see it.
  - When the failure is `retryable: false`, schedule a `UNUserNotification` via `UNUserNotificationCenter` with title "Couldn't import to Palateful" and body keyed off `error_code`. Permission gate: only if user already granted notification permission (no new prompt from the extension).
  - For PUT failures (URLSession delegate, line 299–305), preserve the failure record but DO NOT attempt to re-PUT from the extension — the file URL doesn't survive App Group, so the existing comment ("share is effectively lost") stays accurate; the difference is the user now sees the failure surface in the app.
- **`pending_imports_reconciler.dart`**:
  - Read new `retryable` and `attempt_count` and `next_attempt_at` fields from each App Group record (defaulting to retryable=true for legacy records pending migration).
  - Honor `next_attempt_at` — skip records whose backoff hasn't elapsed.
  - On 4xx (permanent) response: increment a permanent-fail counter, mark record `failed: true`, surface to UI; do NOT re-POST.
  - On 5xx / 429 / network: increment `attempt_count`, compute next backoff (1s, 4s, 16s, 1m, 5m, 30m), set `next_attempt_at`, leave record alive. After 6 attempts, mark as `failed` (treat exhausted-retries as permanent so users are not gas-lit by silently-dropped shares).
  - Reuse the new `retryable` field from the server's error response (see backend section). Fall back to `4xx → permanent / 5xx → transient` heuristic if the field is missing (older server, network failure with no body).
- **New widget: `FailedImportsBanner`** in the Import Activity Hub:
  - Shows "*N imports couldn't be processed*" when `failedImportCount > 0`.
  - Tap → opens a sheet listing each failed record with a friendly error message (mapped from `error_code` via a new `importFailureCopy` map alongside `mutationFailureCopy`), per-row "Dismiss" and "Retry" actions.
  - Reads from a new `FailedImportsService` that consolidates server-side failed `import_items` (existing) AND local App Group records that never made it past reconciliation.
- **Telemetry**: when `FailedImportsBanner` is shown, log impression + per-row tap-Retry / tap-Dismiss for product feedback.

## Backend changes

- **`import_router.py`** — every endpoint takes `request: Request = None` (FastAPI `fastapi.Request`) via the function signature and forwards `request=request` into the `.call(...)` invocation. This is the structural fix for the request_id observability gap. Pattern:
  ```python
  @import_router.post("/recipe-books/{book_id}/import")
  async def start_import(
      book_id: str,
      params: StartImport.Params,
      request: Request,
      user: User = Depends(get_current_user_async),
      database: AsyncDatabase = Depends(get_async_database),
  ):
      return await StartImport.call(
          book_id=book_id,
          params=params,
          request=request,
          user=user,
          database=database,
      )
  ```
- **Error response shape extension** on `/recipe-books/{book_id}/import` and `/imports/upload-url`:
  - Add `retryable: bool` to every `failure(...)` return path. Classification rule:
    - `400` (`INVALID_REQUEST`, `IMPORT_INVALID_SOURCE_TYPE`) → `retryable=False`
    - `403` (`RECIPE_BOOK_ACCESS_DENIED`, `CROSS_USER_KEY`) → `retryable=False`
    - `404` (`RECIPE_BOOK_NOT_FOUND`) → `retryable=False`
    - `409` (`OBJECT_NOT_READY`, `DUPLICATE_IMPORT`) → `retryable=True` for `OBJECT_NOT_READY` (S3 visibility lag), `retryable=False` for `DUPLICATE_IMPORT` (already imported, not a real failure for the user)
    - `413/415` (`file_too_large`, `unsupported_mime`) → `retryable=False`
    - `429` (`RATE_LIMITED`) → `retryable=True` (and existing `retry_after` is still honored)
    - `5xx` (any) → `retryable=True`
  - The `failure(...)` helper stays as-is; the endpoint passes `retryable` as a kwarg, the helper threads it into the response payload alongside `error_code` / `error_message` / `retry_after`.
- **`utils.api.endpoint.failure(...)`** signature accepts an optional `retryable: bool | None = None` and includes it in the JSON body when set. Default `None` keeps every other endpoint's wire shape unchanged.
- **Decimal serialization sweep** — same fix as commit a5c8438 (cart) applied to recipe responses:
  - `GetRecipe.IngredientResponse.quantity_normalized: Decimal | None` (and any sibling Decimal field) gets a `@field_serializer` that coerces to `float | None` so the wire payload is a JSON number, not a string. Also covers any other Decimal-typed response field discovered in the sweep (audit notes flag `recipe.py:22, 42, 44`; the actual files to scan are listed in the story File List).
  - Pin a regression test asserting `model_dump_json()` produces a JSON number for both populated and null cases on every Decimal field touched.
  - Out-of-scope (separate follow-on epic if needed): pantry, cooking_log, meal_event Decimal fields. We fix what the user can see today (recipe ingredients) plus everything that's wire-coupled to the cart fix.

## Infrastructure changes

None. No new endpoints. No migrations. The App Group schema change is additive (new optional fields on the existing `share_pending_imports` JSON list) — Swift writes and Dart reads both default missing fields to safe values.

## Initial design principles

- **Permanent vs transient is a server contract, not client guesswork.** The server knows whether a 400 means "your input was bad and will always be bad" or whether retrying could ever help. Encode that in the response so clients don't have to maintain a parallel error taxonomy.
- **Bounded retries.** Exponential backoff stops at 6 attempts (~36 minutes wall-clock). After that, the record is marked failed and surfaced to the user — no infinite background retry loops burning telemetry quota.
- **Failures are persistent state, not transient telemetry.** The App Group record stays alive on failure (with `failed: true`), so the user can see and act on every failure even if the share extension already dismissed.
- **One copy of the user-friendly error map.** Add `importFailureCopy` alongside `mutationFailureCopy` (referenced in `app/lib/core/state/README.md`) so the same error_code → user message convention spans imports and mutations.
- **Don't over-scope the request_id fix.** The structural gap is platform-wide (26 of 27 routers don't forward `Request`), but the audit-cited evidence and the highest-volume failure surface is the import router. Fix import_router here; note the platform-wide sweep as a follow-on so this epic doesn't grow into a router refactor.
- **No share-extension in-memory PUT.** The 80 MB RSS budget guard exists for a reason (UploadService.swift:21–25 + ci_post_clone.sh lint). Do not refactor the file-streamed PUT.

## File structure

```
services/api/src/routers/v1/
  import_router.py                       # MODIFY — wire request: Request through every endpoint
services/api/src/api/v1/import_job/
  start_import.py                        # MODIFY — pass retryable kwarg into every failure(...)
  get_upload_url.py                      # MODIFY — same
libraries/utils/utils/api/
  endpoint.py                            # MODIFY — failure() accepts retryable kwarg, threads to response body
services/api/src/api/v1/recipe/
  _response.py                           # MODIFY — IngredientResponse field_serializer for quantity_normalized
  get_recipe.py                          # MODIFY — schema add field_serializer if Decimal at top-level
services/api/tests/
  test_schemas.py                        # MODIFY — Decimal regression tests on recipe ingredient fields
  api/v1/import_job/test_start_import.py # MODIFY — test retryable field on each failure path; test request_id capture
app/ios/PalatefulShare/
  UploadService.swift                    # MODIFY — markFailed persists failure state; UNUserNotification on permanent
  PendingImports.swift                   # MODIFY — record schema gains failed/error_code/retryable/attempt_count/next_attempt_at
app/lib/core/services/
  pending_imports_reconciler.dart        # MODIFY — backoff + retryable handling
  failed_imports_service.dart            # NEW — consolidates server + local failed records
app/lib/core/state/
  import_failure_copy.dart               # NEW — error_code → user message map
app/lib/features/imports/widgets/
  failed_imports_banner.dart             # NEW
  failed_imports_sheet.dart              # NEW
app/test/features/imports/
  failed_imports_banner_test.dart        # NEW
  pending_imports_reconciler_backoff_test.dart  # NEW
```

## Stories

### `ifh-1` — Backend: request_id propagation + retryable classification on /import & /upload-url

**Acceptance:**
- Every endpoint in `import_router.py` accepts `request: Request` and forwards it via `request=request` to the `.call(...)` invocation. Verify by reading any `error_logs` row written from an import-path 4xx — `request_id` is no longer null.
- `utils.api.endpoint.failure(...)` accepts an optional `retryable: bool | None` kwarg; when set, the JSON response body includes `"retryable": true|false` alongside `error_code` / `error_message`.
- `StartImport.execute(...)` and `GetImportUploadUrl.execute(...)` pass the appropriate `retryable` value on every `failure(...)` and re-raise pattern. Classification follows the table in the Backend section.
- Existing behavior for endpoints that don't pass `retryable` is unchanged — no `retryable` key appears in their response bodies.
- New unit tests cover each failure path's classification (parametrized).
- A unit test asserts that an APIException raised from `StartImport.execute` while `request: Request` was forwarded results in an `error_logs` row with the expected `request_id`. (Use the existing test harness pattern for `_log_api_error_to_db`.)
- 100% line coverage maintained on every touched file.

### `ifh-2` — Backend: Decimal-typed response serialization sweep

**Acceptance:**
- `GetRecipe.IngredientResponse.quantity_normalized` (and any sibling Decimal field on a Recipe-domain response) carries a `@field_serializer` that coerces `Decimal | None` → `float | None`.
- `model_dump_json()` of a populated `IngredientResponse` produces a JSON number (e.g. `1.5`), not a JSON string (`"1.5"`). Pinned by a unit test in `test_schemas.py` asserting both populated and null cases.
- Sweep covers every Decimal-typed response field in the Recipe domain (grep verifies). Note in the story commit message which other Decimal fields were inspected and ruled in/out of scope.
- 100% line coverage maintained.
- A regression test loads a recipe with a non-null `quantity_normalized` through the actual `GetRecipe.call(...)` path (using the existing async test client) and asserts the JSON wire payload's `quantity_normalized` field is a number.

### `ifh-3` — iOS Share Extension: persist failure state + system notification on permanent failures

**Acceptance:**
- `PendingImport` Swift struct gains optional fields: `failed: Bool`, `errorCode: String?`, `errorId: String?`, `retryable: Bool?`, `attemptedAt: Date?`. JSON encoding of the App Group record includes these (snake_case keys) so the Dart side can read them.
- `UploadService.markFailed` writes the failure metadata back into the persisted `PendingImport` record (via `PendingImports.upsert`) instead of dropping the record. Telemetry emission is preserved.
- `markFailed` schedules a `UNUserNotification` when `retryable == false`. Notification permission is queried (not requested) — if permission is `notDetermined` or `denied`, fall back to telemetry-only and skip the notification (extensions cannot prompt for permission). Notification body is keyed off `errorCode` via a small Swift `errorCopy(for:)` helper that mirrors the Dart `importFailureCopy` map.
- For the `submitImport` path, classification of `retryable` reads the new server response field if present; falls back to status code (`4xx` → false except 408/429/5xx → true) when the field is absent.
- Existing 409-with-3-retries logic is unchanged.
- Swift unit test covers: (a) markFailed persists fields into the App Group record, (b) markFailed with retryable=false schedules a notification when permission is granted, (c) markFailed with retryable=true does NOT schedule a notification.

### `ifh-4` — Dart Reconciler: exponential backoff + permanent-failure UX

**Acceptance:**
- `PendingImportsReconciler.reconcile()` honors a `next_attempt_at` timestamp on each record — records whose backoff hasn't elapsed are skipped (left in App Group untouched).
- On a successful POST, record is dropped (existing behavior).
- On a transient error (network exception OR server returned `retryable: true` OR fallback heuristic 5xx/429/408): increment `attempt_count`, compute next `next_attempt_at` using the backoff schedule (1s, 4s, 16s, 1m, 5m, 30m), persist updated record. After 6 attempts, mark `failed: true` and stop retrying.
- On a permanent error (server returned `retryable: false` OR fallback heuristic 4xx other than 408/409/429): mark `failed: true`, set `error_code` from response body, persist record. Do NOT re-POST.
- Reading the server response — extract `error_code` and `retryable` from the JSON body via the existing `ApiClient` error path (story decides whether `ApiClient.postImportForBook` already exposes the response body on error or whether we need to surface it).
- New Dart unit tests in `pending_imports_reconciler_backoff_test.dart` cover: (a) transient error increments attempt_count and sets next_attempt_at, (b) permanent error marks failed without retrying, (c) backoff schedule matches the spec, (d) record marked failed after 6 attempts, (e) record skipped while next_attempt_at is in the future.
- Existing reconciler tests continue to pass.

### `ifh-5` — Frontend: FailedImportsBanner + FailedImportsSheet wired into Import Activity Hub

**Acceptance:**
- New `FailedImportsService` exposes a stream of failed import records sourced from (a) the App Group via `PendingImports.list().where(failed)` and (b) server-side `import_items` in `failed`/`unrecoverable` state. De-dup by `idempotency_key` if both sides have the same record (server wins).
- `FailedImportsBanner` widget shows count + "tap to review" affordance; mounts at the top of the Import Activity Hub when the count is > 0; hides when count is 0.
- Tap opens `FailedImportsSheet` listing each failed record with: source-type icon, user-visible filename/URL, friendly error message (from `importFailureCopy`), per-row Dismiss + Retry buttons. Retry calls reconciler with attempt_count reset to 0; Dismiss removes the record from the App Group / archives the server-side import item.
- Reactivity: emits / subscribes via the existing MutationBus per `app/lib/core/state/README.md`; banner state updates in real time as failures clear or new ones arrive.
- New `import_failure_copy.dart` map ships at least: `network`, `unknown`, `jwt_expired`, `file_too_large`, `unsupported_mime`, `rate_limited`, `s3_put_failed`, `object_not_ready`, `cross_user_key`, `recipe_book_access_denied`, `recipe_book_not_found`. Default fallback uses `error_code` verbatim.
- Widget tests cover: (a) banner hidden when no failures, (b) banner shown with correct count, (c) sheet renders multiple failure rows, (d) Retry resets attempt_count and triggers reconciler, (e) Dismiss removes record from list.

### `ifh-6` — Regression sweep + e2e

**Acceptance:**
- e2e: import a URL that returns 502 → reconciler backs off, retries, eventually succeeds; user sees no failure UI.
- e2e: import a file with `unsupported_mime` (415) → record marked failed immediately, FailedImportsBanner appears with friendly copy on next foreground; UNUserNotification fires on iOS if permission granted.
- e2e: PUT to S3 fails with network error inside extension → record persists with `failed: true, error_code: s3_put_failed, retryable: false`; user sees the failure surface in app.
- e2e: import a recipe whose ingredients include a non-null `quantity_normalized` → recipe-detail screen renders without throwing the `as num?` cast error. (Regression for the cart bug class on the recipe surface.)
- e2e: backwards-compat — App Group records written by the pre-epic share extension (no `failed`/`retryable` fields) are still picked up by the reconciler and treated as retryable until first response.
- Performance: reconciler tick latency unchanged within ±5ms on a list of 10 pending records (microbenchmark in test).
- Spot-check via `audit_errors.py --drill api:APIException` after staging deploy: at least one drill row has a non-null `request_id` from the `/v1/recipe-books/.../import` path.
- Sprint-status updated, retrospective: optional.

## Dependencies

- **Hard:** none.
- **Soft:** `epic-import-row-rich-detail` and `epic-import-activity-nav` already shipped the per-import-item UI surface; the `FailedImportsBanner` mounts above that surface — no coupling beyond placement.

## Out of scope (deliberately deferred)

- **Platform-wide `Request` forwarding sweep.** 26 of 27 routers don't pass `Request` to `.call(...)`. Follow-on epic to apply the same pattern across the rest of the codebase. The audit-cited surface is import; that's what we fix here.
- **In-memory PUT in share extension.** Memory budget forbids it. See do-NOT in audit handoff.
- **Replacement of generic `unknown`/`s3_put_failed` user-facing copy with bug-tracker integration.** The friendly copy is good enough; deeper diagnostic surfacing belongs in a separate observability epic.
- **Pantry/cooking_log/meal_event Decimal sweep.** Same Pydantic v2 footgun likely lurks but those surfaces are not currently visibly broken; pin a follow-on if/when error_logs surfaces a hit.

## Open questions for the user

None — the audit handoff was explicit on every constraint (no in-memory PUT, retries must terminate, image-source-type bug is orthogonal). Proceeding.
