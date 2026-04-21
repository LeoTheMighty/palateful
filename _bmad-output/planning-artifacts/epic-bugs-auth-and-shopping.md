<!-- drafted 2026-04-21 from dogfood bug list in BUGS.md -->
# Epic: Bug Fixes — Auth, Imports/Notifs Copy, Shopping Cart, Token Refresh

## Overview

Dogfood bug batch. Four unrelated-but-small fixes cluster well enough to ship together as
one epic because each is a single-story, single-surface change:

1. **Logout lands on an Auth0-hosted page** instead of returning to `/login`.
2. **"Archive" copy in imports + notifs reads weird for successful items** — should say
   "Dismiss". UI-text-only rename; backend `/archive` endpoints stay.
3. **Shopping cart unopenable after using "Add ingredients" from calendar events
   repeatedly**, plus long-standing WebSocket errors surfacing in Crashlytics. Harden
   the open path, instrument it properly, and make WS failures reportable + recoverable.
4. **Token-refresh failures produce weird app errors** — the Dio 401 interceptor exists
   and refreshes correctly, but on refresh failure it just propagates without logging
   the user out, so stale tokens produce confusing downstream errors. Single-point fix
   in `api_client.dart`.

**Goal:** After this epic, (a) logout goes `app → Auth0 logout → app /login` with no
intermediate Auth0-branded page on native, (b) successful imports/notifs say "Dismiss",
(c) the shopping cart opens reliably even after heavy calendar-event ingredient adds
and reports failures with enough detail to diagnose, and (d) any screen hitting a 401
that can't be refreshed ends up on /login, not on a mystery error.

## Design Principles

1. **UI-copy changes are copy-only.** Do not rename backend endpoints, method names,
   or analytics events — `/archive`, `archiveActivity(id)`, `archiveImportItem(id)`
   all keep their current names. Only visible text changes.
2. **One centralized fix for token-refresh failure.** The Dio interceptor is the one
   place that already knows about refresh; extend it instead of sprinkling try/catch
   across screens. Web doesn't support refresh (`refreshToken()` returns false on web)
   — that path counts as "refresh failed" and triggers logout too.
3. **Shopping-cart failures must be reportable.** Any `_loadList()` failure or WS
   exception must call `ErrorReporter.report(...)` with `area='shopping.cart'` or
   `area='shopping.websocket'` so `audit_errors.py --service=client` finds them.
   `debugPrint` is not a diagnostic tool.
4. **No backend schema changes, no migrations.** Every fix is either Flutter-only or
   a narrow backend response shape tweak (no new columns, no alembic runs).
5. **Delete, don't restyle.** Replace `Archive` → `Dismiss` at every UI site; do not
   keep both terms in the codebase alongside each other with a flag.
6. **No feature flags, no shims.** Logout-redirect gets the Auth0 scheme passed
   unconditionally; it's the right behavior for every build.

## Locked Decisions

- **Native logout returnToUrl scheme:** use `Environment.auth0Scheme` — the same value
  that drives login callback — with path `login`. Rely on the existing `intent-filter`
  / `CFBundleURLSchemes` wiring that made the login callback work. No new platform
  config.
- **"Dismiss" is the only replacement term** — not "Done", "Hide", "Got it". The user
  explicitly asked for "dismiss".
- **The `ApiClient.archiveActivity()` / `archiveImportItem()` Dart method names stay.**
  Renaming them would cascade into call sites with no user-visible benefit.
- **On refresh-unavailable (web) OR refresh failure, interceptor calls
  `authService.logout()` then rejects the original error.** Don't try to preserve the
  request; the user is going to /login anyway. Race with in-flight requests is
  acceptable — the interceptor already guards with `_isRefreshing`.
- **Shopping-cart WS reconnect keeps its current 5s timer.** This story does not
  redesign the reconnect strategy — it just ensures failures are logged and survive
  token expiry.

## End-user flow

### Flow A — Logout

1. User on Profile → "Sign Out". Confirms.
2. App clears credentials locally, then triggers Auth0's `/v2/logout` with a
   `returnToUrl` pointing back at the app's callback scheme.
