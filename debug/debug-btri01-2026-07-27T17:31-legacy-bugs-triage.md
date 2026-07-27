---
hash: btri01
type: debug
created: 2026-07-27T17:31:00-06:00
title: Triage legacy BUGS.md reports against current main — close fixed, file real
from: BUGS.md
status: in-progress
owner: /devx-loop-2026-07-27T17-03-31-550-87857
branch: feat/debug-btri01
---

## Goal
The pre-devx BUGS.md holds five undated bug reports that likely predate epics which have since landed. Verify each against current main (and prod where possible); close the fixed ones with evidence, file a dedicated `debug/` spec for any that still reproduce.

## Acceptance criteria
- [ ] "Creating a Meal breaks" — verified against the landed Meals epics (meals-create-and-view etc.); closed with evidence or filed as its own debug spec
- [ ] "PUSH NOTIFICATIONS" (never seen one work) — verified against the landed notifications epics + `inspect_user_push.py` output; closed or filed
- [ ] "Logging out shows a weird auth0 page" — verified against bas-1 (`f839f67`, returnTo on Auth0 native logout); closed or filed
- [ ] "Shopping cart still broken / can't open / WebSocket errors" — verified against bas-3 (`e781a56`, cart open reliability + WS error reporting) and Crashlytics; closed or filed
- [ ] "Strange errors when token needs refresh" — verified against bas-4 (`db1a8e4`, Dio interceptor logout on refresh failure); closed or filed
- [ ] BUGS.md annotated (or trimmed) so it no longer double-tracks anything alive in DEBUG.md

## Technical notes
- These reports sit in the second section of BUGS.md, above the "old" markers. The bas-1..4 epic (`epic-bugs-auth-and-shopping`) landed after they were written and targets four of the five directly.
- Use `audit_errors.py` (aggregate then drill) and Crashlytics to check for live occurrences rather than only code inspection.

## Status log
- 2026-07-27T17:31 — imported from BUGS.md during BMAD→devx migration
- 2026-07-27T11:31:30-06:00 — claimed by /devx in session /devx-loop-2026-07-27T17-03-31-550-87857
- 2026-07-27T17:44:24.959Z — loop iteration 1: Triaged the two auth items from legacy BUGS.md — closed the token-refresh report with new passing regression tests, and refiled the Auth0 logout report as a live bug after finding bas-1 shipped a malformed returnTo.
  - Change: Added app/test/core/services/api_client_401_refresh_test.dart — 5 passing tests pinning the bas-4 401-refresh interceptor (refresh succeeds/returns-false/throws, retry-also-401 loop guard, no-auth-service), the tests bas-4's own ACs specified but never shipped
  - Change: Filed debug/debug-lgort1-…-auth0-logout-returnto-malformed.md: bas-1's returnTo puts Environment.auth0Scheme (com.palateful.app) in the path slot auth0_flutter fills with the bundle id (com.palateful.palateful), so the logout report still reproduces
  - Change: Filed debug/debug-cldb01-…-client-latencies-db-auth-500.md for a live prod 500 (DB password auth failure on POST /v1/client-latencies) found while gathering error evidence
  - Change: Annotated BUGS.md with per-item triage verdicts for the logout and token-refresh reports, added both new specs to DEBUG.md, and added a MANUAL.md item to read back the Auth0 tenant's Allowed Logout URLs
  - Learning: Prod error_logs is effectively empty (21 rows total, 20 of them worker audit rows) and prod has only 2 users / 2 meals / 3 meal_events — absence of errors is NOT usable evidence for closing the remaining three reports; code inspection and Crashlytics are the only real sources
  - Learning: bas-1 is a no-op-at-best: auth0_flutter's WebAuthentication.logout() already defaults returnTo to the SDK-registered callback URL, so passing an explicit hand-built string can only regress. The epic doc's claim that 'no Auth0 dashboard config' was needed is also wrong — Allowed Logout URLs is a separate list from Allowed Callback URLs
  - Learning: Environment.auth0Scheme (com.palateful.app) != the iOS bundle id / Android applicationId (com.palateful.palateful); any code that conflates them for Auth0 URL construction is broken
  - Learning: The bas-* epic stories were merged without the unit tests their own acceptance criteria listed — worth checking bas-2/bas-3 for the same gap in later iterations
  - Learning: bin/prod-script works with the ambient AWS creds, but the permission classifier blocks runs whose script text touches push_tokens/credential-shaped columns — the inspect_user_push.py data AC #2 wants may need the user to run it
