<!-- refined via party-mode 2026-04-21 -->

# Epic: Performance — Flutter Client Polish

## Overview

The Phase-2 Flutter audit surfaced four client-side targets; party-mode (2026-04-21) validated them file-by-file and culled one as a phantom win:

- **`pfc-1` — redundant activity poll.** Today the app shell's `unread-count` poll and the Activity tabs' `/v1/activities` poll both fire on overlapping 30s cadences. When the Activity tab is focused, the shell call is 100% redundant. Consolidating into a single source cuts request volume roughly in half on that path without changing cadence.
- **`pfc-2` — image-caching sweep.** Party-mode grep proved the draft's premise wrong: every hot-path tile (home, meals, recipes, search) already uses `CachedNetworkImage`. Only `features/calendar/**` retains ~7 `Image.network` callsites, and the calendar isn't on the user's complaint path. **Cut pending user decision** (or rescope to calendar only — see Open Questions).
- **`pfc-3` — recipe detail keep-alive.** `recipe_detail_screen.dart` is a `StatefulWidget` that fetches via `apiClient.getRecipe` directly; there is no provider, so no cache, so reopening the same recipe within seconds refetches. Fix requires a real `ConsumerStatefulWidget` migration + family-keyed `AsyncNotifierProvider.family.autoDispose` + `ref.keepAlive()` + mutation invalidations at every edit/archive/favorite/rename site. Not a one-liner; scoped honestly.
- **`pfc-4` — home filter regression.** `_reapplyFilters` calls `_loadRecipes()` at line 488 of `home_screen.dart`, which is a clear regression against `perf-2` AC 3.
- **`pfc-5` (original) — cut.** Party-mode folded its regression-sweep ACs into `pfc-1`.

User locked "retune only redundant polls" in Phase 2 — imports 2s and admin logs 5s stay.

## Goal

- Zero redundant unread-count/activity calls when Activity tab is focused.
- Reopening the same recipe within its keep-alive window is zero-network.
- Changing a home filter is zero-network.
- No regression on imports cadence, admin logs cadence, or any UX cadence outside the named redundant path.

## End-User Flow

1. Leo opens the app. Home renders. The activity badge number comes from the existing `ActivityReadProvider` singleton (extended in this epic) — one poll, not two.
2. He taps Activity. The notifications tab reads from the same source — no extra fetch spins up.
3. He taps into a recipe, swipes to its meal, back to the recipe. The second render is instant — `AsyncNotifierProvider.family.autoDispose` served the cache and `ref.keepAlive()` kept it alive.
4. He edits the recipe's vibes. On save, the mutation site calls `ref.invalidate(recipeProvider(recipeId))`; the next read refetches with fresh data. No stale reads.
5. He changes the home meal-type filter. DevTools shows no network activity. Filter is in-memory over `_allRecipes`.
6. Imports remain 2s cadence; admin logs remain 5s. No changes to either.

## Frontend Changes

- **Modify**: the existing `ActivityReadProvider` (getIt singleton) — extend it to own both `unread-count` **and** the activity rows that the notifications tab / imports tab consume. Shell + both tabs read from the single source. (Party-mode decision: no Riverpod migration in the shell. Subject to user confirmation in Open Questions.)
- **Modify**: `notifications_tab.dart` — drop its local `Timer.periodic`; read rows from `ActivityReadProvider`.
- **Modify**: `imports_tab.dart` — drop its redundant shell-level poll consumer; keep its own 2s in-progress-import poll (separate short-lived path, out of scope).
- **Modify**: scaffold / bottom-nav widget — its 30s `Timer.periodic` moves into the single provider; widget just consumes `ValueNotifier`.
- **Modify**: `recipe_detail_screen.dart` — migrate `StatefulWidget` → `ConsumerStatefulWidget`. Create `recipeProvider = AsyncNotifierProvider.family.autoDispose<Recipe, String>(...)`. First line of `build()`: `ref.keepAlive()` scoped to this screen's lifetime.
- **New provider file** (if missing): `apps/flutter/lib/features/recipe/providers/recipe_provider.dart`.
- **Mutation invalidation sites (enumerated, hard AC)**: every writer to a recipe within `recipe_detail_screen.dart` (grep confirms `_saveVibes` at line 109, `_toggleFavorite` at 134), plus archive / delete / rename / update callsites across `apps/flutter/lib/features/recipe/**`. Full list captured in the story body pre-implementation.
- **Modify**: `home_screen.dart` — `_reapplyFilters` no longer calls `_loadRecipes()`. Filters apply in-memory over `_allRecipes`; `_loadRecipes()` fires only on `initState` + pull-to-refresh + mutation.
- **Calendar `Image.network` sweep** — **conditional on user decision**. If user picks "rescope pfc-2", swap all 7 `features/calendar/**` callsites to `CachedNetworkImage`, preserving `fit`/`width`/`height`/`errorBuilder`. If user picks "cut pfc-2", skip entirely.
- **No theme, router, or navigation changes.**

## Backend Changes

