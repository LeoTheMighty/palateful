# QA Walkthrough — hmp-1 MealTile v2

Run this against the latest build after pulling main. Report regressions
in `epic-meals-home-promotion` thread.

## Preconditions

- At least 1 Meal across any readable book (create via Book-detail
  long-press → Create Meal if none exists).
- At least 3 recipes so the chip-row "+N" case is reachable.

## Home grid — MealTile chrome

- [ ] Every Meal tile on the home grid shows a 2-px accent border.
- [ ] "Meal" pill renders in the top-left of each tile's collage.
- [ ] Pill has `Icons.layers_outlined` + "Meal" label.
- [ ] Pill is readable on a dark collage image (drop shadow present).
- [ ] Below the meal name, a single line of component names separated
      by `· `: e.g. "Kale Salad · Lemon Dressing".
- [ ] When component count > 2, the line ends with `· +N` where N is
      the count beyond the first two shown.

## Chip row — archived-component fallback

- [ ] Archive one of a Meal's component recipes (via Recipe detail →
      Archive). Pull-to-refresh home.
- [ ] The Meal's chip row now includes `· (archived)` at the end.
- [ ] With 2+ archived components the suffix appears only once, not
      per archived component.

## Favorite overlay

- [ ] Tap the star overlay on a not-favorited Meal tile — heart fills
      immediately (optimistic). No snackbar.
- [ ] Meal appears at the front of the Favorites carousel.
- [ ] Tap the star on a favorited tile — heart empties, Meal drops off
      the carousel.
- [ ] Simulate offline (airplane mode), tap the star. After the request
      fails, the heart reverts to its prior state (rollback). The
      carousel reflects the rollback state too.
- [ ] Tapping the star does NOT open the Meal detail — only the star
      target is tappable for the favorite action.

## Tile body + navigation

- [ ] Tapping outside the star overlay opens `/meals/:id` for that
      Meal (unchanged behavior).

## Book-detail regression (no resolver supplied)

- [ ] Open a recipe book that contains a Meal.
- [ ] MealTile renders with:
      - Accent border + pill + no component-name chips.
      - Chip-row slot shows "(N recipes)" (backward-compat fallback).
- [ ] Tile body tap behavior unchanged.

## Zero-Meal state

- [ ] On an account with zero Meals, home renders bit-identically to
      pre-epic — no MealTile widgets, no Meal pill, no regressions in
      the recipe grid layout or favorites carousel.

## Selected-state (hmp-2 pre-wire)

- [ ] MealTile accepts `selected: bool` without layout glitches. At
      this story's scope the prop is always false from home; a widget
      test proves the checkmark overlay renders when `selected: true`.

## Automated coverage

- `flutter test test/features/meals/meal_tile_test.dart` — 16 cases,
  all pass.
- `flutter test test/features/home/home_screen_meals_test.dart` —
  existing home-grid meal tests continue to pass.
- `npx nx run api:test` — `test_meal_router.py::test_happy` asserts
  `component_recipe_ids` on the list response.
