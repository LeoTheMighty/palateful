<!-- refined via party-mode 2026-04-18 -->
# Epic: Calendar Per-Meal Shopping Add (replace "Add week to shopping list" bulk)

## Overview

The calendar AppBar today has a single **"Add week to shopping list"** icon that calls `POST /v1/shopping-lists/{list_id}/populate-from-calendar` with the visible week's date range. In production dogfood this action produced 12 garbage line-items with raw-string names like *"1 recipe pasta dough, rolled out into wide ribbons, about 1/4-inch thick"* because some `ingredients` rows have their raw recipe line stored in `canonical_name`. The underlying canonical-name data bug is **out of scope** (tracked separately); this epic pivots the UX so the bulk amplifier is gone and users opt in per-meal.

**Goal.** After this epic, Leo opens the calendar, sees a week of planned meals, and each card with a linked recipe shows an `Icons.add_shopping_cart_outlined` tap target. He taps one → it lands on his default list with a snackbar "Added 7 ingredients to Groceries" → the card's icon flips to a muted `Icons.check` and stays that way until the grid reloads. The AppBar shopping-list button is gone. The backend endpoint is gone. Session-persistent "added" indicator prevents accidental re-adds within the same browse; reschedule (or week switch, or active-calendar switch, or pull-to-refresh) wipes the state so a replanned meal is a fresh decision.

## Design Principles (refined via party-mode 2026-04-18)

1. **Per-card over per-week.** Intentionality beats batch. 7 targeted adds → 7 intended meals' worth of items; the bulk path produced 12 unreadable items with no surgical undo.
2. **Reuse, don't duplicate.** The per-card tap runs the existing `_addIngredientsFromEvent` verbatim — one shopping-list resolution, one chooser sheet, one snackbar with "Change" action.
3. **Delete, don't deprecate.** Backend endpoint, impl module (`populate_from_calendar.py`), dedicated test file, and `TestPopulateFromCalendarExtended` class in `test_coverage_gaps.py` go in the same commit. Shared helpers (`get_user_calendar_ids`, `utils/deadline.py::calculate_item_due_date`) stay — both have other live callers (`list_meal_events.py`, `populate_from_recipe.py`, `get_deadlines.py`).
4. **Hidden, not disabled-grey,** when no recipe is linked. Matches the existing chevron visibility rule in `_buildEventTile` line 910.
5. **Client-only "added" state.** Session-scoped `Set<String> _addedEventIds` keyed on `event.id`. No column, no endpoint, no cross-device sync. Write happens **only** after a successful `populateFromRecipe` response where `items_added > 0`.
6. **Don't swallow existing tap targets.** The row `onTap` (meal detail sheet) and `onLongPress` (action sheet) stay. The icon uses an `IconButton` child; its tap does not bubble.
7. **Icon sizing matches the existing row rhythm.** Use a `SizedBox(width: 32, height: 32)` wrapper around the `IconButton` with `padding: EdgeInsets.zero` and `iconSize: 18` — mirrors the "Add meal" day-header pattern at `calendar_screen.dart:764–773`. A default 48-px IconButton hit region would blow the row layout out.
8. **Semantics before polish.** The icon carries a `Semantics(button: true, label: ...)` that flips between "Add to shopping list" and "Added to shopping list, double-tap to add again" in the checked state — not "Already added" (the double-tap override must be discoverable to AT users).
9. **Success gate on `items_added`.** If the API returns `items_added == 0` (recipe has no ingredients, or all skipped), do **not** set the check mark — show the existing snackbar but leave the icon as add-cart. A check mark on a no-op is a lie.
10. **Icon update is not racy against reloads.** After `populateFromRecipe` returns, the handler re-checks `mounted` **and** verifies the load-generation captured pre-await equals `_loadGeneration` now; only then does it write to `_addedEventIds`. A mid-flight `_loadEvents()` wins — the stale add result is silently dropped visually (the user still got their snackbar from the original tap).
11. **Coverage is load-bearing.** `services/api` is pinned at 100%. Run `npx nx run api:test --coverage` locally before merging cpms-2; any newly-orphaned line in a shared helper is a stop-ship.
12. **Deploy both, not one-then-other.** In dogfood, a 404 window is worse than the dual-deploy coordination cost — see Risks.

