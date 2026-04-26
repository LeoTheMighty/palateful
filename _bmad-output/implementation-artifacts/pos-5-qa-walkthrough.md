# QA walkthrough — Story pos-5 (store-listing assets brief)

**What shipped:** the paste-ready App Store + Google Play listing copy
and a 5-screen screenshot-overlay brief, both in
`pos-5-app-store-and-play-console-listing-assets.md`. This story does
NOT ship PNG screenshot files — the operator captures and uploads
those via the existing `apl-2` runbook at the next Android promotion.

## Setup

Open the story file:
`_bmad-output/implementation-artifacts/pos-5-app-store-and-play-console-listing-assets.md`

Optional: open the source-of-truth copy
(`pos-1-content-copy-for-all-surfaces.md`) and the apl-2 runbook
(`apl-2-produce-play-console-store-listing-assets.md`) side-by-side
for cross-referencing.

## Reviewer checklist

### Section A: App Store Connect copy
- [ ] Subtitle ≤30 chars (count manually: `echo -n "Free forever.
  Pantry-aware." | wc -c` → 28). Confirm "28" ≤ 30.
- [ ] Promotional text ≤170 chars. Confirm count.
- [ ] Description body lead block byte-identical to the canonical
  200-word body in pos-1.
- [ ] Keywords list ≤100 chars including commas.
- [ ] "What's New" hook line is the canonical tagline.

### Section B: Google Play copy
- [ ] Short description ≤80 chars (count: 73 expected).
- [ ] Full description = same body as App Store (no divergence).

### Section C: Screenshot brief
- [ ] 5 rows in the table, each naming an existing in-app surface
  (Home, Recipe detail, Meals, Pantry, Why-we're-free).
- [ ] Screen #5 (Why-we're-free) references a surface that ships in
  pos-2 — confirm pos-2 is merged before the operator captures.
- [ ] Each row's top caption is in the canonical phrasing family
  (variations are fine for screenshot brevity, but the meaning must
  match — "Free forever — unlimited.", etc.).
- [ ] Brand palette colors specified (#8B5A3C wood, #1C1612 ink,
  #F3EAE1 brand-tint, #6B5D52 ink-muted). Match the values in
  `app/web-landing/styles.css` (pos-3) so web + store assets stay
  visually coherent.
- [ ] Canvas dimensions named for both iOS (1290×2796) and Android
  (1080×2400).
- [ ] File-path conventions match `app/android/play-store-assets/screenshots/`
  + `app/ios/store-assets/screenshots/` per the apl-2 runbook.

### Forbidden-strings sanity sweep
- [ ] Run from repo root:
  ```bash
  grep -nE "premium|paywall|subscription|upgrade|unlock" \
    _bmad-output/implementation-artifacts/pos-5-app-store-and-play-console-listing-assets.md
  ```
- [ ] All matches must be in negation contexts (e.g. "no premium tier
  — ever," "no ads, no premium tier"). Confirm row-by-row that no
  affirmative usage slipped in.

## Acceptance gate

If any checkbox above fails, fix in the story file before unblocking
the operator paste.

## Out of scope (operator action)

- Capturing the 5 PNG screenshots, overlaying brand text, and
  uploading via apl-2. This is intentionally not in this autonomous
  loop's scope — operator does it from a real device against a release
  build.
- Localized listings (Spanish, French, etc.). Single-language for now.
- A/B-test variants of the description. Single-variant for now.
