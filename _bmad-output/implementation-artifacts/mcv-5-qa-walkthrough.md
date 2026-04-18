# QA Walkthrough: mcv-5

Create Meal user flow — the first user-facing story in this epic.

## Manual smoke

### Path 1 — Multi-select

1. Sign in; open a book with ≥2 recipes (e.g., Dinners).
2. Long-press a recipe — enters select mode.
3. Tap a second recipe — AppBar reads "2 selected."
4. **Verify bulk bar**: the first action is **Create Meal**, enabled.
5. Tap Create Meal → sheet opens with:
   - Name pre-filled as `"<first name> + <second name>"` (truncated
     to 60 chars with `…`).
   - Horizontal strip of both recipe thumbnails.
   - Create button enabled.
6. Tap Create → sheet dismisses, green snackbar "Meal '<name>'
   created", navigates to `/meals/<id>` (mcv-4 placeholder until
   mcv-6 lands).
7. Back-nav returns to the book; grid reloads.

### Path 2 — "+ New Meal" overflow

1. Open the same book, NOT in select mode.
2. Tap the overflow (⋮) menu → pick **New Meal**.
3. Sheet opens empty AND auto-opens the picker on first frame.
4. Type "Kale" — picker switches to cross-book search; tap to
   select "Kale Salad".
5. Clear search; pick "Lemon Dressing" from the book-scoped list.
6. Tap Done — picker closes, sheet now shows both components;
   Name is pre-filled.
7. Tap Create → same flow as Path 1.

### Error path — component archived between selection and save

1. Using Path 1, select 2 recipes in book A.
2. In a second app window (or admin panel), archive one of them.
3. Back in the sheet, tap Create.
4. **Verify**: inline error banner "Some recipes are no longer
   available. Remove them to continue." appears; the archived
   thumbnail shows an "Unavailable" overlay and a **Remove**
   button below it; Create stays disabled.
5. Tap Remove on the archived thumbnail; Create re-enables (if
   ≥2 components remain); retry succeeds.

### Below-2 rule

1. Path 1: select 2, open sheet, long-press one thumbnail to
   remove.
2. **Verify**: helper text "A meal needs at least 2 recipes."
   appears, Create disables. Undo snackbar restores the component.

## Automated

- `dart analyze lib/features/meals/` → clean.
- `flutter test test/features/meals/` → 23 existing + 9
  create_meal_sheet + 5 recipe_multiselect_picker pass.

## Out of scope (lands later)

- Meal detail body (collage, action bar, component list) → mcv-6.
- MealTile in the book grid → mcv-7.
- Share, Plan-for-Date, Add-to-Shopping-List live actions →
  sibling epics (sharing-and-ai, calendar).
