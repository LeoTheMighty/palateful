# QA walkthrough — afh-5 empty-state gateway links + pull-to-refresh

## Empty-state gateway link — Notifications

- [ ] Use a test user with 0 active notifications + >0 archived / old-read notifications. Open Activity → Notifications.
- [ ] See "You're all caught up" illustration. Below it, a muted underlined link reads **"See past notifications (N) ⌄"**.
- [ ] Tap the link — the See-all footer expands AND the scroll view animates down so the footer + its rows are visible.
- [ ] Repeat with a user who has 0 lifetime notifications — the "You're all caught up" text shows, NO gateway link.

## Empty-state gateway link — Imports

- [ ] Same on the Imports tab. Link reads **"See past imports (N) ⌄"**.
- [ ] Tap → See-all footer expands + auto-scrolls into view.
- [ ] For a brand-new user with no import history — pure "All clear — no imports yet" with no gateway link.

## Pull-to-refresh — Notifications

- [ ] Seed a user with 2 active notifications + some archived history. Open Notifications. Expand See-all.
- [ ] From outside the app, archive one of the user's active notifications server-side (e.g., by having a partner perform an action that resolves one).
- [ ] Pull down on the Notifications tab. Spinner rotates. After release: active list, see-all count, and See-all rows all refresh. Archived row appears in See-all.
- [ ] Collapse See-all, pull-to-refresh — same count update, no See-all row fetch wasted.

## Pull-to-refresh — Imports

- [ ] Same pattern on Imports. Expanding See-all then pulling refreshes page 1 without losing scroll of the active sections.

## A11y

- [ ] VoiceOver / TalkBack on: swiping to the gateway link, the label reads "See past notifications, 27 items, tap to expand" (or the imports equivalent).
- [ ] Keyboard nav: Tab focuses the link; Enter activates.

## No regression

- [ ] Bottom-nav bell badge still accurate.
- [ ] Tab switching preserves scroll on both tabs (PageStorageKey).
- [ ] Both footers still paginate + archive correctly (afh-3/4 coverage).
