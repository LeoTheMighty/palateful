# QA walkthrough — pfc-4 home filter is zero-network

Pre-dogfood sanity check that flipping filters never refetches the
backing lists.

## 1. Cold-load baseline

- [ ] Launch the app. Open DevTools → Network.
- [ ] Home renders. Observe `GET /v1/recipe-books`,
      `GET /v1/recipe-books/:id`, `GET /v1/favorites`, and
      `GET /v1/meals?scope=home` each fire exactly once.
- [ ] Clear the Network log.

## 2. Filter flip — zero network

- [ ] Tap the "Sort & filter" pill.
- [ ] Switch Meal type to "Breakfast" → Apply.
- [ ] Network log: EMPTY. Grid visibly filters.
- [ ] Switch Sort to "Newest" → Apply. Network log stays empty.
- [ ] Switch Show type to "Meals only" → Apply. Network log stays
      empty.
- [ ] Toggle "Hide components of Meals" ON → Apply. Network log stays
      empty.
- [ ] Pick a specific vibe → Apply. Network log stays empty.

## 3. Allowed refetch paths still work

- [ ] Pull-to-refresh the home grid. Network log fires the four list
      endpoints once.
- [ ] Clear Network log.
- [ ] Archive a recipe from recipe detail → back out to home. Network
      log fires the four list endpoints once (expected — mutation
      path).
- [ ] Clear Network log.
- [ ] Save a new recipe from the Add sheet. Network log fires the four
      list endpoints once post-save (expected — mutation path).

## 4. Clear all undo (edge case)

- [ ] Set a non-default filter (e.g. Vibe = "Comfort").
- [ ] Open Sort & filter → Clear all → Apply. Grid reflows to no filter.
- [ ] Tap the "Undo" snackbar action. Filter state restores; grid
      reflows back to "Comfort". Network log stays empty across BOTH
      the clear AND the undo.

## 5. Mid-load filter flip (rare timing edge)

- [ ] Enable Network Throttling → Slow 3G.
- [ ] Launch the app. While Home is still spinning, open filter sheet
      and flip Meal type. Apply.
- [ ] Home resolves. Verify the final grid state reflects the user's
      filter (server-truth recipes, filtered per the user's latest
      selection). No orphan or blank state.
