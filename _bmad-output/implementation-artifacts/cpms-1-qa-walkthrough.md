# cpms-1 QA Walkthrough

## Pre-flight

1. `git pull origin main && flutter pub get` in `app/`.
2. Back your Calendar tab with at least two shopping lists and a few
   planned meals — mix: one recipe-backed meal, one free-text meal,
   one recurring meal.

## AppBar removal

- [ ] Open the Calendar tab. The top-right **shopping-cart icon is
      gone** — title, week-nav, and FAB remain.

## Per-card icon — happy path

- [ ] Every week card whose title is a **linked recipe** renders a
      small `add_shopping_cart_outlined` icon between the title and
      the chevron.
- [ ] Tapping the icon (NOT the card body) lands ingredients on the
      user's default list and flashes a snackbar "Added N ingredients
      to <List>." with a "Change" action when >1 list exists.
- [ ] After the snackbar, the card's icon flips to a muted **check**
      mark. Tooltip reads "Added to shopping list."

## Per-card icon — free-text meal

- [ ] A card with no linked recipe (e.g. "Takeout Pizza") renders **no**
      shopping-cart icon. The row width redistributes — no blank
      column left over.

## Row-tap behavior unchanged

- [ ] Tapping the **card body** (not the icon) still opens the meal
      detail sheet.
- [ ] **Long-press** still opens the Reschedule / Add to shopping
      list / Remove sheet.
- [ ] Using the long-press path's "Add to shopping list" entry also
      flips the card's check — both entry points share state.

## Session-scoped indicator

- [ ] The check mark persists while you're on the grid.
- [ ] Swipe week forward → week back → check is **cleared** (fresh
      load).
- [ ] Pull-to-refresh → check cleared.
- [ ] Leave and re-enter the Calendar tab → check cleared.
- [ ] Switch active calendar (if you have more than one) → check
      cleared.
- [ ] Reschedule the meal → new card is un-checked.

## Ghost-flip guard

- [ ] While on a slow network, tap the icon, then **immediately** tap
      the week-right chevron to load the next week. When the add
      request resolves, the new week's cards should NOT show a
      phantom check.

## Double-tap override

- [ ] Tap an already-checked card again — the add runs a second
      time, snackbar shows again, icon stays as a check.

## Accessibility

- [ ] With VoiceOver/TalkBack on, swipe to the icon — label reads
      "Add to shopping list."
- [ ] After a successful add, the label on the same icon reads
      "Added to shopping list, double-tap to add again."

## Error & edge cases

- [ ] Tap the icon with **zero shopping lists**: snackbar "No
      shopping lists — tap + to create one." Icon stays un-checked.
- [ ] Tap the icon when the API throws: snackbar "Failed to add
      ingredients." Icon stays un-checked.
- [ ] Tap a recipe whose ingredient list is empty: `items_added ==
      0`. Snackbar still fires ("Added 0 ingredients to <List>") but
      the icon **does not** flip to a check.

## Regression

- [ ] Calendar week-grid layout, thumbnails, chip styling, recurring
      badge — all unchanged.
- [ ] Existing long-press flow, reschedule flow, mark-cooked flow —
      all unchanged.
- [ ] Snackbar "Change" action (when user has >1 list) still opens
      the default-list chooser.
