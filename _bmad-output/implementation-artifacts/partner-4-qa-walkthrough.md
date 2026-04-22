# QA Walkthrough — partner-4

## Setup

- [ ] Leo creates a meal event "Saturday brunch" and invites Sarah.
- [ ] Sarah has push tokens + `partner_activity` enabled.

## Flow E-accept — Sarah accepts

1. [ ] Sarah opens the invite, taps **Accept**.
2. [ ] Leo's phone receives:
       - title: `🥞 Sarah's coming to Saturday brunch!`
       - body:  `They just RSVP'd yes.`
       - image: attached recipe cover (when event has `recipe.image_url`).
3. [ ] Tapping the push lands on `/calendar/meals/{meal_event_id}`
       (deep-link handled by Epic A; verify during partner-5 QA).

## Flow E-decline — Sarah declines

1. [ ] Sarah opens the invite, taps **Decline**.
2. [ ] Leo's phone receives:
       - title: `Sarah can't make Saturday brunch`
       - body:  `Tap to swap recipes if needed.`

## Flow E-maybe — Sarah marks maybe

1. [ ] Sarah opens the invite, taps **Maybe**.
2. [ ] Leo's phone receives:
       - title: `Sarah might join Saturday brunch`
       - body:  `They marked themselves as a maybe.`

## Flow E-self — Leo RSVPs his own event

1. [ ] Leo RSVPs to his own event (some flows allow owner as a
       participant row).
2. [ ] No push arrives (owner-self-RSVP silent).

## Prefs / quiet hours

- [ ] Leo with `partner_activity=false`: Sarah's RSVP → no push.
- [ ] Quiet hours active: push suppressed.

## Automated checklist

- [x] `npx nx run api:lint` passes.
- [x] `poetry run pytest tests/test_meal_event.py -k TestNotifyMealEvent`
      — 24 passed (including 5 new for this story).
- [x] `poetry run pytest libraries/utils/test/` — 436 passed.
