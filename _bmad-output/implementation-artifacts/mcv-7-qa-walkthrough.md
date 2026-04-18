# QA Walkthrough: mcv-7

Mixed recipe + meal grid in the book detail view, and archived meals in
the global Archived Recipes screen.

## Manual smoke

### Book grid

1. Open a book that has both recipes and (at least one) Meal.
2. **Verify grid**: mixed tiles render in the same `GridView.count`.
   Meals show the 1/2/3/4-up collage hero + meal name + "N recipes"
   badge. Recipes render exactly like before.
3. **Verify sort**: most-recently-updated item (Meal or Recipe) appears
   first. Edit a Meal's name (via mcv-6's edit screen) → return to the
   book grid → the edited Meal should move to the front.
4. **Header**: reads "Recipes & Meals (total)" when meals exist,
   "Recipes (N)" otherwise.
5. **Tap a Meal tile** → navigates to `/meals/:id` (the mcv-6 detail
   screen).
6. **Multi-select**: long-press a recipe → enter select mode →
   `MealTile` becomes non-interactive (tap does nothing). The bulk
   bar's Create Meal / Move / Tags / Archive all still work on the
   selected recipes.

### Vibe filter

7. With a book containing recipes (at least one with a vibe) + meals,
   apply a vibe filter. Recipes matching the vibe render; meals are
   hidden (they don't carry vibe metadata). Clear the filter → meals
   return.

### Meals load failure

8. Offline simulation (or 500 from the meals endpoint): book still
   loads, a banner above the grid reads "Couldn't load meals in this
   book.", recipe tiles render.

### Archived view

9. Archive one meal (via mcv-6's Archive action).
10. Open Archived Recipes (Profile → Archive, or wherever the route
    lives).
11. **Verify meal row**: shows meal name, "Meal · N recipes" subtitle,
    "Archived MM/DD/YYYY" timestamp, and a **Restore** button.
12. Tap **Restore** → snackbar "Meal restored", row disappears, meal
    becomes available again in its book's grid.
13. Search box filters both recipes and meals by name.

## Automated

- `dart analyze lib/features/meals/ lib/features/recipe_books/ lib/
  features/recipes/archived_recipes_screen.dart` → clean.
- `flutter test test/features/meals/ test/features/recipe_books/`
  → 90 tests pass.
- `npx nx run api:test` → 1894 passed, 100% coverage.

## Out of scope (future work)

- Drag-reorder of the mixed grid → TBD (no AC in this epic).
- Infinite scroll / pagination for meals in the book → the initial
  fetch asks for 50; rare books with >50 meals will need paging.
- Home-grid and search surfaces showing meals → epic-meals-
  discoverability.
