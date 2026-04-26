# Story pos-2 — Frontend: Why-we're-free page + onboarding reassurance line

**Status:** done
**Epic:** [epic-recime-positioning](../planning-artifacts/epic-recime-positioning.md)
**Source-of-truth copy:** [pos-1-content-copy-for-all-surfaces](pos-1-content-copy-for-all-surfaces.md)

## Goal

Land two in-app surfaces:
1. A new `WhyWeAreFreePage` reachable from `Profile → About → Why we're
   free`, rendering the 150-word copy from pos-1 and a Palateful-vs-one-
   competitor comparison toggle (NOT a 4-column grid — unreadable on
   360-px Android per party-mode refinement).
2. A single subtle reassurance line under the existing "Your recipes,
   all in one place" subtitle on the onboarding welcome screen:
   "100% free, no ads, no premium tier — ever."

## Acceptance criteria

- [x] New widget `app/lib/features/about/why_we_are_free_page.dart`.
- [x] Reachable from `/profile/why-we-are-free` go-route, surfaced as a
  `Profile → About → Why we're free` tap target above where a privacy
  link would sit.
- [x] Comparison toggle uses tabs (`vs Recime`, `vs Recipe Notes`,
  `vs Mela`) with 7 rows × 2 columns, NOT a 4-column grid.
- [x] Onboarding welcome screen renders the canonical reassurance line
  with `bodySmall` style on `onSurfaceVariant` color, between the
  existing "Your recipes, all in one place" subtitle and the feature
  cards.
- [x] Widget tests for both surfaces; default-tab + tab-switch + 360-px
  no-overflow + 7-row label coverage.
- [x] Standalone QA walkthrough at
  `_bmad-output/implementation-artifacts/pos-2-qa-walkthrough.md`.

## File List

- `app/lib/features/about/why_we_are_free_page.dart` (new)
- `app/lib/features/onboarding/onboarding_welcome_screen.dart`
  (added reassurance line)
- `app/lib/features/profile/profile_screen.dart`
  (added "About" section with Why-we're-free tile)
- `app/lib/core/router/app_router.dart`
  (registered `/profile/why-we-are-free` route)
- `app/test/features/about/why_we_are_free_page_test.dart` (new — 7 tests)
- `app/test/features/onboarding/onboarding_welcome_reassurance_test.dart`
  (new — 2 tests)
- `_bmad-output/implementation-artifacts/pos-2-qa-walkthrough.md` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip)

## Implementation notes

- Each tab is a `SingleChildScrollView` with `IntroBody` + comparison
  rows. Earlier draft put `IntroBody` outside the tabs with the comparison
  in a `ListView.separated` Expanded — but the IntroBody crowded out the
  ListView's first rows on smaller viewports, so tests couldn't find the
  Price-row label. Moving everything into per-tab scrollables means the
  whole page scrolls together; user sees intro, scrolls to comparison.
- `_competitors` map is local to the file. If the comparison values drift,
  the source of truth is `pos-1-content-copy-for-all-surfaces.md` →
  re-sync this file from there.
- Forbidden-string note: the body intentionally says "premium," "subscription,"
  and "upgrade" in the **last paragraph** as quoted forbidden tokens, to
  make the grep-guard commitment visible to users. pos-6a's allowlist must
  cover this file.

## Out of scope

- Privacy-policy link in the About section: deferred to pos-4.
- "Donate" / one-time-payment CTA: not in this round (epic open question).
