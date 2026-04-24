<!-- refined via party-mode 2026-04-22 -->
# Epic — Reactive Migration: Meals + Calendar + Meal Events

**Planned**: 2026-04-22
**Scope split**: Migration epic #1 of 2 — applies the MutationBus convention (from `epic-reactive-foundation-home-imports`) to meals, calendars, and meal events. No new primitives; this is the next-largest cluster of mutation sites after the foundation.
**Depends on**: `epic-reactive-foundation-home-imports` (MutationBus + Snackbar helper + regression test harness; `Meal*` / `Calendar*` / `MealEvent*` event subtypes ship as stubs in `rf-1`).
**Parallelizable with**: `epic-reactive-migration-books-profile-pantry-and-polish`.
**Status**: backlog

## Overview

Foundation epic ships MutationBus + migrates Home grid + Imports. This epic migrates the next highest-traffic cluster: meals, calendars, meal events. These features share a lot of state — a Meal has component recipes; a meal event references a Meal OR a Recipe; the Calendar screen reads meal-events; Meal detail's "Upcoming plans" row reads meal-events; Recipe detail's "Used in these Meals" block reads meals. Without cross-surface reactivity here, Leo's complaint reproduces any time he creates or edits a meal or a calendar event.

No new primitives. This epic is a repeat application of the Foundation pattern: every mutation site in `MealService` / `CalendarService` / `MealCalendarService` emits; every list/detail provider subscribes; regression widget tests assert cross-surface re-render.

## Inherited locked decisions (foundation epic — NOT re-litigated)

All nine locked decisions from `epic-reactive-foundation-home-imports` § "Locked decisions for downstream epics" apply verbatim here. In particular:

