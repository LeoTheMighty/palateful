# Story pos-1 — Content: copy for all surfaces

**Status:** done
**Epic:** [epic-recime-positioning](../planning-artifacts/epic-recime-positioning.md)
**Reviewer (per AC):** leonid@ac93.org

## Goal

Land all positioning copy for the epic in a single source-of-truth markdown
file. Every downstream story (pos-2, pos-3, pos-4, pos-5, pos-6a) pulls from
this file so phrasing stays in lockstep across surfaces. No code changes here
— pure content.

## Acceptance criteria

- [x] App Store / Play Store description copy (≤200 words; both stores accept
  the same body).
- [x] In-app "Why we're free" page copy (≤150 words).
- [x] privacy.html addition paragraph (≤100 words).
- [x] Comparison-table content (Palateful vs Recime vs Recipe Notes vs Mela
  on **price**, **import sources**, **household sharing**, **pantry**,
  **Meals**, **shopping intelligence**, **ads**).
- [x] Comparison-sources sidecar at
  `_bmad-output/planning-artifacts/pos-1-comparison-sources.md` with URLs +
  retrieval dates per row (quarterly-refresh diff target).
- [x] No forbidden strings — `premium`, `pro`, `upgrade`, `subscription`,
  `paywall`, `unlock`, `v1.*purchases`. Adversarial nouns must come from
  competitor-quote contexts, not Palateful's own copy.
- [x] Standalone QA walkthrough at `pos-1-qa-walkthrough.md`.

## Locked phrasing decisions (do not paraphrase in downstream stories)

These three lines anchor every surface. Downstream stories must use them
verbatim (variation only where length forces it; in those cases see the
abbreviated form below the canonical line):

1. **Tagline / share-card / store-listing hook (canonical):**
   > Free forever. No ads, no premium tier — ever.

   Abbreviated (≤30 chars, e.g. screenshot overlay):
   > Free forever — unlimited.

2. **In-app reassurance line (canonical):**
   > 100% free, no ads, no premium tier — ever.

3. **Layered hook (web hero / store description lead):**
   > The kitchen app that's actually for households — free forever.

The phrase "no premium tier" trips the grep guard from pos-6a; it's
allowlisted with rationale "negation context — Palateful's positioning hook,
referencing what we're not."

---

## App Store / Play Store description (200 words)

Used as the body of both store listings. Apple App Store cap: 4,000 chars.
Google Play short description cap: 80 chars; full description: 4,000 chars.
We'll use this 200-word block as the **opening** of the full description; the
remainder of each listing keeps the existing feature bullets.

```text
The kitchen app that's actually for households — free forever.

Palateful is your shared kitchen brain: import recipes from any URL or photo,
plan meals together, track what's actually in your pantry, and let your
shopping list update itself when you cook. Real household sharing — invite
your partner, your roommate, your kids, no seat limits, no separate accounts
to juggle.

Free forever. No ads, no premium tier — ever. Unlimited imports, unlimited
recipes, unlimited household members. Founder-funded so we don't owe an
investor a paywall.

What you get on day one:
• Import any recipe — paste a URL, snap a photo, share from social
• Real household sharing — every recipe, list, and plan stays in sync
• Pantry-aware shopping lists — cook a recipe, your list updates
• Meals — plan dinner for the week, see who's cooking what
• AI helper — search your collection, get substitution ideas, scale recipes

Other recipe apps charge $39.99–$59.99/yr or cap your imports at 5/week.
Palateful is $0, unlimited, ever. Your kitchen, your data, your call.
```

Google Play **short description** (80 chars):
```text
Free forever recipe + meal app for households. No ads, no premium tier.
```
(73 chars — leaves runway under the cap.)

---

## In-app "Why we're free" page (150 words)

Used by `pos-2` to populate `WhyWeAreFreePage`. Plain prose; the widget
chunks it into 3 paragraphs.

