# QA walkthrough — Story pos-2 (Why-we're-free page + onboarding line)

**What shipped:** an in-app `Why we're free` page reachable from
`Profile → About → Why we're free`, plus a subtle reassurance line
("100% free, no ads, no premium tier — ever.") under the existing
onboarding welcome subtitle.

## Setup

Recent local debug build (`flutter run` from `/app`) on iOS or Android.
For onboarding, sign in on a fresh account to reach the welcome screen
(or hot-restart with `has_completed_onboarding=false` for that user).

## Onboarding reassurance line

- [ ] Sign in fresh, land on `/onboarding/welcome`.
- [ ] Below the "Your recipes, all in one place" subtitle, a smaller
  caption reads exactly `100% free, no ads, no premium tier — ever.`
  in `onSurfaceVariant` color.
- [ ] On a 360-px-wide device (e.g. small Android), the line stays on a
  single row (or wraps cleanly without overflow). No red/yellow strip
  in dev mode.
- [ ] The line does not push the name input below the fold on a
  reasonable-sized phone (use the viewport-overflow test as the gate).

## Why-we're-free page

- [ ] `Profile` tab → scroll to **About** section. A tile labelled
  "Why we're free" with subtitle "Founder-funded, no premium tier — ever"
  appears above the existing Account section.
- [ ] Tap it. The route is `/profile/why-we-are-free`.
- [ ] AppBar title: `Why we're free`. AppBar bottom shows three tabs:
  `vs Recime`, `vs Recipe Notes`, `vs Mela`.
- [ ] Default tab is `vs Recime`. Body shows:
  - 4 paragraphs of intro copy (founder-funded story).
  - A divider.
  - Two header cells: `Palateful` (filled with primaryContainer color)
    and `Recime` (filled with surfaceContainerHighest).
  - 7 comparison rows: Price, Import sources, Household sharing,
    Pantry tracking, Meal planning, Shopping intelligence, Ads.
  - Price row: Palateful = `Free forever`, Recime = `$39.99–$59.99/yr`.
- [ ] Tap `vs Recipe Notes`. Right column header changes to
  `Recipe Notes`. Price cell now shows `Free` (matches sidecar).
- [ ] Tap `vs Mela`. Right column header changes to `Mela`. Price cell
  shows `$4.99 one-time (iOS)`.
- [ ] All three tabs share the same intro paragraphs (each tab is its
  own scroll view; switching tabs scrolls back to top).
- [ ] On a 360-px-wide viewport: no overflow warnings. Text wraps in
  the comparison cells. Tabs are scrollable (`isScrollable: true`).

## Per-tab visual sanity

- [ ] Dark theme: header cells contrast cleanly against the dark
  surface; `Palateful` cell uses primaryContainer + onPrimaryContainer
  text; competitor cell uses surfaceContainerHighest.
- [ ] Light theme: same — primary container is brand-tinted, competitor
  is neutral.

## Forbidden-strings sanity

- [ ] In the body of the page (last intro paragraph), the words
  "premium," "subscription," and "upgrade" appear as **quoted forbidden
  tokens** — Palateful's commitment is meta-text *about* what we
  forbid, not Palateful copy that uses those tokens unironically. This
  is intentional. pos-6a's grep-guard allowlist must cover this file.

## Regression checks

- [ ] Existing onboarding flow (name → notifications → start) still
  works end to end.
- [ ] Profile screen renders all sections in order: Edit Profile,
  Recipes, Appearance, Settings, **About** (new), Account.
- [ ] Logout button in Account section still shows error-colored.

## Out of scope

- Privacy policy link in the About section — deferred to pos-4.
- Web rendering of the comparison table — pos-3 owns that with full
  4-column layout (web viewport > 1024px).

## Acceptance gate

If any checkbox above fails on a real device, treat as a regression and
fix in this story file's File List before merging dependent stories.
