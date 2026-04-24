<!-- refined via party-mode 2026-04-23 -->

# Epic: Performance — Frontend Fetch Minimization

## Overview

The Phase-2 audit (2026-04-23) enumerated every HTTP call issued by every Flutter screen on mount and under steady state. The finding: the `epic-perf-flutter-client-polish` round (2026-04-21) closed the two highest-volume wins (activity-poll consolidation + recipe-detail keep-alive) but left a long tail of duplicate, N+1, and wide-hydration calls. The user observed the tail directly in Chrome DevTools while using Flutter web. This epic closes that tail.

Concrete targets surfaced by the audit, with file:line citations:

1. **Duplicate `getRecipeBooks()` across 7+ surfaces.** Home (`app/lib/features/home/providers/home_content_provider.dart:102`), Recipe Detail (`app/lib/features/recipes/recipe_detail_screen.dart`, two sites), and every import entry screen (5 sites under `app/lib/features/recipes/add_recipe/`) call `apiClient.getRecipeBooks()` directly. No shared Riverpod provider. Every session hits the endpoint 6–8 times unnecessarily.
2. **N+1 `listImportItems(jobId)` in Activity Hub.** `app/lib/features/activity/imports_tab.dart:134` iterates import jobs and calls `listImportItems(jobId)` once per job. `app/lib/features/activity/providers/imports_see_all_provider.dart:129` does the same on the See-all pagination path. Ten visible jobs ⇒ ten serial GETs on every tab open.
3. **Activity-poll + MutationBus overlap.** `activity_read_provider.dart:222` fires a 30s tick; `imports_tab.dart:97-101` also listens on MutationBus and silent-reloads on every `ImportItemDismissed` / `ImportItemRetried`. During an active import session both fire simultaneously.
4. **Notifications-tab double-fetch on mount.** `notifications_tab.dart:80` calls `getActivities()` followed by `refreshUnreadCount()` — two round-trips for one piece of UI state. The count is already derivable from the list response.
5. **`listMealsInBook()` on book detail mount.** `recipe_book_detail_screen.dart` fires the fetch as soon as the screen renders, even when the user is just scanning books — not inside the Meals tab.
6. **Session caches with no TTL.** Providers marked `ref.keepAlive()` (books, profile, home, pantry, prefs) never stale. A 2-hour session still reads data from first mount.
7. **16 uncached `Image.network(` sites.** `features/calendar/**` has 9 (confirmed by grep), `features/recipes/**` has 7 more. Every scroll re-downloads.
8. **No Dio dedup.** Parallel callers issuing the same GET both round-trip.
9. **Fat detail payloads.** `GET /v1/recipes/{id}` returns ingredients + steps + comments + versions in one blob. `GET /v1/import-items/{id}` includes the full `parsed_recipe` JSON unconditionally.

The fix philosophy: **cache once, share widely, lazy-fetch, and trim what you don't render.** No behavior changes — same data, same screens, same user flows.

## Goal

- At least **30% fewer HTTP GETs** on the canonical dogfood flow (Home → Activity Hub → Recipe detail → back), measured via Chrome DevTools HAR.
- Zero duplicate `getRecipeBooks()` calls per session. Single source of truth.
- Activity Hub fetches all visible import items in **one** round-trip regardless of job count.
- Notifications tab opens with **one** network call, not two.
- Session caches revalidate on TTL expiry (10 min default for stable reference data, 5 min for content) without breaking MutationBus invalidation.
- No user-visible behavior change. Regression budget: zero.

## End-User Flow