3. Browser opens, Auth0 session ends, browser redirects back to the app deep-link.
4. App clears session state and router lands on `/login`.
5. No intermediate Auth0-branded "You are signed out" page stays on screen.

### Flow B — Dismissing a successful import or notification

1. User sees a successful import row on the Imports tab (green check, "Imported").
2. User taps the row to expand, sees a "Dismiss" button (was "Archive").
3. Tap → row animates out. Snackbar reads "Dismissed" (was "Archived"). Error paths
   read "Couldn't dismiss, try again" (was "archive").
4. Same on Notifications tab — the swipe / action that previously said "archive"
   now says "dismiss". Backend call is unchanged.

### Flow C — Opening shopping cart after heavy calendar-event ingredient adds

1. User taps "Add ingredients" on many calendar events across the week. Each tap
   calls `POST /v1/meal-events/{id}/add-to-shopping-list` and the list grows.
2. User navigates to the shopping cart (either full screen or floating widget).
3. The cart loads and displays the items. If load fails (any reason — large response,
   DB hiccup, network), the failure reaches `ErrorReporter.report()` with full
   context (list_id, status code, error type). The user sees an error banner, not a
   generic blank screen.
4. The WebSocket connects. If the WS handshake fails (e.g. token expired between
   `_loadList` and connect), the failure is reported AND the service attempts one
   token refresh before reconnecting. Subsequent errors use the existing 5s
   reconnect backoff.

### Flow D — Token-refresh failure → clean logout

1. User has been backgrounded long enough that refresh token has also expired /
   Auth0 revoked it.
2. User foregrounds app. Any API call → 401. Interceptor tries refresh → fails.
3. Interceptor calls `authService.logout()` which clears credentials and session
   state. The `AuthService` `notifyListeners()` flows into the app-level listener
   that redirects to `/login`.
4. User sees the login screen, not a DioException / red error text on whatever
   screen they were on.

## Frontend changes

### bas-1 — Auth0 logout returnTo
- `app/lib/core/services/auth_service.dart:215` — replace
  ```dart
  await _auth0!.webAuthentication(scheme: Environment.auth0Scheme).logout();
  ```
  with
  ```dart
  await _auth0!.webAuthentication(scheme: Environment.auth0Scheme).logout(
    returnTo: '${Environment.auth0Scheme}://login',
  );
  ```
  (Verify the exact parameter name from `auth0_flutter` 1.14.0 — it's either
  `returnTo` or `returnToUrl` on the native SDK. Web uses `returnToUrl`.)
- No additional imports, no env var, no platform config changes. The scheme is
  already registered for login callback.

### bas-2 — Archive → Dismiss copy
- `app/lib/features/activity/widgets/import_row_expansion_actions.dart:103` —
  button label `Archive` → `Dismiss`. Update the docstring comment block at
  lines ~6-10 that documents row state transitions.
- `app/lib/features/activity/imports_tab.dart`
  - line ~229: success toast `Archived` → `Dismissed`
  - line ~250: `"Can't archive while importing"` → `"Can't dismiss while importing"`
  - lines ~251, ~253: `"Couldn't archive, try again"` → `"Couldn't dismiss, try again"`
- `app/lib/features/activity/notifications_tab.dart`
  - line ~196: `"Couldn't archive, try again"` → `"Couldn't dismiss, try again"`
  - line ~19: comment `POST /v1/activities/{id}/archive` — leave; it names the actual
    endpoint and is accurate.
- **Do not rename:** `ApiClient.archiveActivity()`, `ApiClient.archiveImportItem()`,
  `ApiClient.unarchiveActivity()`, `ApiClient.unarchiveImportItem()`, or any
  backend handler.

### bas-3 — Shopping cart hardening + WebSocket error reporting
- `app/lib/features/shopping_cart/models/shopping_list_item.dart:47-73` — make
  `fromJson` defensive:
  - `id`: keep `as String` (backend guarantees; crash here is a real bug we want
    logged).
  - `name`: fall back to `''` if null (defensive — rendering empty text is better
    than crashing the whole list parse).
  - Every nullable DateTime parse: wrap in try/catch that logs via
    `debugPrint` and returns null (a single bad row should not take out the list).
