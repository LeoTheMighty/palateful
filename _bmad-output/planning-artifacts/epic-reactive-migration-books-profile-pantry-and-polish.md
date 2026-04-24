<!-- refined via party-mode 2026-04-22 -->
# Epic — Reactive Migration: Recipe Books + Profile + Pantry + Failure-UX Polish

**Planned**: 2026-04-22
**Scope split**: Migration epic #2 of 2 — closes the remaining mutation sites (recipe books, profile + notification prefs, pantry) on MutationBus, stands up the **three service classes that don't exist today** (`RecipeBookService`, `ProfileService`, `NotificationPrefsService`), consolidates `ShoppingCartService` WS handlers onto the bus, collapses `PantryService`'s hidden list-state cache, picks up the `CookingLogCreated` surface handed off from the meals/calendar epic, and ships the central mutation-failure copy map + Snackbar wiring across every mutation site landed in the foundation and first migration epic.
**Depends on**: `epic-reactive-foundation-home-imports` (MutationBus primitive + Snackbar helper + test harness). Hands down from `epic-reactive-migration-meals-calendar` the `CookingLogCreated` event surface (see "Inherited handoff" below).
**Parallelizable with**: `epic-reactive-migration-meals-calendar`.
**Status**: backlog

## Overview

Foundation epic ships MutationBus + migrates Home and Imports. First migration epic covers meals, calendars, meal-events. This epic is the cleanup pass — every remaining mutation site across the app joins the MutationBus convention:

- **Recipe books** (create, rename, archive, unarchive, delete, member-role update, member add/remove) — requires **creating `RecipeBookService`**; today every write is `_apiClient.*` from inside screen `_State` objects.
- **Profile + notification preferences** (display name, avatar, username, per-category toggles, scalar prefs like quiet hours) — requires **creating `ProfileService` + `NotificationPrefsService`**; today profile writes live in `_ProfileScreenState.setState` closures, and prefs writes live in `_NotificationPreferencesScreenState._toggleCategory` + `_updatePreference` closures.
- **Pantry** (add, update, remove) — service exists but **holds local list state** via an internal `_current: Pantry?` cache and a `StreamController<Pantry?>`; this epic refactors it to a stateless API client per Foundation Locked Decision #9, collapsing onto the MutationBus + a new `pantryIngredientsProvider(pantryId)`.
- **Recipe-detail cooking-history** — new `CookingLogCreated` event lands here; see "Inherited handoff" below.
- **Central failure-UX polish**: one copy map, one Snackbar helper, every mutation site in every epic wired to it.
- **ShoppingCartService WS-adapter consolidation**: `_handleMessage`'s `item_added` / `item_updated` / `item_checked` / `item_removed` branches emit MutationBus events alongside their existing StreamController sinks. `presence_update` and `sync_response` are **not** mutations and do not emit (UX raised this — presence is transient session state, not a resource mutation). The `ShoppingListScreen` rewrite is explicitly **deferred** to a follow-on; external `ShoppingCartService` API stays source-compatible.

## Inherited locked decisions (foundation epic — NOT re-litigated)

All nine locked decisions from `epic-reactive-foundation-home-imports` § "Locked decisions for downstream epics" apply verbatim here. In particular:

