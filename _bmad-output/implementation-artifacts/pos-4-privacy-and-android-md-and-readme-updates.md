# Story pos-4 — Privacy + ANDROID.md + README updates

**Status:** done
**Epic:** [epic-recime-positioning](../planning-artifacts/epic-recime-positioning.md)
**Source-of-truth copy:** [pos-1-content-copy-for-all-surfaces](pos-1-content-copy-for-all-surfaces.md)

## Goal

Strip every "v1 — reserved for future subscriptions / Play Billing"
hedge from operator-facing docs that future planners will read, and
add the canonical 100-word "Free forever" paragraph to `privacy.html`
so the App Store / Play Store reviewer reading the privacy URL during
review sees the commitment in the same document.

## Acceptance criteria

- [x] `app/web/privacy.html` — added new `<h2>10. Free forever</h2>`
  section with the canonical 100-word paragraph from pos-1; renumbered
  the existing "Contact" section to 11. Stripped "in the future,
  subscription billing" hedges from the Google Play + Apple App Store
  subprocessor entries in Section 3.
- [x] `ANDROID.md` Section 6 (Content rating, line ~468) — replaced
  the `(v1 — change to Yes when Play Billing ships)` qualifier on the
  "Digital purchases" row with `Palateful is free, no in-app purchases,
  and committed to staying that way`.
- [x] `ANDROID.md` Section 15 (Data Safety) — Block 8 (Play Billing):
  - Replaced the "skip Block 8 (Play Billing — reserved for future
    subscriptions)" hedge in the section preamble.
  - Removed the `v1 — Palateful is free` parenthetical on the
    `Collected:` line.
  - Rewrote the `Notes:` block to drop the "Flip to Yes once
    subscription entitlements ship" forecast, replacing with a
    cross-reference to the pos-6a grep guard.
- [x] `README.md` — no edit needed (greppped for pricing-related terms;
  no matches).
- [x] No forbidden strings outside negation contexts (the only hits in
  privacy.html and ANDROID.md after this story are negation-context —
  "no premium tier awaiting activation," "no in-app purchases,"
  "common paywall language" — all of which the pos-6a grep guard's
  allowlist will cover with rationale).
- [x] Privacy.html still validates as HTML5 (manual check: section
  numbers 1–11 sequential; Section 11 is the final pre-footer section).
- [x] Standalone QA walkthrough at `pos-4-qa-walkthrough.md`.

## File List

- `app/web/privacy.html` (4 edits: subprocessor hedge × 2, new Section
  10 added, Contact renumbered to 11)
- `ANDROID.md` (3 edits: Section 6 row, Section 15 preamble, Block 8
  body)
- `_bmad-output/implementation-artifacts/pos-4-privacy-and-android-md-and-readme-updates.md`
  (this file)
- `_bmad-output/implementation-artifacts/pos-4-qa-walkthrough.md` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip)

## Out of scope

- README.md edits — the file does not mention pricing today; the
  free-forever stance lives in the App Store / Play Store description
  (pos-1) and the in-app surfaces (pos-2). Adding a stance line to
  README would be marketing copy in a developer-facing file.
- Changing the Effective Date / Version of the privacy policy. The
  edit is non-substantive (positioning + hedges removed); the
  v1.0 + 18 April 2026 metadata stays. Material substance changes
  (data collection scope, retention, subprocessors) trigger a version
  bump; this round doesn't qualify.
- The privacy policy footer-meta line still reads "Privacy Policy v1.0"
  — that "v1.0" is a privacy-doc version number, NOT the "v1 product
  hedge" the epic targets. It stays.
