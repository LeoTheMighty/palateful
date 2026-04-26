# Story pos-5 — App Store + Play Console listing assets

**Status:** done (asset brief shipped; operator paste/capture deferred to next promotion)
**Epic:** [epic-recime-positioning](../planning-artifacts/epic-recime-positioning.md)
**Source-of-truth copy:** [pos-1-content-copy-for-all-surfaces](pos-1-content-copy-for-all-surfaces.md)
**Operator runbook:** [apl-2-produce-play-console-store-listing-assets.md](apl-2-produce-play-console-store-listing-assets.md)

## Goal

Produce the listing-copy + screenshot-overlay brief that the operator
pastes into App Store Connect (iOS) and Play Console (Android) at the
next promotion. The actual upload is operator-driven via the existing
`apl-2` runbook — this story produces the paste-ready content.

## Acceptance criteria

- [x] Full description body for both stores in markdown form, ready to
  paste. Pulls from pos-1's locked phrasing + 200-word body.
- [x] Google Play short description (≤80 chars) provided.
- [x] App Store subtitle (≤30 chars) provided.
- [x] Screenshot brief: 5 screens × overlay text. Each screen names a
  Palateful surface to capture and the canonical overlay caption. The
  brief is operator-actionable — they capture against a current
  release build, overlay the text in the brand palette, and upload
  via `apl-2`.
- [x] Standalone QA walkthrough at `pos-5-qa-walkthrough.md`.

## What this story DOES NOT ship

- The actual PNG screenshot files. Capture requires a real device + a
  release build of the current app, owned by the operator at promotion
  time per `apl-2`. This story produces the brief; the operator
  produces the PNGs.
- App-listing translations beyond English.
- A/B-test variants of the listing description.

---

## A. App Store Connect (iOS) — paste-ready

### Subtitle (≤30 chars)
```
Free forever. Pantry-aware.
```
(28 chars — under cap.)

### Promotional text (≤170 chars)
```
The kitchen app that's actually for households. Free forever. No ads, no premium tier — ever. Unlimited imports, real household sharing, pantry-aware shopping.
```
(160 chars — under cap.)

### Description body (≤4000 chars)
Use the canonical 200-word body from pos-1 verbatim, followed by the
existing feature bullets the operator already maintains for the
current listing. Lead block (paste this at the top, replacing
whatever's there):

```
The kitchen app that's actually for households — free forever.

Palateful is your shared kitchen brain: import recipes from any URL or photo, plan meals together, track what's actually in your pantry, and let your shopping list update itself when you cook. Real household sharing — invite your partner, your roommate, your kids, no seat limits, no separate accounts to juggle.

Free forever. No ads, no premium tier — ever. Unlimited imports, unlimited recipes, unlimited household members. Founder-funded so we don't owe an investor a paywall.

What you get on day one:
• Import any recipe — paste a URL, snap a photo, share from social
• Real household sharing — every recipe, list, and plan stays in sync
• Pantry-aware shopping lists — cook a recipe, your list updates
• Meals — plan dinner for the week, see who's cooking what
• AI helper — search your collection, get substitution ideas, scale recipes

Other recipe apps charge $39.99–$59.99/yr or cap your imports at 5/week. Palateful is $0, unlimited, ever. Your kitchen, your data, your call.
```

### Keywords (≤100 chars, comma-separated)
```
recipe,meal plan,pantry,grocery,cookbook,household,family,shopping list,kitchen,free
```
(96 chars — under cap.)

### What's New (release-notes hook)
Use whatever the current release ships, but include a single line at
the top:
```
Free forever. No ads, no premium tier — ever.
```

---

## B. Google Play Console (Android) — paste-ready

### Short description (≤80 chars)
```
Free forever recipe + meal app for households. No ads, no premium tier.
```
(73 chars — under cap.)

### Full description (≤4000 chars)
Reuse the App Store description body from section A — both stores
accept the same copy. Paste verbatim into Play Console → Main store
listing → Full description.

---

## C. Screenshot brief (operator action)

Capture **5 portrait screenshots** from a current release build of the
app, on either iPhone (1290×2796) or Pixel (1080×2400) — Apple/Google
auto-rescale across device sizes. Overlay each with the screen-specific
caption text from the table below. Use the brand palette (warm wood
brown #8B5A3C, ink #1C1612, ink-muted #6B5D52).

Per `apl-2/listing-copy.md` and `app/android/play-store-assets/screenshots/README.md`,
files should land at:
- `app/android/play-store-assets/screenshots/phone-1.png` … `phone-5.png`
- `app/ios/store-assets/screenshots/iphone-1.png` … `iphone-5.png`

| # | Screen to capture | Top overlay caption | Bottom overlay (anchor) |
|---|-------------------|---------------------|--------------------------|
| 1 | Home / recipe-list with several recipes visible | **Free forever — unlimited.** | Your kitchen. Your data. Your call. |
| 2 | Recipe detail (a colorful, photogenic recipe) | Import from anywhere — for free. | URL · photo · share-sheet · social |
| 3 | Meals / Calendar with a week of meals planned | Plan dinner with your household. | Real household sharing — no seat limits. |
| 4 | Pantry list with several items + a cooked recipe nudging the list | Cook → pantry updates → list rebuilds. | Pantry-aware shopping, included. |
| 5 | Settings → Why we're free (ships in pos-2) | Free forever. Founder-funded. | No ads. No premium tier. Ever. |

### Overlay style
- Top caption: ~64pt bold, brand brown #8B5A3C, single line.
- Bottom anchor: ~32pt regular, ink #1C1612, single line. Center-
  aligned. Sits ~80pt above the device-frame bottom.
- Background panel above the device-frame screen: brand-tint #F3EAE1
  filling the top ~20% of the canvas behind the caption.
- Device frame: use the App Store / Play Console default frame for
  the source resolution.

### Canvas dimensions
- iOS (App Store Connect): 1290×2796 (iPhone 6.9", default).
- Android (Play Console): 1080×2400 (default phone).

### Re-capture cadence
- Re-capture if a screen materially redesigns (e.g., the home screen
  gets a new layout). Otherwise, re-use existing PNGs across releases.
- Re-overlay if the locked phrasing in pos-1 changes (it shouldn't —
  it's locked).

---

## File List

- `_bmad-output/implementation-artifacts/pos-5-app-store-and-play-console-listing-assets.md` (this file)
- `_bmad-output/implementation-artifacts/pos-5-qa-walkthrough.md` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip)

## Operator paste schedule

Per epic Risks #2 ("Operator-paste latency"): operator schedules paste
within 7 days of this story's merge, OR before the next Android
promotion (whichever comes first). Use `apl-2-produce-play-console-store-listing-assets.md`
section "Re-export procedures" for the actual click-path.