- Service-layer emits (decision #1) — every mutation emit lives inside a service method. Where the service doesn't exist today (`RecipeBookService`, `ProfileService`, `NotificationPrefsService`), we create it before wiring emits.
- `ref.listen(mutationBusProvider, ...)` + `ref.invalidateSelf()` / `ref.invalidate(instance)` distinction (decision #2).
- Bulk events + 100ms coalesce fallback (decision #3 + #4).
- Long-lived singleton `StreamController.broadcast()` + non-autoDispose `Provider<Stream>` (decision #5).
- Reconcile-only for v1 (decision #6) — **but see the notification-prefs toggle resolution below: current code is already optimistic with rollback, we preserve that, and document it as the single exception to reconcile-only specifically for UI toggles where server-confirm latency is user-visible**.
- Toast + auto-rollback via `mutation_snackbar.dart` (decision #7).
- No new WebSocket routes (decision #8).
- `getIt` services stateless (decision #9) — **enforced here on `PantryService`**, which violates it today.

## Inherited handoff from `epic-reactive-migration-meals-calendar`

That epic explicitly deferred `CookingLogCreated` to this one, citing "cooking logs aren't rendered on any meal/calendar surface; when the recipe-details cooking-history block gets MutationBus wiring, it'll land in the books/profile/pantry epic." Picked up here.

- **Emit site**: `PostCookFeedbackSheet`'s submit handler (currently writes `cooking_log` via `_apiClient.*` directly; the handler gets extracted into a small `CookingLogService.create(...)` as part of `rp-3` so emits live at the service layer per Locked Decision #1).
- **Event**: `CookingLogCreated(cookingLog: CookingLog.Response, recipeId: string)`.
- **Subscribers**:
  - `recipeCookingHistoryProvider(recipeId)` (**NEW** — `FutureProvider.family.autoDispose<List<CookingLog>, String>`) — lives in `app/lib/features/recipes/providers/cooking_history_provider.dart`. Subscribes to `CookingLogCreated` with `event.recipeId == recipeId` filter; invalidates.
  - The recipe-detail screen's cooking-history block (today a `StatefulWidget` with one-shot `initState` fetch; converted to `ConsumerWidget + ref.watch(recipeCookingHistoryProvider(recipeId))` here). **Confirm file name in `rp-3`** — the current block lives in `recipe_detail_screen.dart` inline; if it's inline, extraction into a `RecipeCookingHistorySection` widget is in scope.
- **Scope fold**: lands as part of `rp-3` (Pantry + CookingLog — both are "a service that ought to exist but partially doesn't"; grouping them keeps the story size consistent with the others).

## Goal

**Outcome**: Every remaining mutation site — books, profile, prefs, pantry, cooking logs, plus the WS-mirrored shopping-list path — follows the MutationBus convention. Mutation failures everywhere show tap-to-retry Snackbars with centralized verb/noun copy. No list surface in the app goes stale until refresh after a user mutation.

**Single measurable proof (PM scripted dogfood)**: Leo runs one scripted session after ship on **one device**:

1. Open a recipe book → **Rename** → "Weeknight Wins" → assert (a) books-list shows the new name; (b) Home header for the active book shows the new name; (c) profile → "Shared with you" shows the new name — all without pull-to-refresh.
2. Profile → Notifications → toggle **Meals** off → assert the toggle moves **immediately** (optimistic, preserves today's UX); force a failure via airplane-mode mid-tap and assert the toggle snaps back + Snackbar appears.
3. Pantry → **+** → add "Flour" → assert the row appears in the list within one frame of server 200; no pull-to-refresh.
4. Shopping list is open on both phones (Leo + partner) → partner taps **+** → partner adds "Milk" → assert Leo's shopping list shows "Milk" within one frame (already works via WS; assert it ALSO works after WS-adapter consolidation lands).
5. Recipe detail → tap **Mark Cooked** → complete cook-feedback sheet → assert the cooking-history block on the same recipe detail screen shows the new entry without refresh.
6. Induce one mutation failure (e.g., archive a book with airplane mode on) → assert central Snackbar fires with `"Couldn't archive recipe book. Tap to retry."` → tap retry → toggle airplane off → assert success reconciles.

If all six pass, the epic is "done" from end-user vantage. Distinct from CI-level proof.

**CI-level proof**: Every mutation type in the full events catalog has a passing regression test. A grep-guard in CI (`tools/no-silent-catch-check.sh`) fails if any `catch` block in a `*Service.dart` file swallows an exception without calling `showMutationFailureSnackbar` OR being in the allowlist. A unit test in `mutation_failure_copy_test.dart` enumerates every `MutationType` enum value and asserts a copy-map entry exists.

## End-user flow

### Flow A: "I renamed a recipe book"

1. Leo opens recipe-book detail → **Rename** → "Weeknight Wins" → **Save**.
2. `RecipeBookService.rename(bookId, newName)` (**new class**) calls `PUT /v1/recipe-books/{id}` — the endpoint already returns the full `RecipeBook.Response` (verified in backend audit). On 200 the service emits `MutationEvent.RecipeBookUpdated(RecipeBook.Response)` before returning.
3. Books list screen — `recipeBooksProvider` subscribes to `RecipeBookCreated | Updated | Archived | Unarchived | MemberChanged` — invalidates; list shows the new name.
4. Home header (active book's name) — `homeContentProvider` already subscribes to the relevant union via Foundation rf-3; patches/refetches in place.
5. Shared-books screen (Profile → Shared) — `sharedRecipeBooksProvider` subscribes; re-renders.

### Flow B: "I toggled 'Notify me about meal reminders' off" (optimistic — see resolved question #1)

1. Leo opens Profile → Notifications → toggles the Meals category off.
2. Toggle visually flips **immediately** — optimistic, matches today's behavior. (`_optimisticCategoryState[key] = false`.)
3. `NotificationPrefsService.updateCategoryPref(category='meals', enabled=false)` (**new class**) calls `PUT /v1/users/me/notification-preferences` with `{categories: {meals: false}}`. Endpoint returns the full prefs blob.
4. On 200: service emits `MutationEvent.NotificationPrefsUpdated(fullPrefsBlob)`; `notificationPrefsProvider` patches from the payload; the optimistic local state is discarded (server is source of truth going forward).
5. On 4xx/5xx: the optimistic toggle **snaps back** to its pre-tap state (uses `mutation_snackbar.dart`'s rollback callback hook — see rp-2 AC #4); central Snackbar shows `"Couldn't update notification preferences. Tap to retry."`; retry re-invokes the service call.

### Flow C: "I added a pantry ingredient by name"

1. Leo opens Pantry → taps **+** → types "Flour" → **Add**.
2. `PantryService.addPantryIngredient(pantryId, data)` — refactored to be **stateless**: calls `POST /v1/pantries/{id}/ingredients`, parses `PantryIngredient.Response`, emits `MutationEvent.PantryItemAdded(PantryIngredient.Response, pantryId)`, returns. No more internal `_current` cache; no more `_pantryController.add(...)`.
3. `pantryIngredientsProvider(pantryId)` (**new** `FutureProvider.family.autoDispose`) subscribes to `PantryItemAdded | PantryItemUpdated | PantryItemRemoved` with `event.pantryId == pantryId` filter → invalidates.
4. `PantryListScreen` (`StatefulWidget` today) is converted to `ConsumerWidget + ref.watch(pantryIngredientsProvider(pantryId))`. Undo-delete UX is preserved (the existing `SnackBarAction(label: 'Undo', ...)` pattern is NOT replaced by the central failure Snackbar — it's a success-flow undo, not a failure rollback).

### Flow D: "Shopping list WS frame arrives — partner just added an item"

1. Partner taps **+** on the shopping list on her phone → server-side broadcast fires a WS `item_added` frame.
2. Leo's `ShoppingCartService._handleMessage` switch hits `case 'item_added'` — the existing `_itemAddedController.add(item)` line stays; a new `emitMutation(ShoppingListItemAdded(item, listId: _currentListId!))` line follows it.
3. Every downstream subscriber (future `shoppingListProvider` if landed; `activityHubProvider` for badge count if subscribed) reacts as if Leo had added the item locally.
4. Existing `ShoppingListScreen` setState handler on `_itemAddedController` still fires. **ShoppingListScreen rewrite is explicitly deferred** (see resolved question #2) — scope-boundary preserved.

### Flow E: "I marked a recipe cooked" (inherited from meals epic)

1. Leo on Recipe detail → **Mark Cooked** → `PostCookFeedbackSheet` → rates → submits.
2. `CookingLogService.create(recipeId, feedback)` (**new class**) calls `POST /v1/recipes/{id}/cooking-logs`, on 200 emits `CookingLogCreated(CookingLog.Response, recipeId)`.
3. `recipeCookingHistoryProvider(recipeId)` subscribes; invalidates; the cooking-history section on the same screen refetches and shows the new entry.

### Flow F: "My mutation failed"

1. Leo archives a recipe book (or any mutation in any feature). Network blips mid-request.
2. Catch-block in the handler calls `showMutationFailureSnackbar(context, MutationType.archiveRecipeBook, retry: () => handler())`.
3. Snackbar appears: `"Couldn't archive recipe book. Tap to retry."` (verb + noun come from `mutation_failure_copy.dart`).
4. Tap invokes `retry`. Success → reconciles via MutationBus emit. Repeat failure → Snackbar re-appears.
5. Same flow for every mutation site across every feature. No per-feature ad-hoc error handlers in `*Service.dart` files (enforced by the grep guard).

## Frontend changes

### Service inventory — what exists vs. what's new (VERIFIED against codebase)

| Service | Status | File | Notes |
|---|---|---|---|
| `RecipeBookService` | **DOES NOT EXIST** — create it | `app/lib/features/recipe_books/services/recipe_book_service.dart` (new) | Recipe-book CRUD today lives as raw `_apiClient.*` calls inside `_RecipeBookDetailScreenState`, `_RecipeBooksScreenState`, `_ArchivedRecipeBooksScreenState`, `_RecipeBookMembersScreenState`. Service absorbs: `create`, `updateRecipeBook` (rename), `archive`, `restore`, `delete`, `listRecipeBooks`, `getRecipeBook`, `addMember`, `updateMemberRole`, `removeMember`, `bulkMoveRecipes`, `bulkArchiveRecipes`, `bulkUpdateTags`. |
| `RecipeBookSyncService` | **Exists** — WS only | `app/lib/features/recipe_books/services/recipe_book_sync_service.dart` | Keeps external API. WS handlers `_handleMessage` (cases `recipe_added`, `recipe_updated`, `recipe_removed`) add `emitMutation(Recipe*)` calls **after** firing their existing StreamControllers. Parallel to `ShoppingCartService` consolidation — lower WS frames into MutationBus. |
| `ProfileService` | **DOES NOT EXIST** — create it | `app/lib/features/profile/services/profile_service.dart` (new) | Absorbs the raw `_apiClient.*` calls currently inside `_ProfileScreenState`: `getMe`, `updateProfile(name/bio)`, `setUsername`, `submitFeedback`, `exportRecipes`. |
| `NotificationPrefsService` | **DOES NOT EXIST** — create it | `app/lib/features/profile/services/notification_prefs_service.dart` (new) | Absorbs raw calls inside `_NotificationPreferencesScreenState`: `getNotificationPreferences`, `updateNotificationPreferences` (single scalar write + per-category write). Merges both the `_toggleCategory` path and the `_updatePreference` path. |
| `PantryService` | **Exists — but refactor required** | `app/lib/features/pantry/services/pantry_service.dart` | Today holds `_current: Pantry?` + `StreamController<Pantry?>`. Violates Foundation Locked Decision #9. Refactor: delete `_current`, delete `_pantryController`, delete `dispose`/`loadDefaultPantry` (moves into the new `pantryProvider`). Service becomes a thin API-client that emits on mutations. **Breaking API change**: `PantryListScreen`'s `StreamSubscription<Pantry?>` pattern is replaced by `ref.watch(pantryIngredientsProvider(pantryId))`. |
| `CookingLogService` | **DOES NOT EXIST** — create it | `app/lib/features/recipes/services/cooking_log_service.dart` (new) | Absorbs the `_apiClient.*` call in `PostCookFeedbackSheet`'s submit handler. Single method: `create(recipeId, feedbackBlob)`. |
| `ShoppingCartService` | **Exists — add emits to `_handleMessage`** | `app/lib/features/shopping_cart/services/shopping_cart_service.dart` | No structural refactor. Inside the existing `_handleMessage(data)` `switch(type)` statement: cases `item_added` / `item_updated` / `item_checked` / `item_removed` each get one new line: `emitMutation(ShoppingListItem*(item, listId: _currentListId!))`. Cases `presence_update`, `sync_response`, `pong`, `connected` do **not** emit (not mutations). Local (non-WS) mutations via `addItem`/`updateItem`/`toggleItemChecked`/`deleteItem` also emit (on their success branch). Dual-path idempotence: if local mutation + WS frame both fire for the same id, subscribers refetch twice (wasteful but not incorrect — matches Foundation's WS/MutationBus duplication risk mitigation). |
| `AuthService` | **No profile-data state** — no change | `app/lib/core/services/auth_service.dart` | Verified: holds only auth tokens + `default_recipe_book_id`/`default_shopping_list_id`/`_hasCompletedOnboarding`/`_isAdmin`. No display name, no avatar, no prefs. No collapse needed. |

### Provider inventory — new vs. existing (VERIFIED)

| Provider | Status | File |
|---|---|---|
| `recipeBooksProvider` | **NEW** — `FutureProvider.autoDispose<List<RecipeBook>>` | `app/lib/features/recipe_books/providers/recipe_books_provider.dart` (new) |
| `archivedRecipeBooksProvider` | **NEW** — same file |
| `activeRecipeBookProvider(bookId)` | **NEW** — `FutureProvider.family.autoDispose` | same file |
| `sharedRecipeBooksProvider` | **NEW** — flat list of books Leo is a member of but not owner of | same file |
| `recipeBookMembersProvider(bookId)` | **NEW** — `FutureProvider.family.autoDispose` | same file |
| `profileProvider` | **NEW** — `FutureProvider.autoDispose<UserProfile>` | `app/lib/features/profile/providers/profile_provider.dart` (new) |
| `notificationPrefsProvider` | **NEW** — `FutureProvider.autoDispose<NotificationPrefs>` | `app/lib/features/profile/providers/notification_prefs_provider.dart` (new) |
| `pantryIngredientsProvider(pantryId)` | **NEW** — `FutureProvider.family.autoDispose<List<PantryIngredient>, String>` | `app/lib/features/pantry/providers/pantry_provider.dart` (new) |
| `defaultPantryProvider` | **NEW** — `FutureProvider.autoDispose<Pantry>` (the pantry meta, not the ingredients) | same file |
| `recipeCookingHistoryProvider(recipeId)` | **NEW** — `FutureProvider.family.autoDispose<List<CookingLog>, String>` | `app/lib/features/recipes/providers/cooking_history_provider.dart` (new) |

### Screens touched

- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — replace every `_apiClient.*` mutation with the new service method. Replace every `ScaffoldMessenger.showSnackBar(SnackBar(...))` in a mutation-failure path with `showMutationFailureSnackbar(context, MutationType.*, retry: ...)`. Remove the `_loadRecipeBook()` post-mutation call — rely on provider invalidation instead. WS subscription via `RecipeBookSyncService` **stays**; handlers can be simplified from `_loadRecipeBook()` on every event to trusting the MutationBus invalidation chain.
- `app/lib/features/recipe_books/recipe_books_screen.dart`, `archived_recipe_books_screen.dart`, `recipe_book_members_screen.dart` — same pattern. Consume the new providers; move mutations into the service.
- `app/lib/features/profile/profile_screen.dart` — `ConsumerWidget` + `ref.watch(profileProvider)`. Display-name / bio / username editors delegate to `ProfileService`. Failure paths → `showMutationFailureSnackbar`.
- `app/lib/features/profile/notification_preferences_screen.dart` — `ConsumerWidget` + `ref.watch(notificationPrefsProvider)`. `_toggleCategory` and `_updatePreference` delegate to `NotificationPrefsService`. **Keep** the optimistic-toggle local state — see resolved question #1.
- `app/lib/features/profile/shared_calendars_screen.dart` — consume `sharedRecipeBooksProvider` where it currently renders shared books (verify scope during `rp-1` implementation; may be out-of-scope if the screen actually shows calendars, not books).
- `app/lib/features/pantry/screens/pantry_list_screen.dart` — `ConsumerWidget` + `ref.watch(pantryIngredientsProvider(pantryId))`. Delete the `StreamSubscription<Pantry?>` + `_pantry` local state. Keep the swipe-to-dismiss undo Snackbar (success-flow UX, unchanged). Failure paths → `showMutationFailureSnackbar`.
- `app/lib/features/pantry/screens/pantry_editor_screen.dart` — delegate writes to `PantryService.updatePantryIngredient`. Failure → Snackbar.
- `app/lib/features/recipes/widgets/post_cook_feedback_sheet.dart` (verify filename during `rp-3`) — delegate the cooking-log write to the new `CookingLogService`. Failure → Snackbar.
- `app/lib/features/recipes/recipe_detail_screen.dart` — extract the inline cooking-history block into `RecipeCookingHistorySection` widget (file: `widgets/recipe_cooking_history_section.dart`). Convert to `ConsumerWidget + ref.watch(recipeCookingHistoryProvider(recipeId))`. No new mutation sites here; read-only subscribe.
- `app/lib/features/shopping_cart/services/shopping_cart_service.dart` — **surgical edit only**: add `emitMutation(...)` calls inside the existing `_handleMessage` switch (cases: `item_added`, `item_updated`, `item_checked`, `item_removed`). Plus: inside each local API method (`addItem`, `updateItem`, `toggleItemChecked`, `deleteItem`), add an `emitMutation(...)` on the success branch. No external API change; no structural refactor; ShoppingListScreen rewrite explicitly deferred.

### Mutation-failure central plumbing

- `app/lib/core/state/mutation_failure_copy.dart` — expanded from the foundation stub to cover every `MutationType` enum value across all four epics. Enum-keyed const map: `MutationType.renameRecipeBook → (verb: 'update', noun: 'recipe book')`, etc. See AC `rp-5 #1` for the enumeration test.
- `app/lib/core/state/mutation_snackbar.dart` — already lands in Foundation; this epic extends the optional `rollback` callback parameter for optimistic-toggle paths (e.g. notification prefs):
  ```dart
  void showMutationFailureSnackbar(
    BuildContext context,
    MutationType type, {
    required VoidCallback retry,
    VoidCallback? rollback,   // NEW — called once, immediately, before the Snackbar shows, for optimistic-UI sites
    String? suffix,
  });
  ```
- **Grep-guard** — see resolved question #3 (rp-5 AC #3 below): a shell script in `tools/no-silent-catch-check.sh` runs in CI. Decision: shell guard for v1, custom_lint deferred.

### Empty / loading / error states (UX)

- Books list / shared-books / archived-books: existing empty states unchanged.
- Profile / prefs: prefs-save error → rollback + central Snackbar; toggle visually snaps back.
- Pantry list: existing empty state unchanged. `valueOrNull`-during-refetch guard applies (no shimmer flash after a mutation).
- Recipe detail cooking-history: new `SizedBox.shrink()` on empty list (the block already handles empty gracefully today — verify during implementation).
- Shopping list: no visual change (WS path already works; new internal plumbing only).

### Non-optimistic vs. optimistic toggle UX spec (resolved question #1)

The draft's "non-optimistic notification-prefs toggle" was wrong — **today's notification-prefs toggle is already optimistic with rollback** (`_toggleCategory` in `notification_preferences_screen.dart`: `setState` first, then `await`, then revert on exception). The draft proposed a regression: wait for server-confirm + spinner + 300ms delay before the toggle moves.

**Resolution**: preserve today's optimistic behavior. Rationale (UX + Frontend): (a) a 300ms disabled-spinner state on every toggle tap is worse UX than the current pattern by any reasonable measure; (b) the Locked Decision #6 "reconcile-only for v1" means "don't add NEW optimistic paths" — it does not mean "rip out existing optimism that works"; (c) optimistic-toggle + rollback is the right pattern for toggles specifically, where the state is binary and server-confirm latency is user-visible.

**Spec**:
- Tap → `setState(() => _optimisticCategoryState[key] = value)` (or equivalent local state) — toggle flips immediately, within one frame (~16ms).
- Await service call.
- On success: service emits `NotificationPrefsUpdated(serverBlob)`; `notificationPrefsProvider` patches; local optimistic state is cleared; toggle stays in its new position (now server-confirmed).
- On failure: `setState(() => _optimisticCategoryState.remove(key))` (revert); `showMutationFailureSnackbar(context, MutationType.updateNotificationPrefs, retry: () => _toggleCategory(key, value), rollback: null /* already reverted */)`. Snackbar copy: `"Couldn't update notifications. Tap to retry."`.
- **Duration budget**: the local `setState` happens synchronously; no spinner, no dimming. Budget for the entire round-trip: 800ms p95 (same as Foundation's server-call budget). If the round-trip exceeds 5s, the Snackbar appears anyway on eventual failure; the toggle stays optimistically-flipped until then (user sees "it worked" until proven otherwise).
- **Failure-revert visual**: the toggle animates back to its pre-tap position (Flutter `Switch` handles this natively). No flash, no color change.

### Subscriber coalescing

All new list providers (`pantryIngredientsProvider`, `recipeBooksProvider`, `sharedRecipeBooksProvider`, `recipeCookingHistoryProvider`) use the `MutationEventCoalescer` helper from the meals/calendar epic (rmc-4). Pattern inherited:

```dart
final coalescer = MutationEventCoalescer();
ref.listen(mutationBusProvider, (prev, next) {
  if (!_shouldInvalidate(next)) return;
  coalescer.schedule(() => ref.invalidateSelf());
});
ref.onDispose(coalescer.cancel);
```

### New / extended event subtypes (stubs ship in Foundation rf-1; payloads finalized here)

- `RecipeBookCreated(RecipeBook.Response)`
- `RecipeBookUpdated(RecipeBook.Response)`
- `RecipeBookArchived(bookId, restoredDefaultBookId: String?)` — ids-only per backend shape (verified; endpoint returns `{success, restored_default_recipe_book_id}`).
- `RecipeBookUnarchived(RecipeBook.Response | null)` — shape TBD during `rp-1`; null-safe.
- `RecipeBookDeleted(bookId)`
- `RecipeBookMemberAdded(bookId, userId, role)`
- `RecipeBookMemberChanged(bookId, userId, newRole: String | null)` — null if removed.
- `NotificationPrefsUpdated(NotificationPrefs.Response)` — full blob; backend already returns full shape (verified in `update_notification_preferences` endpoint: `UpdateNotificationPreferences.Response` includes all scalar fields + `categories` map).
- `ProfileUpdated(User.Response)` — backend `PUT /users/me` already returns full object.
- `UsernameUpdated(newUsername)` — ids-only (response is slim; acceptable — username is single-surface).
- `PantryItemAdded(PantryIngredient.Response, pantryId)` — endpoint returns full `PantryIngredient` via `format_pantry_ingredient` (verified).
- `PantryItemUpdated(PantryIngredient.Response, pantryId)` — same.
- `PantryItemRemoved(ingredientId, pantryId)` — ids-only (DELETE returns summary; verified).
- `CookingLogCreated(CookingLog.Response, recipeId)` — **inherited from meals/calendar epic handoff**.
- `ShoppingListItemAdded(ShoppingListItem.Response, listId)` — emitted from BOTH local add AND WS frame lowering.
- `ShoppingListItemUpdated(ShoppingListItem.Response, listId)` — includes checked-off transitions (i.e., `item_checked` WS frame lowers to this; idempotent with the `item_updated` frame).
- `ShoppingListItemRemoved(itemId, listId)`
- **Non-events** (explicitly not emitted): `PresenceUpdate` (transient), `SyncResponse` (transport-level), WS `connected` / `pong` (keepalive).

## Backend changes

**None.** Verified endpoint-by-endpoint:

| Endpoint | Response | Event payload |
|---|---|---|
| `PUT /v1/recipe-books/{id}` | Full `UpdateRecipeBook.Response` (BaseModel) | Full in `RecipeBookUpdated` |
| `POST /v1/recipe-books/{id}/archive` | `{success, restored_default_recipe_book_id}` | ids-only `RecipeBookArchived` |
| `POST /v1/recipe-books/{id}/restore` | TBD (inspect during `rp-1`) | Null-safe payload |
| `DELETE /v1/recipe-books/{id}` | slim | ids-only |
| `PATCH /v1/recipe-books/{id}/members/{uid}` | member object | Full in `RecipeBookMemberChanged` |
| `PUT /v1/users/me` | Full `User.Response` | Full in `ProfileUpdated` |
| `PUT /v1/users/me/notification-preferences` | **Full prefs blob** (`UpdateNotificationPreferences.Response` — verified: `push_enabled`, `email_digest`, `quiet_hours_start`/`end`, `timezone`, `partner_activity`, `categories` map) | Full in `NotificationPrefsUpdated` |
| `POST /v1/pantries/{id}/ingredients` | Full `format_pantry_ingredient(result.row, ingredient=ingredient)` | Full in `PantryItemAdded` |
| `PATCH /v1/pantries/{id}/ingredients/{iid}` | Full `format_pantry_ingredient(row)` | Full in `PantryItemUpdated` |
| `DELETE /v1/pantries/{id}/ingredients/{iid}` | slim `{success}` | ids-only `PantryItemRemoved` |
| `POST /v1/recipes/{id}/cooking-logs` (verify path during `rp-3`) | Full `CookingLog.Response` (assume; audit in `rp-3`) | Full in `CookingLogCreated` |
| Shopping-list endpoints | Already return full items | Already matches shape |

**Net backend delta for this epic: zero.**

## Infrastructure changes

**None.** No new AWS resources, no Terraform, no env vars, no migrations.

**CI impact of the new grep guard (Infra-raised concern, resolved)**: `tools/no-silent-catch-check.sh` runs as a step in the existing `.github/workflows/*.yml` Flutter-test job. Expected runtime: <1s (grep over ~50 service files). Not a new job, not a new workflow — single step addition. No CI cost concern.

## Design principles (applied — not new)

1. **Service-before-emit.** If a service doesn't exist today, create it first, then wire emits. No emits from inside screen `_State` objects (exception: Foundation epic's `ImportHistoryScreen` edge case, already flagged as tech debt in that epic).
2. **Stateless services.** Every service in this epic's inventory holds zero list-state post-migration (including the refactored `PantryService`). `ShoppingCartService` + `RecipeBookSyncService` keep their WS transport-state (connection, sequence); that's transport, not domain state.
3. **Optimism only where already present.** Today's two optimistic paths — pantry delete + notification-prefs toggle — are preserved. No new optimistic paths introduced.
4. **Undo-Snackbars are distinct from failure-Snackbars.** The pantry delete's `SnackBarAction(label: 'Undo')` is a success-flow UX affordance and stays separate from `showMutationFailureSnackbar`. Grep-guard does not touch these (they're not in a `catch` block).
5. **WS-lowering is additive.** `ShoppingCartService` and `RecipeBookSyncService` WS handlers add emits alongside existing StreamController sinks — never replace.

## File structure

```
app/lib/features/recipe_books/
├── services/
│   ├── recipe_book_service.dart              (NEW — CRUD + emits)
│   └── recipe_book_sync_service.dart         (existing; add emits in _handleMessage)
├── providers/
│   └── recipe_books_provider.dart            (NEW — recipeBooksProvider, archivedRecipeBooksProvider, activeRecipeBookProvider, sharedRecipeBooksProvider, recipeBookMembersProvider)
├── recipe_book_detail_screen.dart            (migrate to service + failure Snackbars)
├── recipe_books_screen.dart                  (consume provider)
├── archived_recipe_books_screen.dart         (consume provider)
└── recipe_book_members_screen.dart           (consume provider)

app/lib/features/profile/
├── services/
│   ├── profile_service.dart                  (NEW — absorbs _apiClient.* calls)
│   ├── notification_prefs_service.dart       (NEW — absorbs _apiClient.* calls)
│   └── feedback_cache_service.dart           (existing; unchanged)
├── providers/
│   ├── profile_provider.dart                 (NEW)
│   └── notification_prefs_provider.dart      (NEW)
├── profile_screen.dart                       (ConsumerWidget)
├── notification_preferences_screen.dart      (ConsumerWidget; keep optimistic toggle)
└── shared_calendars_screen.dart              (consume sharedRecipeBooksProvider if applicable)

app/lib/features/pantry/
├── services/
│   └── pantry_service.dart                   (REFACTOR — delete _current, delete _pantryController, become stateless; emit on mutations)
├── providers/
│   └── pantry_provider.dart                  (NEW — pantryIngredientsProvider, defaultPantryProvider)
└── screens/
    ├── pantry_list_screen.dart               (ConsumerWidget; keep undo Snackbar)
    └── pantry_editor_screen.dart             (delegate writes to service)

app/lib/features/recipes/
├── services/
│   └── cooking_log_service.dart              (NEW — single create() method; emit CookingLogCreated)
├── providers/
│   └── cooking_history_provider.dart         (NEW — recipeCookingHistoryProvider(recipeId))
├── widgets/
│   ├── post_cook_feedback_sheet.dart         (delegate to CookingLogService)
│   └── recipe_cooking_history_section.dart   (NEW — extracted from recipe_detail_screen)
└── recipe_detail_screen.dart                 (use RecipeCookingHistorySection)

app/lib/features/shopping_cart/
└── services/
    └── shopping_cart_service.dart            (surgical edits: emit in _handleMessage cases + in local mutation methods)

app/lib/core/state/
├── mutation_failure_copy.dart                (expand to full catalog — every MutationType enum value)
└── mutation_snackbar.dart                    (extend with optional rollback: VoidCallback?)

tools/
├── no-silent-catch-check.sh                  (NEW — grep guard)
└── silent-catch-allowlist.txt                (NEW — allowlist file for legitimate recovery paths)

test/
├── app/lib/features/recipe_books/
│   ├── recipe_books_reactivity_test.dart
│   ├── rename_recipe_book_propagates_test.dart
│   └── shared_books_reactivity_test.dart
├── app/lib/features/profile/
│   ├── notification_prefs_optimistic_toggle_test.dart      (success + failure + rollback)
│   └── profile_updated_reactivity_test.dart
├── app/lib/features/pantry/
│   ├── pantry_service_stateless_test.dart                  (regression — no internal cache)
│   └── pantry_reactivity_test.dart
├── app/lib/features/recipes/
│   └── cooking_history_reactivity_test.dart                (CookingLogCreated handoff)
├── app/lib/features/shopping_cart/
│   └── ws_adapter_emits_mutation_test.dart
└── app/lib/core/state/
    ├── mutation_failure_copy_test.dart                     (enumerates MutationType enum)
    └── mutation_snackbar_tap_retry_test.dart
```

## Story list with acceptance criteria

### rp-1 — RecipeBookService + providers + screens

**AC**:
1. `app/lib/features/recipe_books/services/recipe_book_service.dart` exists. Methods: `listRecipeBooks`, `listArchivedRecipeBooks`, `getRecipeBook(id)`, `createRecipeBook(...)`, `updateRecipeBook(id, ...)` (rename + other field edits), `archiveRecipeBook(id)`, `restoreRecipeBook(id)`, `deleteRecipeBook(id)`, `addMember(bookId, userId, role)`, `updateMemberRole(bookId, userId, role)`, `removeMember(bookId, userId)`, `bulkMoveRecipes(recipeIds, targetBookId)`, `bulkArchiveRecipes(recipeIds)`, `bulkUpdateTags(...)`. Each mutation method emits exactly one MutationBus event on server 2xx with the payload shape documented above. `leaveBook` is a TODO stub deferred to `epic-recipe-book-sharing` if/when that surfaces; no emit.
2. Service is stateless — holds no list/detail cache. Verified by `rp-1` unit test that constructs two service instances and drives mutations through both without any shared state.
3. `app/lib/features/recipe_books/providers/recipe_books_provider.dart` exists with: `recipeBooksProvider`, `archivedRecipeBooksProvider`, `activeRecipeBookProvider(bookId)`, `sharedRecipeBooksProvider`, `recipeBookMembersProvider(bookId)`. Each body has a `ref.listen(mutationBusProvider, ...)` filtering to the relevant event union; list providers use the `MutationEventCoalescer` (inherited from meals/calendar epic); `activeRecipeBookProvider(bookId)` patches in place on `RecipeBookUpdated` where `event.book.id == bookId` (**no refetch** on hit).
4. `recipe_book_detail_screen.dart`, `recipe_books_screen.dart`, `archived_recipe_books_screen.dart`, `recipe_book_members_screen.dart` are `ConsumerWidget`/`ConsumerStatefulWidget`. All raw `_apiClient.*` mutation calls removed; replaced with `RecipeBookService` calls. All raw `ScaffoldMessenger.showSnackBar(...)` in mutation-failure paths replaced with `showMutationFailureSnackbar(context, MutationType.*, retry: ...)`.
5. `RecipeBookSyncService._handleMessage`: inside the switch, cases `recipe_added` / `recipe_updated` / `recipe_removed` each emit an `emitMutation(Recipe*(...))` **after** firing the existing StreamController. External API (StreamControllers on `onRecipeAdded`, etc.) unchanged — existing consumers keep working.
6. Widget test `rename_recipe_book_propagates_test.dart`:
   - (a) Pump a harness with `RecipeBookDetailScreen(bookId='X')` AND `RecipeBooksScreen` mounted in a split layout.
   - (b) Drive `RecipeBookService.updateRecipeBook('X', name: 'Weeknight Wins')` through a mocked ApiClient returning the updated book.
   - (c) Assert both screens render the new name within one frame of the mocked server 200.
   - (d) No pull-to-refresh gesture invoked; no imperative `setState` calls; no `_loadRecipeBook()` call on the detail screen post-mutation.
7. Widget test `recipe_books_reactivity_test.dart`: drive create, archive, delete, member-role-change — each asserts one event emitted + provider invalidated exactly once.
8. Integration test `shared_books_reactivity_test.dart`: drive a `RecipeBookMemberAdded` event (simulating Leo being added to a partner's book); assert `sharedRecipeBooksProvider` invalidates.
9. Failure-path test: mock `PUT /v1/recipe-books/{id}` to throw `DioException`; assert `showMutationFailureSnackbar` is called with `MutationType.updateRecipeBook`; assert tapping retry re-invokes the service method.
10. Copy stubs added to `mutation_failure_copy.dart`: `createRecipeBook`, `updateRecipeBook`, `archiveRecipeBook`, `restoreRecipeBook`, `deleteRecipeBook`, `addBookMember`, `updateBookMemberRole`, `removeBookMember`, `bulkMoveRecipes`, `bulkArchiveRecipes`, `bulkUpdateTags`.

### rp-2 — ProfileService + NotificationPrefsService + optimistic toggle

**AC**:
1. `app/lib/features/profile/services/profile_service.dart` exists. Methods: `getMe`, `updateProfile(name?, bio?)`, `setUsername(username)`, `submitFeedback(text, category)`, `exportRecipes`. Each mutation method emits `ProfileUpdated(User.Response)` or `UsernameUpdated(newUsername)` on 2xx.
2. `app/lib/features/profile/services/notification_prefs_service.dart` exists. Methods: `getNotificationPreferences`, `updateNotificationPreferences(push_enabled?, email_digest?, quiet_hours_start?, quiet_hours_end?, timezone?, partner_activity?)` — single scalar-field update, `updateCategoryPref(category, enabled)` — single category toggle. Both mutation methods emit `NotificationPrefsUpdated(fullPrefsBlob)` on 2xx with the full server response body.
3. `profile_screen.dart` is a `ConsumerStatefulWidget` consuming `ref.watch(profileProvider)`. All raw `_apiClient.*` writes replaced with service calls. Failure Snackbars via `showMutationFailureSnackbar`.
4. `notification_preferences_screen.dart` is a `ConsumerStatefulWidget` consuming `ref.watch(notificationPrefsProvider)`. **Preserves the optimistic toggle**: `_toggleCategory(key, value)` does `setState(() => _optimisticCategoryState[key] = value)` synchronously before awaiting the service call; on failure, reverts via `setState` and calls `showMutationFailureSnackbar(..., rollback: null /* already reverted */)`.
5. Widget test `notification_prefs_optimistic_toggle_test.dart`:
   - (a) **Success path**: pump screen; tap Meals toggle off. Before awaiting the service future, assert the toggle is visually off (within one frame of tap). Await mocked success response. Assert toggle remains off (now server-confirmed). Assert exactly one `NotificationPrefsUpdated` event emitted. Assert `notificationPrefsProvider` patches in place (no extra fetch).
   - (b) **Failure path**: pump screen; tap Timer toggle off. Assert toggle flips off within one frame. Await mocked 500 response. Assert toggle reverts to on within one frame of the failure. Assert `showMutationFailureSnackbar` called with `MutationType.updateNotificationPrefs`. Assert Snackbar copy `"Couldn't update notifications. Tap to retry."` (320px-safe).
   - (c) **Retry path**: in (b), tap Retry on the Snackbar. Mock the next call to succeed. Assert toggle flips back off + Snackbar dismisses.
6. Widget test `profile_updated_reactivity_test.dart`: drive `ProfileService.updateProfile(name: 'Leo 2.0')`; assert `profileProvider` patches in place with the server payload; assert any other surfaces watching the provider re-render.
7. Copy stubs added: `updateProfile`, `setUsername`, `submitFeedback`, `updateNotificationPrefs`, `toggleNotificationCategory` (latter two map to the same Snackbar copy — verified in copy map).

### rp-3 — Pantry refactor (stateless) + CookingLog handoff from meals epic

**AC**:
1. `PantryService` refactored to be stateless: `_current`, `_pantryController`, `pantryStream`, `current`, `dispose()`, `loadDefaultPantry()` are **removed**. Remaining methods: `addPantryIngredient`, `updatePantryIngredient`, `deletePantryIngredient` — each emits `PantryItem*` on 2xx. `getDefaultPantry()` stays as a read method (no emit; used by `defaultPantryProvider`).
2. `app/lib/features/pantry/providers/pantry_provider.dart` exists with: `defaultPantryProvider` (fetches pantry meta), `pantryIngredientsProvider(pantryId)` (`FutureProvider.family.autoDispose`, fetches ingredient list — may share the fetch with `defaultPantryProvider` if the endpoint returns both; verified pattern during implementation). `pantryIngredientsProvider(pantryId)` subscribes to `PantryItem*` events with `event.pantryId == pantryId` filter; uses `MutationEventCoalescer`.
3. `pantry_list_screen.dart` is a `ConsumerStatefulWidget` using `ref.watch(pantryIngredientsProvider(pantryId))`. `StreamSubscription<Pantry?>` removed; `_pantry`, `_isLoading`, `_error` local state removed (Riverpod owns it). **Swipe-to-dismiss undo Snackbar preserved verbatim** (it's a success-flow UX, not a failure path).
4. Regression test `pantry_service_stateless_test.dart`: construct two `PantryService` instances; invoke `addPantryIngredient` on one; assert the other's behavior is unaffected (no shared state). Assert `PantryService` has no `_current`-like field via mirror/reflection OR via a checked-in grep assertion (`grep -E '(_current|_pantryController|pantryStream)' pantry_service.dart` must return empty).
5. Widget test `pantry_reactivity_test.dart`:
   - (a) Pump `PantryListScreen` with `pantryIngredientsProvider('P1')` mocked to return `[flour, butter]`.
   - (b) Drive `PantryService.addPantryIngredient('P1', {name: 'Sugar', ...})` through a mocked ApiClient.
   - (c) Assert `PantryItemAdded` event emitted.
   - (d) Assert `pantryIngredientsProvider('P1')` invalidated exactly once.
   - (e) Assert sugar row appears within one frame; no skeleton flash (valueOrNull guard).
6. **CookingLog sub-story (handoff from meals/calendar epic)**:
   - (a) `app/lib/features/recipes/services/cooking_log_service.dart` exists with one method: `create(recipeId, feedbackBlob) -> CookingLog`. Emits `CookingLogCreated(log, recipeId)` on 2xx.
   - (b) `app/lib/features/recipes/providers/cooking_history_provider.dart` exists with `recipeCookingHistoryProvider(recipeId)`. Subscribes to `CookingLogCreated` filtered by `event.recipeId`; invalidates.
   - (c) `post_cook_feedback_sheet.dart` delegates the log write to `CookingLogService` (remove the raw `_apiClient.*` call). Failure → `showMutationFailureSnackbar(context, MutationType.createCookingLog, retry: ...)`.
   - (d) Recipe-detail cooking-history block extracted into `RecipeCookingHistorySection` widget; converts to `ConsumerWidget + ref.watch(recipeCookingHistoryProvider(recipeId))`. If the block doesn't exist today (verify during implementation), this sub-AC's scope is limited to (a)+(b)+(c) and a TODO is left in recipe_detail_screen for a future UI-level follow-on.
   - (e) Widget test `cooking_history_reactivity_test.dart`: pump recipe detail; submit post-cook feedback; assert cooking-history section refetches and shows the new entry within one frame of server 200.
7. Copy stubs added: `addPantryItem`, `updatePantryItem`, `deletePantryItem`, `createCookingLog`.

### rp-4 — ShoppingCartService WS adapter consolidation

**AC**:
1. Inside `_handleMessage(data)` in `shopping_cart_service.dart`, cases `item_added`, `item_updated`, `item_checked`, `item_removed` each add a single `emitMutation(...)` line **after** the existing `_*Controller.add(...)` line. Handler method is **not** renamed or restructured.
2. Inside each local mutation method (`addItem`, `updateItem`, `toggleItemChecked`, `deleteItem`), add `emitMutation(...)` on the success branch (before `return`). Local mutation events carry the full parsed `ShoppingListItem.Response`; delete carries `(itemId, listId)`.
3. Cases `presence_update`, `sync_response`, `pong`, `connected` do **NOT** emit — they are not mutations.
4. External `ShoppingCartService` API (`onItemAdded`, `onItemUpdated`, `onItemRemoved`, `onPresenceUpdate`, `onSync`, `onWebSocketStateChange`) is unchanged; all existing `ShoppingListScreen`-side consumer code continues to compile and run without modification.
5. Widget test `ws_adapter_emits_mutation_test.dart`:
   - (a) Construct `ShoppingCartService`; register a subscriber on `mutationBusProvider`.
   - (b) Inject a simulated WS `{"type": "item_added", "data": {...}}` frame via a test seam (`handleMessageForTest(jsonString)` — add the seam if not present; pattern already exists on `RecipeBookSyncService`).
   - (c) Assert `MutationEvent.ShoppingListItemAdded` is emitted exactly once with the expected payload.
   - (d) Assert the pre-existing `_itemAddedController` still fired (subscriber on `onItemAdded` received the event).
   - (e) Repeat for `item_updated`, `item_checked` (both lower to `ShoppingListItemUpdated`), `item_removed`.
   - (f) Inject a `presence_update` frame → assert NO MutationBus event emitted (regression guard against over-emitting).
6. Dual-path idempotence test: simulate a local `addItem(...)` call that succeeds, then immediately inject a WS `item_added` frame for the same item. Assert two `ShoppingListItemAdded` events emitted; assert subscribers are idempotent (refetching twice is wasteful but correct — matches Foundation's WS/MutationBus duplication risk mitigation).
7. **Scope boundary (resolved question #2)**: the `ShoppingListScreen` rewrite onto `shoppingListProvider` is **NOT** in scope for this epic. Documented as a follow-on in `Risks / deferred` below.

### rp-5 — Central mutation-failure copy + grep guard + end-to-end sweep

**AC**:
1. `app/lib/core/state/mutation_failure_copy.dart` has an entry for every `MutationType` enum value across all four epics. A unit test `mutation_failure_copy_test.dart` uses `MutationType.values` to enumerate every enum case and asserts `mutationFailureCopy.containsKey(type)` for each — fails the build if a new enum value lacks a map entry. (Resolves the "copy-map drift" risk with an explicit test rather than a const-init assertion, which wouldn't fire at compile time in Dart.)
2. `showMutationFailureSnackbar(BuildContext, MutationType, {required VoidCallback retry, VoidCallback? rollback, String? suffix})` handles Snackbar display, tap-to-retry binding, optional rollback invocation (fired once, immediately, before the Snackbar shows), and dismissal on the next successful MutationBus emit of the same `MutationType`.
3. **Grep guard — concrete rule (resolves question #3)**:
   - Script `tools/no-silent-catch-check.sh` runs: `find app/lib/features -path '*/services/*.dart'` to enumerate service files, then for each file extracts every `catch` block and checks: **the block must contain either `rethrow` OR `throw` OR `showMutationFailureSnackbar(` OR `emitMutation(` OR `ErrorReporter.report(` OR be listed in `tools/silent-catch-allowlist.txt`**. Failure → non-zero exit + list of offending `file:lineno` locations.
   - `tools/silent-catch-allowlist.txt` format: one `file:lineno:rationale` per line. Initial entries (audited during `rp-5`):
     - `app/lib/features/shopping_cart/services/shopping_cart_service.dart:<line of "// Ignore malformed messages">:WS malformed-message recovery` (equivalent pattern exists in `RecipeBookSyncService`).
     - Any `on SocketException catch` path that returns cached data — enumerate during implementation.
   - Allowlist entries require a code-review comment on the PR that adds them (enforced by checklist in `.claude/commands/review.md`, not by the script).
   - Script runtime target: <1 second across all service files.
   - `custom_lint` alternative is **not** adopted for v1 — rationale: shell-script guard is faster to set up (<2h), easier to debug on CI failures, and the IDE-surfacing benefit of `custom_lint` isn't load-bearing for a solo-operator codebase. Documented in a comment at the top of `no-silent-catch-check.sh`. Revisit if the allowlist grows past ~20 entries.
4. End-to-end smoke test (can be a single integration-test file or a scripted widget-test sweep): exercises one representative mutation per feature (create recipe, rename book, toggle pref, add pantry item, dismiss import, create meal, submit cooking log) with one induced failure per mutation — asserts each Snackbar copy matches the expected `"Couldn't <verb> <noun>"` pattern. All seven assertions live in one test file for grep-ability (`mutation_failure_copy_e2e_test.dart`).
5. Grep sweep: zero `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to ...')))` (or equivalent) remains inside a `catch` block in any `app/lib/features/**/services/*.dart` file. Enforced by the grep guard in AC #3. Non-mutation snackbars (success toasts, the pantry undo-Snackbar) remain allowed — they are not in `catch` blocks.
6. Planning-artifact update: append a pointer to the MutationBus convention README (at `app/lib/core/state/README.md`, authored in Foundation) to `CLAUDE.md`'s "Key References" section — single-line entry: `- **app/lib/core/state/README.md** - MutationBus convention (emit/subscribe patterns, coalescer recipe, WS-lowering recipe)`.
7. Deterministic CI: all new reactivity tests use `pumpWithMutation` (Foundation rf-1 helper); no `pumpAndSettle` with wall-clock timeouts; no `Future.delayed` in test bodies. Per-test p95 runtime <2s.

## Dependencies

- **Cross-epic**: Depends on `epic-reactive-foundation-home-imports` (MutationBus + Snackbar helper + `mutation_failure_copy.dart` stub + `pumpWithMutation` test helper + all downstream event stubs). Parallelizable with `epic-reactive-migration-meals-calendar`.
- **Inherited handoff**: `CookingLogCreated` event + subscriber surface (from meals/calendar epic) lands as part of `rp-3`.
- **Internal ordering**: `rp-1` ↔ `rp-2` ↔ `rp-3` ↔ `rp-4` (all parallelizable — different surfaces, no shared files beyond `mutation_failure_copy.dart` which everyone appends to). `rp-5` depends on all four (copy-map enumerates all mutation types; grep guard fails if any service catch-block still swallows).
- **No backend dependency.** Verified endpoint-by-endpoint.

## Resolved questions

These were "Open questions for the user" in the draft. Party-mode resolved them in-file:

- ~~**Non-optimistic toggles for notification prefs**~~ → **Resolved: preserve today's optimistic + rollback behavior**. The draft proposed a regression — today's `_toggleCategory` is already optimistic with revert-on-failure, and a 300ms disabled-spinner state on every toggle tap is worse UX than the current pattern. Locked Decision #6 ("reconcile-only for v1") means "don't add NEW optimistic paths" — it does not mean "rip out existing optimism that works". See "Non-optimistic vs. optimistic toggle UX spec" above for the full spec and `rp-2` AC #5 for the test coverage.
- ~~**`ShoppingListScreen` rewrite**~~ → **Resolved: explicitly deferred to a follow-on epic**. `rp-4` keeps external `ShoppingCartService` API source-compatible; WS handlers lower to MutationBus alongside existing StreamController sinks. A future epic (post-dogfood polish) can land `shoppingListProvider` as a second consumer and collapse the StreamControllers. Scope-boundary preserved.
- ~~**Grep guard vs `custom_lint`**~~ → **Resolved: shell-script guard for v1, `custom_lint` deferred**. Rationale: shell-script is faster to set up (<2h vs. ~1 day for custom_lint), easier to debug on CI failures, and the IDE-surfacing benefit of `custom_lint` isn't load-bearing for a solo-operator codebase. See `rp-5` AC #3 for the concrete rule + allowlist strategy. Revisit if the allowlist grows past ~20 entries OR if the dev team grows past one full-time contributor.

## Escalation for the user

**None**. All three previously-open questions resolved in party-mode; no blockers before `rp-1` starts.

**Cross-epic addendum feedback** (flagged in party-mode, no action required before epic kickoff):
- **Back to Foundation epic**: no addendum needed. All Foundation decisions hold.
- **Back to meals/calendar epic**: no addendum needed. The `CookingLogCreated` handoff is absorbed cleanly here.
- **Forward to a future epic**: `ShoppingListScreen` rewrite + `shoppingListProvider` lands as a polish epic (not this one). Tracked in Risks below.

## Risks

- **Copy-map enum drift**: new mutation type added in a future epic without a copy-map entry breaks Snackbar display. Mitigation: `rp-5` AC #1 — unit test enumerates `MutationType.values` and asserts every value has an entry. Build fails immediately on new enum case without copy.
- **Silent-catch false positives**: grep guard flags legitimate `on X catch` blocks that are genuinely recovery paths. Mitigation: `tools/silent-catch-allowlist.txt` (format: `file:lineno:rationale`); allowlist additions require code-review sign-off via `.claude/commands/review.md` checklist.
- **WS-adapter double-emit**: local mutation + WS frame both fire for the same id. Mitigation: subscribers are idempotent (refetch-twice is wasteful but correct); explicitly tested in `rp-4` AC #6.
- **`ShoppingCartService` regression**: surgical edit touches a critical path. Mitigation: all existing shopping-cart tests must pass unchanged; `rp-4` adds `ws_adapter_emits_mutation_test.dart` on top; presence/sync regression test guards against over-emitting (`rp-4` AC #5f).
- **`PantryService` refactor is a breaking API change** for `PantryListScreen` and `PantryEditorScreen`. Only two call-sites today; both updated in the same PR. `dispose()`/`loadDefaultPantry()`/`current`/`pantryStream` references outside the service must be zero post-refactor — verified by grep during implementation.

### Risks identified via party-mode

- **(PM) The six-step scripted dogfood session is ground-truth.** CI passing is necessary but not sufficient. Captured in the "Single measurable proof" block; if any step fails after CI green, `bmad-bmm-correct-course` is the response.
- **(UX) Draft proposed a regression on the notification-prefs toggle.** Today's code is already optimistic with rollback — the draft's "non-optimistic with 300ms spinner" would have been a step backwards. Caught in party-mode; resolved to preserve existing behavior with explicit spec (see "Non-optimistic vs. optimistic toggle UX spec" section).
- **(Frontend) Draft assumed services existed that don't exist.** `RecipeBookService`, `ProfileService`, `NotificationPrefsService`, `CookingLogService` all need to be **created** as part of this epic. Today's mutation sites are raw `_apiClient.*` calls inside `_State` objects. Corrected in Service Inventory table; scope expanded by roughly one net-new file per service (4 files).
- **(Frontend) Draft under-estimated the PantryService refactor.** Existing service holds list state (`_current` + `StreamController`), violating Foundation Locked Decision #9. Not a trivial "add emit" — requires deleting the cache, deleting the stream, and migrating `PantryListScreen` off `StreamSubscription<Pantry?>`. Called out in `rp-3` AC #1–#3 and Risks.
- **(Frontend) Draft got `ShoppingCartService` handler names wrong.** Handlers are `_handleMessage` with a `switch(type)` (cases `item_added` / `item_updated` / `item_checked` / `item_removed` / `presence_update` / `sync_response` / `connected` / `pong`), not standalone `_handleItemAdded` / `_handlePresenceUpdate` methods. Corrected in `rp-4` AC #1; presence/sync explicitly excluded from emit paths (they are not mutations).
- **(Frontend + Architect) Pantry undo-Snackbar is a success-flow affordance, not a failure-rollback.** Must stay distinct from the central `showMutationFailureSnackbar`. The grep guard does not touch it (it's not in a `catch` block). Documented explicitly in Design Principles #4.
- **(Backend/Architect) `PUT /v1/users/me/notification-preferences` returns the full prefs blob** — verified by reading `push_tokens.py` `UpdateNotificationPreferences.Response`. Zero backend change needed; draft's "double-check" question resolves to "already correct".
- **(Backend/Architect) Recipe-book archive/delete return slim responses** — same pattern as meals epic. Events carry ids-only payloads; subscribers invalidate (no in-place patching for archive). Acceptable — archived books are a terminal transition.
- **(Infra) Grep guard is a CI step, not a new job.** Runtime <1s; no CI cost concern. Shell-script v1, custom_lint deferred (see resolved question #3).
- **(QA) Copy-map enumeration test** uses `MutationType.values` at test-time rather than a `const` init `assert` — Dart's `const` assertions don't run at compile time in a way that would fail CI for missing map entries, so a runtime enumeration test in `mutation_failure_copy_test.dart` is the right mechanism. Corrected in `rp-5` AC #1 vs. the draft's "const-time lint warning via assert".
- **(QA) Grep-guard allowlist file** uses `file:lineno:rationale` format + requires code-review sign-off on additions. Line-number matching is brittle across rebases; mitigation: allowlist entries are re-verified in each PR that touches the file (reviewer checklist); if line-number match fails, the script surfaces it as an offending catch-block and the reviewer updates the allowlist. Accept brittleness — alternative (file-scoped allowlist) over-broadens; line-precise is the right tradeoff for a small codebase.
- **(Architect) Net-new files this epic introduces**: 4 new services (`RecipeBookService`, `ProfileService`, `NotificationPrefsService`, `CookingLogService`), 5 new provider files, 1 new extracted widget (`RecipeCookingHistorySection`), 1 grep-guard script + allowlist. All additive; no deletions except `PantryService`'s internal cache. Net epic size: larger than draft implied but still within a reasonable multi-story scope.

### Deferred to future epics

- **`ShoppingListScreen` rewrite + `shoppingListProvider`** — the full collapse of `ShoppingCartService`'s StreamControllers onto a Riverpod provider. This epic stops at the WS-lowering consolidation; the screen rewrite is a follow-on polish epic.
- **`custom_lint` rule for silent-catch** — deferred per resolved question #3. Revisit when allowlist grows past ~20 entries or a second developer joins.
- **Cross-device reactivity for recipe books / profile / pantry** — no WS broadcasts for these domains (Foundation Locked Decision #8). Partner-sees-my-change is a separate epic.
- **`invalidateRecipeBook` / `invalidateProfile` shims** — since `RecipeBookService`/`ProfileService` don't exist today, there are no existing `invalidate*` call-sites to shim. Fresh code; direct adoption of the MutationBus pattern from day one. No shim needed.