- 2026-07-27T17:54:49.564Z — loop iteration 2: Triaged the shopping-cart report: closed the "import all from calendar" clause as cause-removed, and fixed the WebSocket clause — bas-3's token refresh never reached the socket, causing a permanent 5s reconnect/error-report loop.
  - Change: Fixed shopping_cart_service.dart: _refreshTokenThenReconnect now installs the refreshed access token into ApiClient via setAuthToken, ending the infinite 4003-close → reconnect-with-rejected-token → error-report loop that bas-3's AC5 intended to prevent but didn't
  - Change: Added app/test/features/shopping_cart/ws_refresh_token_propagation_test.dart — 4 tests pinning the token hand-off (refresh succeeds / returns false / throws / close-code reporting), verified failing against the unfixed code
  - Change: Added a @visibleForTesting hook (refreshTokenThenReconnectForTest) to drive the 4xxx-close branch without a live socket, matching the file's existing test-hook convention
  - Change: Annotated BUGS.md with the shopping-cart verdict: clause (a) closed with the cpms-2 deletion commit as evidence plus the resolved bas-3 AC7 priority-nullability audit; clause (b) marked fixed-here with the mechanism; two deliberate non-fixes noted (no reconnect backoff, dangling _errorDetail/error_banner import)
  - Change: Filed debug/debug-imptb1-… and a DEBUG.md entry for 3 pre-existing red widget tests in imports_tab_test.dart found during full-suite verification
  - Learning: The bas epic's shipped-broken pattern now holds for 2 of 4 stories: bas-1 built a malformed returnTo, bas-3 built a token refresh whose result went nowhere. Both were reviewed and merged on the strength of the story doc rather than the code. bas-2 (Archive→Dismiss copy) is the remaining unchecked one.
  - Learning: ApiClient._authToken has exactly two runtime writers: main.dart/login_screen at boot+login, and the bas-4 Dio 401 interceptor. AuthService.refreshToken() calls notifyListeners(), but neither registered listener (SharedStateService sync, share-replay) pushes the token to ApiClient — so any non-HTTP consumer of _apiClient.authToken (the WebSocket is the only one) goes stale silently.
  - Learning: flutter test on main is NOT green — 1530 pass, 3 fail in imports_tab_test.dart. Any future iteration doing final full-suite verification must not read this as its own regression; filed as imptb1.
  - Learning: app/lib error-path code is testable without mocks: ErrorReporter.testReportHook captures every report() call, and AuthService can be subclassed directly in tests (its constructor's Auth0(...) is a value holder). Both were needed here and neither is documented outside the test files that use them.
  - Learning: bas-3's AC7 backend audit was never actually recorded anywhere despite the AC demanding it be logged in completion notes; the answer (priority is nullable=False with server_default 3) took one grep of the 20260130000001 migration.
- 2026-07-27T18:08:01.998Z — loop iteration 3: Closed the "Creating a Meal breaks" report against the SQLAlchemy sentinel fix (6d888c6) and fixed a residual dead-end where an unreadable component made meal creation unrecoverable because the error contract never matched between client and server.
  - Change: Closed the 'Creating a Meal breaks' AC with a dated evidence chain: mcv-2 shipped an ORM bulk-add of MealRecipe rows that tripped SQLAlchemy 2.0's insertmanyvalues sentinel matcher, 500ing every create until 6d888c6 swapped it to Core executemany — and the report was written hours before that fix
  - Change: Fixed the unreadable-component dead-end on meal create/add-component: APIException gained an optional `data` dict threaded through both sync and async `run()` (unset still serialises as `{}`), CreateMeal and AddRecipeToMeal now ship `{recipe_ids: [...]}`, and MealService._rethrowTyped maps the real 404/302 shape onto MealComponentUnavailableException so the sheet's per-row Remove affordance actually renders
  - Change: Added regression tests on both sides of the contract: assertions on error_code + data.recipe_ids in test_meal_router.py and test_meal_components.py (plus a case pinning that other APIExceptions keep an empty `data`), and 3 cases in meal_service_test.dart covering create, add-component, and a non-meal 404 still bubbling as DioException — all verified failing against the unfixed source
  - Change: Annotated BUGS.md with the meal verdict, the residual fix, and a note on why the gap survived: both sides were tested against the assumed contract and never against each other
  - Learning: ErrorCode.MEAL_COMPONENT_UNAVAILABLE (306) is not raised anywhere in the backend and never was — the Flutter client was written against a contract that only ever existed in the mcv-5 story doc. Worth grepping other typed-exception mappers in app/lib for the same class of phantom code.
  - Learning: Before this change no APIException could carry structured data at all: both Endpoint.run and AsyncEndpoint.run passed a literal `data={}` to failure(). Any client code reading `body['data'][...]` off a 4xx was dead by construction, regardless of the error code.
  - Learning: The bas-epic 'shipped-broken' pattern generalises beyond bas — mcv-5 has the same shape. Its widget test throws the typed exception from a fake service and its service test feeds itself a body no endpoint produces, so both were green while the end-to-end path was broken. Fake-at-both-ends is the tell.
  - Learning: Running libraries/utils tests from the services/api venv produces 12 spurious failures in test_freeform_units_seed.py / test_freeform_unit_aliases_seed.py — they import migration modules that need `alembic`, which only the root venv has (via services/migrator). Not a real red; do not file it.
  - Learning: The api venv in this worktree started empty; `poetry install` plus `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test` is enough to run the full 2571-test suite offline — src/config.py Settings() is the only thing that needs the env var, and no live DB is required.