- Service-layer emits (decision #1) — `MealService.createMeal`, `MealService.addRecipeToMeal`, `MealCalendarService.createMealEvent`, etc. are the single emit points.
- `ref.listen(mutationBusProvider, ...)` + `ref.invalidateSelf()` (owned autoDispose) / `ref.invalidate(instance)` (family members) (decision #2).
- 100ms subscriber coalescing as the fallback for non-bulk event floods (decision #4) — **critical here** because recurrence materialization can emit 52 `MealEventCreated` in one server round-trip.
- MutationBus is a long-lived singleton `StreamController.broadcast()` wrapped in non-autoDispose `Provider<Stream<MutationEvent>>` (decision #5).
- Reconcile-only (decision #6). Existing optimistic `setState` paths — meal-edit component reorder / remove, meal-detail favorite optimism in `meal_detail_screen._toggleFavorite` — stay untouched.
- Toast + auto-rollback via `mutation_snackbar.dart` (decision #7). Copy stubs for every meal/calendar/event verb land here; the full copy map consolidation is in the books/profile/pantry epic.
- No new WebSocket routes (decision #8). No cross-device reactivity in scope.
- `getIt` services stateless (decision #9).

### Meal/calendar-specific locked decisions

- **Recurrence materialization = 100ms debounce, NOT a bulk event.** The `POST /v1/recurrence-rules` server already materializes the first 9 weeks inside the same transaction (see `meal_calendar_service.dart` comment). A future partner's materialization can emit many more. We do NOT introduce `MealEventsBulkMaterialized` because: (a) only one call site, (b) no per-item suppression saved since the events are authored on the server — the client only observes the effect via a re-fetch anyway, (c) adding a bulk event forces every subscriber to handle two event types. The 100ms coalesce (decision #4) handles this cleanly. One flood → one refetch per subscribed list provider.
- **Mark-as-cooked emits `MealEventCompleted(mealEventId)` only.** Today `_markMealCooked` calls `markMealCompleted(eventId)` which writes `status=completed` via `PATCH /v1/meal-events/{id}`. The subsequent `PostCookFeedbackSheet` writes a cooking log for the *recipe* (not for the event). **`CookingLogCreated` is out of scope for this epic** — cooking logs aren't shown on any meal/calendar surface; when the recipe-details cooking-history block gets MutationBus wiring, it'll land in the books/profile/pantry epic. Resolves draft open question #2.
- **Component reorder emits `MealComponentsReordered(mealId, Meal.Response)`.** Distinct from `MealUpdated` because (a) subscribers that only care about name/description don't invalidate unnecessarily, (b) the payload is semantically different (order vector, not scalar fields), (c) searchability — grep-able from story `rmc-1` forward. Resolves draft open question #1.
- **`CalendarMemberAdded/Removed` deferred.** Calendar member CRUD lives in `epic-calendars-sharing`. Stubs ship there, not here. This epic touches only self-owned calendars + calendars the user is a member of; member-list reactivity is tracked in the sharing epic's scope. Resolves draft open question #3.

## Goal

**Outcome**: Every meal, meal-component, meal-event, and calendar mutation propagates to every UI surface displaying that data, instantly, without a manual refresh.

**Single measurable proof (PM scripted dogfood)**: Leo runs one scripted session after ship on **one device**:
1. Create Meal "Sunday Roast" (3 components) → pop to Home → tile visible without pull-to-refresh.
2. Open Meal detail for "Weeknight Pasta" → Add Recipe → pick "Garlic Bread" → back on detail, chip strip includes "Garlic Bread" without refresh. Navigate to Garlic Bread recipe → "Used in these Meals" row shows "Weeknight Pasta".
3. Open Calendar → tap Friday → plan "Sunday Roast" at 6:30 PM → cell renders the new chip without reload; day-sheet list already updated.
4. Mark the Friday event as cooked → cell chip re-renders with cooked indicator; if Meal detail's "Upcoming plans" row is open in a separate tab, it's updated.

If these four steps all pass without a single pull-to-refresh gesture, the epic is "done" from end-user vantage. Distinct from the CI-level proof below.

**CI-level proof**: six regression widget tests in `app/test/features/meals/` and `app/test/features/calendar/` (enumerated in the file-structure section) are green in the closing commit. See `rmc-1`..`rmc-5` ACs for assertions.

## End-user flow

### Flow A: "I created a meal"

1. Leo taps **+** → **Create Meal** → multi-selects 3 recipes → confirms → names it "Sunday Roast" → taps **Save**.
2. `MealService.createMeal(...)` calls `POST /v1/recipe-books/{bookId}/meals`, on 2xx emits `MutationEvent.MealCreated(Meal.Response, bookId)`. Emit happens *inside* the service method, before the `Future` resolves (Locked Decision #1).
3. Navigator pops to Home.
4. `homeContentProvider` (Foundation epic; already subscribed to `MealCreated`) invalidates → Home grid renders the new tile within one frame of the pop animation.
5. `mealsByBookProvider(bookId)` (existing `FutureProvider.family`) subscribes to `MealCreated` / `MealUpdated` / `MealArchived` / `MealFavorited` with payload `bookId` filter → invalidates → the book's meal list (if visible elsewhere) re-renders.
6. `mealsAllProvider` (existing, flat cross-book list) subscribes to the same union without a `bookId` filter.

### Flow B: "I added a component recipe to an existing meal"

1. Leo opens Meal detail for "Weeknight Pasta" → taps **Add Recipe** → picks "Garlic Bread".
2. `MealService.addRecipeToMeal(mealId, recipeId: ...)` calls `POST /v1/meals/{id}/components`, on 2xx emits `MutationEvent.MealComponentAdded(mealId, recipeId, Meal.Response)`. Payload contains the **full updated Meal** (the endpoint already returns it — verified in backend audit below).
3. Meal detail patches in place from the payload — `mealByIdProvider(mealId)` (existing) subscribes with `event.mealId == mealId` filter and patches via `state = AsyncData(event.updatedMeal)` rather than a round-trip refetch.
4. Recipe detail "Used in these Meals" block (on the Garlic Bread recipe, if Leo happens to navigate there — e.g., he has the recipe open in a tab split or returns via back-stack): `usedInMealsProvider(recipeId)` (**new** — see UX note below) subscribes to `MealComponentAdded | MealComponentRemoved` with `event.recipeId == recipeId` filter → invalidates.
5. Home grid tile updates component-chip labels if visible (via `homeContentProvider`'s `MealUpdated | MealComponentAdded | MealComponentRemoved` subscription).

**UX edge case (Flow B)**: Recipe detail could be open simultaneously with Meal detail in a split/sheet context. Today `MealsUsingThisRecipe` is a `StatefulWidget` with a one-shot `initState` fetch — it would NOT update. After migration it'll live in a `ConsumerWidget`; emission reaches it via `ref.listen`. No flicker risk because the widget renders `valueOrNull` during refetch (the Foundation loading-flicker guard applies here — same `valueOrNull` + `isRefreshing` pattern as Home). Verified by widget test in `rmc-2` AC #3.

### Flow C: "I planned a meal for Friday dinner"

1. Leo opens Calendar → taps Friday → taps **+** → picks "Sunday Roast" meal → sets 6:30 PM → taps **Plan**.
2. `MealCalendarService.createMealEvent(...)` calls `POST /v1/meal-events`, on 2xx emits `MutationEvent.MealEventCreated(MealEvent.Response)`.
3. Calendar screen — today an imperative `_CalendarScreenState` with a `_loadGeneration` counter and setState-driven `_eventsByDay` map — is refactored to consume `mealEventsByRangeProvider((start, end, activeCalendarId))` (**new** provider — see Frontend changes). Provider subscribes to `MealEventCreated | MealEventUpdated | MealEventDeleted | MealEventCompleted` with range-containment filter → invalidates → grid re-renders the cell.
4. Day detail sheet (if Friday is open): consumes `mealEventsByDayProvider(date, activeCalendarId)` (**new**); subscribes with exact-date-match filter → invalidates → sheet list re-renders.
5. Meal detail "Upcoming plans" row (Meal detail surface exists today but has no such row yet — verify during `rmc-3`; if absent, `upcomingEventsForMealProvider(mealId)` still lands for the future row, **no unused-provider is shipped**: row lands in the same story).
6. **Recurrence case**: if Leo created a recurrence rule (not a single event), `MealCalendarService.createRecurrenceRule(...)` materializes 9 weeks server-side in one transaction (see existing comment in service). The server response carries the rule itself but not the materialized events. Client emits `RecurrenceRuleCreated(MealRecurrenceRule.Response)` and then re-fetches the events window — which causes `mealEventsByRangeProvider` to invalidate once. If a future partner's materialization emits 52 `MealEventCreated` via the WS adapter (not in scope but stubs need to handle it correctly), the 100ms subscriber coalescer guarantees at most one refetch per list provider.

### Flow D: "I marked a meal event as cooked"

1. Leo opens a day's meal card → taps **Mark as Cooked** (on calendar screen's `_markMealCooked`).
2. `MealCalendarService.markMealCompleted(eventId)` calls `PATCH /v1/meal-events/{id}` with `status=completed`, on 2xx emits `MutationEvent.MealEventCompleted(mealEventId)`. **Note**: today this endpoint returns the full updated `MealEvent.Response` even though `markMealCompleted` currently returns `void` and the handler imperatively calls `_loadEvents()`. The epic upgrades the service method to return the updated event and carry it in the payload — no backend change (the endpoint already returns it, service just ignored the result).
3. Calendar grid: event chip re-renders with the cooked indicator (via `mealEventsByRangeProvider` subscription).
4. Day detail sheet: the event card re-renders. The existing imperative `_loadEvents()` in the calendar screen is **removed** once the provider is in place — `setState` → provider invalidation is the new contract (Foundation locked decision #6 still applies: the optimistic path here is a Snackbar+rollback pattern, not a pre-mutation setState, so nothing to preserve).
5. Existing `PostCookFeedbackSheet` flow runs independently — it writes a `cooking_log` scoped to the recipe, not the event. We emit no event for `CookingLogCreated` in this epic (see locked decision above).

**Failure path (all flows)**: `showMutationFailureSnackbar(context, MutationType.<verb>, retry: ...)` replaces the ad-hoc `ScaffoldMessenger.showSnackBar(SnackBar(content: Text('Failed to ...')))` call sites enumerated in `rmc-1` + `rmc-3`.

## Frontend changes

### Provider inventory (new vs. existing — verified)

| Provider | Status | File |
|---|---|---|
| `mealsByBookProvider(bookId)` | **Existing** — `FutureProvider.family` | `app/lib/features/meals/providers/meals_provider.dart` |
| `mealsAllProvider` | **Existing** — flat cross-book | same file |
| `mealByIdProvider(mealId)` | **Existing** — `FutureProvider.family` (note: draft called it `mealDetailProvider`; use the real name) | same file |
| `invalidateMeal(ref, mealId, bookId)` helper | **Existing** — kept as a thin shim for one release cycle per Foundation rf-4 pattern, then deleted | same file |
| `calendarsListProvider` | **Existing** — `FutureProvider<List<Calendar>>` | `app/lib/features/calendar/providers/active_calendar_provider.dart` |
| `activeCalendarProvider` | **Existing** — `AsyncNotifierProvider` | same file |
| `mealEventsByRangeProvider((start, end, calendarId))` | **NEW** — `FutureProvider.family.autoDispose` | `app/lib/features/calendar/providers/meal_events_provider.dart` (new file) |
| `mealEventsByDayProvider((date, calendarId))` | **NEW** — same file |
| `upcomingEventsForMealProvider(mealId)` | **NEW** — same file |
| `usedInMealsProvider(recipeId)` | **NEW** — replaces `FutureBuilder` in `meals_using_this_recipe.dart` | `app/lib/features/recipes/providers/used_in_meals_provider.dart` (new file) |
| `favoriteMealsProvider` | **Does not exist today** — Home grid's favorites carousel is fed by `homeContentProvider` (fan-out). No separate provider needed. Draft's mention removed. |

### Service-layer mutation sites (emit points — `rmc-1` / `rmc-3`)

- `MealService` (all write methods — verified against the file):
  - `createMeal` → `MealCreated(Meal.Response, bookId)` — payload has bookId extracted from `Meal.Response.recipe_book_id`.
  - `updateMeal` → `MealUpdated(Meal.Response)`.
  - `addRecipeToMeal` → `MealComponentAdded(mealId, recipeId, Meal.Response)`.
  - `removeRecipeFromMeal` → `MealComponentRemoved(mealId, recipeId, Meal.Response)`.
  - `reorderMealComponents` → `MealComponentsReordered(mealId, Meal.Response)`.
  - `archiveMeal` → `MealArchived(mealId, bookId)`. **Backend note**: the endpoint returns `{success, archived_at}` today — it does NOT return the full Meal. The event carries ids only, not a payload. Subscribers invalidate; detail providers drop the cached meal. Acceptable — archive is a terminal transition and detail-view-of-archived is rare. (Backend audit finding — see Backend changes below.)
  - `restoreMeal` → `MealUnarchived(Meal.Response | null)`. Same caveat: endpoint returns shape TBD (verify in `rmc-1`). If it returns a slim response, event carries `mealId + bookId` only.
  - `favoriteMeal` / `unfavoriteMeal` → `MealFavorited(mealId, bookId, isFavorited: bool)`. **Backend note**: Foundation epic `rf-2` promised `/v1/meals/{id}/favorite` returns full `Meal.Response`. Today it returns `{is_favorite: bool}` only. If Foundation ships rf-2 first (sequenced dependency), this epic's service emits with the full payload. If `rf-2` meal-favorite portion is not yet live when `rmc-1` starts, the event carries `mealId + bookId + isFavorited` only and subscribers invalidate rather than patch. **No blocker — ACK'd as graceful degradation.**
  - `share` → `MealShared(mealId, shareToken)`. Listed for completeness; ships fully with `epic-meals-sharing-and-ai`. Stub declared in Foundation `rf-1`.

- `CalendarService` (all write methods):
  - `createCalendar` → `CalendarCreated(Calendar.Response)`.
  - `updateCalendar` → `CalendarUpdated(Calendar.Response)`.
  - `deleteCalendar` → `CalendarDeleted(calendarId)`.
  - `updateCalendarMember` / `removeCalendarMember` / `leaveCalendar` → **deferred** to `epic-calendars-sharing` per locked decision.

- `MealCalendarService` (meal-event + recurrence — note the service is named `MealCalendarService`, not `CalendarService`; draft got this wrong):
  - `createMealEvent` → `MealEventCreated(MealEvent.Response)`.
  - `updateMealEvent` → `MealEventUpdated(MealEvent.Response)`.
  - `moveMealEventToCalendar` → `MealEventUpdated(MealEvent.Response)` (delegated update; no separate event needed — old/new calendar ids are on the payload).
  - `rescheduleMealEvent` → `MealEventUpdated(MealEvent.Response)`.
  - `deleteMealEvent` → `MealEventDeleted(mealEventId, calendarId)`.
  - `markMealCompleted` → refactor to return `MealEvent.Response` (the endpoint returns it) + emit `MealEventCompleted(mealEventId, calendarId)`.
  - `createRecurrenceRule` → `RecurrenceRuleCreated(MealRecurrenceRule.Response)`. Materialization emits are server-side; client observes via next range fetch.
  - `updateRecurrenceRule` → `RecurrenceRuleUpdated(MealRecurrenceRule.Response)` (the method returns `Map<String, dynamic>` today; payload parsing lands in `rmc-3`).
  - `deleteRecurrenceRule` → `RecurrenceRuleDeleted(ruleId, scope)`.
  - `moveRecurrenceRuleToCalendar` → `RecurrenceRuleUpdated` (delegated).

### Screens touched

- `app/lib/features/meals/meal_edit_screen.dart` — today uses `invalidateMeal(ref, mealId, bookId)` after every mutation. Replace the call with reliance on the service-layer emit; `invalidateMeal` stays as a one-release shim. `ScaffoldMessenger.showSnackBar` failure paths → `showMutationFailureSnackbar`.
- `app/lib/features/meals/meal_detail_screen.dart` — `_toggleFavorite`, `_archiveMeal` call sites: remove ad-hoc snackbars; keep the existing `_optimisticFavorite` optimistic-setState path (Locked Decision #6 — reconcile-only for v1, don't add new optimism, don't remove existing).
- `app/lib/features/meals/widgets/create_meal_sheet.dart` — create-meal flow; same pattern.
- `app/lib/features/calendar/calendar_screen.dart` — **the big refactor**: today `_CalendarScreenState` imperatively loads events into `_eventsByDay` with a `_loadGeneration` counter. Rewrite to `ref.watch(mealEventsByRangeProvider((weekStart, weekEnd, activeCalendarId)))`. `_loadEvents()` is deleted. `_loadGeneration` counter is deleted (Riverpod cancels in-flight fetches on invalidate — the counter is redundant after migration). Callbacks from child sheets (`day_detail_sheet`, `meal_detail_sheet`, `plan_meal_sheet`) that today invoke `_loadEvents()` are removed; the subscription does it.
- `app/lib/features/calendar/widgets/day_detail_sheet.dart` — consume `mealEventsByDayProvider`; no callback back to parent for refresh.
- `app/lib/features/calendar/widgets/plan_meal_sheet.dart` — on save success, emit-path runs inside `MealCalendarService.createMealEvent`; sheet just pops. `ScaffoldMessenger` on failure → `showMutationFailureSnackbar`.
- `app/lib/features/calendar/widgets/meal_detail_sheet.dart` — consumes provider for the single event (or rides `mealEventsByDayProvider`).
- `app/lib/features/calendar/meal_detail_screen.dart` — deep-link event detail screen; consumes a `mealEventByIdProvider(eventId)` if needed. **Decision**: skip this provider unless the screen is currently broken — a one-shot fetch for a deep-link detail is acceptable, and `MealEventUpdated` subscription on the screen's local state via `ref.listen` is a narrow migration.
- `app/lib/features/recipes/widgets/meals_using_this_recipe.dart` — convert from `StatefulWidget + FutureBuilder` to `ConsumerWidget + ref.watch(usedInMealsProvider(recipeId))`. Keep the "empty / error → `SizedBox.shrink()`" invariant — critical for public recipe pages.

### New event subtypes (stubs declared in Foundation `rf-1`; payloads finalized here)

Per the Foundation's events-catalog table, these ship as stubs in `rf-1` so this epic only adds emit/subscribe call sites:

- `MealCreated(Meal.Response, bookId)`
- `MealUpdated(Meal.Response)`
- `MealArchived(mealId, bookId)`  *(ids-only — backend returns slim shape)*
- `MealUnarchived(Meal.Response | null)` *(shape TBD — defensive)*
- `MealFavorited(mealId, bookId, isFavorited: bool, updatedMeal: Meal.Response | null)`
- `MealComponentAdded(mealId, recipeId, Meal.Response)`
- `MealComponentRemoved(mealId, recipeId, Meal.Response)`
- `MealComponentsReordered(mealId, Meal.Response)`
- `MealShared(mealId, shareToken)` *(ships fully with sharing epic)*
- `CalendarCreated(Calendar.Response)`
- `CalendarUpdated(Calendar.Response)`
- `CalendarDeleted(calendarId)`
- `MealEventCreated(MealEvent.Response)`
- `MealEventUpdated(MealEvent.Response)` — covers reschedule, status change, move-calendar
- `MealEventDeleted(mealEventId, calendarId)`
- `MealEventCompleted(mealEventId, calendarId)`
- `RecurrenceRuleCreated(MealRecurrenceRule.Response)`
- `RecurrenceRuleUpdated(MealRecurrenceRule.Response | null)` *(response shape varies by scope; null-safe payload)*
- `RecurrenceRuleDeleted(ruleId, scope)`

### Empty / loading / error states (UX)

- All surfaces reuse existing skeletons/loading states. No new empty states.
- `valueOrNull`-during-refetch guard from Foundation applies to: Home grid (already done), Calendar screen grid (new here), day detail sheet (new), Meal detail (keep the `_optimisticFavorite` optimism), Recipe detail "Used in these Meals" block. The calendar grid does NOT flash to shimmer between a cook-mark emission and the subsequent refetch.
- `mutation_failure_copy.dart` is extended with entries for every meal/calendar/event verb. Copy lands in `rmc-5`; **seeded stubs** added in `rmc-1` so failure-path tests can assert.

### Subscriber coalescing recipe (rmc-4 canonical pattern)

```dart
// Inside a FutureProvider.family.autoDispose body.
Timer? debounce;
ref.listen(mutationBusProvider, (prev, next) {
  if (!_shouldInvalidate(next)) return;
  debounce?.cancel();
  debounce = Timer(const Duration(milliseconds: 100), () {
    debounce = null;
    ref.invalidateSelf();
  });
});
ref.onDispose(() => debounce?.cancel());
```

**Cold-stop correctness** (QA raised this): if the last event arrives at T then the provider is disposed at T+50ms, the timer fires *after* disposal with no ill effect (`invalidateSelf` is safe on disposed providers in Riverpod 2 — it's a no-op). **The last-event-elision risk only matters if the timer never fires** — mitigated by `ref.onDispose(() => debounce?.cancel())` which cancels cleanly and is asserted in `rmc-4` AC #5.

## Backend changes

**Near-zero.** Every meal / meal-event / calendar mutation endpoint already returns the full response object **except the three listed below**. The draft's "zero backend delta" claim was slightly wrong; we're calling out three slim-response endpoints that force subscribers to invalidate-and-refetch rather than patch.

| Endpoint | Current response | Client impact |
|---|---|---|
| `POST /v1/meals/{id}/favorite` + `DELETE /v1/meals/{id}/favorite` | `{is_favorite: bool}` (via `MealFavoriteResponse`) | Foundation epic `rf-2` already promises to fix this to `Meal.Response`. If landed before `rmc-1`, event carries full Meal. Otherwise event carries ids + bool; subscribers invalidate. **Not blocking.** |
| `POST /v1/meals/{id}/archive` + `POST /v1/meals/{id}/restore` | `{success, archived_at}` (via `MealArchiveResponse`) | Kept as-is — archived meals don't need in-place patching, subscribers invalidate. |
| `PATCH /v1/recurrence-rules/{id}` (update scope=occurrence) | `Map<String, dynamic>` — varies by scope | Keep; event payload is null-safe. |

**Explicit non-changes**:
- No WebSocket broadcasts for meals / calendars / meal-events (Locked Decision #8 from Foundation). Partner-sees-my-change is deferred.
- No new endpoints, no response-shape fixes beyond what Foundation already promises, no schema migrations.
- Server-side MCP tool mutations (`services/api/src/mcp_server/tools/meals.py` and `mcp_server/tools/calendar_*` if any) do not emit to the Flutter MutationBus — they run server-side. This is a non-issue until cross-device reactivity is in scope.

**Net backend delta for this epic: zero** (Foundation's rf-2 covers the meal-favorite shape fix; nothing net-new here).

## Infrastructure changes

**None.** No Terraform, no env vars, no new infra, no migrations. (Infra: confirmed — same stance as Foundation + nothing added.)

## Design principles (applied — not new)

These are the Foundation epic's design principles, applied in this context. Not re-litigated.

1. **Payload-in-place patching where the backend cooperates.** `MealComponentAdded/Removed/Reordered`, `MealUpdated`, `MealEventCreated/Updated/Completed`, `CalendarCreated/Updated` all carry full resource payloads → detail providers patch via `state = AsyncData(payload)`. Slim-response endpoints (archive/restore/favorite) fall back to invalidate.
2. **Family-keyed filtering inside `ref.listen`.** Subscribers that care about a specific id (meal/recipe/calendar) filter in the listener body before calling `ref.invalidate(...)`.
3. **Coalesce at the subscriber, not the bus.** 100ms window for `mealEventsByRangeProvider` / `mealEventsByDayProvider` / `upcomingEventsForMealProvider`.
4. **Service is stateless.** `MealService` / `CalendarService` / `MealCalendarService` are stateless API clients today (verified — no local list caches in any of the three files). No state removal needed; just add emits.

## File structure

```
app/lib/features/meals/
├── meal_edit_screen.dart                     (replace invalidateMeal with implicit via service emit; keep as shim)
├── meal_detail_screen.dart                   (failure-path → showMutationFailureSnackbar)
├── providers/
│   └── meals_provider.dart                   (add ref.listen subscriptions to all three existing providers)
├── services/
│   └── meal_service.dart                      (emit on every mutation method)
└── widgets/
    └── create_meal_sheet.dart                (failure-path → showMutationFailureSnackbar)

app/lib/features/calendar/
├── calendar_screen.dart                      (rewrite imperative _loadEvents to ref.watch(mealEventsByRangeProvider); delete _loadGeneration)
├── meal_detail_screen.dart                   (consume single-event provider; ref.listen on MealEventUpdated/Deleted/Completed)
├── providers/
│   ├── active_calendar_provider.dart         (add listen to CalendarCreated/Updated/Deleted)
│   └── meal_events_provider.dart             (NEW — three sibling providers + 100ms coalescer)
├── services/
│   ├── calendar_service.dart                  (emit on createCalendar/updateCalendar/deleteCalendar)
│   └── meal_calendar_service.dart             (emit on every mutation; upgrade markMealCompleted to return event)
└── widgets/
    ├── plan_meal_sheet.dart                  (failure-path → showMutationFailureSnackbar; no callback-based refresh)
    ├── day_detail_sheet.dart                 (consume mealEventsByDayProvider)
    └── meal_detail_sheet.dart                (consume mealEventsByDayProvider filtered by id)

app/lib/features/recipes/
├── providers/
│   └── used_in_meals_provider.dart           (NEW — family-keyed by recipeId)
└── widgets/
    └── meals_using_this_recipe.dart          (StatefulWidget → ConsumerWidget)

app/lib/core/state/
└── mutation_failure_copy.dart                (extend with meal / calendar / event verb stubs)

app/test/features/meals/
├── meals_by_book_reactivity_test.dart
├── meal_detail_component_reactivity_test.dart
├── used_in_meals_reactivity_test.dart
└── meal_edit_screen_failure_snackbar_test.dart

app/test/features/calendar/
├── calendar_grid_event_reactivity_test.dart
├── day_sheet_reactivity_test.dart
├── plan_meal_sheet_failure_snackbar_test.dart
└── recurrence_debounce_stress_test.dart       (rmc-4 — 52-event storm, fakeAsync)

app/test/core/state/
└── meal_event_coalescer_test.dart             (rmc-4 unit test for the coalescer helper — fakeAsync)
```

## Story list with acceptance criteria

### rmc-1 — Meal mutation sites + meal providers reactivity

**AC**:
1. Every write method in `app/lib/features/meals/services/meal_service.dart` (`createMeal`, `updateMeal`, `addRecipeToMeal`, `removeRecipeFromMeal`, `reorderMealComponents`, `archiveMeal`, `restoreMeal`, `favoriteMeal`, `unfavoriteMeal`) emits exactly one MutationBus event on server 2xx with the payload shape documented above. `share` is stubbed with a TODO deferring to the sharing epic (explicit comment; no emit yet).
2. `MealService` holds no list/detail state (verified — already the case; re-assert via a code review checklist item).
3. `mealsByBookProvider(bookId)` body adds `ref.listen(mutationBusProvider, ...)` filtering to `MealCreated | MealUpdated | MealArchived | MealUnarchived | MealFavorited | MealComponentAdded | MealComponentRemoved` with `event.bookId == bookId` filter; invalidates via `ref.invalidateSelf()`.
4. `mealsAllProvider` subscribes to the same union without `bookId` filter.
5. `mealByIdProvider(mealId)` subscribes to `MealUpdated | MealComponentAdded | MealComponentRemoved | MealComponentsReordered` with `event.mealId == mealId` filter. On match with a full-Meal payload, patches via `state = AsyncData(event.updatedMeal)` — **no refetch round-trip**. On `MealFavorited` with `updatedMeal == null`, falls back to `ref.invalidateSelf()`.
6. `invalidateMeal(ref, mealId, bookId)` helper stays as a one-release shim; its body becomes `ref.invalidate(mealByIdProvider(mealId))` only (service handles the emits). All existing call sites in `meal_edit_screen.dart` / `meal_detail_screen.dart` continue to compile unchanged for backward compat.
7. Mutation-failure paths in `meal_edit_screen.dart`, `meal_detail_screen.dart`, `create_meal_sheet.dart` call `showMutationFailureSnackbar(context, MutationType.<verb>, retry: ...)` — no more raw `ScaffoldMessenger.showSnackBar(SnackBar(...))` in these files.
8. Copy stubs added to `mutation_failure_copy.dart` for `createMeal`, `updateMeal`, `archiveMeal`, `unarchiveMeal`, `favoriteMeal`, `unfavoriteMeal`, `addComponent`, `removeComponent`, `reorderComponents`.
9. Widget test `meal_detail_component_reactivity_test.dart`: pump Meal detail with mocked `mealByIdProvider` returning a 2-component Meal; emit `MealComponentAdded(mealId, recipeId, 3-component-Meal)`; pump one microtask + one frame via `pumpWithMutation` helper (from Foundation rf-1); assert (a) the third component appears in the chip strip; (b) no refetch round-trip occurred (mocked API client call count unchanged).
10. Integration test `meals_by_book_reactivity_test.dart`: drive `MealService.createMeal` through a mocked ApiClient; assert `MealCreated` is emitted exactly once with the expected `bookId` payload; assert `mealsByBookProvider(bookId)` invalidates exactly once.

### rmc-2 — "Used in these Meals" reactivity on Recipe detail

**AC**:
1. `app/lib/features/recipes/providers/used_in_meals_provider.dart` exists as `FutureProvider.family.autoDispose<List<MealSummary>, String>` keyed by `recipeId`; fetches via `MealService.listMealsUsingRecipe(recipeId)`.
2. Provider body includes `ref.listen(mutationBusProvider, ...)` filtering to `MealComponentAdded | MealComponentRemoved` with `event.recipeId == recipeId` filter; invalidates via `ref.invalidateSelf()`. Also subscribes to `MealArchived` / `MealUnarchived` / `MealUpdated` with **no** recipe filter (because the provider is a list; the cross-lookup result can change when any referenced meal mutates) — **but** invalidation for these broader events is gated by the 100ms coalescer to avoid a refetch per unrelated meal change. Narrow filter first, debounce as fallback.
3. `MealsUsingThisRecipe` widget converts from `StatefulWidget + FutureBuilder` to `ConsumerWidget + ref.watch(usedInMealsProvider(widget.recipeId))`. The load-bearing "empty / error → `SizedBox.shrink()`" invariant is preserved (see `meals_using_this_recipe.dart` comment block) — critical for public recipe pages (`public_recipe_screen.dart`) which do NOT mount this widget.
4. Widget test `used_in_meals_reactivity_test.dart`:
   - (a) Pump Recipe detail with mocked `usedInMealsProvider(recipeId)` returning `[MealA]`; assert MealA chip visible.
   - (b) Emit `MealComponentAdded(mealId: MealB.id, recipeId: recipeId, updatedMeal: MealB)` via `pumpWithMutation`.
   - (c) Mock provider's next fetch returns `[MealA, MealB]`.
   - (d) Assert MealA and MealB both visible; no skeleton between refresh (valueOrNull guard).
5. Public recipe screen test: assert `MealsUsingThisRecipe` is NOT mounted (privacy invariant preserved; unchanged by this epic).

### rmc-3 — Calendar + meal-event mutation sites + list providers

**AC**:
1. `CalendarService.createCalendar` / `updateCalendar` / `deleteCalendar` emit `CalendarCreated` / `CalendarUpdated` / `CalendarDeleted`. Member-CRUD methods (`updateCalendarMember`, `removeCalendarMember`, `leaveCalendar`) have TODO stubs deferring to `epic-calendars-sharing`; no emit.
2. `MealCalendarService` emits on every write: `createMealEvent`, `updateMealEvent`, `moveMealEventToCalendar` (delegates `MealEventUpdated`), `rescheduleMealEvent` (delegates `MealEventUpdated`), `deleteMealEvent`, `markMealCompleted`, `createRecurrenceRule`, `updateRecurrenceRule`, `deleteRecurrenceRule`, `moveRecurrenceRuleToCalendar` (delegates `RecurrenceRuleUpdated`).
3. `markMealCompleted(eventId)` signature changes from `Future<void>` to `Future<MealEvent>` — the backend endpoint already returns the full updated event (via `PATCH /v1/meal-events/{id}`); today the method discards the response. All call sites (`calendar_screen.dart._markMealCooked`) updated; `_loadEvents()` call removed (replaced by provider invalidation triggered by the event).
4. `calendarsListProvider` subscribes to `CalendarCreated | CalendarUpdated | CalendarDeleted` → invalidates. `activeCalendarProvider`'s `clearInvalid()` flow stays unchanged (uses explicit invalidate; not a MutationBus path).
5. `mealEventsByRangeProvider((start, end, calendarId))` exists as `FutureProvider.family.autoDispose`. Subscribes to `MealEventCreated | MealEventUpdated | MealEventDeleted | MealEventCompleted` with range-containment filter (`start ≤ event.scheduledAt ≤ end && event.calendarId == calendarId`). Also subscribes to `RecurrenceRule*` events (no filter; the rule may generate new events in any range). Invalidation goes through the 100ms coalescer (see `rmc-4`).
6. `mealEventsByDayProvider((date, calendarId))` exists; filters by exact-date-match (date-truncated comparison on local TZ). Same 100ms coalescer.
7. `upcomingEventsForMealProvider(mealId)` exists; filters `MealEvent*` by `event.mealId == mealId`; coalesces. Provider returns only future events (server-side filter via `?since=now` query, if supported; else client-side).
8. `calendar_screen.dart` refactored: `_CalendarScreenState` stops maintaining `_eventsByDay` map via imperative `_loadEvents()` + `_loadGeneration` counter. Instead `ref.watch(mealEventsByRangeProvider((weekStart, weekEnd, activeCalendarId)))` drives the grid. `_loadGeneration` deleted. `_loadEvents()` deleted. Child sheet callbacks (`onEventsChanged`, etc.) deleted.
9. `day_detail_sheet.dart` consumes `mealEventsByDayProvider`; no parent callback for refresh.
10. Widget test `calendar_grid_event_reactivity_test.dart`: pump calendar screen with mocked `mealEventsByRangeProvider` returning `[]`; emit `MealEventCreated(mealEvent in visible range)`; assert cell renders the new event within one pump + one frame; assert no skeleton flash (valueOrNull visible during refetch).
11. Widget test `day_sheet_reactivity_test.dart`: pump day sheet open on Friday; emit `MealEventCompleted(event_on_friday_id)`; assert the sheet's event card re-renders with a cooked indicator.
12. Widget test `plan_meal_sheet_failure_snackbar_test.dart`: pump plan-meal sheet; mock `createMealEvent` to throw `DioException`; tap save; assert `showMutationFailureSnackbar` is called with `MutationType.planMealEvent`; sheet stays open.

### rmc-4 — Recurrence materialization debounce correctness

**AC**:
1. A dedicated `MealEventCoalescer` helper lives in `app/lib/core/state/` (reusable — other providers can adopt the same 100ms pattern). Helper wraps a `Timer`, exposes `schedule(VoidCallback)` and `cancel()`; `schedule` resets the timer to 100ms.
2. Unit test `meal_event_coalescer_test.dart` uses `package:fake_async` (`FakeAsync.run((async) { ... })`) — **NOT wall-clock `Future.delayed`**:
   - (a) Schedule 52 callbacks within 50ms of fake time; advance fake time by 50ms; assert **zero** callback invocations.
   - (b) Advance fake time by another 100ms (total 150ms); assert **exactly one** invocation.
   - (c) Cold-stop: schedule, advance 50ms, call `cancel()`, advance 200ms; assert zero invocations.
   - (d) Last-event-elision guard: schedule 52 callbacks over 50ms (each 1ms apart); advance to 150ms from last schedule; assert the final invocation happens (timer fires on the *last* callback, not dropped).
3. Stress test `recurrence_debounce_stress_test.dart` (widget-test harness, not isolated unit):
   - (a) Pump a calendar screen with `mealEventsByRangeProvider` mocked to return an initial event set.
   - (b) Using `FakeAsync`, emit 52 `MealEventCreated` events in 50ms (one per ms), each for a distinct event in the visible range.
   - (c) Advance fake time by 150ms.
   - (d) Assert mocked API client's `listMealEventsForRange` was called **exactly once** during the flood (the pre-flood load counts separately; assertion is on post-emit refetches).
   - (e) Assert all 52 events are visible in the final pumped frame (completeness, not just debounce).
   - (f) Assert `ref.onDispose` of the provider cancels the pending timer cleanly — mount/unmount the provider mid-flood; advance fake time; assert no callback fires after unmount.
4. The coalescer does NOT introduce a third-party debounce package dependency — pure Dart `Timer`.
5. Cold-stop correctness (QA last-event-elision concern): the 52nd `MealEventCreated` emitted at T must trigger an invalidation, not be elided by a subsequent disposal. AC #3f covers this.

### rmc-5 — Regression sweep + end-to-end tests + copy map

**AC**:
1. End-to-end widget test (or `integration_test/`): create Meal flow — pump Home → tap + → pick 3 recipes → save → pop → assert Home grid contains the new meal tile within one frame of the mocked server 200, no pull-to-refresh gesture.
2. End-to-end widget test: add-component flow — pump Meal detail → tap Add Recipe → pick a recipe → assert (a) detail chip strip updates; (b) if Recipe detail for the picked recipe is simultaneously mounted (integration harness with two screens stacked), "Used in these Meals" row updates.
3. End-to-end widget test: plan-meal flow — pump Calendar (Friday visible) → tap Friday → plan "Sunday Roast" → assert (a) Friday cell renders a new chip; (b) day sheet list contains the event (if day sheet is open).
4. End-to-end widget test: mark-cooked flow — pump Calendar with a meal event on today → tap Mark Cooked on the event card → mocked API returns updated event with `status=completed` → assert (a) grid cell chip shows cooked indicator; (b) no refetch beyond the one triggered by `MealEventCompleted`.
5. All existing meal / calendar widget tests pass unchanged.
6. `mutation_failure_copy.dart` has entries for every meal / calendar / event verb (`createMeal`, `updateMeal`, `archiveMeal`, `unarchiveMeal`, `favoriteMeal`, `unfavoriteMeal`, `addComponent`, `removeComponent`, `reorderComponents`, `createCalendar`, `updateCalendar`, `deleteCalendar`, `createMealEvent`, `updateMealEvent`, `rescheduleMealEvent`, `moveMealEvent`, `deleteMealEvent`, `markMealCompleted`, `createRecurrenceRule`, `updateRecurrenceRule`, `deleteRecurrenceRule`, `moveRecurrenceRule`). Copy is 320px-safe (verified in `rf-1` by UX; reused here).
7. Deterministic CI: all new tests use `pumpWithMutation` or `FakeAsync` — no `pumpAndSettle` with wall-clock timeouts, no `Future.delayed` in test bodies. Per-test p95 runtime <2s.
8. Grep sweep: any `ScaffoldMessenger.of(context).showSnackBar(...)` call in `app/lib/features/meals/` or `app/lib/features/calendar/` that was previously a mutation-failure path has been migrated to `showMutationFailureSnackbar`. Non-mutation snackbars (e.g., cook-mode feedback success toasts) remain unchanged.

## Dependencies

- **Cross-epic**: Depends on `epic-reactive-foundation-home-imports` (MutationBus + `mutation_failure_copy.dart` + `mutation_snackbar.dart` + test helper + all Meal*/Calendar*/MealEvent* stubs via `rf-1`). Foundation `rf-2` meal-favorite shape fix is a soft dependency — if not live when `rmc-1` starts, event carries ids only; acceptable.
- **Parallelizable with** `epic-reactive-migration-books-profile-pantry-and-polish`.
- **Internal ordering**: rmc-1 → rmc-2 (Meal events must exist as emitted types before usedInMeals can subscribe); rmc-3 ↔ rmc-1 (can parallelize — different surfaces); rmc-4 blocks rmc-3's AC #5/#6/#7 invalidation path; rmc-5 closes after all four.
- **No backend dependency** net-new; Foundation `rf-2` covers the one inherited gap.

## Resolved questions

- ~~Component reorder: new event type or `MealUpdated`?~~ → **Resolved (locked above)**: `MealComponentsReordered` — searchable, semantically distinct, avoids subscriber over-invalidation.
- ~~Mark-as-cooked vs. cook-mode-completed: single event or two?~~ → **Resolved**: `MealEventCompleted` only. `CookingLogCreated` is a separate concern; cooking logs aren't rendered on any meal/calendar surface, so they ship with books/profile/pantry migration (recipe detail's cooking history block).
- ~~`CalendarMemberAdded/Removed` now or later?~~ → **Resolved**: deferred to `epic-calendars-sharing`. Stubs ship there.

## Escalation for the user

**None**. All three previously-open questions resolved in party-mode; no blockers before `rmc-1` starts.

One **cross-epic decision to propagate to `epic-reactive-migration-books-profile-pantry-and-polish`**: `CookingLogCreated` MutationBus event should land in that epic's recipe-detail-cooking-history subscribe surface. Added as a note for that epic's planner to pick up — not a story this epic owns.

## Risks

- **Recurrence-materialization refetch storm** (addressed in `rmc-4`). If the coalescer has a correctness bug, 52 events → 52 refetches → OOM-loop risk. Mitigation: `rmc-4` AC #3 exhaustive stress test with `FakeAsync`. Also: all three meal-event list providers share the coalescer helper — one correct implementation protects all three.
- **`MealComponentAdded/Removed/Reordered` event types not searchable in today's codebase**: downstream epics (sharing, AI tools) must know about them. Mitigation: stubs added in Foundation `rf-1` so cross-epic adopters don't re-edit `mutation_event.dart`.
- **Calendar grid p95 regression**: the grid currently fetches a week window on mount via `_loadEvents()`. If subscription-invalidation + coalesce change the fetch pattern, p95 could regress. Mitigation: coalesce should reduce fetches (52 → 1), not increase; `rmc-5` regression test asserts visible re-render within one frame post-emit, NOT a wall-clock p95 bound.
- **`MealFavorited` payload shape depends on Foundation `rf-2` meal-favorite landing**: if rf-2 is delayed or rolled back, this epic's favorite path is degraded (ids-only payload + invalidate). Mitigation: event type is null-safe (`updatedMeal: Meal.Response | null`); subscribers fall back cleanly.
- **`MealService.archiveMeal` slim response**: archive endpoint returns `{success, archived_at}` — event carries ids only. Detail cache for the archived meal is invalidated; next read returns the archived Meal (which includes `archived_at`). Acceptable — archived-meal-detail is a rare surface.

### Risks identified via party-mode

- **(PM) The four-step scripted dogfood session is the ground-truth check.** Six passing CI widget tests are necessary but not sufficient. If any of the four scripted steps fails after CI passes, the epic is not done — `bmad-bmm-correct-course` is the response. Captured in the "Single measurable proof" block under Goal.
- **(UX) Recipe detail + Meal detail open simultaneously.** Draft didn't explicitly call out the split/tab case. Flow B covers it; `rmc-2` AC #4 tests the exact case. No flicker risk because `valueOrNull` + `isRefreshing` is inherited from Foundation's loading-flicker guard — same pattern applies to every ConsumerWidget surface migrated here.
- **(Frontend) Draft confused `CalendarService` vs. `MealCalendarService`.** Meal events live on `MealCalendarService`; `CalendarService` is only for calendar CRUD + member ops. All emit paths split correctly; `rmc-3` AC #1 vs #2 reflect the split.
- **(Frontend) Draft invented `mealDetailProvider` that doesn't exist.** Real name is `mealByIdProvider`. Corrected in the provider inventory table and all AC references.
- **(Frontend) Draft invented `favoriteMealsProvider`.** No such provider today — Home grid's favorites carousel is a fan-out slot in `homeContentProvider`. Removed from scope; no new provider needed.
- **(Backend/Architect) Draft's "zero backend changes" was slightly wrong.** Meal favorite is a slim response (fixed by Foundation `rf-2`); archive/restore + recurrence-update scope=occurrence are also slim. Called out explicitly in Backend changes § — no new net fixes here, but the "zero" framing would have been misleading.
- **(Backend/Architect) Server-side MCP meal mutations don't emit client events.** Not a bug today (partner-sees-my-change deferred). If/when cross-device reactivity lands, MCP mutations will need a WS broadcast. Out of scope.
- **(Infra) Deploy order.** Since this epic has near-zero backend changes, client can ship independently once Foundation `rf-2` is live. If someone force-ships client before Foundation rf-2: degraded meal-favorite path (no full payload); functional but extra round-trip. Documented; no action required.
- **(QA) Cold-stop correctness on the coalescer.** Draft didn't explicitly test last-event-elision. `rmc-4` AC #2d covers it — the 52nd emit at T must still trigger exactly one invalidation at T+100ms, not be elided.
- **(QA) FakeAsync contract.** All timer-based tests (`rmc-4`) run inside `FakeAsync.run(...)`. Wall-clock waits are banned in these tests — `pumpAndSettle` too. Enforced by `rmc-5` AC #7 grep sweep.
- **(Architect) `markMealCompleted` signature change is a breaking API change for the service method.** Only one call site today (`calendar_screen.dart._markMealCooked`); updated in the same PR. No external-package consumers.
