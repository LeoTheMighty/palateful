# Story cpms-1: Flutter — remove weekly AppBar button + per-card shopping-cart icon

**Status:** done
**Epic:** epic-calendar-per-meal-shopping-add

## Goal

Replace the blunt "Add week to shopping list" AppBar icon (which
produces garbage line-items at a 12-to-1 blast radius) with a
per-card `Icons.add_shopping_cart_outlined` icon on every calendar
event whose `event.recipe != null`. Tap → `_addIngredientsFromEvent`
reusing the existing one-meal flow verbatim; on
`items_added > 0` the icon flips to a muted `Icons.check` in a
session-scoped Set keyed on `event.id`, guarded by a load-generation
int so mid-flight reloads can't leave ghost indicators.

## Scope

### Flutter — `app/lib/features/calendar/calendar_screen.dart`

- DELETE the AppBar shopping-cart `IconButton` (currently wraps
  `_generateWeeklyShoppingList` at lines 620–625).
- DELETE `_generateWeeklyShoppingList()` (lines 381–490) and the
  `_isGeneratingList` field (line 51).
- ADD `final Set<String> _addedEventIds = <String>{};` to
  `_CalendarScreenState` next to the existing `_loadGeneration`.
- In `_loadEvents()`'s initial setState block, clear
  `_addedEventIds` (the `_loadGeneration++` already lives there).
- Modify `_addIngredientsFromEvent`: capture
  `final generation = _loadGeneration;` before any `await`. On the
  `populateFromRecipe` success branch, after receiving the result,
  if `mounted && generation == _loadGeneration && result.itemsAdded > 0`,
  `setState` to add `event.id` to `_addedEventIds` before showing
  the snackbar. A zero-add does NOT flip the check.
- In `_buildEventTile`, insert — between the title/chip
  `Expanded` column and the existing chevron — a conditional
  `SizedBox(width: 32, height: 32)` wrapping an `IconButton`
  (`padding: EdgeInsets.zero`, `iconSize: 18`) gated on
  `event.recipe != null`. Icon toggles between
  `Icons.add_shopping_cart_outlined` and `Icons.check` based on
  `_addedEventIds.contains(event.id)`. Wrap in `Semantics(button:
  true, label: ...)` that flips between "Add to shopping list" and
  "Added to shopping list, double-tap to add again."

### Flutter — `app/lib/features/shopping_cart/services/shopping_cart_service.dart`

- DELETE `populateFromCalendarRange` (lines 161–177) and its doc
  comment.

### Flutter — `app/lib/core/services/api_client.dart`

- DELETE `populateShoppingListFromCalendar` (lines 467–471).

### Tests — `app/test/features/calendar/`

- DELETE `generate_weekly_list_test.dart` in full.
- NEW `per_meal_shopping_add_test.dart` — see test list below.

## Acceptance Criteria

1. Calendar AppBar renders no shopping-cart action; nothing else in
   the AppBar shifts.
2. Every card with `event.recipe != null` renders a tappable
   `Icons.add_shopping_cart_outlined` button with tooltip "Add to
   shopping list."
3. Cards with `event.recipe == null` render no `IconButton` and no
   placeholder `SizedBox` — row collapses exactly like the
   chevron-absent case does today.
4. Tapping the icon invokes `_addIngredientsFromEvent(event)`.
   Tapping the card body still opens the meal detail sheet.
   Long-press still opens the options sheet. The icon's tap does
   not bubble.
5. On success with `items_added > 0`, the icon flips to
   `Icons.check` (muted tone). Tooltip flips to "Added to shopping
   list." Semantics label flips to "Added to shopping list,
   double-tap to add again."
6. `_loadEvents()` clears `_addedEventIds` and bumps
   `_loadGeneration`; reschedule, week nav, tab re-entry,
   calendar-switch, and pull-to-refresh all restore the un-checked
   state.
7. Adding via the long-press action sheet also flips the card's
   indicator (shared write inside `_addIngredientsFromEvent`).
8. Tapping an already-checked card re-runs the add; no guard.
   Snackbar fires again; icon stays checked.
9. `ShoppingCartService.populateFromCalendarRange` and
   `ApiClient.populateShoppingListFromCalendar` are removed. `rg
   'populateFromCalendar|populateShoppingListFromCalendar' app/`
   returns empty. Dart analyzer passes.
10. The existing `_addIngredientsFromEvent` behavior (default-list
    resolution, chooser sheet, "Change" action, error snackbars) is
    untouched. All existing call sites (long-press sheet) work
    identically.
11. If `populateFromRecipe` returns `items_added == 0`, the icon
    does NOT flip to check; snackbar still fires.
12. If `_loadEvents` completes while an add request is in-flight,
    the success handler does NOT flip the icon on the new grid.
13. Icon is reachable via TalkBack/VoiceOver swipe; label reads
    appropriately for un-added and checked states.
14. Icon tap target is 32×32 logical pixels (`SizedBox` wrapper);
    row height unchanged vs. baseline.

## Tests (widget, `per_meal_shopping_add_test.dart`)

- Per-card icon renders when event has recipe; count matches
  recipe-backed events.
- Per-card icon hidden when `event.recipe == null`.
- Tapping icon calls `populateFromRecipe` with the event's recipe
  id (not `populateFromCalendarRange`).
- Tap success with `items_added > 0` flips icon to `Icons.check`;
  tooltip/Semantics update.
- Tap success with `items_added == 0` does NOT flip the icon;
  snackbar still fires.
- Icon tap does NOT bubble: meal detail sheet is not pushed.
- Icon tap size is 32×32 logical pixels.
- Semantics label reads "Add to shopping list" / "Added to
  shopping list, double-tap to add again."
- Zero shopping lists → "No shopping lists — tap + to create one";
  no icon flip.
- `populateFromRecipe` throws → no icon flip; "Failed to add
  ingredients" snackbar.
- Mid-flight `_loadEvents` (week-nav) does NOT flip the icon.
- Long-press → "Add to shopping list" also flips the icon on
  success (shared state).

## File List

Modified:
- `app/lib/features/calendar/calendar_screen.dart`
- `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
- `app/lib/core/services/api_client.dart`

Deleted:
- `app/test/features/calendar/generate_weekly_list_test.dart`

New:
- `app/test/features/calendar/per_meal_shopping_add_test.dart`

## QA Walkthrough

See `cpms-1-qa-walkthrough.md`.
