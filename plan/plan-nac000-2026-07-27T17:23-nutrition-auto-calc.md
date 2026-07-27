---
hash: nac000
type: plan
created: 2026-07-27T17:23:00-06:00
title: Nutrition auto-calculation — USDA-sourced macros on every recipe, free for everyone
from: _bmad-output/planning-artifacts/epic-nutrition-auto-calc.md
status: ready
mode: YOLO
---

## Scope
Match Recime's Premium-gated nutrition feature but ship it free: every recipe displays an auto-calculated per-serving nutrition card (calories / protein / carbs / fat) computed by joining the user's ingredients to USDA FoodData Central data loaded into a new `ingredients.nutrition_per_unit` column. Values are cached on `recipes.nutrition_per_serving`; recalc is always async (worker-enqueued, WS-lowered back to the client), with the bulk-import path computing inline during import to avoid recalc storms. Unmatched ingredients are visible, not silent — an inline manual-entry path (the same per-ingredient override sheet used on recipe edit) keeps users unblocked, per-recipe manual overrides are available on edit, and the "* Estimated" disclaimer is mandatory on all three surfaces (card, breakdown sheet, override sheet). The USDA snapshot lives in S3 version-pinned by `USDA_DATA_VERSION`, loaded by an operator-driven, audit-gated, reversible script; a `users.preferences.show_nutrition` toggle short-circuits computation entirely when OFF.

## Pre-split stories (BMAD)
- nutri-0 — Ops decision + setup: S3 snapshot upload (`s3://palateful-data/usda/<version>/`) + `USDA_DATA_VERSION` env-var plumbing; half-day ops-only story that BLOCKS nutri-1a/1b (added by party-mode; operator decision required on snapshot version)
- nutri-1a — Backend: migration adding `ingredients.nutrition_per_unit` JSON column (reversible, cheap; split from nutri-1 per party-mode 2026-04-25)
- nutri-1b — Backend: `load_usda_nutrition.py` reading from S3 with pre-flight diff report, `--yes` gate, audit row, and sibling `revert_usda_nutrition.py` rollback script (the risky half, own sign-off)
- nutri-2 — Backend: `nutrition_calculator.py` service (unit normalization via existing aliases, missing-ingredient flagging) + `recipes.nutrition_per_serving` / `manual_nutrition_override` migration
- nutri-3 — Backend: GET response-shape addition + recalc-on-save hook — enqueued to worker, not inline; bulk-import path skips the hook; AC includes 50-recipe-import load test asserting bounded recompute fan-out
- nutri-4 — Frontend: NutritionCard + breakdown sheet + missing-ingredient entry (reusing the per-ingredient override sheet), MutationBus subscription + WS-lowering integration
- nutri-5 — Frontend: per-recipe manual override on edit + `show_nutrition` Settings toggle + e2e; builds the shared per-ingredient override sheet early so nutri-4 can reuse it; disclaimer-on-three-surfaces AC

## Dependencies / notes
- nutri-0 is a blocking ops/human step: operator uploads the USDA snapshot to S3 and confirms the version pin before any data-load work starts.
- Should ship after `epic-social-video-import` (freshly-extracted recipes pick up nutrition on first render) and coordinates with `epic-recime-mass-import` (bulk-import inline-nutrition path prevents an 87-recipe recalc storm).
- Reuses unit-normalization from `epic-extractor-richer-ingredients`; no new AWS resources (S3 bucket exists).
- Key risks flagged by the epic: USDA fuzzy-match false positives (confidence threshold + rejected-match audit + manual review of top unmatched ingredients before prod load), disclaimer-miss liability (widget tests + CI grep guard on nutrition widgets), and the toggle being a fake promise (integration test asserts zero calculator calls when OFF).
- Cookable-recipes nutrition filtering ("low-carb only") is explicitly deferred to a future quality-of-life epic.
- When /devx-plan picks this up it should emit dev specs from the pre-split stories rather than re-chunking from scratch.

## Status log
- 2026-07-27T17:23 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; no implementation commits on main as of import
