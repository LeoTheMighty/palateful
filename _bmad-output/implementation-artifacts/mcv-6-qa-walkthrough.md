# QA Walkthrough: mcv-6

Meal detail + edit — the first user-facing surfaces to show a Meal's
full anatomy.

## Manual smoke

### Detail screen

1. Sign in. Create a 2-recipe meal from a book (via mcv-5's Create
   Meal flow).
2. Tap the Meal tile / navigate to `/meals/<id>`.
3. **Verify hero**: 2-up collage of the component thumbnails. If one
   component has no image, the placeholder icon renders in its cell.
4. **Verify title row**: Meal name + description.
5. **Verify action bar**: Favorite (outlined heart), Plan, Shop,
   Share (last three look disabled/grey and have tooltips on
   long-press), Archive (red), Edit.
6. Tap **Favorite** → heart fills immediately (optimistic), then
   backend confirms. Tap again to unfavorite — should return to
   outlined heart.
7. **Verify action bar tooltips**: Long-press Plan → "Available when
   calendars ship". Long-press Shop → "Schedule this meal first".
   Long-press Share → "Available when sharing ships".
8. **Component list**: tap a component row → opens `/recipes/<id>`.
9. Back-nav to the meal — Favorite state persists.

### Edit screen

10. From detail, tap **Edit**. AppBar close → Cancel; Save on the right.
11. **Name + description**: both pre-filled. Change either; tap Save —
    snackbar "Meal saved", pop back to detail. Detail shows new name/
    description.
12. **Drag-to-reorder**: long-press a drag handle, drag to a new
    position. Optimistic reorder; backend commits per drop.
13. **Add Recipe FAB**: opens the picker (defaults to the meal's book,
    searchable across books). Already-attached components show
    "Added" badge and can't be tapped. Pick one, tap Done — the row
    appears in the list.
14. **Swipe-to-delete at 3→2**: swipe any row left → confirm → row
    removes, backend commits.
15. **Swipe at 2→1 rejects**: create a fresh 2-component meal, open
    Edit, swipe one row. Snackbar: "A meal needs at least 2
    recipes…". Row stays.

### Unavailable components

16. Archive one of the component recipes (via the recipes admin screen
    or another user's archive). Open the Meal detail.
17. **Verify partial-unavailability banner**: banner above the list
    reads "Some components are unavailable."
18. **Verify hero chip**: top-right shows "1 of 2" (or "N of M").
19. **Verify muted row**: the unavailable row is greyed out and
    labeled "Unavailable".
20. Archive the second component too. Detail now shows the banner
    "All components are unavailable. Archive or edit to fix." and
    the hero chip reads "All components unavailable".

### Archive & restore

21. From detail, tap **Archive**. Confirmation dialog: Cancel /
    Archive. Tap Archive → navigates back, snackbar "Meal archived".
22. Restore path is not wired in v1 (comes via the Archived view in
    mcv-7). To manually restore, `POST /v1/meals/<id>/restore` via
    the backend.

## Automated

- `dart analyze lib/features/meals/` → clean.
- `flutter test test/features/meals/` → 62 tests pass
  (23 existing mcv-4 + 14 mcv-5 + **25 new mcv-6**).
- `npx nx run api:test` → **1894 passed**, 100% coverage.

## Out of scope (lands later)

- Meal tile in the book grid → mcv-7.
- Share button live-wiring → epic-meals-sharing-and-ai.
- Plan for Date / Add to Shopping List live-wiring →
  epic-meals-calendar.
