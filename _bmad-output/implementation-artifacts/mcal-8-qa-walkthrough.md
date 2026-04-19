# QA Walkthrough — mcal-8 (Flutter: calendar tile + day sheet + detail sheet + chooser)

## Pre-reqs
- Scheduled events: at least 1 recipe-only event AND at least 1 Meal event on different days.

## Meal-event tile rendering
1. Open Calendar. On the Meal-event tile, you should see:
   - Thumbnail: first component image, or layers icon if missing.
   - Title with a small `Icons.layers` inline prefix.
   - Meal-type chip underneath as today.
   - "2 recipes" caption below the chip.
2. Recipe-only events should render **unchanged** — no stack icon, no caption.

## Day-detail sheet
1. Tap an empty day. If there's at least one Meal event on other days, tap the day with one (via the + or bare row).
2. The row for the meal event should show the layers icon + title + "Dinner · 7:00 PM · 2 recipes".

## Event detail sheet — Meal event
1. Tap the Meal event tile. Detail sheet opens.
2. You should see:
   - Header: meal name + scheduled time.
   - **Open Recipe** primary button (enabled).
   - **Open Meal · 2 recipes** outlined button (NEW — visible only for Meal events).
   - Reschedule, Unschedule, Mark Cooked secondary row.
3. Tap **Open Meal**. The app navigates to `/meals/{id}` and the detail sheet dismisses.
4. Reopen the sheet. Tap **Open Recipe**. Because the Meal has 2 components, the chooser appears.
5. Chooser should show title "Which recipe?" + subtitle = meal name.
6. Archived components should NOT appear in the chooser.
7. Tap a component — the sheet dismisses and the app navigates to `/recipes/{componentRecipeId}`.

## Regression — recipe-only events
1. Tap a recipe-only event.
2. Detail sheet shows the same layout as before (no Open Meal row, no chooser).
3. Tap **Open Recipe** — navigates directly to `/recipes/{id}`.

## Per-card shopping-cart icon
1. A Meal event tile should now show the `add_shopping_cart_outlined` icon on the right.
2. Tap the icon. After a list-picker confirmation, the snackbar should say "Added N ingredients to X".
3. The icon should flip to a check mark if `items_added > 0`.

## Pass criteria
- No regression on recipe-only event rendering or "Open Recipe" navigation.
- Chooser appears only when the Meal has ≥2 available components.
- 1-available-component Meal event skips the chooser and pushes directly.
- All-archived edge case: chooser shows "No recipes are available to open." (Both rare and handled gracefully.)

## Tests
- `app/test/features/calendar/meal_detail_sheet_test.dart` — +3 tests in new "Meal event (mcal-8)" group.
- `app/test/features/calendar/calendar_recipe_chooser_sheet_test.dart` — 4 tests (NEW).
- Full calendar + meals suite: 174 pass locally.
