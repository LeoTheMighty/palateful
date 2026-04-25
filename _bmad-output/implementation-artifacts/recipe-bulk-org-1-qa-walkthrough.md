# recipe-bulk-org-1 — QA walkthrough

**Story:** Frontend `Add to…` + `Move to…` actions on long-press bar.

## Setup

1. Sign in as a user with at least 4 recipes split across ≥2 books
   (e.g. some in Trying Out, some in a personal book like "Mom's").
2. Make sure `Trying Out` (the `is_system=true` book seeded by
   `recipe-defaults-1`) exists.

## Happy paths

- [ ] Long-press a recipe on Home → multi-select bar appears.
- [ ] Tap a second recipe → bulk bar shows: primary (Create Meal) +
      `Add to` + `Move to` + Archive.
- [ ] Tap `Add to` → bottom sheet titled **"Add to…"** opens. Trying
      Out is the first row (with the sparkle icon). Other writable
      books follow. A "+ New book" row sits at the bottom.
- [ ] Tap any book → sheet closes, selection exits, snackbar reads
      `Moved 2 recipes to <book>` with an `Undo` action.
- [ ] Tap `Undo` within 5 s → snackbar replaces with `Move undone`,
      both recipes return to their original books.
- [ ] Repeat with `Move to` — same behavior, sheet titled **"Move to…"**.
- [ ] Tap `+ New book`, type `qa-test-book`, submit → sheet closes
      and the snackbar says `Moved 2 recipes to qa-test-book`. The
      Recipe Books screen shows the new book with the moved recipes
      inside.

## Edge cases

- [ ] Selection contains a Meal → `Add to` and `Move to` are hidden;
      only Create Meal / Add to "<meal>" + Archive render.
- [ ] Pick a destination book that is the *only* source of the
      selection → snackbar reads `Already in <book>` and nothing moves.
- [ ] Selection spans 2 source books (e.g. one from Trying Out + one
      from "Mom's") → tapping `Add to` works the same way; the snackbar
      is still `Moved N recipes to <book>`. (Multi-source disambiguation
      for `Move to…` ships in story 3.)
- [ ] Tap `Add to`, then dismiss the sheet without picking → no toast,
      selection stays active.
- [ ] Try moving with no network → snackbar reads
      `Couldn't move recipes — try again` (default mutation-failure
      copy); selection stays active for retry.

## Visual checks

- [ ] System books (Trying Out) lead with the sparkle icon and use the
      primary color. User books use the default `menu_book_outlined`.
- [ ] `+ New book` row is colored primary so it's distinguishable from
      a real book.
- [ ] Bulk bar height does not change between Recipe-only and Meal
      selections (the new buttons just appear/disappear).

## Regression

- [ ] Long-press → Archive flow unchanged.
- [ ] Long-press → Create Meal flow unchanged.
- [ ] Recipe-book detail screen's existing bulk-move flow still works
      (this story did not touch it).