- `app/lib/features/shopping_cart/screens/shopping_list_screen.dart:88-96` —
  inside the `catch (e)` of `_loadList`, call:
  ```dart
  ErrorReporter.report(
    e,
    null,
    area: 'shopping.cart',
    operation: 'loadList',
    extras: {'list_id': widget.listId},
  );
  ```
  before updating state. Same in `floating_cart_widget.dart:107-115`.
- `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
  - `_doConnect` (lines 207-234): the `catch (e)` at 231 must report via
    `ErrorReporter.report(e, null, area: 'shopping.websocket', operation: 'connect', extras: {'list_id': _currentListId})`.
  - `_handleError` (lines 303-307): report via
    `ErrorReporter.report(error, null, area: 'shopping.websocket', operation: 'stream', extras: {'list_id': _currentListId})`.
  - `_handleDisconnect` (lines 309-312): if the channel closed with a code in the
    4000-4999 range (app-defined close codes — Auth0 token rejection lands here
    per `websocket.py` lines 146/159), call
    `authService.refreshToken()` once before scheduling reconnect. On refresh
    success, the next `_doConnect` will use the fresh token. On refresh failure,
    fall through to the existing 5s reconnect (it will error again and the error
    reporter will surface it).
  - Guard `_currentListId` non-null before URI construction at line 219-221; if
    it's null we should log + return, not attempt `Uri.parse` with a literal
    `null` in the path.

### bas-4 — Token-refresh failure → logout
- `app/lib/core/services/api_client.dart:34-80` — extend the 401 branch of the
  `onError` interceptor. Logic:
  ```dart
  if (error.response?.statusCode == 401 && _authService != null && !_isRefreshing) {
    _isRefreshing = true;
    try {
      final refreshed = await _authService!.refreshToken();
      if (refreshed && _authService!.accessToken != null) {
        _authToken = _authService!.accessToken;
        final opts = error.requestOptions;
        opts.headers['Authorization'] = 'Bearer $_authToken';
        final response = await _dio.fetch(opts);
        _isRefreshing = false;
        return handler.resolve(response);
      }
      // Refresh attempted but failed — tokens are gone or Auth0 rejected.
      // Kick the user to /login via AuthService.logout() which notifies
      // listeners; app-level listener redirects to /login.
      await _authService!.logout();
      _authToken = null;
    } catch (e) {
      // Refresh threw — same outcome as refreshed==false.
      await _authService!.logout();
      _authToken = null;
      debugPrint('Token refresh error during request: $e');
    } finally {
      _isRefreshing = false;
    }
  }
  ```
- No call-site changes. Every screen that uses `ApiClient` inherits the new behavior.
- **Web gotcha:** `AuthService.refreshToken()` returns `false` on web without
  attempting anything. That's fine — the new branch treats "refreshed == false"
  identically to "refresh threw": logout + kick to login.

## Backend changes

None required for bas-1, bas-2, bas-4.

**bas-3 (optional, small):** review `services/api/src/api/v1/shopping_list/get_shopping_list.py`
for any unhandled edge cases that could 500 on large lists. Specifically:
- Confirm `item.priority` is non-null in the DB (the Pydantic response defaults to 3,
  but if the column allows NULL and some row is NULL, Pydantic coerces fine because
  `priority: int = 3` has a default only if the field is omitted, not if it's None).
  If any production rows have `priority=None`, the Pydantic model will raise. Quick
  check: the SQLAlchemy `ShoppingListItem.priority` column definition — is it
  `nullable=False default=3`? If yes, we're fine and no change needed.

No migrations. No new endpoints.

## Infrastructure changes

None. No env vars, no Terraform, no Auth0 dashboard config — the post-logout callback
scheme is already registered (it's the same scheme login uses).

## File structure (expected)

```
app/lib/core/services/
├── auth_service.dart                   # MODIFIED — returnTo on native logout
└── api_client.dart                     # MODIFIED — logout-on-refresh-failure branch