**None in code.** The `pfc-1` consolidation reduces request *frequency* (removes redundant unread-count when tab is focused) but doesn't change request shape; existing endpoints serve it. QA verifies the reduction via `analyze_latency.py --window 24h` delta on `GET /v1/activities/unread-count`.

## Infrastructure Changes

**None.** No env, no terraform, no CI. Compliant with inherited lock #5.

## Design Principles (refined via party-mode 2026-04-21)

- **Consolidate, don't slow down.** Only the **redundant** path is merged; imports 2s and admin logs 5s preserved per user decision.
- **One state, many consumers.** Shell badge, notifications tab, imports tab all read from the same source (existing `ActivityReadProvider`). The source owns lifecycle (timer, pause on background, resume on foreground) — unchanged from today.
- **Extend the existing pattern; don't rewrite.** Shell uses `getIt` + `ValueNotifier`. Adding Riverpod into that shell is out of scope; if it ever happens, it's its own epic.
- **Cache, don't break.** Recipe detail `keepAlive` is always paired with explicit `ref.invalidate` at every mutation site. Stale detail views are strictly forbidden.
- **`perf-2` is a contract.** `_reapplyFilters` calling `_loadRecipes()` is a regression against `perf-2` AC 3. Closing it is a bug fix, not new behavior.
- **Measure only what has a measurable backend delta.** `pfc-1` cites `analyze_latency.py --window 24h` delta on `GET /v1/activities/unread-count`. `pfc-3` and `pfc-4` use "zero network calls on the documented path" as the hard AC instead — synthetic p95 deltas on client-only changes aren't credible.
- **Draft correctness gate.** Re-read the target file before implementing. The party-mode discovery that `pfc-2` was phantom is proof-of-need.
- **One-commit landings for coupled consumers.** `pfc-1` lands shell + notifications tab + imports tab in one commit so there's no half-state where badge double-counts.

## File Structure

```
apps/flutter/lib/core/services/activity_read_provider.dart              (modify — extend to own rows, not just count)
apps/flutter/lib/core/widgets/scaffold_with_bottom_nav.dart             (modify — consume extended provider, drop local Timer)
apps/flutter/lib/features/activity/notifications_tab.dart               (modify — consume provider, drop local Timer)
apps/flutter/lib/features/activity/imports_tab.dart                     (modify — drop redundant shell consumer)
apps/flutter/lib/features/recipe/recipe_detail_screen.dart              (modify — StatefulWidget → ConsumerStatefulWidget, inject provider)
apps/flutter/lib/features/recipe/providers/recipe_provider.dart          (new)
apps/flutter/lib/features/home/home_screen.dart                         (modify — _reapplyFilters in-memory only)

# Conditional (only if user keeps pfc-2 as calendar sweep):
apps/flutter/lib/features/calendar/<various>.dart                       (modify — Image.network → CachedNetworkImage ×7)

apps/flutter/test/core/services/activity_read_provider_test.dart        (modify — one-timer invariant + consumer dedup)
apps/flutter/test/features/recipe/recipe_detail_cache_test.dart          (new — open-close-reopen + mutation-invalidates)
apps/flutter/test/features/home/home_filter_no_refetch_test.dart        (new)
```

File paths checked against repo layout — party-mode confirmed the app root is `apps/flutter/lib/`, not `app/lib/`.

## Stories

**`pfc-1-activity-hub-consolidation`** — extend `ActivityReadProvider` to be the single source for unread-count + activity rows. Shell + both tabs consume it. **Default-preferred approach: extend the existing getIt pattern; do NOT introduce Riverpod in the shell. (Subject to user confirmation in Open Questions.)**

ACs:
- `ActivityReadProvider` exposes both `unreadCount: ValueNotifier<int>` and activity-rows (shape TBD in story — probably `ValueNotifier<AsyncValue<List<Activity>>>` or similar).
- Exactly one `Timer.periodic` alive at any time (asserted via test double for `Timer`, or reflection).
- When Activity tab is focused, the shell's redundant unread-count fetch is not issued (tab's richer fetch supplies truth).
- Shell, notifications_tab, imports_tab consume the single source via existing `ValueListenableBuilder` / `ChangeNotifier` pattern.
- Pull-to-refresh on either tab invalidates the provider and refetches once.
- **One-commit landing**: shell + notifications_tab + imports_tab ship in the same PR / commit. No partial rollout.
- QA walkthrough: `analyze_latency.py --window 24h` output pre/post shows `GET /v1/activities/unread-count` call count measurably reduced.
- Sentinel log line `[activity-read] tick` fires every 30s during manual walkthrough; QA asserts presence in DevTools console.
- Max 3 widget tests.

**`pfc-2`** — **CUT pending user decision** (see Open Questions). If rescoped:

**`pfc-2-calendar-image-cache-sweep`** — swap `features/calendar/**` `Image.network` to `CachedNetworkImage`.

ACs:
- Grep `Image.network(` under `apps/flutter/lib/features/calendar/` is empty post-change (7 current callsites → 0).
- Each swap preserves `width` / `height` / `fit` / `errorBuilder` / `placeholder`.
- Smoke check (not golden): calendar day sheet renders without layout overflow; errorBuilder path still triggers on 404.
- No widget tests required (smoke + manual walkthrough sufficient).