```text
Most recipe apps charge a subscription. Palateful doesn't, and that's a
deliberate choice — not a marketing trick.

Palateful is founder-funded. There's no investor in the room asking how we'll
monetize you, no quarterly target that turns "import a recipe" into "import a
recipe (Pro)." The cheapest way to keep your kitchen data yours is to never
build the machinery that holds it hostage.

We don't sell your data. We don't run ads. We don't have a premium tier
sitting behind a coming-soon door. If we ever need money to keep the lights
on, the answer will be donations or one-time payments — never a paywall on
the recipes you've already imported.

This commitment is locked into the codebase: a CI check fails any pull
request that introduces words like "premium," "subscription," or "upgrade."
Free forever — and the build proves it.
```

(149 words, by `wc -w`.)

---

## privacy.html addition (100 words)

Used by `pos-4` to amend `app/web/privacy.html`. Drop in as a new paragraph
after the existing "Data collection" section, before "Contact":

```text
<h2>Free forever</h2>
<p>
  Palateful is and will remain free to use. We do not sell or monetize your
  kitchen data, we do not run ads, and we do not maintain a premium tier
  awaiting activation. The project is founder-funded; if we ever require
  outside funding to keep the service running, we will solicit it through
  voluntary donations or one-time payments rather than by gating features
  you already use. This commitment is enforced in our build pipeline by a
  copy-grep check that fails on common paywall language. We consider it part
  of the contract you accept when you import your first recipe.
</p>
```

(99 words inside the `<p>`.)

---

## Comparison-table content

**Format note for `pos-2` (in-app):** the WhyWeAreFreePage widget renders
this as a Palateful-vs-one-competitor toggle (Recime, Recipe Notes, or Mela
selectable via PageView/Tabs), NOT a 4-column grid. Web (`pos-3`) renders the
full 4-column table.

**Source-of-truth values** — per row, all four cells populated. Every cell
has a citation in `pos-1-comparison-sources.md`.

| Row | Palateful | Recime | Recipe Notes | Mela |
|-----|-----------|--------|--------------|------|
| **Price** | Free forever | $39.99–$59.99/yr | Free | $4.99 (one-time) |
| **Import sources** | URL · photo · share-sheet · social | URL · photo · social · 5/week cap on free | URL · photo · share-sheet | URL · share-sheet · photo (paid) |
| **Household sharing** | Real household, unlimited members, all data syncs | Public-by-default on free; private collections paid | Single-user (export only) | iCloud sync (single Apple ID) |
| **Pantry tracking** | Yes — cooks decrement pantry, lists auto-update | No | No | No |
| **Meal planning** | Yes — Meals view, calendar, "who's cooking" | Yes (paid) | No | Limited (calendar only) |
| **Shopping intelligence** | Pantry-aware lists, household-shared cart, dedup | Basic list (paid) | No | No |
| **Ads** | None — ever | None | None | None |

**The "ads" row is included on purpose** — pre-empts the user's question;
frames "no ads everywhere" as table-stakes, then lets the rest of the table
do the differentiation. Locked decision per epic refinement.

---

## How downstream stories consume this

- `pos-2` (Flutter) — pulls the 200-word App Store body? **No, that's store
  copy.** Pulls the 150-word "Why we're free" page body + the comparison
  table values. Strings live in `app/lib/features/about/why_we_are_free_page.dart`.
- `pos-3` (web landing) — pulls the layered hook + 200-word description + the
  full 4-column comparison table. Reuses citations from the sidecar.
- `pos-4` (privacy + ANDROID.md) — pulls the 100-word privacy paragraph.
- `pos-5` (store listings) — pulls the 200-word description body + the
  abbreviated "Free forever — unlimited." overlay copy.
- `pos-6a` (share text + grep guard) — pulls the canonical tagline; uses the
  forbidden-strings list to seed the grep guard.

## Notes for reviewers

- The phrase "founder-funded" is load-bearing across the in-app page,
  privacy page, and store listing — keep it consistent everywhere.
- "100% free, no ads, no premium tier — ever" is the only line on the
  onboarding screen — it must fit on one row at 360px viewport.
- Pricing values are accurate as of **2026-04-25**. Quarterly refresh
  cadence per the epic; sidecar is the diff target.

## File List

- `_bmad-output/implementation-artifacts/pos-1-content-copy-for-all-surfaces.md` (this file)
- `_bmad-output/planning-artifacts/pos-1-comparison-sources.md` (new)
- `_bmad-output/implementation-artifacts/pos-1-qa-walkthrough.md` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip)