app/lib/features/activity/
├── imports_tab.dart                    # MODIFIED — snackbar copy: archive→dismiss
├── notifications_tab.dart              # MODIFIED — error msg copy: archive→dismiss
└── widgets/
    └── import_row_expansion_actions.dart  # MODIFIED — button: Archive→Dismiss

app/lib/features/shopping_cart/
├── models/
│   └── shopping_list_item.dart         # MODIFIED — defensive fromJson
├── services/
│   └── shopping_cart_service.dart      # MODIFIED — ErrorReporter on WS failures +
│                                       #             token refresh on 4xxx close code
└── screens/
    └── shopping_list_screen.dart       # MODIFIED — ErrorReporter on load failure

# Test files: reuse or light-add where existing coverage lives. No new test directories.
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| bas-1 | Auth0 native logout returnTo | 🟡 P1 | 0.25 d | None |
| bas-2 | Rename Archive → Dismiss in imports/notifs UI | 🟢 P2 | 0.25 d | None |
| bas-3 | Shopping cart open reliability + WS error reporting | 🟡 P1 | 0.5 d | None |
| bas-4 | Dio interceptor: logout on refresh failure | 🟡 P1 | 0.25 d | None |

**Total estimated effort: ~1.25 days**

All four stories are independent and can be implemented in any order.

---

## Story bas-1: Auth0 native logout — return to app

As Leo,
I want the app to land on `/login` after I sign out,
so that I don't see an Auth0-branded "logged out" page mid-flow.

### Acceptance Criteria

1. `auth_service.dart` native logout (line ~215) passes `returnTo` (or SDK's equivalent
   parameter name) set to `'${Environment.auth0Scheme}://login'`.
2. Verified on iOS and Android: signing out from Profile → Sign Out returns the app to
   `/login` without an intermediate Auth0 page persisting on screen.
3. Web logout behavior unchanged — it already passes `returnToUrl` (auth_service_web.dart:98).
4. No new env vars, no new Auth0 dashboard config, no new intent-filters / URL schemes.
5. If the Auth0 SDK rejects the callback URL (mismatched allowed logout URL in Auth0
   dashboard), the existing `catch (e)` in `logout()` still clears local state — the
   user is still logged out in the app even if the browser step misfires.
6. Unit test (or widget test): `auth_service_test.dart` — mock the
   `WebAuthentication.logout` call and assert `returnTo` argument is the expected
   scheme-based URL.

### Key Files
- Modify: `app/lib/core/services/auth_service.dart`
- Test: `app/test/core/services/auth_service_test.dart` (extend if exists; otherwise add
  minimal logout-returnTo assertion alongside existing auth tests).

---

## Story bas-2: Rename "Archive" → "Dismiss" in imports + notifications UI

As Leo,
I want successful imports and notifications to offer "Dismiss", not "Archive",
so that the action language matches the intent (you're clearing a finished item, not
filing it).

### Acceptance Criteria

1. `import_row_expansion_actions.dart` — the `_archiveButton()` label text is
   `Dismiss`. Function / variable / widget names stay (`_archiveButton`, etc.) —
   only visible text changes.
2. `imports_tab.dart` snackbar strings:
   - success → `Dismissed` (was `Archived`)
   - in-progress guard → `Can't dismiss while importing`
   - error → `Couldn't dismiss, try again` (both occurrences)
3. `notifications_tab.dart:196` error snackbar → `Couldn't dismiss, try again`.
4. No changes to `ApiClient.archiveActivity()`, `ApiClient.archiveImportItem()`,
   `ApiClient.unarchive*()` methods.
5. No changes to backend `/archive`, `/unarchive` endpoints.
6. Grep for `Archiv` in `app/lib/features/activity/` — the only remaining hits are
   comments that reference the backend endpoint path literally (that's accurate and
   stays) or unrelated content like archived recipe books.
