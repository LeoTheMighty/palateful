# QA walkthrough — Story pos-1 (positioning copy source-of-truth)

**What shipped:** the canonical copy for every Palateful free-forever
positioning surface — App Store / Play Store description body, in-app
"Why we're free" page text, privacy.html paragraph, and comparison table
(Palateful vs Recime / Recipe Notes / Mela on price + 6 capability rows
+ ads). Lives in
`_bmad-output/implementation-artifacts/pos-1-content-copy-for-all-surfaces.md`.
A separate citations sidecar lives at
`_bmad-output/planning-artifacts/pos-1-comparison-sources.md`. No code
changes — purely text artifacts that downstream stories pull from.

## Setup

No app build required. Open both files in your editor:
- `_bmad-output/implementation-artifacts/pos-1-content-copy-for-all-surfaces.md`
- `_bmad-output/planning-artifacts/pos-1-comparison-sources.md`

## Reviewer checklist (leonid@ac93.org)

- [ ] **Locked phrasing block** — read the three canonical lines. Confirm
  the abbreviated short form ("Free forever — unlimited.") fits a
  screenshot overlay at typical font sizes (≤30 chars).
- [ ] **App Store description (200 words)** — read aloud. Does the layered
  hook ("free AND pantry-aware AND household-native AND Meals-capable")
  come across in plain prose without sounding like marketing-bingo?
- [ ] **80-char Google Play short description** — count chars manually
  (`echo -n "..." | wc -c`) — should be ≤80.
- [ ] **In-app "Why we're free" (150 words)** — read aloud. Three
  paragraphs as written? Tone matches the rest of the app (plainspoken,
  no breathless marketing)?
- [ ] **privacy.html paragraph (100 words)** — fits within `<p>` tag,
  references the grep-guard CI commitment, doesn't introduce legal claims
  beyond the existing privacy policy scope.
- [ ] **Comparison table — 7 rows × 4 columns populated**:
  - Price, Import sources, Household sharing, Pantry, Meal planning,
    Shopping intelligence, Ads.
  - Every cell has a value (no "—" without a citation explaining why).
  - "Ads: None" appears for all four columns (frame-the-question goal).
- [ ] **Sidecar citations file** — every cell on the comparison-table has
  a corresponding row in `pos-1-comparison-sources.md` with a URL and a
  `retrieved: 2026-04-25` date.
- [ ] **Forbidden strings absent in Palateful's own copy** — `grep -nE
  'premium|paywall|subscription|upgrade|unlock|v1.*purchases'` against
  the story file should match only inside competitor-quote contexts (e.g.
  "Other recipe apps charge $39.99-$59.99/yr"), never as Palateful's
  own positioning. Run from repo root:
  ```bash
  grep -nE 'premium|paywall|subscription|upgrade|unlock' \
    _bmad-output/implementation-artifacts/pos-1-content-copy-for-all-surfaces.md
  ```
  Expected matches:
  - The "no premium tier — ever" line × 3 (canonical lines + privacy paragraph + Why-we're-free body) — these are negation contexts.
  - "subscription" mention in the Why-we're-free body's first sentence
    ("Most recipe apps charge a subscription") — also negation context.
  - The grep-guard's own forbidden-strings list mentioned in the
    privacy paragraph + Why-we're-free body.
  Anything else is a regression — fix before merging dependent stories.

## Acceptance gate

If any reviewer-checklist item fails, treat as a regression and update
this story file before unblocking pos-2 / pos-3 / pos-4 / pos-5 / pos-6a.
The grep guard from pos-6a will eventually enforce the forbidden-strings
contract automatically; until then this checklist is the gate.

## Out of scope (deliberately)

- Translations / localization — single-language for now.
- Image / icon assets — `pos-5` covers screenshots; tagline overlays use
  the abbreviated "Free forever — unlimited." line from the locked-phrasing
  block.
- Comparison table updates beyond the 4 competitors named — adding a 5th
  competitor is a fresh PR with a fresh sidecar row, not an edit here.
