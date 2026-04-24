<!-- refined via party-mode 2026-04-22 -->
# Epic — Reactive Foundation: MutationBus + Home + Imports

**Planned**: 2026-04-22
**Scope split**: Foundation epic — introduces the cross-cutting reactivity primitive and kills the two most-complained dogfood bugs (add-recipe invisible on Home; dismiss-import visible until refresh). Blocks two per-domain migration epics (`epic-reactive-migration-meals-calendar`, `epic-reactive-migration-books-profile-pantry-and-polish`).
**Status**: backlog

## Overview

Flutter app is ~50/50 reactive today. WS-driven surfaces (shopping list, shared recipe-book recipe CRUD) work instantly; imperative `setState`-in-`initState` surfaces (Home grid, Imports tab, meals, calendars, profile, pantry) go stale until a manual pull-to-refresh. Root gap: no cross-cutting mutation event primitive — every mutation site individually decides which providers to invalidate, and most don't.

This epic ships the **MutationBus** — a single typed event stream with broadcast semantics, a documented emit convention for mutation handlers (service-layer, see "Locked decisions" below), and a documented subscribe convention for list/detail providers. It migrates the two worst-regression surfaces (Home grid + Imports tab) end-to-end to prove the pattern, fixes two backend response-shape gaps that block client-side patching, and ships a regression-test kit (widget tests that assert cross-surface re-render on mutation).

The migration epics that follow (meals/calendar; books/profile/pantry) are straight repeats of this pattern on other features. By the end of this epic, the named dogfood complaints are closed and the pattern is established for the rest.

## Goal

**Outcome**: Every recipe mutation and every import mutation propagates to every UI surface that displays that data, without a manual refresh, backed by a reusable cross-cutting primitive the rest of the app can adopt.

**Single measurable proof (PM)**: Leo runs one scripted dogfood session after ship — (a) paste URL → save recipe → pop back → Home tile visible without pull-to-refresh; (b) open Imports tab → dismiss a failed import → badge count decrements and row is gone without pull-to-refresh — both observed on one device within 60s. If this scripted session passes, the epic is "done" from the end-user vantage point. This is distinct from the CI-level proof below.

**CI-level proof**: Two regression widget tests land in `app/test/` — `home_screen_reactivity_test.dart` and `import_history_reactivity_test.dart` — and both are green in the commit that closes the epic. See `rf-6` ACs for the exact assertions.

## Locked decisions for downstream epics

These are the foundation-level decisions finalized in party-mode. The two migration epics (`meals-calendar`, `books-profile-pantry`) inherit them as-is; **do not re-litigate** per epic.

1. **Service-layer emits, not UI-handler.** `RecipeService.createRecipe(...)` is the single emit point for `RecipeCreated`. Rationale (Frontend + Architect): (a) guaranteed single source of truth — no missed emits when a new UI caller forgets; (b) WS-lowering adapter and local mutation converge on the same code path; (c) if a UI handler needs screen-specific context, it emits a **second**, scoped event (e.g. `HomeTileHighlighted`) on a separate bus — not a replacement. Resolves draft open question #2.
2. **Subscribers use `ref.listen(mutationBusProvider, (prev, next) => ...)`** and invalidate via `ref.invalidateSelf()` for `autoDispose` providers they own, or `ref.invalidate(providerInstance)` for family members they don't. `ref.refresh(...)` is reserved for user-intent (pull-to-refresh). This distinction is in the README.
3. **Bulk mutations emit a first-class bulk event AND suppress per-item events.** Bulk-archive of 50 recipes emits exactly one `RecipeBulkArchived(recipeIds: [...], bookId)`. Subscribers that care handle both singular and bulk types. No 100ms coalescer in subscribers for this epic — explicit bulk events are simpler and deterministic. Resolves draft open question #1.
4. **100ms subscriber coalescing is the fallback for non-bulk event floods** (e.g. rapid WS frames from a partner typing across many recipes in <1s). Implemented inside the subscriber, not the bus. Spec lives in `rf-1` AC and `README.md`.
5. **MutationBus is backed by a long-lived singleton `StreamController.broadcast()`**, wrapped in a `Provider<Stream<MutationEvent>>` (non-autoDispose) so the underlying controller is never closed mid-lifecycle. The previously drafted `StreamProvider.autoDispose` was a Riverpod anti-pattern for a global broadcast bus — autoDispose would tear down the subscription the moment the last widget unmounted, dropping any event that arrived in the microtask gap. (Frontend raised this; now locked.)
6. **Reconcile-only for v1.** Existing optimistic `setState` paths (dismiss, favorite, check-off) stay. No new optimistic paths introduced in this epic or in either migration epic. Optimism-everywhere is a separate future polish epic.
7. **Toast + automatic rollback on failure** via `mutation_snackbar.dart`. Every mutation handler's catch-block calls `showMutationFailureSnackbar(context, type, retry)`. No ad-hoc `ScaffoldMessenger.showSnackBar` in new code.
8. **WebSocket expansion is deferred.** Existing WS paths (shopping list, recipe-book recipe CRUD) stay. The WS inbound handler lowers into `emitMutation(...)` via a thin adapter. No new WS routes for meals / calendars / meal-events in any of the three epics.
9. **getIt services don't hold list state.** Services are stateless API clients. Any service with cached list state (`ActivityReadProvider`, `ShoppingCartService`) wraps a MutationBus subscription **internally**; the external API is unchanged. No parallel read paths through both a service and a Riverpod provider.