7. No new i18n / ARB file needed — strings stay inline (matches project convention;
   no existing localization system).
8. Widget test: a single spot-check test asserts the Imports tab expanded row shows
   `Dismiss` on a successful import and that the snackbar after tapping reads
   `Dismissed`.

### Key Files
- Modify: `app/lib/features/activity/widgets/import_row_expansion_actions.dart`
- Modify: `app/lib/features/activity/imports_tab.dart`
- Modify: `app/lib/features/activity/notifications_tab.dart`
- Test: existing `app/test/features/activity/imports_tab_test.dart` (extend with one
  assertion) — or add a minimal file if none exists.

---

## Story bas-3: Shopping cart open reliability + WebSocket error reporting

As Leo,
I want the shopping cart to open reliably even after I've added ingredients from many
calendar events, and when something does go wrong I want the error reported through
`ErrorReporter` so I can find it in `audit_errors.py --service=client`,
so that the cart stops being a silent dead-end and I can actually diagnose prod
problems.

### Acceptance Criteria

1. **Defensive `ShoppingListItem.fromJson`** (`shopping_list_item.dart:47-73`):
   - `name` falls back to empty string if the key is missing or null (rendering an
     empty row is better than crashing the whole cart).
   - DateTime fields (`checked_at`, `due_at`) wrapped in try/catch — parse failure
     returns null rather than throwing.
   - `id` stays strict (`as String`) — a null id IS a real bug we want to see.
2. **`ShoppingListScreen._loadList` error path** (line ~88-96): the `catch (e)` block
   calls
   ```dart
   ErrorReporter.report(e, null, area: 'shopping.cart', operation: 'loadList', extras: {'list_id': widget.listId});
   ```
   BEFORE updating `_error` state. Same call added to
   `FloatingCartWidget._loadList` (line ~107-115).
3. **WebSocket `_doConnect` catch** (`shopping_cart_service.dart:231`): reports via
   `ErrorReporter.report(e, null, area: 'shopping.websocket', operation: 'connect', extras: {'list_id': _currentListId})`.
4. **WebSocket `_handleError`** (lines 303-307): reports via
   `ErrorReporter.report(error, null, area: 'shopping.websocket', operation: 'stream', extras: {'list_id': _currentListId})`.
5. **Token-refresh on WS close codes 4xxx**: `_handleDisconnect` inspects the channel's
   close code if available (`_wsChannel?.closeCode`). If the code is in the
   4000-4999 range (app-defined — backend uses 4003/4004 per `websocket.py:146,159`),
   the service calls `authService.refreshToken()` once before scheduling reconnect.
   On refresh success the next `_doConnect` uses the fresh token (pulled from
   `_apiClient.authToken` as before).
6. `_currentListId` is non-null-checked before `Uri.parse('$wsBaseUrl/v1/ws/shopping-lists/$_currentListId?token=$token')` —
   if it's null, the method logs via `ErrorReporter.report` (area='shopping.websocket',
   operation='connect', extras={'reason':'null_list_id'}) and returns without
   attempting the connection.
7. **Backend audit** — read `libraries/utils/utils/models/shopping_list_item.py` and
   confirm `priority` column is `nullable=False` with a server-side default. If any
   row can have `priority=None`, the Pydantic `ItemResponse.priority: int = 3` will
   raise during list load with a 500. If that's the case, either (a) coerce in the
   endpoint (`priority=item.priority or 3`) or (b) mark the field `int | None`. Log
   the outcome of this check in the story completion notes so bas-3 QA has a record.
8. **No backend schema change, no migration.** If the priority audit in AC7 shows
   NULL data in prod, the fix is a response-layer coerce, not a column change.
9. **Test coverage:**
   - Dart unit test: `ShoppingListItem.fromJson` with `name` omitted → `name == ''`,
     doesn't throw.
   - Dart unit test: `ShoppingListItem.fromJson` with malformed `checked_at` →
     `checkedAt == null`, doesn't throw.
   - Backend test: if AC7 triggers a code change in get_shopping_list, add a pytest
     case that a shopping list with a `priority=None` item still returns 200.