1. Leo opens the app. Home renders. One `GET /v1/recipe-books` is issued (via shared provider); no second call from recipe detail when Leo taps a recipe.
2. Leo opens Activity Hub. One `GET /v1/import-items?job_ids=a,b,c` returns all imports across all visible jobs — not 10 serial calls. One `GET /v1/activities` returns the list with `unread_count` embedded; no separate `/unread-count` fetch.
3. Leo dismisses an import. MutationBus fires; Activity Hub silently reloads. The 30s poll tick that would have fired 7 seconds later is suppressed (dedup window respected).
4. Leo scrolls through his recipe book grid. No `listMealsInBook()` calls fire — meals load only when he taps into a book's Meals tab.
5. Leo opens a recipe. The detail payload arrives without versions + comments. Tapping the Versions tab triggers the lazy fetch. Ingredients + steps are in the initial payload as before.
6. Leo scrolls the calendar. Meal photos load from local cache on revisit — no network. Same for recipe photos on recipe screens.
7. Leo's session lasts 45 minutes. The recipe-books provider silently revalidates 10 minutes after last read; he never sees stale data, never sees a spinner.
8. Two parallel parts of the UI request the same endpoint in the same 300ms; Dio coalesces into one round-trip.

Net visual experience: identical to today. Network tab dramatically quieter.

## Frontend Changes

