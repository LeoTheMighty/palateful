# QA walkthrough — afh-4 Flutter Imports See-all pagination swap

## Core flows

- [ ] Open Activity → Imports tab. Scroll to bottom. Existing `See all (N)` footer renders with chevron-down.
- [ ] Tap "See all" — spinner briefly, then first batch of archived items renders (should be ≤ ~100 rows; page size is 50 jobs × their items).
- [ ] Continue scrolling — within 200px of bottom, a small spinner appears and the next page loads.
- [ ] Reach the end — "That's everything. (N total)" muted row. No further fetches on continued scroll.

## Archive/unarchive flows

- [ ] Swipe right on a See-all item → snackbar "Unarchived" with Undo. Tap Undo within 3s → row reappears.
- [ ] Swipe right on an active (non-See-all) yellow-row → "Archived" snackbar. Confirm the See-all footer count ticks UP by 1 on next expand or refresh.
- [ ] Swipe right again on See-all item, wait 3s → committed unarchive. Footer count ticks DOWN by 1.

## Error path

- [ ] Airplane mode on, tap See all → spinner briefly → "Couldn't load more. Tap to retry." row.
- [ ] Airplane mode off, tap retry → rows load.

## Persistence

- [ ] Expand See-all, scroll halfway, switch to Notifications tab, switch back → still expanded, scroll offset preserved.
- [ ] Collapse and re-expand → rows render from cache, no spinner.

## Visual

- [ ] Rows in See-all are muted (onSurface at 0.65 alpha) — identical shade to the Notifications See-all (afh-3).
- [ ] Caret flips between `chevron_down` / `chevron_up`.
- [ ] Source-type icons (url/photo/pdf/etc.) render in muted color.

## No-regression

- [ ] Active rows in the four color sections (In Progress / Needs Review / Failed / Auto-Imported) render as before.
- [ ] Caret-expand on an active yellow row still works (no item-extent clipping).
- [ ] 30s poll still refreshes both active sections + see-all count.
- [ ] Bell badge behavior unchanged.

## Known limitation

- Some >30d-completed (non-archived) items may show in the count but not the rendered list. Log a bug only if it's clearly visible during QA (e.g., count reads 200 but list obviously cuts off at a much lower number with no loading row).
