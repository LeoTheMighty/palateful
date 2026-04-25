<!-- refined via party-mode 2026-04-25 -->
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

---

## Refinements applied (party-mode 2026-04-25)

### End-user-flow additions / rewrites
- **Add step 0 — placement spec:** below ingredients, above steps; on small viewports, collapses to a single-line summary chip with disclosure. Document why (cook eye-flow: "what's in it" → "is it heavy?" → "how do I make it").
- **Rewrite step 3 — unify entry points:** missing-ingredient inline entry sheet uses the SAME per-ingredient override sheet built for recipe-edit. ONE UI, two entry points. Don't ship two manual-entry flows.
- **Add step 6 — disclaimer everywhere:** "* Estimated" appears on the card, the breakdown sheet header, AND inside the manual-override sheet. Spec it explicitly.
- **Reframe step 5 — toggle is taste, not perf:** Settings toggle is a clutter / taste preference (not a perf optimization). Default ON. Perf is an implementation consequence, not a user promise.

### Frontend section additions
- `nutrition_card.dart` **subscribes via `MutationBus` to `RecipeIngredientsChanged` events** (per `app/lib/core/state/README.md`). Uses existing coalescer recipe.
- When backend recalc completes async, **WS-lowering recipe pushes the new `nutrition_per_serving` snapshot**; nutrition card re-renders from the bus event. Failure path uses `mutationFailureCopy` map for snackbar.
- **Named preference key:** `users.preferences.show_nutrition: bool` (default `true`). Document next to existing prefs.
- **Replace the missing-ingredient inline entry widget** with a thin entry-point that opens the SAME per-ingredient override sheet built for recipe-edit. One UI.

### Backend section additions
- **Recalc-on-save is ENQUEUED to the worker, NOT inline.** Recipe-update response returns immediately; WS-lowering pushes new `nutrition_per_serving` when worker finishes. Adds latency to worker, not to the cook tapping Save.
- **Bulk-import path computes nutrition INLINE within the import task** (single pass over already-parsed ingredients), bypassing the recalc-on-save hook. Hook checks `if recipe.created_via_import and recipe.created_at within last N seconds: skip` to prevent double-compute.
- **USDA re-load fan-out is BATCHED + RATE-LIMITED** by the worker (`process_nutrition_recompute_batch` with N recipes per task). Not a sync recipe-update storm.
- **Sync vs async contract documented** in calculator service docstring.
- **New operator-only admin endpoint `POST /v1/admin/nutrition/reload`** to enqueue the data-load script + return audit row id. Alternative to ssh-into-container.

### Infrastructure section additions
- **DECISION (blocking nutri-1): USDA snapshot lives in S3** (`s3://palateful-data/usda/v2026q1/`) — NOT committed to repo, NOT runtime-downloaded from USDA. Reasons: keeps repo lean, version-pinned by S3 prefix, prod container has IAM access, USDA CDN not a runtime dep.
- **USDA version pin via `USDA_DATA_VERSION` env var** (default `v2026q1`). Quarterly cadence; operator decision.
- `load_usda_nutrition.py` reads from S3 (not local FS), writes pre-flight diff report (matched / unmatched / changed-rows count) to audit row, requires `--yes` to commit.
- **Rollback story:** previous `nutrition_per_unit` snapshotted to `error_logs.context` JSON before each USDA load. Sibling `revert_usda_nutrition.py` script reverses a bad load. Document in `CLAUDE.md` Ops Scripts section.
- Reaffirm: no new AWS resources (S3 bucket already exists per infra inventory).

### Story changes
- **Add `nutri-0` — operator decision + S3 snapshot upload + `USDA_DATA_VERSION` env var plumbing.** Half-day, ops-only. **Blocks `nutri-1`.**
- **Split `nutri-1` into `1a` + `1b`:**
  - `1a` — migration only (reversible, cheap).
  - `1b` — data-load script + S3 read + rollback script + audit row. The risky part with its own AC + sign-off.
- **Modify `nutri-3`:** explicitly call out that recalc is enqueued, not inline; bulk-import path skips the hook; AC includes a 50-recipe-import load test asserting <N recompute tasks fire (not 50).
- **Modify `nutri-4`:** add MutationBus + WS-lowering integration to AC; merge missing-ingredient entry sheet with the per-ingredient override sheet built in `nutri-5`.
- **Modify `nutri-5`:** pull the per-ingredient override sheet earlier so `nutri-4` can reuse it; add AC for "* Estimated" disclaimer presence in all three surfaces (card, breakdown, override sheet).

### Open questions (escalated)
1. **USDA snapshot location.** Recommend **S3** (`s3://palateful-data/usda/<version>/`). Confirm before `nutri-0`. Repo-commit and runtime-download both rejected per party-mode discussion.
2. **Manual-override granularity.** Recommend BOTH — per-recipe (4 fields, primary v1) AND per-ingredient (advanced; reuses missing-ingredient entry sheet). Per-recipe overrides per-ingredient when both present. Confirm or simplify to per-recipe-only.
3. **Nutrition-card placement.** Recommend below ingredients / above steps; collapsed-chip on small viewports.
4. **Recalc fan-out cap.** When USDA re-load touches an ingredient used by 10k recipes — what's the acceptable recompute window? Recommend batched, 100/min, completes in <2h; user-visible during rolling window.
5. **Sync vs async on recipe-edit Save.** Recommend async (worker + WS push). Cook-tap-Save latency stays untouched.

### Locked decisions (last epic in round; cross-epic facts now locked)
- **USDA data version pinned via `USDA_DATA_VERSION` env var** (initial `v2026q1`); refresh **quarterly, operator-driven, audit-row gated**.
- **USDA snapshot in S3** (`s3://palateful-data/usda/<version>/`), NOT in git, NOT runtime-downloaded.
- **Nutrition recalc is ALWAYS async** (worker-enqueued), never inline on the recipe-update request path. Bulk-import flows compute inline-during-import to avoid hook fan-out.
- **`users.preferences.show_nutrition: bool`** is now the canonical preference key.
- **"* Estimated" disclaimer is mandatory on the card, breakdown sheet, AND override sheet** — three surfaces, not one. Widget-test asserts presence on all three.
- **Cookable-recipes ranking nutrition filter** ("low-carb only" etc.) is **deferred to a future quality-of-life epic**, not this round.

### Risks
1. **USDA fuzzy-match false positives** ("cream of tartar" matched to "heavy cream"). *Mitigation:* match-confidence threshold + rejected-match audit log; below-threshold stays NULL ("Nutrition unavailable"); manual review queue for top-100 highest-recipe-count unmatched ingredients before each USDA load goes prod.
2. **Disclaimer-miss liability** — if a single surface ships without "* Estimated" we've over-claimed precision on a free, unverified data source. *Mitigation:* widget-test asserts disclaimer text presence on all three surfaces; lint rule or grep guard in CI flagging any nutrition widget that doesn't import `EstimatedDisclaimer` shared component.
3. **Recalc storm on bulk import** — Recime mass-import lands 87 recipes; recalc fires 87 times. *Mitigation:* bulk-import path computes nutrition inline within the import task and skips the hook (`recipe.created_via_import` guard); `nutri-3` AC asserts ≤1 recompute per imported recipe; worker rate-limit cap as belt-and-braces.
4. **Settings toggle is a fake promise** — if "Show nutrition = OFF" still computes server-side, the perf claim is a lie. *Mitigation:* AC requires GET endpoint to short-circuit before calculator invocation when `users.preferences.show_nutrition is False`; integration test asserts zero calculator calls; observability log line confirms skip-rate in prod.
