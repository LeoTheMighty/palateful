# QA Walkthrough — hmp-2 Home selection mode + bulk bar scaffold

## Preconditions
- At least 2 recipes on home.
- Optional: at least 1 Meal to exercise Meal-side selection paths.

## Long-press entry

- [ ] Long-press a recipe tile. Haptic tick fires. Header shifts to an
      AppBar reading "1 selected" with an X (close) leading icon.
- [ ] Tile gains a dim overlay + centered checkmark.
- [ ] FAB (add recipe) disappears.
- [ ] Favorites carousel + "Recently Cooked" strip + batch-import
      status widget collapse from view while selection is active.
- [ ] A bottom bulk bar docks with: primary slot (disabled — "Select 1
      more recipe to create a Meal, or select a Meal to add to") and
      an always-enabled Archive button.

## Multi-select growth

- [ ] Tap a second recipe — header reads "2 selected"; primary slot
      swaps to `Create Meal` (enabled).
- [ ] Long-press a Meal tile — header reads "N selected"; if only the
      Meal is selected, primary disabled with `Select recipes to add
      to this Meal`. Pick a recipe — primary swaps to
      `Add to "<meal name>"`.
- [ ] Select 2 Meals — primary disabled with tooltip
      `Select only one Meal at a time`.

## Exit paths

- [ ] Tap X in the selection AppBar — exits. Header restores;
      contextual sections + FAB reappear; bulk bar collapses.
- [ ] Android only: back gesture exits (the controller's state drops
      automatically when all sets empty; confirm this keeps parity
      with iOS).
- [ ] Tap the exact same tile twice in selection mode — toggles off;
      if that's the last selection, mode exits automatically.

## Stub actions

- [ ] Create Meal → snackbar `coming in next story (hmp-3)`. No
      dispatch happens.
- [ ] Add to Meal → same snackbar.
- [ ] Archive → same snackbar.

## Background-refresh race

- [ ] Enter selection mode (select at least 1 recipe and 1 Meal).
      Trigger a reload (pull-to-refresh, or let a batch-import
      websocket-sync fire). Anything that vanished from the list
      drops silently.
- [ ] If the selection empties entirely, the snackbar `Selection
      cleared — content changed` shows and selection mode exits.

## Zero-regression

- [ ] All non-selection behaviors unchanged — open a recipe, open a
      Meal, toggle a favorite, open the filter sheet. All work.
- [ ] Recipe card's existing long-press sheet is GONE (Start Cooking +
      Archive both still live on Recipe Detail — the home sheet was a
      duplicate).
- [ ] Book detail screen's multi-select flow is untouched — still
      works as before.

## Automated coverage

- `flutter test test/features/home/` — 41 cases, all pass.
- `dart analyze lib/features/home/` — 3 pre-existing warnings; none
  new from hmp-2.
