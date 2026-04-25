# recipe-bulk-org-4 — QA walkthrough

**Story:** Recipe-detail book picker — tap-to-reveal pill row replaces
the modal `ListView`.

## Setup

- Sign in as a user with at least 3 writable books (Trying Out,
  one personal book, and one more for moving into).
- Open any recipe in a writable book.

## Happy paths

- [ ] Recipe detail screen loads. Below the title (or the lineage badge
      when present), a single 📒 pill shows the recipe's current book
      name. The popup-menu "Move to Book…" item is gone.
- [ ] Tap the pill → it expands into a horizontal scrollable row of
      every writable book + a trailing `+ New book` pill. Trying Out
      (system) appears first.
- [ ] The current book's pill is highlighted (filled chip).
- [ ] Tap a different book's pill → recipe moves; row collapses;
      snackbar reads `Moved 1 recipe to <book>` with a 5 s `Undo`.
- [ ] Tap `Undo` → recipe returns to the original book; toast reads
      `Move undone`.
- [ ] Tap the pill again, then tap `+ New book`. Type "qa-detail-test"
      and submit → snackbar reads `Moved 1 recipe to qa-detail-test`,
      and the new book exists in the books list.

## Edge cases

- [ ] Tap the pill, then tap the current book's pill (the highlighted
      one) → the row collapses without making any change.
- [ ] User is a viewer on a recipe (`can_edit` false) → the pill row
      is hidden entirely.
- [ ] Open a recipe in Trying Out and tap the pill → Trying Out is
      pinned at the front of the expanded list.

## Visual checks

- [ ] Collapsed pill is left-aligned with the rest of the body content.
- [ ] Expanded row scrolls horizontally without wrapping.
- [ ] No visible flicker between collapsed and expanded states.
- [ ] System book uses the sparkle (`auto_awesome_outlined`) avatar; user
      books have no avatar in the chip; "+ New book" uses the `+` icon.

## Regression

- [ ] Popup-menu items still work: Add to Cart, Plan for…, Copy,
      Make My Copy, Archive.
- [ ] Recipe-book detail screen long-press bulk move flow unchanged.
- [ ] Home long-press `Add to / Move to` flows from stories 1 and 3
      unchanged.
