# QA Walkthrough — mcal-2 `aggregate_meal_ingredients`

Story is backend-only (a pure domain function consumed by mcal-5 endpoints that ship in the next commit). Manual QA is bounded to reading the implementation + confirming unit-test coverage of the edge matrix. No UI surface yet.

## Checklist

- [x] `libraries/utils/utils/services/meal_service.py` exports `AggregatedIngredient` + `aggregate_meal_ingredients`.
- [x] Function signature matches epic spec: `(meal: Meal, session: Session) -> list[AggregatedIngredient]`.
- [x] Dedupe key is `(ingredient_id, normalize_unit_display(unit_display, session))`.
- [x] Same-unit merge sums `quantity_display` values; `contributing_recipe_ids` preserves insertion order with dedup.
- [x] Cross-unit variants do NOT merge (verified by `test_cross_unit_keeps_separate_rows`).
- [x] Null/empty-unit ingredients dedupe separately from unit-specified variants (verified by two dedicated tests).
- [x] Archived component recipe → skipped + `logger.warning` (verified).
- [x] Archived book → skipped + `logger.warning` (verified).
- [x] Zero-ingredient component → skipped at debug level, no warnings (verified).
- [x] `None` quantity treated as zero — defensive, doesn't blow up.
- [x] 16/16 new unit tests green.
- [x] Full utils suite: 255 passed, no regression.
- [x] `npx nx run utils:lint` passes.

## What's next

- mcal-3 wires `meal_id` into `POST/PATCH/GET /v1/meal-events` + `/v1/meal-recurrence-rules`.
- mcal-5 plumbs `aggregate_meal_ingredients` into two new HTTP surfaces: `POST /v1/meals/{meal_id}/add-to-shopping-list` and `POST /v1/meal-events/{event_id}/add-to-shopping-list`.

Nothing user-facing lands until mcal-7 / mcal-8 / mcal-9 (Flutter surfaces).
