<!-- draft: pre-party-mode -->
# Epic: Nutrition Auto-Calculation — USDA-Sourced, Free for Everyone

## Overview

Match Recime's nutrition feature (which they Premium-gate at $39.99–$59.99/yr; we ship it free). Every recipe — imported or manually created — displays an auto-calculated nutrition card per serving (calories, protein, carbs, fat) sourced from USDA FoodData Central data joined to the user's ingredients. When ingredient matching fails, an inline manual-entry path keeps the user unblocked. Recipe edit screen exposes optional manual-override fields.

## Goal

Be the only free recipe app where every recipe shows nutrition out of the box. Reinforces the "free + capability stack" positioning vs Recime (Premium-gated) and Recipe Notes (no nutrition). Lays groundwork for future "low-carb / high-protein / under-500-cal" filtering on cookable-recipes ranking.

## End-user flow

1. **Recipe detail — nutrition card.** User opens any recipe. Below the ingredients section, a new card displays: "Per serving: 420 cal · 32g protein · 38g carbs · 18g fat" with a small "* Estimated based on USDA data" disclaimer below.
2. **Tap to expand.** Tapping the card opens a sheet with per-ingredient breakdown: each ingredient + its contribution to total macros. Helps users understand what's driving the numbers (and spot ingredient-matching errors).
3. **Missing-ingredient empty state.** If one or more ingredients can't be matched to USDA data, the card shows "Nutrition unavailable for: heavy cream — [enter manually]" with an inline manual-entry path (sheet appears with calorie / protein / carb / fat fields scoped to that ingredient + serving).
4. **Manual override on recipe edit.** On the recipe edit screen, optional fields let the user override calculated values per serving (calories / protein / carbs / fat). Useful when the USDA estimate disagrees with the user's judgement (e.g., "this recipe says heavy cream but I always sub Greek yogurt").
5. **Settings toggle.** A user can disable the nutrition card globally via Settings → "Show nutrition" (default on). When OFF, no nutrition computation runs for that user (perf optimization on the hot recipe-detail render path).

## Frontend changes

- New widget `app/lib/features/recipes/recipe_detail/nutrition_card.dart` — renders per-serving macros + "* Estimated" disclaimer. Tappable to open expanded sheet.
- New widget `app/lib/features/recipes/recipe_detail/nutrition_breakdown_sheet.dart` — per-ingredient breakdown showing each ingredient's macro contribution.
- New widget `app/lib/features/recipes/recipe_detail/missing_ingredient_nutrition_entry.dart` — inline manual-entry sheet for ingredients without USDA matches.
- `app/lib/features/recipes/recipe_edit/recipe_edit_screen.dart` — add optional manual-override fields below the existing fields (calories / protein / carbs / fat per serving). When non-empty, override displayed values.
- `app/lib/features/profile/settings_screen.dart` — add "Show nutrition" toggle (default on). Stored in `users.preferences` JSON.

## Backend changes

- **Schema migration 1** — extend `ingredients` table with `nutrition_per_unit` JSON column. Schema: `{calories: float, protein_g: float, carbs_g: float, fat_g: float, base_unit: str (e.g., 'g' or 'ml' or 'piece'), density_g_per_ml: Optional[float]}`. Defaults to NULL when no USDA match is available.
- **One-time data-load script** `services/api/scripts/load_usda_nutrition.py` — downloads the USDA FoodData Central CSV (Foundation Foods + SR Legacy subsets, ~5000 most-common ingredients), normalizes to our schema, performs fuzzy match against existing `ingredients.canonical_name` (using existing trigram + alias logic from `epic-extractor-richer-ingredients`), upserts `nutrition_per_unit` for matched rows. Audit row written on completion summarizing matched / unmatched / multi-match counts. Idempotent on re-run.
- **Schema migration 2** — extend `recipes` table with `nutrition_per_serving: Mapped[Optional[dict]]` JSON column (computed value cache) + `manual_nutrition_override: Mapped[Optional[dict]]` JSON column (user-entered override).
- New service `services/api/src/services/nutrition_calculator.py` — given a recipe's ingredients + servings, sums each ingredient's `nutrition_per_unit` × parsed quantity (with unit normalization via existing aliases logic from `epic-extractor-richer-ingredients`), divides by `recipe.servings`. Returns `{calories, protein_g, carbs_g, fat_g, missing_ingredients: [...]}` for ingredients that couldn't contribute (no USDA match).
- **Recalc-on-save hook** — wired into the recipe-update path: after a recipe's ingredients change, recompute `nutrition_per_serving` and write back. Same hook fires when the global ingredient's `nutrition_per_unit` changes (rare; only on USDA data-load re-runs).
- `GET /v1/recipes/{id}` response shape addition — `nutrition_per_serving: Optional[NutritionPerServing]` (populated from cached `recipes.nutrition_per_serving`, falling back to `manual_nutrition_override` if set, falling back to `null` if no nutrition data is available).
- New `recipes.nutrition_per_serving` is response-shape additive; old clients ignore the field.

## Infrastructure changes

- **One-time USDA data load** via `load_usda_nutrition.py` — operator-driven, run on staging first, audit-row sign-off, then prod. Documented in `CLAUDE.md` Ops Scripts section.
- **Two Alembic migrations** — schema additions to `ingredients` + `recipes`. Both backwards-compatible (new nullable columns).
- **No new AWS resources, no new env vars.** USDA data load is a one-shot script reading from a public CSV download (committed to repo as a snapshot for repeatability, ~50 MB compressed).
- **API coverage stays at 100%** per project standard.

## Initial design principles (from research; party-mode TBD)

