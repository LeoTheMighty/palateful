# QA walkthrough — afh-3 Flutter Notifications See-all footer

Run on the staging build with a test user who has:
- 2 or 3 active partner_action notifications (so the active list isn't empty)
- >5 archived partner_actions (so See-all has content)
- Ideally some partner_actions older than 30 days + read

## Core flows

- [ ] Open the Activity tab — Notifications tab is default.
- [ ] Scroll to bottom — see the "See all (N)" footer in muted brown/grey type, with a history icon and a `chevron down` caret.
- [ ] Tap the footer — it expands, spinner briefly, then a list of archived/old rows renders in the same muted type. Dates like "3 months ago" display.
- [ ] Scroll within the expanded list — when near the bottom, a second page loads inline (small spinner, then rows appear).
- [ ] Continue scrolling — reach the end, confirm "That's everything. (N total)" muted row. No more fetches.

## Archive/unarchive flows

- [ ] Swipe a See-all row to the right — row disappears, "Unarchived" snackbar with Undo button. Tap Undo within 3s — row reappears.
- [ ] Swipe another See-all row right, wait 3s for the snackbar to expire — row stays gone (unarchive committed).
- [ ] Archive an active notification from the main list — switch to Imports tab, switch back, expand See-all: new row is now at top.

## Empty states

- [ ] New / fresh test user with 0 total notifications → "You're all caught up" empty state, no "See all" footer (count = 0).
- [ ] User with 0 active + some history → "You're all caught up" empty state with "See all (N)" footer visible beneath.

## Error path

- [ ] Airplane mode on, tap "See all" → spinner briefly, then "Couldn't load more. Tap to retry." muted row (no crash).
- [ ] Airplane mode off, tap the retry row → rows load.

## Persistence

- [ ] Expand See-all, scroll halfway, switch to Imports tab, switch back → still expanded, scroll offset preserved.
- [ ] Collapse, re-expand immediately → rows render from cache, no spinner.

## Visual polish

- [ ] All See-all rows are muted (onSurface at 0.65 alpha), not primary foreground.
- [ ] The Imports tab See-all footer (existing) is still muted and visually matches.
- [ ] The caret flips between `chevron_down` and `chevron_up` on expand/collapse.

## No-regression

- [ ] Bell badge in the bottom nav still sums notifications + imports_actionable.
- [ ] Archive swipe on an active notification still works (3s undo, optimistic).
- [ ] 30s poll on the Notifications tab still refreshes the active list.