10. **Manual dogfood check:** tap "Add ingredients" on at least 5 calendar events,
    then open the shopping cart. Cart opens. Kill WebSocket connection (airplane
    mode toggle) and verify the error banner surfaces without the whole screen
    crashing; turn airplane mode off, WS reconnects within ~10s.

### Key Files
- Modify: `app/lib/features/shopping_cart/models/shopping_list_item.dart`
- Modify: `app/lib/features/shopping_cart/screens/shopping_list_screen.dart`
- Modify: `app/lib/features/shopping_cart/widgets/floating_cart_widget.dart`
- Modify: `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
- Audit (may modify): `services/api/src/api/v1/shopping_list/get_shopping_list.py`
- Test: `app/test/features/shopping_cart/models/shopping_list_item_test.dart`
- Test: `services/api/tests/api/v1/shopping_list/test_get_shopping_list.py` (if AC7
  triggers a change)

---

## Story bas-4: Dio interceptor — logout on refresh failure

As Leo,
I want any API call that can't refresh the auth token to send me to `/login` cleanly,
so that I don't get strange `DioException` errors scattered across random screens
when my session has truly expired.

### Acceptance Criteria

1. `api_client.dart` `onError` interceptor's 401 branch:
   - If refresh succeeds → retry with new token (status quo, unchanged).
   - If `AuthService.refreshToken()` returns `false` (refresh-unavailable, e.g. web,
     or refresh-token rejected by Auth0) → `await _authService!.logout()`, clear
     `_authToken`, continue to `handler.next(error)` so the caller sees the original
     401 and the app-level listener redirects to /login.
   - If `AuthService.refreshToken()` throws → same outcome as `false`: log the
     exception via `debugPrint`, call `logout()`, clear `_authToken`, fall through.
2. `_isRefreshing` guard stays — prevents recursive refresh loops.
3. No new logout path outside the interceptor. The existing `main.dart:156-180`
   startup-getMe retry-on-401 can optionally be simplified to just call the
   interceptor (via `apiClient.getMe()`) since the interceptor now handles the
   full 401 → refresh-or-logout flow centrally. Don't block this story on that
   cleanup — call it out in the story completion notes as a follow-up.
4. After logout-on-refresh-failure fires, the app-level listener (`AppShell` or
   similar) redirects to `/login` on `AuthService.notifyListeners()` — verify the
   existing listener already does this; if not, fix the missing piece.
5. Web platform: `refreshToken()` returns `false` on web (auth_service.dart:265).
   AC1 branch handles that → web users with expired tokens also land on /login,
   not on a DioException.
6. **No changes to screens** — verify by grepping `catch.*DioException` or similar
   to confirm existing screens don't double-handle 401 in a way that would fire
   before the interceptor. If a screen pre-empts the interceptor, note it but do
   NOT rip it out in this story (scope creep).
7. **Test coverage:**
   - Unit test with a mocked `AuthService.refreshToken()` returning `false` asserts
     `AuthService.logout()` was called.
   - Unit test with `refreshToken()` throwing asserts `logout()` was called.
   - Unit test with `refreshToken()` succeeding asserts `logout()` was NOT called.
8. **Manual dogfood check:** in dev, manually invalidate the stored refresh token
   (e.g., via device settings clear / secure-storage manipulation), foreground
   the app, trigger any API call, observe landing on `/login` without a
   red-error screen or DioException dialog.

### Key Files
- Modify: `app/lib/core/services/api_client.dart`
- Test: `app/test/core/services/api_client_test.dart` (extend existing — or add new
  if none exists for 401 refresh behavior).

### Follow-up (not blocking)
- Simplify `main.dart:156-180`'s hand-rolled 401-retry-on-startup now that the
  interceptor handles the full flow.

---

## Dependencies

- No dependencies on other epics.
- All four stories are independent; any order works.
- Recommended order for a single operator: bas-2 (trivial, fast morale win) → bas-1
  (single line) → bas-4 (interceptor) → bas-3 (largest, touches backend audit).