- **New** `app/lib/features/recipe_books/providers/recipe_books_provider.dart` — single `AsyncNotifierProvider.family.autoDispose<List<RecipeBook>, void>` with `ref.keepAlive()`, TTL 10min, MutationBus subscription on `RecipeBookCreated/Updated/Deleted/Archived` events.
- **Modify** all 7+ `apiClient.getRecipeBooks()` callsites to read from the provider. Grep baseline captured in story AC.
- **Modify** `app/lib/features/activity/imports_tab.dart:134` — replace per-job loop with single `apiClient.listImportItemsBatch(jobIds: [...])` (or `listImportJobs(include: 'items')` — party-mode decides).
- **Modify** `app/lib/features/activity/providers/imports_see_all_provider.dart:129` — same replacement on pagination path.
- **Modify** `app/lib/features/activity/providers/activity_read_provider.dart:222` — add `_lastMutationReloadAt` timestamp; tick suppresses reload if bus-driven reload happened within 10s.
- **Modify** `app/lib/features/activity/notifications_tab.dart:80` — delete the `refreshUnreadCount()` call; read the count from the list response's new `unread_count` field.
- **Modify** `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — remove eager `mealsByBookProvider(bookId)` fetch from initState; trigger from Meals tab's `onTap` / `TabController.listener`.
- **Modify** `app/lib/core/state/` — generic `maxAge` helper that wraps `ref.keepAlive()` with a revalidation `Timer`. Opt-in per provider via constructor param.
- **Apply TTL** to `recipeBooksProvider` (10m), `profileProvider` (10m), `notificationPrefsProvider` (10m), `homeContentProvider` (5m), `defaultPantryProvider` (10m).
- **Modify** `app/lib/core/services/api_client.dart` (or Dio setup under `app/lib/core/di/`) — new `RequestDedupInterceptor` that coalesces in-flight identical GETs (method + path + query + Authorization subject) in a 300ms window. Writes pass through.
- **Modify** every `Image.network(` site under `app/lib/features/calendar/**` (9 sites — cited by audit) and `app/lib/features/recipes/**` (7 sites) to `CachedNetworkImage(...)`, preserving `fit` / `width` / `height` / `errorBuilder`.
- **New** `tools/image-network-check.sh` — bash grep guard (mirrors `tools/no-silent-catch-check.sh`) that fails CI if a file under `app/lib/features/` contains `Image.network(` outside an allowlist (e.g., public-share landing pages that intentionally skip cache).
- **Modify** `app/lib/features/recipes/recipe_detail_screen.dart` — strip versions + comments from initial fetch; lazy-load when respective tabs open. Existing `recipeProvider` keep-alive unchanged.

## Backend Changes

- **Modify** `services/api/src/api/v1/user_activity/list_activities.py` — add optional `unread_count` field on the `ListActivities.Response`, computed with the allow-list filter already used by the unread-count endpoint. Zero regression: old clients ignore the new field.
- **Add** `GET /v1/import-items?job_ids=<comma-separated-uuids>` OR `GET /v1/import-jobs?include=items` — party-mode decides the shape in Phase 6. Either is purely additive. If the `?include` pattern wins, `GET /v1/import-jobs` stays default-lean; opt-in only.
- **Modify** `services/api/src/api/v1/recipe/get_recipe.py` — accept `?include=ingredients,steps,comments,versions` (additive, default = today's shape). When `versions` or `comments` is absent from the include list, the field is omitted from the response (not null — truly absent). Tests pin both code paths.
- **Modify** `services/api/src/api/v1/import_item/get_import_item.py` — `?include=parsed_recipe` (default false). `parsed_recipe` is the heavy JSON; it's only needed by the telemetry viewer.
- **No** database schema changes. All endpoints are read-side. All changes are additive query-parameter behavior.

## Infrastructure Changes

- **None.** No terraform, no new env vars, no new secrets, no CI-workflow changes (the image-check script runs under the existing lint/test job).

## Design Principles (refined via party-mode 2026-04-23)

- **Share, don't duplicate.** One Riverpod provider per resource; every surface reads from it. Service-layer API calls (e.g., `recipeBookService.getRecipeBooks()`) are only legitimate inside the provider — grep-enforced.
- **Lazy everything that isn't visible.** Tabs fetch on selection, not on parent mount. Response fields are omitted unless the caller asks via `?include=`.
- **Additive backend changes, lenient defaults.** Every new query parameter keeps today's default response shape. Old clients see zero diff until the follow-up release flips the default (tracked separately as `ffm-9-followup`).
- **MutationBus is authoritative; TTL is the backstop.** Local + WS-lowered events invalidate first; TTL catches only the case where neither fired (another device, auth refresh, cold resume). TTL revalidation never flips UI to `AsyncLoading` — in-place replace on success, `ErrorReporter.log` on failure.
- **Dedup is a safety net, not architecture.** Shared providers solve the real problem; the Dio interceptor catches accidental parallel paths from separate entry points. Dedup cache key is `method + path + sorted-query + Authorization-header-hash` (hash, not subject — avoids JWT-parsing dependency). Writes always pass through.
- **CI enforces every invariant.** Grep guards for `Image.network(`, `apiClient.getRecipeBooks()` outside the provider, `refreshUnreadCount()`. Every guard mirrors `tools/no-silent-catch-check.sh` (bash-3 portable, `file:lineno:rationale` allowlist format).
- **Field-absence means absent, not null.** Omitted `?include=` fields are dropped from the JSON entirely via FastAPI `response_model_exclude_unset`. JSON Schema consumers distinguish "not requested" from "explicitly null."
- **Measure before and after.** Every story pins a DevTools HAR (or equivalent) pre/post on the canonical dogfood flow. No measurement = no merge.
- **Deploy backend first for field adds; version-gate frontend.** `ffm-4` and `ffm-9` backend ships before the Flutter client removes the old call path. Flutter retains fallback for one release so web + mobile can deploy independently.
- **Coverage is non-negotiable.** `services/api` pins 100%. Every new `?include=` branch ships with a test for both code paths in the same PR.

## File Structure

```
app/lib/features/recipe_books/providers/recipe_books_provider.dart           (new — shared provider, TTL, MutationBus)
app/lib/features/home/providers/home_content_provider.dart                   (modify — read via provider, not apiClient directly)
app/lib/features/recipes/recipe_detail_screen.dart                           (modify — read via provider; lazy versions/comments)
app/lib/features/recipes/add_recipe/*.dart                                   (modify — 5 screens use provider)
app/lib/features/activity/imports_tab.dart                                   (modify — batch endpoint; bus/tick dedup)
app/lib/features/activity/providers/imports_see_all_provider.dart            (modify — batch endpoint)
app/lib/features/activity/providers/activity_read_provider.dart              (modify — _lastMutationReloadAt + 10s floor)
app/lib/features/activity/notifications_tab.dart                             (modify — single-fetch; read unread_count from list)
app/lib/features/recipe_books/recipe_book_detail_screen.dart                 (modify — lazy listMealsInBook)
app/lib/core/state/provider_ttl.dart                                         (new — maxAge helper)
app/lib/core/services/api_client.dart                                        (modify — RequestDedupInterceptor wired)
app/lib/core/services/request_dedup_interceptor.dart                         (new)
app/lib/features/calendar/**/*.dart                                          (modify — 9 Image.network → CachedNetworkImage)
app/lib/features/recipes/**/*.dart                                           (modify — 7 Image.network → CachedNetworkImage)
tools/image-network-check.sh                                                 (new — grep guard)

services/api/src/api/v1/user_activity/list_activities.py                     (modify — optional unread_count field)
services/api/src/api/v1/import_item/list_import_items.py                     (modify — ?job_ids batch filter)
services/api/src/api/v1/recipe/get_recipe.py                                 (modify — ?include query param)
services/api/src/api/v1/import_item/get_import_item.py                       (modify — ?include=parsed_recipe)
services/api/tests/api/v1/*                                                  (modify/new — pin new + old response shapes)

tools/no-silent-catch-check.sh                                               (reference only — pattern to follow)
```

## Story List (draft — ACs firmed up per-story)

### ffm-1 — Shared recipeBooksProvider + 10-callsite migration
**Shape:** `FutureProvider.autoDispose<List<RecipeBook>>` with `ref.keepAlive()` — matches canonical pattern in `app/lib/core/state/README.md:55-85` (mirrors `homeContentProvider`). `AsyncNotifierProvider` deferred to a follow-up when optimistic mutation-patching is actually needed.
**Callsite inventory (10 total, verified by grep):** home (`home_content_provider.dart:102`), recipe detail (`recipe_detail_screen.dart` × 2 — lines ≈ where draft cited + line 467), recipe books screen (`recipe_books_screen.dart:41`), recipe book detail (`recipe_book_detail_screen.dart:425`), and 5 import entry screens under `app/lib/features/recipes/add_recipe/`. Service-layer `recipe_book_service.dart:26` stays — that IS the legitimate wrapper.
**AC:** (1) new `recipeBooksProvider` exists with TTL+MutationBus; (2) grep on `app/lib/features/` for `apiClient.getRecipeBooks()` and `recipeBookService.getRecipeBooks()` returns zero hits outside the provider file + generated mocks; (3) home + recipe detail + books-list + book-detail + 5 import entry screens render identical data to pre-change; (4) session-log during a canonical flow shows exactly one `GET /v1/recipe-books` call; (5) QA walkthrough pins DevTools HAR pre/post.

### ffm-2 — Batch import-items endpoint (`?job_ids=`) + Flutter caller
**Shape locked:** `GET /v1/import-items?job_ids=<csv>` — additive filter on existing endpoint. Not `GET /v1/import-jobs?include=items` (bigger blast radius, response shape change, pagination semantics already live on the list endpoint).
**Response shape:** flat list; each item carries its `job_id`. Callers group client-side.
**Cap:** 50 UUIDs per call; overflow returns 400 with a clear message.
**AC:** (1) endpoint accepts `?job_ids=a,b,c` (CSV, max 50); (2) single-value `?job_ids=X` returns same shape as today's `?job_id=X` single-filter response; (3) imports_tab + imports_see_all_provider issue at most one GET per refresh; (4) integration test with 12 import jobs confirms single round-trip and `apiClient.listImportItems` called exactly once; (5) overflow (51 UUIDs) returns 400; (6) existing single-job caller tests still pass.

### ffm-3 — Activity poll short-circuits on recent MutationBus reload
**Locked:** floor lives in the **poll**, not the mutation. Mutation path stays dumb-and-cheap; poll reads `_lastMutationReloadAt` and short-circuits.
**AC:** (1) `_lastMutationReloadAt` timestamp lives on `ActivityReadProvider`; (2) 30s tick short-circuits if bus-driven reload fired within 10s; (3) dedup tested with fake-clock helper (10 ticks, 3 bus-driven reloads interleaved, assert exactly 7 network round-trips); (4) no regression on imports 2s in-progress poll (out of scope — preserved per user lock); (5) QA walkthrough: trigger MutationBus `ImportItemDismissed` just before a scheduled tick, verify tick skipped.

### ffm-4 — Notifications tab single-fetch-on-mount
**Locked:** `unread_count` is a **snapshot**, computed inline from the same filtered query used by the list endpoint, in the same transaction — no drift risk. Documented on response model: "count is accurate as-of this response's rows."
**Deploy order:** backend ships first. Flutter retains `refreshUnreadCount()` fallback for one release to survive the web+mobile independent-deploy window.
**AC:** (1) `ListActivities.Response` has nullable `unread_count` field; (2) `notifications_tab.dart` reads the count from the list response; `refreshUnreadCount()` call is version-gated (keeps fallback if field is null); (3) badge count updates correctly on first mount, pull-to-refresh, and poll tick; (4) backend snapshot tests updated for new field; 100% coverage preserved; (5) Flutter test confirms one network call on mount when field is populated, two when null (fallback path).

### ffm-5 — Lazy listMealsInBook on book detail
**UX note:** first Meals-tab tap now shows a brief skeleton loader (~200-300ms on cache-warm path). This is new user-visible behavior — not a regression, but surface it in the walkthrough.
**AC:** (1) book detail screen does not fetch meals on initState; (2) fetch fires only when Meals tab becomes selected (`TabController.listener`); (3) Meals tab shows existing skeleton loader on first tap; loader disappears within 300ms on cache-warm path; (4) no regression on rendering once data arrives; (5) test pins call-count = 0 until tab is focused.

### ffm-6 — Session-cache TTL helper + opt-in for 5 providers
**Locked signature:** `keepAliveWithTtl(Ref ref, {required Duration maxAge, required Future<void> Function() revalidate})`. Revalidation fires background fetch; state stays populated (no `AsyncLoading` flip); swap value in place on success; `ErrorReporter.log` + keep stale on failure.
**AC:** (1) `provider_ttl.dart` helper exposes the signature above; (2) `recipeBooksProvider` (10m), `profileProvider` (10m), `notificationPrefsProvider` (10m), `homeContentProvider` (5m), `defaultPantryProvider` (10m) opt in; (3) revalidation is silent (no UI spinner, no state flip); (4) MutationBus invalidation path unchanged; (5) test pins TTL behavior with fake-clock including silent-drop on revalidate failure.

### ffm-7 — Dio request-dedup interceptor
**Key:** `method + path + sorted-query + Authorization-header-hash` (SHA256 of header value — NOT JWT-parsed subject). Authorization-switch (logout mid-session) correctly produces a different key.
**CancelToken handling:** the interceptor holds a reference-counted upstream token. First caller's cancel does NOT tear down the upstream unless all coalesced subscribers have cancelled. Documented footgun in the interceptor doc comment.
**Escape hatch:** `Options(extra: {'no_dedup': true})` skips dedup entirely — used by telemetry writes and any caller that needs independent semantics.
**AC:** (1) interceptor coalesces identical GETs within 300ms; (2) dedup key includes Authorization-header-hash; auth-switch race test pins separate round-trips for different users; (3) writes (POST/PUT/PATCH/DELETE) pass through; (4) on upstream error, all coalesced callers see the same error; (5) `CancelToken` reference-counting test: caller A cancels, caller B completes successfully; (6) `no_dedup` extra bypasses interceptor.

### ffm-8 — Image.network → CachedNetworkImage sweep
**Scope correction (from party-mode grep):** actual counts are 9 calendar + 15+ across `features/recipes` + `features/meals` + `features/home` + `features/search` + `features/profile`. Full sweep target is `app/lib/features/**`.
**Allowlist day-one entries:** public share pages (`public_recipe_screen.dart`, `public_meal_screen.dart` — one-shot visitors get no cache benefit); any `test/` file.
**AC:** (1) all `Image.network(` sites under `app/lib/features/` converted to `CachedNetworkImage` with identical `fit`/`errorBuilder`/`width`/`height`, EXCEPT the day-one allowlist; (2) `tools/image-network-allowlist.txt` committed with documented rationale per entry (`file:lineno:rationale`); (3) visual regression pass: calendar + recipe + home + meals + search + profile flows render identically; (4) second-visit image loads from cache (offline test: disconnect, reload screen, image still displays).

### ffm-11 — CI wiring for `tools/image-network-check.sh`
**Split out from ffm-8** because the original Infrastructure claim "no CI-workflow changes" is wrong — a CI guard requires an explicit workflow invocation alongside the silent-catch check.
**AC:** (1) `tools/image-network-check.sh` mirrors `tools/no-silent-catch-check.sh` exactly (bash-3 portable, same allowlist format); (2) script invocation added to existing lint/test GitHub Actions workflow; (3) intentional-regression test: add `Image.network(` to a non-allowlisted file, verify CI fails with clear message; (4) scope of grep = `app/lib/features/**` (not `app/lib/**` — excludes core DI wiring).

### ffm-9a — Recipe-detail `?include=` (lenient default)
**Locked:** default WITHOUT `?include=` keeps today's full shape (versions + comments included). Flutter explicitly sends `?include=ingredients,steps`. Omitted fields are **absent** from JSON (not null) via FastAPI `response_model_exclude_unset`.
**AC:** (1) `GET /v1/recipes/{id}` accepts `?include=ingredients,steps,comments,versions`; (2) default (no include) returns today's full shape unchanged; (3) Flutter detail screen sends `?include=ingredients,steps`; (4) versions + comments tabs lazy-fetch with their own calls when selected; (5) backend tests pin BOTH code paths (lenient default + explicit include) — 100% coverage preserved on the new branch.

### ffm-9b — Flip `GET /v1/recipes/{id}` default to lean (one release soak after ffm-9a)
**User-locked (2026-04-23):** stays in this epic, lands in the next release after `ffm-9a` (one-release soak window). No separate follow-up epic.
**AC:** (1) default response (no `?include=`) now omits `versions` and `comments`; (2) clients that pre-date `ffm-9a` and relied on the old shape must have shipped their `?include=` upgrade first — validated via Flutter version-bump check; (3) release notes flag the default flip; (4) tests updated to pin new default + explicit-include paths; coverage 100%; (5) rollback is a one-line env-var flag (`RECIPES_LEAN_DEFAULT=false`) flippable via ECS task-def if a hidden consumer surfaces; (6) follow-up AC at +30 days: grep-audit `error_logs` for `KeyError: 'versions'` etc. to confirm zero broken consumers, then delete the env-var fallback.

### ffm-10 — Import-item `?include=parsed_recipe` trim
**AC:** (1) `GET /v1/import-items/{id}` accepts `?include=parsed_recipe`; (2) default response omits the heavy JSON; (3) telemetry viewer screen sends `?include=parsed_recipe`; (4) all other callers (activity feed, dashboard) drop to the lean shape; (5) tests pin both code paths.

## Dependencies

- **None hard.** All stories can land independently under party-mode staging decisions (e.g., backend `ffm-2` batch endpoint ships before the Flutter caller, same deploy or prior).
- **Soft internal**: `ffm-1` before every downstream migration that reads `recipeBooksProvider`; `ffm-6` TTL helper before any provider opts in; `ffm-4` backend field add before the frontend drops the second call.
- **Coordination with in-flight**: `epic-bugs-auth-and-shopping` touches some of the same auth/interceptor paths. Merge order: whichever lands first updates the other's conflict points.

## Open Questions for the User (post-party-mode)

1. **`ffm-9-followup` (flip lean default) — this epic or a separate follow-up?** Recommendation: follow-up in the next release. Clean rollout, lets one release soak. Confirm.
2. **Measurement protocol pre-`bin/perf-audit`.** `bin/perf-audit` lives in `epic-perf-debug-tooling`. Options for THIS epic's "30% fewer GETs" proof: (a) manual Chrome DevTools HAR capture on a documented flow, saved as `reports/ffm-baseline.har` + `ffm-post.har` and diffed; (b) wait for `bin/perf-audit` and block this epic behind `ptd-4`. Recommendation: (a) — manual HAR keeps this epic unblocked.
3. **`ffm-2` cap = 50 `job_ids`** — enough for power users? Alternative: add `?cursor=` paging. Recommendation: 50 is more than enough for expected job counts per user; defer paging.
4. **`meal_autocomplete_field.dart` cache behavior during typing flux.** Cache broken URLs with a negative-cache TTL (e.g., 30s) or re-fetch on every keystroke? Recommendation: negative-cache 30s — avoids hammering the CDN for URLs that will stay 404.
5. **Dedup exception for telemetry.** `/v1/client-latencies` POSTs (from sibling epic `cla-*`) are writes — interceptor already skips writes. Confirm no exception needed.

