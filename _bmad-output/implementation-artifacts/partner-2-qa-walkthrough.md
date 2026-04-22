# QA Walkthrough — partner-2

Manual smoke to run with Leo + Sarah test accounts on iOS after the
build lands. All steps assume Leo owns the shared book.

## Setup

- [ ] Sarah is a member of shared book "Weeknight Dinners" (Leo is owner).
- [ ] Both have push tokens registered and `partner_activity` enabled.

## Flow A — Sarah forks Leo's recipe

1. [ ] Sarah opens Leo's "Sweet Potato Quiche" in Weeknight Dinners.
2. [ ] Sarah forks it to her own book "Sarah's Recipes".
3. [ ] Leo's phone buzzes within ~5s with:
       - title: `🔱 Sarah forked your Sweet Potato Quiche`
       - body:  `They saved it to Sarah's Recipes.`
       - image: the recipe cover (if `image_url` was set).
4. [ ] Tapping the notification will open Sarah's forked copy (handled
       by partner-5; verify once that story lands).

## Flow A-self — Leo forks his own recipe

1. [ ] Leo forks his own recipe into another book he owns.
2. [ ] No push arrives (self-fork silent).

## Flow B — Sarah notes Leo's recipe (shared book)

1. [ ] Sarah opens the recipe and adds the note:
       `Add more cinnamon next time, was a hit.`
2. [ ] Leo's phone receives:
       - title: `Sarah noted your Sweet Potato Quiche 📝`
       - body:  `Sarah: "Add more cinnamon next time, was a hit."`
3. [ ] Notification image: recipe cover when present.

## Flow B-long — Sarah notes Leo's recipe with a 200-char note

1. [ ] Sarah adds a note with >150 chars.
2. [ ] Leo's push body shows the first ~120 chars followed by an
       ellipsis (`…`).

## Flow B-solo — Sarah forks + notes her fresh copy (solo book)

1. [ ] Sarah forks the recipe to Sarah's Recipes (a solo book) and
       adds a note on her copy.
2. [ ] Leo gets **no** notification (book is not shared).

## Flow B-self — Leo notes his own recipe

1. [ ] Leo notes his own recipe in Weeknight Dinners.
2. [ ] No push arrives (self-note silent).

## Prefs / quiet hours

- [ ] Turn Leo's `partner_activity` off in settings. Sarah forks
      → no push. Turn it back on; re-test.
- [ ] During Leo's quiet hours: push arrives is **suppressed** (fires
      again when window ends; verify via logs).

## Automated checklist

- [x] `npx nx run api:lint` passes.
- [x] `cd services/api && pytest tests/test_recipe_book_notifications.py`
      — 28 passed.
- [x] `cd libraries/utils && pytest` — 428 passed (regression check).