- **USDA data is the trusted source.** Better than asking AI to estimate macros (which it does badly + opaquely). USDA FoodData Central is free, public, well-curated, and updated quarterly.
- **Estimated label is permanent.** "* Estimated" disclaimer always present on the nutrition card. We never claim precision; we offer a reasonable starting point.
- **Manual override always available.** Users who care about accuracy can override per-recipe. This is the trust-restoring escape hatch when USDA matches are wrong.
- **Missing ingredients are visible, not silent.** Don't hide unmatched ingredients in the UI. Show them, offer the inline manual-entry path. Trust comes from transparency.
- **Cache aggressively.** `recipes.nutrition_per_serving` cache means recipe-detail render doesn't recompute. Recompute only fires on ingredient changes or global USDA-data updates.
- **Settings toggle is real.** Users who don't care about nutrition shouldn't pay the perf cost. When toggle is OFF, the GET response omits the field entirely.

## File structure (anticipated)

```
app/lib/features/
  recipes/recipe_detail/
    nutrition_card.dart                            # NEW
    nutrition_breakdown_sheet.dart                 # NEW
    missing_ingredient_nutrition_entry.dart        # NEW
    recipe_detail_screen.dart                      # mount NutritionCard
  recipes/recipe_edit/
    recipe_edit_screen.dart                        # add manual-override fields
  profile/
    settings_screen.dart                           # add "Show nutrition" toggle

services/api/src/
  services/nutrition_calculator.py                 # NEW
  api/v1/recipe/get_recipe.py                      # extend response shape
  api/v1/recipe/update_recipe.py                   # recalc-on-save hook
  scripts/load_usda_nutrition.py                   # NEW one-shot data load

services/migrator/migrations/versions/
  20260428010000_ingredients_nutrition_per_unit.py # NEW migration 1
  20260428020000_recipes_nutrition_per_serving.py  # NEW migration 2

data/usda/                                         # NEW (gitignored if too big; otherwise checked in as a small snapshot)
  foundation_foods.csv
  sr_legacy.csv

_bmad-output/implementation-artifacts/
  nutri-1-backend-ingredients-schema-and-usda-data-load.md
  nutri-2-backend-nutrition-calculator-and-recipes-schema.md
  nutri-3-backend-get-response-and-recalc-hook.md
  nutri-4-frontend-nutrition-card-and-breakdown-sheet.md
  nutri-5-frontend-manual-override-and-settings-and-e2e.md
```

## Story list

- **nutri-1 — Backend: ingredients schema + USDA data load.** Migration adds `nutrition_per_unit` JSON column to `ingredients`. New `load_usda_nutrition.py` script fuzzy-matches USDA Foundation Foods + SR Legacy data against existing ingredient rows and upserts. Audit row summarizing matched / unmatched counts. Operator-driven run on staging first. **AC:** migration runs cleanly + reverses cleanly; data-load script populates ~3000-5000 ingredient rows on a fresh prod DB; audit row visible via `audit_errors.py`; idempotent on re-run; integration test covers a sample fixture.
- **nutri-2 — Backend: nutrition_calculator + recipes schema.** New `nutrition_calculator.py` service with unit-normalization via existing aliases. Migration adds `nutrition_per_serving` + `manual_nutrition_override` JSON columns to `recipes`. **AC:** calculator returns correct totals for a 3-ingredient test recipe; handles unit conversions (cups → ml, oz → g); flags unmatched ingredients in the response; 100% test coverage.
- **nutri-3 — Backend: GET response + recalc-on-save hook.** Extend `GET /v1/recipes/{id}` response shape with `nutrition_per_serving` (cached value, falling back to manual override). Recalc hook fires on recipe-update path. **AC:** response shape change is additive (old clients ignore new field); recalc hook fires on ingredient changes + serving-count changes; integration test covers a recipe-edit → response-shape verification flow.
- **nutri-4 — Frontend: NutritionCard + breakdown sheet.** New `NutritionCard` widget mounted on recipe detail. `NutritionBreakdownSheet` for the expanded view. Missing-ingredient empty state with manual-entry sheet. **AC:** card renders for recipes with full match; renders missing-ingredient state correctly; breakdown sheet shows per-ingredient contributions; widget tests cover empty + partial + full states.
- **nutri-5 — Frontend: manual override + Settings toggle + e2e.** Recipe edit screen gets manual-override fields. Settings → "Show nutrition" toggle. End-to-end test: open a recipe → see nutrition card → tap to expand → enter manual override on edit screen → save → see overridden values on detail. **AC:** manual override persists + displays; toggle OFF hides the card globally + omits the field from GET responses; e2e flow passes.

## Dependencies

- **No hard dependencies.** Reuses unit-normalization from `epic-extractor-richer-ingredients`.
- **Should ship after `epic-social-video-import`** so freshly-extracted recipes pick up nutrition immediately on first render (recalc-on-save hook fires after the social-video extractor lands the recipe).

## Open questions for the user

- **USDA snapshot in repo or runtime download?** Default proposed: commit a small snapshot (`data/usda/`) so the data-load script is reproducible offline. Alternative: download at runtime from USDA's public CDN — keeps the repo lean but adds a runtime dependency. Confirm before story `nutri-1`.
- **Should cookable-recipes ranking (`epic-pantry-cook-with-what-you-have`) accept a nutrition filter (e.g., "low-carb only")?** Out of scope for this round but trivial to add once `nutrition_per_serving` is on the recipe row. Flag for a future quality-of-life epic.
- **Manual-override granularity.** Default proposed: per-recipe override (4 fields per serving). Alternative: per-ingredient override (lets users say "for me, butter is 95 cal/tbsp not 102"). Per-recipe is simpler for v1; per-ingredient is the longer-tail story.