## End-user flow

### Flow A: "I just added a new recipe from a URL"

1. Leo taps **+** → **URL Import** → pastes a link → confirms → recipe wizard → taps **Save Recipe**.
2. `RecipeService.createRecipe(...)` calls `POST /recipe-books/{id}/recipes`. On 200, the service emits `MutationEvent.RecipeCreated(recipeId, fullResponse, bookId)` on the MutationBus **before** returning to the caller. (Service-layer emit — see Locked Decision #1.)
3. Navigator pops back to Home.
4. Home grid — now a Riverpod `homeContentProvider` — has a `ref.listen(mutationBusProvider, ...)` that filters to Recipe*/Meal* types and calls `ref.invalidateSelf()`. Refetch is already in flight by the time pop-navigation completes; Home renders the new recipe in the same frame as the pop animation ends (target: within 300ms of server 200 response, **800ms p95** including network time — measured by the widget test's pump cadence, not by wall-clock profiling).
5. Favorites carousel (if the new recipe was marked favorite in the wizard): `homeContentProvider` re-fans out to the favorites fetch on invalidation, so the carousel updates in the same refetch. No separate subscription needed.
6. If user has shared the target book with a partner: existing recipe-book WS broadcast (`recipe_added`) arrives on the partner's device; the partner's WS-to-MutationBus adapter emits `RecipeCreated` — same downstream code path fires on the partner's Home. The partner's `homeContentProvider` is indistinguishable from a local mutation. (Idempotent: if the local emit and the WS-lowered emit both fire on the originating device, two invalidations are a wasted refetch but not a correctness bug. See Risks.)
7. **Failure path**: If `POST /recipes` returns non-200 or times out, no event is emitted. The recipe wizard stays open, `showMutationFailureSnackbar(context, MutationType.createRecipe, retry: () => _saveRecipe())` surfaces. Home is unchanged.

### Flow B: "I dismissed a failed import"

1. Leo swipes-to-dismiss (or taps Dismiss) on a failed import row in the Imports tab.
2. Existing optimistic `setState` in `ImportHistoryScreen._dismissSingleItem()` removes the row from local `_failedJobs` immediately (UX stays instant).
3. `POST /import-items/{id}/dismiss` returns the full updated `ImportItem.Response` (FR-REACT-8 backend change, see `rf-2`). On 200, the handler calls `emitMutation(ImportItemDismissed(itemId, fullItem, jobDismissed: bool))`. (This is one of the few UI-handler emits in the epic; the rationale is that the dismiss flow lives entirely in the widget — there is no `ImportItemService` today. It is **explicitly noted as a migration target** for a follow-on cleanup — see Risks.)
4. `importsSeeAllProvider` listens to `ImportItemDismissed` and invalidates itself. See-all footer drops the row on its next refetch.
5. `ActivityReadProvider` (the getIt service) registers a bus subscription internally and eagerly recomputes `imports_actionable_count` without waiting for the 30s poll tick. The bottom-nav badge decrements immediately.
6. If the dismiss also dismissed the parent job (`jobDismissed=true`), the handler additionally emits `ImportJobDismissed(jobId)`; `importJobsProvider` invalidates.
7. **Failure path** (network error mid-dismiss): Snackbar appears — `"Couldn't dismiss import. Tap to retry."` — row snaps back via the existing `catch { _loadAttentionView(); }` pattern (kept, not replaced, in this epic). Tapping the Snackbar re-invokes `_dismissSingleItem(jobWithItems, item)`.
8. **In-flight visual** (UX): between tap and server 200, the row stays removed from the optimistic list. No spinner or dimming on the dismissed row (it's already gone from the DOM). The bottom-nav badge does NOT pre-decrement — it only decrements on the server 200 (see "Empty/loading/error states" below for why).

## Frontend changes

### New primitives — `app/lib/core/state/`

- `mutation_bus.dart` — sealed class `MutationEvent` with a case per event type (see Backend → events catalog below), plus `final mutationBusProvider = Provider<Stream<MutationEvent>>((ref) => _controller.stream)` backed by a **long-lived** singleton `StreamController<MutationEvent>.broadcast()`. Non-autoDispose — see Locked Decision #5. Exposes `emitMutation(MutationEvent)` as a top-level helper so non-Riverpod code (getIt services, WS adapters) can emit.
- `mutation_event.dart` — sealed class hierarchy with a subclass for every event type in the catalog. Recipe*/ImportItem* subclasses ship live; Meal*/Calendar*/Profile*/Pantry*/Book* subclasses ship as stubs so the two migration epics only add emit/subscribe call sites, not new type cases.
- `mutation_failure_copy.dart` — const map from `MutationType` enum → `(verb, noun)` used by `showMutationFailureSnackbar`. Seeded with import + recipe verbs in this epic; expanded in follow-ons.
- `mutation_snackbar.dart` — `showMutationFailureSnackbar(BuildContext, MutationType, VoidCallback retry, {Duration visibleFor = const Duration(seconds: 5)})`. Single entry point. Width-safe copy: `"Couldn't <verb> <noun>"` fits on two lines at 320px device width; action button label `"Retry"` (5 chars) never wraps. (UX-verified width.)
- `README.md` — convention doc: how to emit, how to subscribe, how to add a new event type, the coarse-key rule, the bulk-event rule, the 100ms coalesce fallback pattern, the WS-lowering rule, how to write the regression widget test.

### Screens touched

- `app/lib/features/home/home_screen.dart` — rewritten from imperative `_loadRecipes()` to `ref.watch(homeContentProvider)`. `homeContentProvider` is a new Riverpod `FutureProvider.autoDispose<HomeContent>` (with `ref.keepAlive()` for session) that fans out to recipe-books + recipes + meals + favorites fetches (same as today's imperative loader). `ref.listen(mutationBusProvider, ...)` inside the provider filters to `RecipeCreated | RecipeUpdated | RecipeArchived | RecipeUnarchived | RecipeFavorited | RecipeForked | RecipeMoved | RecipeBulkArchived | MealCreated | MealUpdated | MealArchived | MealFavorited` and calls `ref.invalidateSelf()`. Pull-to-refresh calls `ref.refresh(homeContentProvider)` (user intent; distinct from invalidate — see Locked Decision #2). Filter/sort state stays client-side and does not refetch (pfc-4 guarantee preserved).
- `app/lib/features/activity/import_history_screen.dart` + `app/lib/features/activity/providers/imports_see_all_provider.dart` — `_dismissSingleItem`, `_dismissAllFailed`, `_retrySingleItem` all emit MutationBus events on server success. `importsSeeAllProvider` listens to the three import-item event types and invalidates.
- `app/lib/features/activity/providers/activity_read_provider.dart` — existing getIt service keeps its 30s poll and external ValueNotifier API, but subscribes to import events internally and recomputes `importsActionableCount` eagerly. (Double path is intentional: poll covers cold-start + WS-missed states; MutationBus covers instant local reactivity.)
- `app/lib/features/recipes/providers/recipe_provider.dart` — family-keyed `recipeProvider(recipeId)` already invalidates manually today via `invalidateRecipe(ref, recipeId)`. Convert to MutationBus subscription (`RecipeUpdated | RecipeArchived | RecipeFavorited` where `event.recipeId == key`) — removes the manual call sites. `invalidateRecipe(...)` is kept as a thin shim for one release cycle to avoid churning un-migrated call sites, then deleted in a follow-on epic. (Architect: protects rollback.)
- Recipe mutation sites (create, update, archive, unarchive, favorite, fork, move, bulk-archive, note CRUD): every mutation goes through `RecipeService` and emits **in the service method**, not in the UI handler. Call sites enumerated in `rf-4`.

### Empty / loading / error states (UX)

- **Home grid — initial load**: existing shimmer skeleton unchanged.
- **Home grid — post-mutation refetch**: `homeContentProvider` invalidation keeps the previous `AsyncData.value` visible via `.valueOrNull` while `isRefreshing=true`. The grid does **not** flash to the skeleton between the invalidate and the next `AsyncData` frame (loading-flicker guard — UX raised this). Pull-to-refresh shows the native `RefreshIndicator` spinner only, not the skeleton.
- **Home grid — mutation + pull-to-refresh overlap** (edge case UX flagged): if Leo pulls-to-refresh while a MutationBus invalidation's refetch is still in flight, the `ref.refresh(...)` cancels the in-flight fetch and starts a new one. Riverpod handles this correctly; ensured by `rf-3` AC #7 (new).
- **Imports tab dismiss — happy path**: row disappears instantly via the existing optimistic `setState`. No spinner, no dimming. The bottom-nav badge does NOT pre-decrement (preserves server-authoritative count; decrements on 200).
- **Imports tab dismiss — failure**: Snackbar surfaces (`"Couldn't dismiss import. Tap to retry."`), row snaps back via `_loadAttentionView()`. Snackbar duration 5s, with a Retry action that re-invokes the dismiss handler. If Leo dismisses multiple in rapid sequence and multiple fail, the Snackbars stack via `ScaffoldMessenger.removeCurrentSnackBar(); show(...)` — newest wins (copy cannot be disambiguated at 320px width, so showing older ones is worse than clearing).
- **Recipe wizard save — failure**: existing wizard error-state unchanged. Snackbar is the new addition — wizard stays open so user can retry.

### Subscriber ref-pattern cheat sheet (Frontend)

| Intent | API | When |
|---|---|---|
| Bus event fires → refetch my data | `ref.invalidateSelf()` inside a `ref.listen(mutationBusProvider, ...)` | Inside a provider body |
| Bus event fires → refetch a sibling provider | `ref.invalidate(siblingProvider)` | From a listener that owns sibling's scope |
| User pulls-to-refresh | `ref.refresh(provider)` | From the UI handler only |
| Family member refetch | `ref.invalidate(recipeProvider(id))` | Inside the `ref.listen` body after filtering `event.recipeId == id` |

## Backend changes

### Response-shape fixes (FR-REACT-8)

- `POST /v1/import-items/{id}/dismiss` — currently returns `{item_id, dismissed_at, job_dismissed}` (see `services/api/src/api/v1/import_job/dismiss_import_item.py`). Change Pydantic `Response` to a union: the old three fields **stay at top level** (backwards-compat for clients reading them), and a new optional `item: ImportItem.Response | None` field is added carrying the full updated object. Architect: this is a **purely additive** change — old clients reading `item_id` / `dismissed_at` / `job_dismissed` continue to work. New clients read `item` when present.
- `POST /v1/recipes/{id}/favorite` — return the full `Recipe.Response` (ingredients, steps, etc.) with `is_favorited` nested inside. Additive. **Payload size note (Architect)**: a full recipe with ingredients + steps is typically 3–12 KB. Current favorite response is ~100 bytes. Watch for a noticeable network cost on slow connections — mitigated because `/favorite` is low-frequency. If payload-size becomes a complaint, fallback is a `?slim=true` query param in a follow-up; not needed day-1.
- `POST /v1/meals/{id}/favorite` — same pattern, full `Meal.Response`. Same payload-size note applies.
- **Deploy order (Infra)**: backend deploys **first**. Old app clients reading only the legacy fields keep working (additive). New client binary can ship any time after backend rollout completes. The only deploy-order risk is if a new app build ships *before* backend — in that case the client parses `item: null` and falls back to the invalidate-and-refetch path (one extra round trip, no correctness bug). Acceptable.

### Events catalog (emitted on the client; backend only ships the data)

Frontend emits, backend does not. Listed here so response contracts match the event payload schema.

| Event | Emitted after | Payload | In this epic |
|---|---|---|---|
| `RecipeCreated` | `POST /recipes` 200 | `Recipe.Response` + `bookId` | Yes |
| `RecipeUpdated` | `PUT /recipes/{id}` 200 | `Recipe.Response` | Yes |
| `RecipeArchived` | `POST /recipes/{id}/archive` 200 | `recipeId`, `bookId` | Yes |
| `RecipeUnarchived` | `POST /recipes/{id}/restore` 200 | `Recipe.Response` | Yes |
| `RecipeFavorited` | `POST /recipes/{id}/favorite` 200 | `Recipe.Response` + `isFavorited: bool` | Yes |
| `RecipeForked` | `POST /recipes/{id}/fork` 200 | new `Recipe.Response` + `parentRecipeId` | Yes |
| `RecipeMoved` | `POST /recipes/{id}/move` 200 | `Recipe.Response` + `oldBookId`, `newBookId` | Yes |
| `RecipeBulkArchived` | `POST /recipes/bulk-archive` 200 | `List<recipeId>`, `bookId` | Yes |
| `ImportItemDismissed` | `POST /import-items/{id}/dismiss` 200 | `ImportItem.Response` + `jobDismissed: bool` | Yes |
| `ImportItemRetried` | `POST /import-items/{id}/retry` 200 | `ImportItem.Response` | Yes |
| `ImportJobDismissed` | synthesized when `ImportItemDismissed.jobDismissed == true` OR after `POST /import-jobs/dismiss-all-failed` | `jobId` | Yes |
| `Meal*` | — | — | **Stubs only**; emits land in `epic-reactive-migration-meals-calendar` |
| `Calendar*`, `MealEvent*` | — | — | **Stubs only**; migration epic |
| `RecipeBookCreated/Updated/Archived` | — | — | **Stubs only**; `books-profile-pantry` epic |
| `PantryItem*`, `ProfileUpdated`, `NotificationPrefsUpdated` | — | — | **Stubs only**; `books-profile-pantry` epic |

## Infrastructure changes

**None.** No new AWS resources, no Terraform changes, no new env vars, no Celery tasks, no migrations. Infra is unchanged from its current state. Deploy order is standard (backend → client); no downtime window required. (Infra: confirmed.)

## Design principles (locked via party-mode)

1. **Coarsest useful key.** One event invalidates one list provider, not 20 item providers — subscribers opt-in by event **type**, not by identity. (Frontend.)
2. **Service-layer emits.** Every mutation emit site is in a `*Service` method, never in a UI handler, so a new UI caller can't forget. The one exception in this epic (`ImportHistoryScreen` emits directly) is called out as technical debt for a cleanup pass. (Architect.)
3. **Reconcile-only for v1.** Existing optimistic `setState` paths stay; no new optimistic paths introduced. (PM — matches user's locked decision.)
4. **Full-object payloads where cheap, ids where not.** Events carry the full resource when the API already returns one (create, update, favorite). Deletes and archives carry only the id. FR-REACT-8 expands the dismiss + favorite responses so this stays true for those paths. (Backend/Architect.)
5. **WS frames = local events.** Existing WS inbound handlers emit MutationBus events via a thin adapter — downstream code cannot distinguish "my mutation" from "partner's WS frame", which is the point. (Frontend.)
6. **No silent drops.** Every mutation catch-block either emits a success event or calls `showMutationFailureSnackbar`. No `try { ... } catch { return null; }`. Enforced via code-review checklist in `.claude/commands/review.md`. (QA.)
7. **No getIt state duplication.** If a Riverpod provider exists for the resource, getIt services are stateless API clients or thin adapters. Existing stateful services (`ActivityReadProvider`, `ShoppingCartService`) wrap a MutationBus subscription internally but keep their external API. (Architect.)
8. **Bulk events, not coalescing, for bulk mutations.** `RecipeBulkArchived` is a first-class event; per-item events are suppressed in bulk paths. 100ms subscriber coalescing is the fallback for non-bulk event floods (e.g. partner's WS spam). (Frontend + QA.)
9. **Widget tests assert the "no refresh needed" invariant.** Every touched surface gets one test that: renders → emits event → pumps one microtask → asserts new state visible, without calling pull-to-refresh. (QA.)
10. **Non-autoDispose broadcast bus.** The MutationBus controller is a module-level singleton; the Riverpod wrapper is `Provider`, not `StreamProvider.autoDispose`. Prevents mid-lifecycle subscription teardown. (Frontend.)

## File structure

```
app/lib/core/state/
├── mutation_bus.dart                  (new — singleton broadcast controller + Provider<Stream>)
├── mutation_event.dart                (new — sealed class + all subtypes incl. stubs)
├── mutation_failure_copy.dart         (new — stub, expanded in follow-ons)
├── mutation_snackbar.dart             (new — showMutationFailureSnackbar helper)
└── README.md                           (new — convention doc)

app/lib/features/home/
└── home_screen.dart                   (refactor — ref.watch(homeContentProvider))
app/lib/features/home/providers/
└── home_content_provider.dart          (new)

app/lib/features/activity/
├── import_history_screen.dart         (emit events in dismiss/retry/dismiss-all)
└── providers/
    ├── imports_see_all_provider.dart  (subscribe)
    └── activity_read_provider.dart    (subscribe internally; external API unchanged)

app/lib/features/recipes/
├── providers/recipe_provider.dart     (subscribe; keep invalidateRecipe as shim)
└── services/recipe_service.dart       (emit on every mutation)

app/lib/features/recipe_books/
└── services/recipe_book_service.dart  (emit on create/update/move — partial; full coverage in follow-on)

services/api/src/api/v1/import_job/dismiss_import_item.py    (additive response fields)
services/api/src/routers/v1/import_router.py                (no-op — endpoint unchanged)
services/api/src/api/v1/recipes/favorite_recipe.py          (full Recipe.Response)
services/api/src/api/v1/meals/favorite_meal.py              (full Meal.Response)

app/test/core/state/mutation_bus_test.dart
app/test/features/home/home_screen_reactivity_test.dart
app/test/features/activity/import_history_reactivity_test.dart
app/test/helpers/mutation_bus_test_helper.dart
services/api/tests/routers/test_import_items_dismiss_shape.py
services/api/tests/routers/test_favorite_response_shape.py
```

## Story list with acceptance criteria

### rf-1 — MutationBus primitive + convention docs + test helper

**AC**:
1. `app/lib/core/state/mutation_bus.dart` exists with a sealed `MutationEvent` class and a subclass for every event in the Events Catalog — including stubs for Meal*/Calendar*/Book*/Pantry*/Profile* so migration epics only add emits/subscribes, not new type declarations.
2. `mutationBusProvider` is `Provider<Stream<MutationEvent>>` (NOT autoDispose) backed by a module-level singleton `StreamController<MutationEvent>.broadcast()`. Multiple concurrent `ref.listen`/`ref.watch` subscribers each receive every emitted event.
3. Top-level `emitMutation(MutationEvent)` helper exists for non-Riverpod emitters (services, WS adapters). `emitMutation` is synchronous-enqueue: calling it within a microtask guarantees subscribers receive it before the next macrotask.
4. Widget-test utility `pumpWithMutation(WidgetTester tester, MutationEvent event)` exists in `app/test/helpers/mutation_bus_test_helper.dart` — emits + pumps one microtask + pumps one frame (`tester.pump(Duration.zero)`). Returns `Future<void>` so tests can await. Used by every reactivity test in rf-3 / rf-5 / rf-6.
5. `README.md` documents: how to emit (service-layer rule), how to subscribe, how to add a new event subtype, the coarse-key rule, the bulk-event rule, the 100ms coalesce fallback recipe (with code sample), the WS-lowering recipe, and the test helper API.
6. Unit test `mutation_bus_test.dart` verifies: (a) broadcast — two subscribers each receive an emitted event; (b) no-memory-leak — 100 subscribe+dispose cycles leave zero listeners on the controller; (c) ordering — two consecutive `emitMutation` calls deliver to subscribers in order; (d) late-subscribe — events emitted before a subscriber joins are NOT received (broadcast semantics, documented).
7. No event is ever dropped in the single-subscriber case. (Regression guard against the draft's autoDispose mistake.)

### rf-2 — Backend response-shape fixes for dismiss + favorite

**AC**:
1. `POST /v1/import-items/{id}/dismiss` keeps the existing top-level fields (`item_id`, `dismissed_at`, `job_dismissed`) AND adds an optional `item: ImportItem.Response` carrying the full updated object. Old fields are required in the schema; `item` is `Optional` for cheap rollback.
2. `POST /v1/recipes/{id}/favorite` returns the full `Recipe.Response` with `is_favorited: bool` nested inside. The response is the complete recipe payload (ingredients, steps, tags — same as `GET /recipes/{id}`), not a slim variant. Payload size documented as 3–12 KB typical.
3. `POST /v1/meals/{id}/favorite` returns the full `Meal.Response`, including nested component refs.
4. Three new Python router tests assert the response shape: (a) all legacy fields present on dismiss; (b) full `item` object present on dismiss; (c) full Recipe / Meal objects on favorite. Tests live in `services/api/tests/routers/`.
5. Flutter API client models for `ImportItem`, `Recipe`, `Meal` parse the new fields. Unit test in `app/test/core/services/` verifies parsing of a golden server response JSON fixture for each endpoint.
6. Manual deploy-order check documented in the story: backend merges + deploys first; app binary ships any time after. Client code guards against `item: null` / missing favorite fields and falls back to invalidate-and-refetch — no crash.

### rf-3 — HomeScreen migration to homeContentProvider

**AC**:
1. `app/lib/features/home/providers/home_content_provider.dart` exists as a `FutureProvider.autoDispose<HomeContent>` using `ref.keepAlive()` for session persistence. It fans out to the same fetches `_loadRecipes` does today: recipe-books + recipes + meals + favorites carousel.
2. `HomeScreen` consumes `ref.watch(homeContentProvider)`; no `initState` API calls, no `setState` on data lists. Filter/sort state stays client-side as local `useState` or `ref.watch(filterStateProvider)` — those do not refetch the network (pfc-4 guarantee preserved).
3. `homeContentProvider` body contains `ref.listen(mutationBusProvider, (prev, next) { if (_shouldInvalidate(next)) ref.invalidateSelf(); });` filtering to `RecipeCreated | RecipeUpdated | RecipeArchived | RecipeUnarchived | RecipeFavorited | RecipeForked | RecipeMoved | RecipeBulkArchived | MealCreated | MealUpdated | MealArchived | MealFavorited`.
4. Pull-to-refresh (`RefreshIndicator.onRefresh`) calls `ref.refresh(homeContentProvider.future)`. Distinct from invalidate — guarantees user-intent fetch even if there's a recent cache hit. (Locked Decision #2.)
5. Between invalidation and the next `AsyncData`, the grid shows the previous `valueOrNull` (no skeleton flash). Verified by widget test (AC #7). (UX loading-flicker guard.)
6. Existing home-screen widget tests pass unchanged.
7. New regression widget test `home_screen_reactivity_test.dart`:
   - (a) Pump `HomeScreen` with a mocked `RecipeService` returning `[A]` then `[A, B]` on second call. Wait for first `AsyncData`.
   - (b) Emit `RecipeCreated(recipeId: 'B', ...)` via the test helper.
   - (c) Pump one microtask + one frame.
   - (d) Assert: `find.text('B')` returns one widget; `find.text('A')` still returns one widget; no skeleton widget (`ShimmerLoading`) is in the tree.
   - (e) Separate test for the pull-to-refresh overlap case: emit + pull-to-refresh within 10ms, assert only one final fetch resolves cleanly (no stuck spinner, no stale state).
8. Deterministic timing: the widget test uses `pumpWithMutation` (which awaits one microtask) and does NOT rely on wall-clock timeouts. No `Future.delayed` in the test body. (QA flaky-risk mitigation.)

### rf-4 — Recipe mutation sites emit MutationBus events (service-layer)

**AC**:
1. Every recipe mutation in `RecipeService` — `createRecipe`, `updateRecipe`, `archiveRecipe`, `unarchiveRecipe`, `favoriteRecipe`, `forkRecipe`, `moveRecipe`, `bulkArchiveRecipes`, notes CRUD — calls `emitMutation(...)` **inside the service method**, on the success branch of the API call. UI handlers (`recipe_wizard_screen._saveRecipe`, `recipe_detail_screen._saveEdit`/`_archiveRecipe`/`_toggleFavorite`/`_forkRecipe`/`_moveToBook`, home-screen `BulkDispatcher.bulkArchive`) do NOT emit; they only await the service call.
2. `invalidateRecipe(ref, recipeId)` helper stays as a thin shim for one release cycle — internally it becomes `ref.invalidate(recipeProvider(recipeId))` only (no emit; emit happens in the service). All existing call sites are audited and confirmed still-working via the MutationBus subscription on `recipeProvider(id)`.
3. Mutation-failure paths in UI handlers call `showMutationFailureSnackbar(context, MutationType.<verb>, retry: () => <handler>)` instead of `ScaffoldMessenger.showSnackBar(SnackBar(...))`. Copy lives in `mutation_failure_copy.dart`.
4. `bulkArchiveRecipes` emits **one** `RecipeBulkArchived(recipeIds: [...], bookId)` event — NOT N `RecipeArchived` events. (Locked Decision #3.)
5. Integration test in `app/test/features/recipes/`: drive each `RecipeService` method through a mocked API client; assert (a) the correct event subtype is emitted on success with the expected payload; (b) no event is emitted on failure; (c) the Snackbar appears on UI-handler failure.
6. Every previously-broken pfc-3 invalidate call (enumerated in the frontend audit — at minimum: `recipe_wizard_screen`, `recipe_detail_screen`, `home_screen`, `recipe_book_screen`) has been removed or replaced with the shim. No `invalidateRecipe` call remains inside a try-block that could skip on error.

### rf-5 — ImportHistoryScreen + Imports tab + activity badge reactivity

**AC**:
1. `_dismissSingleItem`, `_dismissAllFailed`, `_retrySingleItem` all emit `ImportItemDismissed` / `ImportJobDismissed` / `ImportItemRetried` on server success. `_dismissAllFailed` emits **one** `ImportJobDismissed(jobId)` per fully-dismissed job **plus** one `ImportItemDismissed` per dismissed item (batch-level event kept explicit so subscribers can decide granularity).
2. Dismiss + retry call sites are migrated to `showMutationFailureSnackbar` in the catch block. The existing fallback `_loadAttentionView()` stays as the rollback mechanism (reconcile-only — Locked Decision #6).
3. `importsSeeAllProvider` subscribes to all three event types via `ref.listen(mutationBusProvider, ...)` and invalidates. See-all footer shows the updated list on next frame. Test verifies one emit → one invalidation → one refetch (not two).
4. `ActivityReadProvider` getIt service registers a `StreamSubscription<MutationEvent>` on construction that listens for `ImportItemDismissed` / `ImportJobDismissed` / `ImportItemRetried` and calls `refreshUnreadCount()`. External API (`unreadCount`, `importsActionableCount`, `notificationsCount`, `structuredCountsAvailable` ValueNotifiers) is unchanged. The 30s poll stays as-is (covers cold-start + WS-missed states).
5. Failure path: Snackbar on dismiss/retry error with Retry action; row snaps back via the existing `_loadAttentionView()` fallback.
6. New regression widget test `import_history_reactivity_test.dart`:
   - (a) Pump `ImportHistoryScreen` with two failed items in one job. Wait for first `AsyncData`.
   - (b) Call `_dismissSingleItem(jw, item1)` (simulated via tester tap on the Dismiss action or direct state invocation).
   - (c) Mocked API returns 200 with `ImportItem.Response` for item1 + `job_dismissed: false`.
   - (d) Assert: the row for item1 is gone; the row for item2 is still visible; `importsSeeAllProvider` was invalidated exactly once; `ActivityReadProvider.importsActionableCount.value` decreased by 1 without the 30s poll having fired.
7. Flaky-guard: the test uses `tester.pump(Duration.zero)` for microtask draining, never `tester.pumpAndSettle()` with a timeout. (QA.)

### rf-6 — Regression sweep + end-to-end tests + CI guard

**AC**:
1. End-to-end widget test `home_screen_reactivity_test.dart` (or `integration_test/` if that harness exists): full flow — pump home → navigate to add-recipe sheet → simulate save → assert new recipe tile visible on Home **without** a pull-to-refresh gesture, within 800ms p95 of the simulated server response. Uses a mocked API client; no real network.
2. End-to-end widget test `import_history_reactivity_test.dart`: dismiss a failed import → assert (a) `importsSeeAllProvider` invalidated; (b) `ActivityReadProvider.importsActionableCount` decremented; (c) the row is gone from the Imports tab list — all within one frame of the mocked server 200.
3. All existing widget tests in `app/test/features/home/` and `app/test/features/activity/` pass without changes.
4. Coverage assertion: any mutation site touched in rf-4 or rf-5 has at least one test asserting its MutationBus emit. Enforced by `rf-4` AC #5 and `rf-5` AC #6; this AC requires a summary checklist in the story's QA walkthrough covering all mutation sites.
5. CI guard: a code-review checklist item added to `.claude/commands/review.md`: **"Does every new mutation in a `*Service` method call `emitMutation(...)` on the success branch? Does every new mutation UI-handler catch-block call `showMutationFailureSnackbar`?"** Optional stretch: a Dart analyzer lint/rule (if straightforward); not a blocker for the epic close.
6. Deterministic CI: all new tests run under the existing `flutter test` command without an extra harness; p95 wall-clock runtime for the new reactivity tests is <2s each (no `pumpAndSettle` with timeouts, no real delays).

## Dependencies

- **Cross-epic**: Blocks both `epic-reactive-migration-meals-calendar` and `epic-reactive-migration-books-profile-pantry-and-polish`.
- **Internal ordering**: rf-1 → rf-3 → rf-4 → rf-6 ; rf-2 → rf-5 → rf-6 ; rf-1 → rf-5.
- **Cross-layer**: Frontend rf-5 soft-depends on backend rf-2 for the full dismiss object. rf-5 can land with a mocked client response while rf-2 is in flight; end-to-end tests pin the contract.
- **Deploy order**: Backend rf-2 deploys **before** any client binary using the new `item` field. Additive schema guarantees old clients keep working. (Infra.)
- **No dependency on pending epics** (notifications, meals-sharing, Play Console, etc.). Lands standalone.

## Resolved questions

These were "Open questions for the user" in the draft. Party-mode resolved them in-file per the Locked Decisions section above:

- ~~Invalidation-storm debouncing threshold~~ → **Resolved**: emit first-class bulk events (`RecipeBulkArchived`), suppress per-item events in bulk paths. 100ms coalescing reserved for non-bulk event floods (e.g. partner WS spam). See Locked Decision #3 + #4.
- ~~Event emit point — service layer vs. UI handler~~ → **Resolved**: service-layer emits. One explicit exception (`ImportHistoryScreen` direct emit) flagged as cleanup debt in Risks. See Locked Decision #1.
- ~~Should `homeContentProvider` fan out or be split~~ → **Resolved**: one `homeContentProvider` with a `HomeContent` value object. Splitting buys a tiny refetch-cost win at the cost of four provider lifecycles and four separate `ref.listen` subscriptions. The perf target is already met empirically (current imperative loader does the same four fetches in parallel). Revisit if home-load p95 regresses >20% post-migration.

## Escalation for the user

None. All three previously-open questions resolved in party-mode; no remaining blockers require the user's call before `rf-1` starts. If any of the resolved answers proves wrong under dogfood, `bmad-bmm-correct-course` is the right response — don't block the epic kickoff on pre-litigation.

## Risks

- **Hidden mutation sites.** The frontend audit enumerates the major ones; there may be lower-traffic sites (e.g., notes CRUD on recipe detail, cook-feedback flow) that get missed. Mitigation: the code-review checklist in rf-6 catches any future mutation that doesn't emit; post-epic, a grep sweep for `ApiClient.post/put/delete` call sites outside services flags candidates for a cleanup pass.
- **getIt double-source-of-truth.** `ActivityReadProvider` wraps a MutationBus subscription *internally* in rf-5 while keeping its external ValueNotifier API. If a caller reads both the getIt service and a parallel Riverpod provider, they could drift mid-frame. Mitigation: rf-5 includes an audit pass confirming no parallel read paths.
- **WS/MutationBus duplication.** A local mutation emits a MutationBus event AND the backend broadcasts a WS frame that the WS adapter also lowers into a MutationBus event — same event type, same id, fires twice. Mitigation: subscribers are idempotent by design (refetching twice in a row is wasteful but not incorrect). If profiling later shows this costs >5% of mutation latency, add a short (500ms) dedupe window in the WS adapter — not in scope for this epic.

### Risks identified via party-mode

- **(Frontend) `StreamProvider.autoDispose` would have silently dropped events.** The original draft used `StreamProvider.autoDispose<MutationEvent>`. On the last subscriber unmounting, the autoDispose would tear down the underlying stream subscription, and any event emitted in the ~1-frame gap before the next subscriber mounts would be lost — silently, with no test coverage that would catch it. **Locked to non-autoDispose `Provider<Stream>` + singleton controller** (Locked Decision #5); caught only via party-mode.
- **(UX) Loading-flicker between invalidate and refetch.** When `homeContentProvider` is invalidated, the default Riverpod behavior is to transition the `AsyncValue` to `AsyncLoading` before the refetch resolves — which would flash the shimmer skeleton over the grid for one frame. Mitigated by rendering `.valueOrNull` (previous data) during `isRefreshing`, verified in `rf-3` AC #5 + #7. The draft didn't call this out.
- **(UX) Snackbar width at 320px.** The retry-copy pattern `"Couldn't <verb> <noun>. Tap to retry."` can overflow on small screens with verbs like `"unarchive"` + `"recipe"` + retry hint. Trimmed copy: `"Couldn't unarchive recipe"` (title line) + `"Retry"` action button (button, not inline text). Verified by eyeballing at iPhone SE 3rd-gen width (320px) — fits on two lines.
- **(Backend/Architect) Favorite endpoint payload size jump.** From ~100 bytes to 3–12 KB per favorite toggle. Low-frequency endpoint so acceptable; flagged for monitoring in production. Fallback is `?slim=true` in a follow-up if dogfood reports slowness on cellular.
- **(Architect) Technical debt — `ImportHistoryScreen` emits directly from UI handler.** There is no `ImportItemService` today, so the emit lives in the widget. This violates Locked Decision #2 in exactly one spot. **Follow-on cleanup**: pull dismiss/retry into a new `ImportItemService` and move the emit down — tracked as an item in `epic-reactive-migration-books-profile-pantry-and-polish`'s follow-on cleanup pass. Not blocking for this epic.
- **(QA) Flaky async ordering.** Widget tests that emit a bus event + pump could race against microtask scheduling. Mitigated by the `pumpWithMutation` helper (always pumps one microtask + one frame). All new reactivity tests use this helper exclusively; no `pumpAndSettle` with a wall-clock timeout allowed.
- **(PM) Regression-test pass rate ≠ user-visible success.** Two passing CI tests don't prove the user experience. The "Single measurable proof" in Goal — Leo's scripted dogfood session — is the ground-truth check. If the scripted session fails after CI passes, the epic is not done.
- **(Infra) Deploy-ordering during a coordinated release.** If someone force-ships the client build before backend rolls out, new dismiss handlers parse `item: null` and fall back to invalidate-and-refetch — functional but costs an extra round trip per dismiss. Documented in rf-2 AC #6; backend is required to ship first.
