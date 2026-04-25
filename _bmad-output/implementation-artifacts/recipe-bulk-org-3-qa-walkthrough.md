# recipe-bulk-org-3 — QA walkthrough

**Story:** Multi-source `Move to…` shows a disambiguation sheet from the
global "All recipes" home view.

## Setup

- Sign in as a user with at least:
  - 2 recipes in `Trying Out` (the system book seeded by
    `recipe-defaults-1`).
  - 2 recipes in a personal book (e.g. "Mom's").
- A third book to act as a destination (e.g. "Favorites" or any
  user-created book).

## Happy paths

- [ ] Long-press a Trying Out recipe → multi-select. Tap a Mom's recipe
      so the selection spans 2 source books. Tap `Move to`.
- [ ] **Disambiguation sheet** opens titled "Move from which book?".
      Both source rows are checked, with subtitle counts that match the
      selection (e.g. "1 recipe", "1 recipe").
- [ ] Tap Continue → the `Move to…` book picker opens. Pick "Favorites".
- [ ] Snackbar reads `Moved 1 from Trying Out, 1 from Mom's → Favorites`
      (order depends on map iteration — exact prefix order isn't
      contractual). 5 s `Undo` button visible.
- [ ] Tap `Undo` → both recipes return to their respective source books.

## Edge cases

- [ ] Single source `Move to…` (e.g. select 2 recipes, both in
      Trying Out) → the disambiguation sheet does NOT open; the picker
      is the only sheet.
- [ ] Open the disambiguation sheet, uncheck Mom's, Continue → only the
      Trying Out recipe moves. The Mom's recipe stays.
- [ ] Uncheck both rows → `Continue` is disabled. `Cancel` returns to
      the long-press selection bar with no changes.
- [ ] `Add to…` from the same multi-source selection skips the
      disambiguation sheet entirely.
- [ ] Destination is the same as one of the sources (e.g. picking
      "Mom's" while Mom's was a source) → recipes already in Mom's are
      silently skipped (backend behavior); the toast shows the moved
      count only.

## Visual checks

- [ ] Disambiguation sheet shows "Uncheck a book to leave its recipes
      where they are." subtitle.
- [ ] Each row shows `<book name>` + `<count> recipes` (singular when
      count == 1).
- [ ] System book (Trying Out) appears alongside user books — no
      special pin in this sheet (the destination picker is where
      pinning matters).

## Regression

- [ ] Bulk archive flow unchanged.
- [ ] Create Meal / Add to Meal flows unchanged.
- [ ] Story 1 single-source bulk move with toast + Undo still works.
