# Story mcal-2 — Backend `aggregate_meal_ingredients` service + dedupe correctness

**Status:** done
**Epic:** epic-meals-calendar
**Depends on:** mcal-1 (meal_id columns landed), riip-1 (unit_aliases live).

## Scope

One pure-read aggregation function in `libraries/utils/utils/services/meal_service.py` plus a new `AggregatedIngredient` dataclass. The function is the centerpiece of the Meal → shopping-list expansion path; mcal-5 calls it from both the per-Meal and per-event endpoints, and mcal-4's removed `PopulateFromCalendar` Meal-branch would have called it too (path now routes via mcal-5's per-event endpoint).

### Contract

```python
def aggregate_meal_ingredients(
    meal: Meal,
    session: Session,
) -> list[AggregatedIngredient]:
```

- Dedupe key `(ingredient_id, normalize_unit_display(unit_display, session))`.
- Sum `quantity_display` across contributing RecipeIngredient rows.
- Emit one `AggregatedIngredient` per unique key; preserve first-seen order.
- Track contributing recipe ids in insertion order (deduped).

### Edge-case behavior

| Case | Behavior |
|---|---|
| Same ingredient, same normalized unit across components | **Merge** — summed_quantity totaled. |
| Same ingredient, different units (`tbsp` vs `ml`) | **Do not merge** — separate rows. |
| Ingredient with empty-string unit ("2 eggs") | Distinct key `(id, "")`; merges with other empty-unit rows. |
| Component recipe archived | **Skip** + `logger.warning`. |
| Component recipe's book archived | **Skip** + `logger.warning`. |
| Component recipe relationship null | **Skip** silently (shouldn't happen — defensive). |
| Component with zero non-archived ingredients | **Skip** cleanly at debug level. |
| RecipeIngredient with null ingredient relationship | **Skip** the ingredient, keep processing the rest of the recipe. |
| `quantity_display` is `None` | Treat as `Decimal("0")` — defensive. |

## File List

- `libraries/utils/utils/services/meal_service.py` [MODIFY] — new `AggregatedIngredient` dataclass + `aggregate_meal_ingredients` free function.
- `libraries/utils/test/test_aggregate_meal_ingredients.py` [NEW] — 16 unit tests covering the edge-case matrix.

## Acceptance criteria

- `npx nx run utils:lint` clean. ✓
- `poetry run pytest libraries/utils/test/test_aggregate_meal_ingredients.py` — all tests green. ✓
- Full `poetry run pytest libraries/utils/test/` — 255 tests green, no regression. ✓
- Dedupe/merge behavior matches the matrix above.

## QA Walkthrough

See `mcal-2-qa-walkthrough.md`.