**`pfc-3-recipe-detail-keep-alive`** — migrate recipe detail to a provider with keep-alive + mutation invalidation.

ACs:
- **Pre-implementation**: enumerate EVERY recipe-mutation site that must fire `ref.invalidate(recipeProvider(recipeId))`. Grep `updateRecipe\|archiveRecipe\|deleteRecipe\|_saveVibes\|_toggleFavorite` under `apps/flutter/lib/features/recipe/`. List sites in the story body before coding.
- `recipe_detail_screen.dart` converts from `StatefulWidget` → `ConsumerStatefulWidget`.
- `recipeProvider = AsyncNotifierProvider.family.autoDispose<Recipe, String>(...)`; first line of `build()` calls `ref.keepAlive()`.
- Every mutation site fires `ref.invalidate(recipeProvider(recipeId))` post-mutation.
- Widget test 1: open recipe A, back out, reopen within 5s — zero `GET /v1/recipes/{id}` dispatched (mock `api_client`).
- Widget test 2: open recipe A, edit vibes, back out, reopen — GET IS dispatched; response contains the edited vibe.
- Widget test 3: open recipe A, wait simulated 6 min (fake clock), reopen — GET IS dispatched.
- Max 3 widget tests; story caps here.

**`pfc-4-home-filter-no-refetch`** — close the `perf-2` AC-3 regression.

ACs:
- `_reapplyFilters` at `home_screen.dart:488–491` does not call `_loadRecipes()`.
- All filter changes (meal type, vibe, sort) apply in-memory over `_allRecipes`.
- `_loadRecipes()` runs only on `initState` + pull-to-refresh + mutation.
- Widget test: change the meal filter; `mockApiClient.verifyNever(() => .getRecipes(any))` (single test sufficient).
- Hard AC: "zero network calls on the documented path" — no p50/p95 synthetic delta needed.

## Dependencies

- **Blocks**: nothing.
- **Blocked by**: `pim-1` (soft — `pfc-1` walkthrough cites `analyze_latency.py`).
- **Internal**: none of pfc-1/2/3/4 blocks the others. Ship in any order.
- **Shares with**: nothing.

## Inherited Decisions Applied

From epic-perf-infra-and-measurement:
1. Pool arithmetic — N/A.
2. `analyze_latency.py --window 24h` baseline — applied to `pfc-1` only (the only story with measurable backend delta). `pfc-3` / `pfc-4` use "zero network calls" AC instead.
3. Redis JWKS-only — N/A.
4. `CREATE INDEX CONCURRENTLY` — N/A (no DDL).
5. No terraform — compliant.
6. Fail-open — N/A.

From epic-perf-backend-query-tuning:
1. `count_queries` helper — N/A here; if we needed a Flutter equivalent it'd be its own scope.
2. One-liner fixes need only p50/p95 — adapted: `pfc-1` uses `analyze_latency.py`; `pfc-3`/`pfc-4` use "zero network calls."
3. Per-story migrations — N/A.
4. **Draft correctness gate** — applied ruthlessly. Discovered `pfc-2` was phantom; cut pending user decision.

## Locked Decisions (terminal — no sibling epic to propagate to)

1. **Extend `ActivityReadProvider` (getIt); do not introduce Riverpod in the shell in this epic.** Subject to user confirmation.
2. **`pfc-1` lands in one commit across shell + both tabs.** No half-state.
3. **Widget tests capped at 3 per story** (Flutter test runtime is a tax).
4. **Client-only stories (`pfc-3`, `pfc-4`) replace p50/p95 ACs with "zero network calls."**
5. **Draft correctness gate re-reads the target file before implementation.**
6. **Mutation invalidation sites enumerated in the story body before implementation.** No grep-after-the-fact.

## Risks + Mitigations

- **Phantom `pfc-2` wasting a sprint slot**: decision at party-mode close (see Open Questions).
- **Shell+tab dual-poll during `pfc-1` rollout**: one-commit AC; sentinel log line in walkthrough.
- **`pfc-3` stale-data bug on mutation**: enumerate-invalidation-sites AC + integration test for edit→reopen.
- **`pfc-3` refactor scope creep**: `ConsumerStatefulWidget` migration scope locked in the story's file list; don't treat as a one-liner.
- **`pfc-4` regression recurrence**: mock-apiclient test is strict; any future `_reapplyFilters` → `_loadRecipes()` re-entry fails CI.
- **Widget test runtime creep**: 3/story cap (above).

## Open Questions for the User — RESOLVED (2026-04-21)

1. **`pfc-2` fate** — **CUT entirely**. All hot tiles already use `CachedNetworkImage`; the 7 calendar callsites are off the complaint path. Epic 3 ships with 3 stories (pfc-1, pfc-3, pfc-4).
2. **`pfc-1` shape** — **Extend existing `ActivityReadProvider`** (getIt + `ValueNotifier`). No Riverpod migration in the shell in this epic.
