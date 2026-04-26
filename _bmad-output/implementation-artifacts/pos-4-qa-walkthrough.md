# QA walkthrough — Story pos-4 (privacy + ANDROID.md edits)

**What shipped:** the canonical "Free forever" paragraph as a new
Section 10 in `app/web/privacy.html` (Contact renumbered to 11), and
three "v1 — future subscription" qualifiers stripped from `ANDROID.md`
(Section 6 Content rating row, Section 15 preamble, Section 15 Block
8 body). README.md unchanged.

## Setup

No build needed. Open the three files:
- `app/web/privacy.html`
- `ANDROID.md`
- `_bmad-output/implementation-artifacts/pos-1-content-copy-for-all-surfaces.md`
  (for canonical-paragraph cross-check)

## Reviewer checklist

### privacy.html
- [ ] Section numbering goes 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 — no
  gaps, no duplicates.
  ```bash
  grep -nE "^  <h2>[0-9]+\." app/web/privacy.html
  ```
- [ ] Section 10 is "Free forever" — the canonical paragraph from
  pos-1, copied verbatim. Spot-check phrase "founder-funded; if we
  ever require outside funding" appears.
- [ ] Section 11 is "Contact" (was 10 before this story). Email link
  intact.
- [ ] Footer meta reads "Privacy Policy v1.0" — that's the privacy-
  doc version number, intentionally untouched (not a paywall hedge).
- [ ] Section 3 Google Play + Apple App Store subprocessor entries no
  longer mention "in the future, subscription billing." They now read
  "store distribution. Receives only the data Google Play / Apple
  App Store collects as part of its store APIs (device identifier)."
- [ ] HTML still validates: open the file in a browser, view-source,
  check no console errors. (Easier alt: run an HTML linter if
  available — file is hand-written so unlikely to drift.)

### ANDROID.md Section 6 (Content rating)
- [ ] Row "Digital purchases" reads exactly:
  > **No** — Palateful is free, no in-app purchases, and committed
  > to staying that way
- [ ] No leftover `(v1 — change to Yes when Play Billing ships)`
  text on this row.

### ANDROID.md Section 15 preamble (~line 479)
- [ ] Reads "You can skip Block 8 (Play Billing — Palateful is free,
  no in-app purchases, and committed to staying that way); the form
  accepts 'not currently collected' for that data type."
- [ ] No leftover "for v1 you can skip" / "reserved for future
  subscriptions" text.

### ANDROID.md Section 15 Block 8 body
- [ ] `Collected:` line reads: `No (Palateful is free, no in-app
  purchases — and committed to staying that way)`. **No `v1 —`
  parenthetical.**
- [ ] `Notes:` block ends with the cross-reference to pos-6a's grep
  guard, NOT with "Flip Collected to Yes once subscription
  entitlements ship via Play Billing."
- [ ] `Purpose(s):` reads `N/A` (was `App functionality + Fraud
  prevention (when enabled)` — that's contingent-on-future-billing
  language, also stripped).

### Forbidden-strings sanity sweep
- [ ] Run from repo root:
  ```bash
  grep -nE "v1 — Palateful|future subscription|Flip .* to Yes" \
    ANDROID.md app/web/privacy.html
  ```
  Expected: zero matches.
- [ ] Run:
  ```bash
  grep -nE "premium|paywall|subscription|upgrade" \
    ANDROID.md app/web/privacy.html
  ```
  Expected matches are all in negation contexts:
  - privacy.html Section 10 — "no premium tier awaiting activation,"
    "common paywall language."
  - That's it. ANDROID.md should have zero matches after this story.

### Cross-document consistency
- [ ] privacy.html Section 10 paragraph is byte-identical to the
  canonical paragraph in `pos-1-content-copy-for-all-surfaces.md`
  (modulo the surrounding `<p>` tag). Re-paste from pos-1 if drift is
  detected.

## Acceptance gate

Forbidden-strings sweep + section-numbering check + cross-document
consistency. If any fails, fix in this story file's File List before
merging dependent stories. pos-6a's grep guard will eventually enforce
the forbidden-strings contract automatically.

## Out of scope

- App-bundle screenshots overlay text — pos-5 owns that.
- README.md edits — the file does not mention pricing today.
- Privacy doc version bump — the edit is non-substantive (no change
  to data collection scope), so v1.0 / 18 April 2026 stays.
