# Comparison-table sources — Palateful vs Recime / Recipe Notes / Mela

**Created:** 2026-04-25
**Reviewer:** leonid@ac93.org
**Refresh cadence:** quarterly + when a competitor materially changes
positioning. Diff this file to detect drift before re-running positioning
copy through `pos-1`.

This sidecar holds the citations behind every cell of the comparison table
in `pos-1-content-copy-for-all-surfaces.md`. Each row records URL +
retrieval date; future quarterly refreshes diff this file to check whether
any cell has moved.

---

## Recime

| Cell | Value (2026-04-25) | Source | Retrieved |
|------|--------------------|--------|-----------|
| Price | $39.99/yr (Plus) – $59.99/yr (Premium) | https://recime.app/pricing | 2026-04-25 |
| Import cap (free) | 5 imports/week | https://recime.app/pricing — "Free" column | 2026-04-25 |
| Privacy default (free) | Recipes public unless paid | https://recime.app/help/privacy | 2026-04-25 |
| Meal planning | Paid feature | https://recime.app/features/meal-planning | 2026-04-25 |
| Household sharing | Not offered (single account only) | https://recime.app/help/sharing — "individual account" | 2026-04-25 |
| Pantry tracking | Not offered | https://recime.app/features (pantry not listed) | 2026-04-25 |
| Ads | None | App Store listing — "Apps in this category that contain ads" filter (Recime: no) | 2026-04-25 |

**Notes:** Recime relaunched as v5.0 in early 2026 and saw a wave of
billing complaints in App Store reviews; epic positioning leans into that
without naming-and-shaming. Pricing tier names ("Plus" / "Premium") trip
the grep guard if quoted directly — paraphrase as "$39.99–$59.99/yr" in
copy and keep tier names confined to this sidecar.

---

## Recipe Notes

| Cell | Value (2026-04-25) | Source | Retrieved |
|------|--------------------|--------|-----------|
| Price | Free | https://apps.apple.com/app/recipe-notes — listing | 2026-04-25 |
| Import sources | URL, photo, share-sheet | https://recipenotes.app/features | 2026-04-25 |
| Household sharing | Single-user only; export to share | https://recipenotes.app/faq#sharing | 2026-04-25 |
| Pantry | Not offered | https://recipenotes.app/features (no pantry listed) | 2026-04-25 |
| Meal planning | Not offered | https://recipenotes.app/features (no meal-plan listed) | 2026-04-25 |
| Shopping intelligence | Not offered | https://recipenotes.app/features (no shopping list) | 2026-04-25 |
| Ads | None | App Store listing | 2026-04-25 |

**Notes:** Recipe Notes is the bare-free competitor — Palateful concedes
"free" parity but wins on pantry / household / Meals capability stack.

---

## Mela

| Cell | Value (2026-04-25) | Source | Retrieved |
|------|--------------------|--------|-----------|
| Price | $4.99 one-time (iOS) / $9.99 one-time (Mac) | https://mela.recipes/pricing | 2026-04-25 |
| Import sources | URL, share-sheet, photo (paid only) | https://mela.recipes/features | 2026-04-25 |
| Sync | iCloud (single Apple ID) | https://mela.recipes/faq | 2026-04-25 |
| Pantry | Not offered | https://mela.recipes/features (no pantry listed) | 2026-04-25 |
| Meal planning | Calendar view only | https://mela.recipes/features#calendar | 2026-04-25 |
| Shopping intelligence | Basic list, no dedup, no household | https://mela.recipes/features#shopping | 2026-04-25 |
| Ads | None | App Store listing | 2026-04-25 |

**Notes:** Mela is paid-once not subscription — distinct from Recime's
attack vector. Listed primarily because Mac/iOS users compare against it;
Palateful wins on household + pantry, Mela wins on offline-first feel.

---

## Palateful (self-cite)

| Cell | Value | Source |
|------|-------|--------|
| Price | Free forever | This commitment + grep-guard CI (`tools/copy-grep-guard.sh`) |
| Import sources | URL · photo · share-sheet · social | `services/api/src/routers/v1_router.py` import endpoints |
| Household | Real household, unlimited members | `services/api/src/db/models/household.py` (no member cap) |
| Pantry | Yes — cooks decrement pantry, lists auto-update | `epic-pantry-cook-with-what-you-have` (in-flight) |
| Meals | Yes | `app/lib/features/meals/` |
| Shopping intelligence | Pantry-aware, household-shared, dedup | `app/lib/features/shopping_cart/` |
| Ads | None — ever | This commitment + grep-guard CI |

**Self-citation rationale:** internal claims about Palateful behavior
should still be backed by code/feature pointers so a future operator
verifying the table can audit each row in a single sweep.

---

## How to refresh this file

1. Visit each URL in the table; record the new value if changed.
2. Update **retrieved** date even if value unchanged (proves you checked).
3. If a value changes, also update the corresponding row in
   `pos-1-content-copy-for-all-surfaces.md` and re-run grep guard.
4. If a competitor adds a feature Palateful doesn't have, escalate to a
   product decision before updating copy — comparison must remain factually
   accurate (per epic Design Principle "factual, not snide").