## Locked decisions (carry forward to future calendar / shopping epics)

- **Icon-always-visible when recipe linked, hidden otherwise.** Matches the chevron rule. Applies to any future per-card action (e.g., "add to meal plan," "start cooking timer").
- **Session-scoped, load-generation-guarded client state** is the canonical pattern for "already done on this row" indicators that do not need cross-device sync. Reuse the `_addedEventIds` + `_loadGeneration` shape before reaching for a server column.
- **No shim on endpoint deletion** while in dogfood. Future Play Store / App Store phases must reassess; this decision is conditional on single-operator regime.
- **Meals-calendar replan (mcal-4's replacement)**: the expected path is `POST /v1/meal-events/{event_id}/add-to-shopping-list` mirroring the planned per-Meal `POST /v1/meals/{meal_id}/add-to-shopping-list` (mcal-5). Future planners should NOT resurrect `populate-from-calendar` — per-event is the new shape.
- **`items_added == 0` never flips a success indicator.** Apply to any future "did it work" UX.
- **100% coverage gate is a planning input, not a post-hoc check.** Any story that deletes a production Python module MUST enumerate its test sites as scope bullets, not as "verify later."

## End-user flow

### Primary path — add one meal's ingredients

1. Leo opens the Calendar tab. He sees the current week grid. No icon in the AppBar for shopping (removed).
2. On Tuesday dinner he's got "Sheet-pan Salmon" planned. The card renders: thumbnail, title + meal-type chip + duration, an `Icons.add_shopping_cart_outlined` icon button, the existing chevron.
3. Leo taps the shopping-cart icon (not the card body — that still opens the meal detail sheet).
4. The `_addIngredientsFromEvent(event)` handler fires:
   - Loads the user's shopping lists. If none → snackbar "No shopping lists — tap + to create one."
   - If there's a default list, uses it. If exactly 1 list and no default, uses that. Otherwise shows the existing "Choose a shopping list" bottom sheet and remembers the pick as default.
   - Calls `POST /v1/shopping-lists/{list_id}/populate-from-recipe` with the event's `recipe_id`.
   - On success with `items_added > 0`: snackbar reads "Added 7 ingredients to Groceries" (uses existing "Change" action when user has >1 list). The card's icon flips to `Icons.check` muted.
   - On success with `items_added == 0`: snackbar still fires (per existing handler behavior), but the icon stays as add-cart. A zero-add is not a "done" signal.
5. The card's icon now renders `Icons.check` in a muted tone. Icon's Semantics label reads "Added to shopping list, double-tap to add again." Screen-reader users hear the new state on next focus.
6. Leo taps Thursday's "Lentil Soup" — same flow. Both Tuesday and Thursday now show the muted check.

### Card with no linked recipe

7. A calendar event with `event.recipe == null` (free-text meal) does not render the shopping-cart IconButton at all — the row collapses the slot just like the chevron-absent case today (no placeholder `SizedBox`).

### Rescheduling clears the indicator

8. Leo long-presses Tuesday's Salmon → Reschedule → moves it to Wednesday. The grid reloads via `_loadEvents()`. The new Wednesday card renders with the shopping-cart icon (not checked). The Tuesday slot is empty again. The in-memory `_addedEventIds` Set is cleared at the top of `_loadEvents()` alongside the load-generation bump.

### Double-tap override

9. If Leo taps an already-checked card again, the add flow runs a second time (no guard). The snackbar shows the same "Added 7 ingredients to Groceries." This is intentional: the check mark is visual reassurance, not a lockout. The Semantics label surfaces this ("double-tap to add again") so AT users aren't stuck.

### Long-press path still works

10. Long-press on a card still opens the existing action sheet. Its "Add to shopping list" entry is unchanged and also runs `_addIngredientsFromEvent`. Adding via long-press also flips the card's session-state check mark — both entry points share the success update (the `_addedEventIds` write lives inside `_addIngredientsFromEvent`, not at the tap site).

### Deploy / removal of bulk path

11. After deploy, any user still on an old client that calls `POST /v1/shopping-lists/{list_id}/populate-from-calendar` gets a 404. Given this is dogfood (single operator) with both stories deployed together, the 404 window is effectively zero — no shim, no deprecation window. The deleted router's WebSocket broadcast loop is functionally duplicated by the surviving `populate_from_recipe` handler's broadcast (both emit `item_added` events per item), so real-time sync to other shopping-list members is preserved.

## Frontend changes

- `app/lib/features/calendar/calendar_screen.dart`
  - DELETE `_buildAppBar()`'s shopping-cart `IconButton` (lines 620–625).
  - DELETE `_generateWeeklyShoppingList()` (lines 381 through ~489), and the `_isGeneratingList` field (line 51).
  - DELETE the `ShoppingList` import if no longer used elsewhere (check — it is also used by the long-press action sheet path, so likely stays).
  - ADD a new `int _loadGeneration = 0;` field to `_CalendarScreenState` (next to `_isLoading`).
  - ADD `final Set<String> _addedEventIds = <String>{};` to `_CalendarScreenState`.
  - In `_loadEvents()`, inside the top-of-function setState block, add `_loadGeneration++;` and `_addedEventIds.clear();`.
  - Modify `_addIngredientsFromEvent` to capture `final generation = _loadGeneration;` before any `await`, and on the `populateFromRecipe` success branch check `if (mounted && generation == _loadGeneration && result.itemsAdded > 0) setState(() => _addedEventIds.add(event.id));` *before* the snackbar fires.
  - In `_buildEventTile` (line 805), insert — between the title/chip column `Expanded` and the existing chevron — a conditional icon-button block:
    ```dart
    if (event.recipe != null)
      SizedBox(
        width: 32,
        height: 32,
        child: IconButton(
          padding: EdgeInsets.zero,
          iconSize: 18,
          tooltip: _addedEventIds.contains(event.id)
              ? 'Added to shopping list'
              : 'Add to shopping list',
          icon: Icon(
            _addedEventIds.contains(event.id)
                ? Icons.check
                : Icons.add_shopping_cart_outlined,
            color: _addedEventIds.contains(event.id)
                ? colorScheme.onSurface.withValues(alpha: 0.45)
                : colorScheme.onSurface.withValues(alpha: 0.75),
          ),
          onPressed: () => _addIngredientsFromEvent(event),
        ),
      ),
    ```
  - Wrap that `IconButton` (or its `icon: Icon(...)`) with `Semantics(button: true, label: _addedEventIds.contains(event.id) ? 'Added to shopping list, double-tap to add again' : 'Add to shopping list', child: ...)`. Leave the row-level Semantics alone so VoiceOver focus order remains: row (title+meal) → icon → chevron.
  - The existing chevron at line 910 stays untouched — both the chevron and the new icon are already gated on `event.recipe != null`.
- `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
  - DELETE `populateFromCalendarRange` (lines 161–177) and its doc comment.
- `app/lib/core/services/api_client.dart`
  - DELETE `populateShoppingListFromCalendar` (lines 467–471).

## Backend changes

- `services/api/src/api/v1/shopping_list/populate_from_calendar.py` — **delete entire file**.
- `services/api/src/api/v1/shopping_list/__init__.py` — delete the `from .populate_from_calendar import PopulateFromCalendar` import (line 17) and the `"PopulateFromCalendar"` string in `__all__` (line 48).
- `services/api/src/routers/v1/shopping_list_router.py` — delete the `@shopping_list_router.post("/shopping-lists/{list_id}/populate-from-calendar")` handler block (lines 300–317) and its local `from api.v1.shopping_list import PopulateFromCalendar` reference if the `__init__` re-export is the only source.
- `services/api/tests/test_populate_from_calendar.py` — **delete entire file**.
- `services/api/tests/test_coverage_gaps.py` — delete the section 3 comment header (around lines 226–229) and the `TestPopulateFromCalendarExtended` class (lines 231–525). Keep all other classes intact.
- Shared helpers NOT touched: `get_user_calendar_ids` (still used by `list_meal_events.py`, `list_recurrence_rules.py`), `utils/deadline.py::calculate_item_due_date` (still used by `populate_from_recipe.py`, `get_deadlines.py`). Verified by grep — both have live callers outside `populate_from_calendar.py`.

## Infrastructure changes

**None.** No new AWS resources, no new migrations, no new env vars, no Terraform changes, no Docker/CI config changes. Deploy is the standard `npx nx run api:docker-build` path for backend and the standard Flutter release path for the app. The endpoint's WebSocket broadcast responsibility is already mirrored in the `populate_from_recipe` handler — removing the bulk path does not degrade real-time sync to connected shopping-list members.

## File structure — touched paths

```
app/lib/features/calendar/
└── calendar_screen.dart                           # MODIFIED

app/lib/features/shopping_cart/services/
└── shopping_cart_service.dart                     # MODIFIED — delete populateFromCalendarRange

app/lib/core/services/
└── api_client.dart                                # MODIFIED — delete populateShoppingListFromCalendar

app/test/features/calendar/
├── generate_weekly_list_test.dart                 # DELETED
└── per_meal_shopping_add_test.dart                # NEW

services/api/src/routers/v1/
└── shopping_list_router.py                        # MODIFIED — delete populate-from-calendar route

services/api/src/api/v1/shopping_list/
├── __init__.py                                    # MODIFIED — remove PopulateFromCalendar export
└── populate_from_calendar.py                      # DELETED

services/api/tests/
├── test_populate_from_calendar.py                 # DELETED
└── test_coverage_gaps.py                          # MODIFIED — delete TestPopulateFromCalendarExtended

docs/
└── SHARED_SHOPPING_CART.md                        # MODIFIED — remove endpoint doc (~line 680)

_bmad-output/planning-artifacts/
├── prd.md                                         # MODIFIED (addendum appended 2026-04-18)
├── architecture.md                                # PENDING — add dated strikethrough for populate-from-calendar reference at line 1091
├── epics.md                                       # MODIFIED (addendum appended 2026-04-18)
├── epic-meals-calendar.md                         # MODIFIED — dated note at top (mcal-4 deleted, step 7 needs replan)
└── epic-calendar-per-meal-shopping-add.md         # THIS FILE

_bmad-output/implementation-artifacts/
└── sprint-status.yaml                             # MODIFIED — mcal-4 marked deleted; epic-calendar-per-meal-shopping-add block appended
```

## Stories

### cpms-1 — Flutter: remove weekly button + add per-card shopping-cart icon (session-persistent added state)

**Why one story.** The deletion and the addition share state: removing the AppBar handler without adding the per-card path leaves the user with no icon-based shopping-list path at all on the calendar, breaking the dogfood workflow until cpms-1 is merged. Ship them together.

**Scope**
- Delete the AppBar `IconButton` (lines 620–625 of `calendar_screen.dart`).
- Delete `_generateWeeklyShoppingList` and the `_isGeneratingList` field.
- Delete `ShoppingCartService.populateFromCalendarRange`.
- Delete `ApiClient.populateShoppingListFromCalendar`.
- Add `int _loadGeneration = 0;` and `final Set<String> _addedEventIds = <String>{};` to `_CalendarScreenState`.
- Inside `_loadEvents()`'s initial setState block, increment `_loadGeneration` and clear `_addedEventIds`. The generation counter is the authoritative "was this response from the current load" check.
- Modify `_addIngredientsFromEvent`: capture `final generation = _loadGeneration;` before any await; on the `populateFromRecipe` success branch, setState to add `event.id` only if `mounted && generation == _loadGeneration && result.itemsAdded > 0`.
- In `_buildEventTile`, insert the `SizedBox(width:32,height:32)` + `IconButton(padding: EdgeInsets.zero, iconSize: 18, ...)` block (see Frontend changes above) immediately before the existing chevron. Gate on `event.recipe != null` — hidden, not disabled, when null.
- Wrap the IconButton in a `Semantics(button: true, label: ...)` node; label flips between "Add to shopping list" and "Added to shopping list, double-tap to add again." Do not touch row-level Semantics.

**Acceptance criteria**
1. Calendar AppBar renders no shopping-cart action. Nothing else in the AppBar shifts.
2. Every card with `event.recipe != null` in the week grid renders a tappable `Icons.add_shopping_cart_outlined` icon button with tooltip "Add to shopping list."
3. Cards with `event.recipe == null` render no `IconButton` and no placeholder `SizedBox` — row width redistributes to the title column exactly as it does today for the chevron-absent case.
4. Tapping the icon invokes `_addIngredientsFromEvent(event)`. Tapping the card body still opens the meal detail sheet. Long-press still opens the existing action sheet. Icon's tap does not propagate.
5. On success with `items_added > 0`, the icon visibly flips to `Icons.check` (muted tone) for the remainder of the current load. Tooltip flips to "Added to shopping list." Semantics label flips to "Added to shopping list, double-tap to add again."
6. `_loadEvents()` clears `_addedEventIds` and increments `_loadGeneration`; reschedule, week navigation, tab re-entry, active-calendar switch, and pull-to-refresh all restore the un-checked state on the new grid.
7. Adding via the long-press action sheet's "Add to shopping list" entry also flips the card's indicator (shared state write inside `_addIngredientsFromEvent`).
8. Tapping an already-checked card re-runs the add; no guard. Snackbar fires again; icon stays/returns to checked.
9. `ShoppingCartService.populateFromCalendarRange` and `ApiClient.populateShoppingListFromCalendar` are removed — no references remain (`rg 'populateFromCalendar|populateShoppingListFromCalendar' app/` returns empty). Dart analyzer passes.
10. The existing `_addIngredientsFromEvent` behavior (default-list resolution, chooser sheet, "Change" snackbar action, error snackbars) is untouched. All existing call sites (long-press sheet) work identically.
11. If `populateFromRecipe` returns `items_added == 0`, the icon does NOT flip to check; the existing snackbar still fires with the zero-count / "skipped" wording from the existing handler.
12. If `_loadEvents` completes (user navigates week or pulls-to-refresh) while an add request is in-flight, the success handler does NOT flip the icon — the state is owned by the current load generation.
13. Icon tap target is reachable via TalkBack/VoiceOver swipe navigation; label reads "Add to shopping list" when un-added and "Added to shopping list, double-tap to add again" when checked.
14. Icon tap size is 32×32 logical pixels (`SizedBox` wrapper); row height is unchanged vs. the baseline recipe-event fixture.

**Tests (widget, `app/test/features/calendar/per_meal_shopping_add_test.dart`)**
- Per-card icon **renders** when the event has a recipe; count matches the number of recipe-backed events in the fixture week.
- Per-card icon **is hidden** (zero `IconButton` nodes emitted for that row) when `event.recipe == null`.
- Tapping the icon calls `ShoppingCartService.populateFromRecipe` with the event's recipe id (not `populateFromCalendarRange`).
- Tap success with `items_added > 0` flips icon to `Icons.check`; tooltip and Semantics label update.
- Tap success with `items_added == 0` does NOT flip the icon; snackbar still fires.
- Icon tap does NOT bubble: tapping the icon does NOT open the meal detail sheet (verify no sheet is pushed).
- Icon tap target is 32×32 logical pixels (`tester.getSize(find.byType(IconButton).first)` == Size(32,32)); row height unchanged vs. the baseline recipe-event fixture.
- Semantics label on the icon reads "Add to shopping list" / "Added to shopping list, double-tap to add again" in the two states.
- When the user has zero shopping lists, tapping the icon shows the "No shopping lists — tap + to create one" snackbar and does NOT flip the check.
- When `populateFromRecipe` throws, icon does NOT flip; "Failed to add ingredients" snackbar appears.
- Simulating `_loadEvents` mid-flight (by triggering a week-nav tap between the `populateFromRecipe` future creation and its completion) does NOT flip the icon after resolution.
- Long-press → "Add to shopping list" on the action sheet also flips the icon on success (shared state).
- Regression: delete `app/test/features/calendar/generate_weekly_list_test.dart` and assert `rg populateFromCalendarRange app/` returns nothing.

### cpms-2 — Backend: remove populate-from-calendar endpoint + all tests + docs

**Scope**
- Delete `services/api/src/api/v1/shopping_list/populate_from_calendar.py`.
- Remove the `PopulateFromCalendar` import and `__all__` entry from `services/api/src/api/v1/shopping_list/__init__.py` (lines 17, 48).
- Delete the `@shopping_list_router.post("/shopping-lists/{list_id}/populate-from-calendar")` block from `services/api/src/routers/v1/shopping_list_router.py` (lines 300–317).
- Delete `services/api/tests/test_populate_from_calendar.py` in full.
- From `services/api/tests/test_coverage_gaps.py`, delete the section 3 header comment (around lines 226–229) and the `TestPopulateFromCalendarExtended` class (lines 231–525). Keep all other classes intact.
- Update `docs/SHARED_SHOPPING_CART.md` — remove the `POST /v1/shopping-lists/{id}/populate-from-calendar` entry (line ~680) and any surrounding context that references it.
- Confirm `get_user_calendar_ids` (used at the deleted line 86 path) has other live callers (`list_meal_events.py`) and leave it untouched.
- Confirm `utils/deadline.py::calculate_item_due_date` has other live callers (`populate_from_recipe.py`, `get_deadlines.py`) and leave it untouched.
- Grep `services/api/src/routers/` for any stale direct imports from `api.v1.shopping_list.populate_from_calendar` and delete if found.
- Confirm no other runtime caller exists: `rg 'populate-from-calendar|populate_from_calendar|PopulateFromCalendar' services/ app/ docs/` returns zero matches after this story (matches inside `_bmad-output/**` are planning artifacts and can remain).
- Add a one-line dated strikethrough in `_bmad-output/planning-artifacts/architecture.md` at line 1091 noting the endpoint is removed per FR-CPMS-1.

**Acceptance criteria**
1. No Python module at `services/api/src/api/v1/shopping_list/populate_from_calendar.py` exists.
2. `from api.v1.shopping_list import PopulateFromCalendar` raises `ImportError`. The module's `__init__.py` `__all__` no longer lists it.
3. `POST /v1/shopping-lists/{list_id}/populate-from-calendar` returns 404 (FastAPI no longer registers the route).
4. `npx nx run api:test` passes. `npx nx run api:lint` passes. `npx nx run api:test --coverage` meets the pinned 100% threshold (no leftover uncovered lines from orphaned code paths).
5. `docs/SHARED_SHOPPING_CART.md` no longer documents the endpoint.
6. No references remain in any runtime path: `rg 'populate[-_]from[-_]calendar' services/ app/ docs/` returns only hits inside `_bmad-output/**`.
7. The router-level WebSocket broadcast removed with the endpoint is functionally duplicated by the surviving `populate_from_recipe` handler's broadcast (verified by reading the `populate_from_recipe` route at `shopping_list_router.py:294–296`) — per-meal adds preserve real-time updates for connected shopping-list members.
8. `architecture.md` and any other `_bmad-output/planning-artifacts/*` references to the endpoint carry a dated strikethrough note pointing to FR-CPMS-1.

**Tests**
- No new tests added; this story is a net deletion. Existing `test_populate_from_recipe.py` and `test_coverage_gaps.py` (remaining classes) continue to pass as-is.
- Verify coverage doesn't regress: running `npx nx run api:test --coverage` should produce the same pass/fail as before with zero uncovered lines in `services/api/src/`.

## Dependencies

- **Internal**: cpms-1 and cpms-2 should land and deploy **together**. In dogfood this is a single dev-loop cycle. If TestFlight/Play review splits the Flutter deploy from the backend deploy, land cpms-1 (Flutter) first so users transition to the per-card UX before the bulk endpoint disappears; hold cpms-2 until cpms-1 clears review. Rollback for cpms-2: revert the commit; endpoint is restored idempotently (no migrations), old clients resume working immediately.
- **Cross-epic**: `epic-meals-calendar` (in-progress as of 2026-04-18, mcal-1 in-progress) loses story `mcal-4`. That epic's primary-path end-user flow step 7 ("Add to Shopping List on the detail sheet calls PopulateFromCalendar with include_meal_event_ids") needs a new transport at its implementation time — recommended replacement: `POST /v1/meal-events/{event_id}/add-to-shopping-list` mirroring `POST /v1/meals/{meal_id}/add-to-shopping-list` (mcal-5) with the same `aggregate_meal_ingredients` dedupe for Meal events and a simple `populate_from_recipe` call for Recipe events. `mcal-4` is marked `deleted` in `sprint-status.yaml` and a dated note is prepended to `epic-meals-calendar.md`. FR-MEAL-12 (sum-within-meal dedupe) is NOT retracted — only its transport path changes.
- **No other dependencies.** No new migrations, no new env vars, no new AWS resources, no new Terraform.

## Risks

- **Raw-string ingredient names** (original driver). Per-meal adds still produce garbage line-items when the underlying `ingredients.canonical_name` row holds a raw recipe line. Mitigation: scoped to one meal's worth at a time (blast radius 1 vs. 12); user can immediately see and dismiss. Root-cause fix tracked separately.
- **Ghost check-mark race**. If `_loadEvents` fires between a tap's `populateFromRecipe` kick-off and its resolution, naive state writes would put a check on an event that may or may not still exist. Mitigation: load-generation int guard (cpms-1 AC #12) — the stale success silently drops visually, user still gets their snackbar.
- **`event.id` stability across reloads**. The set-based approach is correct by construction: `event.id` is the `meal_events` row PK. In-place reschedule UPDATE preserves id (state still valid, then cleared on next load); new-row reschedule drops the stale entry when the load clears. Low risk; documented.
- **Coverage-pin drift after delete**. Very low risk — grep confirms the two shared helpers have other live callers. Mitigation: run `npx nx run api:test --coverage` as part of cpms-2 before merge.
- **Deploy ordering — simultaneous beats Flutter-first in dogfood**. Backend-first would 404 old clients silently; Flutter-first is safer but coordination burden is low. Rollback plan: revert cpms-2 commit (endpoint restored, old clients work immediately; no migrations to undo).
- **Planning-artifact cross-references**. `populate-from-calendar` appears in `prd.md`, `architecture.md`, and `epic-meals-calendar.md`. cpms-2's scope adds a dated strikethrough in `architecture.md` at line 1091; `prd.md`'s new addendum overrides the prior Meals-calendar passage. `epic-meals-calendar.md` gets a note at the top (already applied). Future planners grepping these files will not design against a ghost endpoint.
- **Bulk-path WebSocket broadcast loss is zero-impact**. Surviving `populate_from_recipe` handler's broadcast covers the per-item `item_added` events to connected members — same shape, same semantics, just per-meal granularity.

## Open questions for the user

None — both open UX decisions were resolved in the Phase 2 batch (always-visible icon when recipe linked, session-persistent load-generation-guarded check-mark), and the cross-epic impact on meals-calendar is handled via dated note + `mcal-4` deletion + documented replacement shape for the future replan.
