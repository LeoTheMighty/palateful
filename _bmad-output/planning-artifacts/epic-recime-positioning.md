<!-- draft: pre-party-mode -->
# Epic: Recime Positioning — Lock In "Free Forever"

## Overview

Weaponize Palateful's free-forever commitment as the dominant positioning hook against Recime ($39.99–$59.99/yr, 5 imports/week limit, public-by-default free tier) and Recipe Notes (the new free competitor). Differentiation message is layered: "we're free **AND** pantry-aware **AND** household-native **AND** Meals-capable" — not just "we're free." Update every user-facing pricing surface (App Store, Play Store, web landing, in-app onboarding, privacy policy, share cards), strip the "v1" qualifier from `ANDROID.md`, and ship a public comparison table.

## Goal

Lock the free-forever commitment in copy AND in the product's surface area so that no future planner — human or agentic — can quietly reintroduce paywall language without an explicit user decision. Convert Recime's billing-complaint backlash + Recime's growing review backlash on the v5.0 rebrand into Palateful installs.

## End-user flow

1. **Discovery (App Store / Play Store)** — Prospective user reads the listing description: "Free forever. No paywalls, no ads, no premium tier — ever. Unlimited imports, unlimited recipes, real household sharing." Comparison line: "Recime: $39.99–$59.99/yr or 5 imports/week. Palateful: $0, unlimited, ever."
2. **Web landing (`palateful.app`)** — Lands on a real public page (replacing today's empty Flutter web shell), sees a hero "The kitchen app that's actually for households — free forever," scrolls to a 4-column comparison table (Palateful vs Recime vs Recipe Notes vs Mela), taps a download CTA → App Store / Play Store.
3. **In-app onboarding** — First app open, the welcome screen carries a single subtle reassurance line below the title: "100% free, no ads, no premium tier — ever." Doesn't take over the screen; placed where it can be skimmed.
4. **In-app "Why we're free"** — Discoverable from Settings → About → "Why we're free." Static page (~150 words) explains: founder-funded, no investor pressure to monetize, your kitchen data is yours, free forever.
5. **Privacy policy** — Reaffirms "We do not sell or monetize your data, and we're committed to keeping Palateful free indefinitely."
6. **Sharing** — When users share a recipe via the existing share-recipe card flow, the card includes "Get Palateful — free forever" tagline.

## Frontend changes

- `app/lib/features/onboarding/onboarding_welcome_screen.dart` — add single reassurance line below the title. Style: small caption, secondary color. No new screen, no new flow.
- New widget `app/lib/features/about/why_we_are_free_page.dart` — static-content scrollable page with curated copy + a small comparison snippet (Palateful vs Recime vs Recipe Notes top-row only, full table on web).
- `app/lib/features/profile/settings_screen.dart` (or wherever Settings → About lives) — add "Why we're free" tap target above the existing privacy policy link.
- `app/lib/features/sharing/recipe_share_card.dart` (or equivalent share-card builder) — append "Get Palateful — free forever" tagline at the bottom of share-card images.
- App Store screenshot designs (4-5 captures) overlaid with "Free forever — unlimited" text. Story `pos-5` produces the operator brief; the operator captures + uploads via the existing `apl-2` runbook.

## Backend changes

None. Pure content / copy / static-page work. No new endpoints, no schema changes, no API contract changes.

## Infrastructure changes

- **Web landing page** — Replace the empty Flutter web shell at `palateful.app` root with a real static landing page (HTML + a small CSS file, no framework). Deployed via the existing Cloudflare Pages setup. The Flutter web app moves to `palateful.app/app` (or stays under a different subpath; confirm in story `pos-3`). Comparison-table content is a server-rendered HTML table; quarterly refresh cycle owned by the operator.
- **Privacy page** — Edit `app/web/privacy.html` to add the free-forever affirmation paragraph.
- **`ANDROID.md` Section 6 (Data Safety)** — Strip the "v1 — Palateful is free, no in-app purchases" hedge. Replace with "Palateful is free, no in-app purchases — and committed to staying that way." Future operators reading `ANDROID.md` get the locked-in stance.
- **App Store Connect / Play Console listings** — Operator updates description copy + uploads new screenshots via the existing `apl-2` runbook. No new infra.

## Initial design principles (from research; party-mode TBD)

- **No "v1" qualifiers anywhere in user-facing copy.** Lock-in is the point. Future monetization, if ever pursued, must be donations / one-time / non-paywall.
- **Layered hook, not single-point.** The full message is "free AND pantry-aware AND household-native AND Meals-capable" — Recipe Notes occupies the bare-free position; Palateful wins on capability stack.
- **Quote Recime's complaints, don't attack Recime.** Comparison table is factual, not snide. Lead with Palateful's strengths, position Recime's weaknesses as table-stakes gaps.
- **No premium / pro / upgrade / unlock language anywhere.** If a future story discovers it needs to gate something, the gate must be removed (or feature cut) — not a paywall added. CI grep guard catches regressions.

## File structure (anticipated)

```
app/lib/features/
  onboarding/onboarding_welcome_screen.dart      # add reassurance line
  about/why_we_are_free_page.dart                # NEW static page
  profile/settings_screen.dart                   # add Settings link
  sharing/recipe_share_card.dart                 # append tagline

app/web/
  index.html                                     # NEW landing (replaces Flutter shell at root)
  styles.css                                     # NEW landing styles
  privacy.html                                   # add free-forever affirmation paragraph

ANDROID.md                                       # strip "v1" qualifier from Section 6
README.md                                        # optional: add free-forever line in description

tools/
  copy-grep-guard.sh                             # NEW CI check for "premium|pro|upgrade|subscription|v1.*purchases"

_bmad-output/implementation-artifacts/
  pos-1-content-copy.md
  pos-2-frontend-why-we-are-free-page.md
  pos-3-web-landing-page.md
  pos-4-privacy-and-android-md-updates.md
  pos-5-app-store-screenshots-and-listing-copy.md
  pos-6-share-card-tagline-and-grep-guard.md
```

## Story list

- **pos-1 — Content: copy for all surfaces.** Write 200-word App Store / Play Store description, 150-word in-app "Why we're free" page, 100-word privacy.html addition, comparison-table content (Palateful vs Recime vs Recipe Notes vs Mela on price + import sources + household + pantry + Meals + shopping intelligence + ads). All copy lives in this story file as the source of truth; downstream stories pull from it. **AC:** all five surfaces have approved copy in markdown; comparison table values are factually verifiable as of 2026-04-25 with citations.
- **pos-2 — Frontend: in-app "Why we're free" page + onboarding line.** New `WhyWeAreFreePage` widget with content from `pos-1`. Settings → About → tap target above privacy link. Onboarding welcome screen gets the single reassurance line. **AC:** new page reachable from Settings; onboarding renders the line; widget tests cover both; no overflow on small screens.
- **pos-3 — Web: real landing page replacing the empty Flutter shell.** Static HTML + CSS deployed via Cloudflare Pages. Hero with `pos-1` content, comparison table, App Store + Play Store CTAs, footer link to privacy. Flutter web app continues to work (under `/app` if needed). **AC:** `palateful.app` shows the new landing; `palateful.app/app` (or the existing subpath) still loads the Flutter app; lighthouse score ≥ 95 on performance + accessibility; comparison table renders on mobile.
- **pos-4 — Privacy + ANDROID.md updates.** Edit `app/web/privacy.html` with the free-forever paragraph from `pos-1`. Edit `ANDROID.md` Section 6 to strip the "v1" qualifier. Edit README.md description line if it mentions pricing. **AC:** all three files updated; privacy.html still validates as valid HTML; ANDROID.md still operator-readable.
- **pos-5 — App Store + Play Console listing assets.** Produce 4-5 screenshots with "Free forever" overlay text in the brand color palette. Update App Store Connect + Play Console descriptions with `pos-1` copy. Operator-driven via the existing `apl-2` runbook; this story produces the brief + the screenshot set + the description copy ready to paste. **AC:** screenshot files exist in `app/android/play-store-assets/` and `app/ios/store-assets/` (or equivalent); listing-copy markdown ready for operator paste; operator paste happens (or scheduled) before the next Android promotion.
- **pos-6 — Share-card tagline + CI grep guard for paywall regressions.** Append "Get Palateful — free forever" tagline to share-recipe card builder. Add `tools/copy-grep-guard.sh` that scans `apps/flutter/lib/`, `app/web/`, `ANDROID.md`, `README.md`, and `_bmad-output/planning-artifacts/` for forbidden strings (`premium`, `pro`, `upgrade`, `subscription`, `v1 — .* purchases`, `paywall`); fails CI if any non-allowlisted match. Allowlist file at `tools/copy-grep-allowlist.txt` (e.g., `pro` in technical contexts like "production"). **AC:** tagline visible on test share-card render; grep guard passes on current codebase; deliberate test regression triggers a CI failure.

## Dependencies

- **None** for the epic as a whole. Internal: `pos-1` blocks `pos-2`, `pos-3`, `pos-4`, `pos-5`, `pos-6`. The other five can run in parallel after `pos-1` lands.
- **Blocks:** all four other Recime-related epics (`epic-social-video-import`, `epic-pantry-cook-with-what-you-have`, `epic-recime-mass-import`, `epic-nutrition-auto-calc`) must honor the free-forever copy bar enforced by the grep guard from `pos-6`.

## Open questions for the user

- **Web landing — single-page or multi-page?** Default is single-page hero + comparison + footer. If a multi-page site (with feature pages, blog) is desired, scope expands to a static-site generator decision (Astro / 11ty / hand-rolled).
- **Domain for the Flutter web app post-relocation.** Default: `palateful.app/app` keeps it under the same domain. Alternative: `app.palateful.app` subdomain — cleaner separation but needs a new Cloudflare Pages config + DNS update. Pick at story `pos-3`.
- **Comparison table refresh cadence.** Default: quarterly + when a competitor materially changes positioning. If the operator wants more / less frequent, adjust the FR-COMP-2 commitment.
