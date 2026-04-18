# Story mcal-1 — Backend migration: meal_id on events + recurrence + cooking_logs + source_meal_id on shopping_list_items

**Status:** in-progress
**Epic:** epic-meals-calendar
**Depends on:** epic-meals-create-and-view (mcv-1 landed the `meals` table — this migration's FKs reference it).

## Scope

One alembic revision `20260418090000_add_meal_id_to_calendar_and_cooking_logs.py` (revision id `mcal1mealid01`, down_revision `mcv1mealtables`).

### Schema changes

1. `meal_events.meal_id` — nullable FK `meals.id ondelete SET NULL`. Index `ix_meal_events_meal_id`. Check constraint `ck_meal_events_recipe_xor_meal` = `num_nonnulls(recipe_id, meal_id) <= 1`. Created NOT VALID then VALIDATE (prod-safe; SHARE UPDATE EXCLUSIVE lock only).

2. `meal_recurrence_rules.meal_id` — parallel treatment. Constraint `ck_meal_recurrence_rules_recipe_xor_meal`. Index `ix_meal_recurrence_rules_meal_id`.

3. `cooking_logs`:
   - `recipe_id` becomes nullable.
   - `meal_id` nullable FK `meals.id ondelete SET NULL`.
   - `parent_meal_log_id` nullable self-FK `cooking_logs.id ondelete CASCADE`.
   - Check constraint `ck_cooking_logs_target` = `(num_nonnulls(recipe_id, meal_id) = 1) OR (parent_meal_log_id IS NOT NULL AND recipe_id IS NOT NULL AND meal_id IS NULL)`. NOT VALID + VALIDATE.

4. `shopping_list_items.source_meal_id` — nullable FK `meals.id ondelete SET NULL`. Additive, no constraint.

### Model changes

- `libraries/utils/utils/models/meal_event.py`
- `libraries/utils/utils/models/meal_recurrence_rule.py`
- `libraries/utils/utils/models/cooking_log.py` (recipe_id `Mapped[uuid.UUID | None]`, add meal_id + parent_meal_log_id; also add CheckConstraint in `__table_args__`)
- `libraries/utils/utils/models/shopping_list.py` (ShoppingListItem gains source_meal_id)

### Downgrade

Reverses all additions. `cooking_logs.recipe_id` NOT NULL restoration guarded by `SELECT COUNT(*) FROM cooking_logs WHERE recipe_id IS NULL = 0` assertion — raises `RuntimeError` if Meal-level logs exist.

### Tests

`services/api/tests/test_meal_calendar_xor_constraint.py` (NEW):
- Inserting a meal_event with `recipe_id` only → OK
- Inserting a meal_event with `meal_id` only → OK
- Inserting a meal_event with neither → OK (free-text event, unchanged semantics)
- Inserting a meal_event with both → `IntegrityError`
- Same matrix for `meal_recurrence_rules`
- `cooking_logs`: `recipe_id` only → OK; `meal_id` only → OK; both, no parent → IntegrityError; child row with `recipe_id` + `parent_meal_log_id` → OK
- `shopping_list_items.source_meal_id` can be set alongside `recipe_id` + `meal_event_id` — purely additive, no constraint.

## File List

- `services/migrator/migrations/versions/20260418090000_add_meal_id_to_calendar_and_cooking_logs.py` [NEW]
- `libraries/utils/utils/models/meal_event.py` [MODIFY]
- `libraries/utils/utils/models/meal_recurrence_rule.py` [MODIFY]
- `libraries/utils/utils/models/cooking_log.py` [MODIFY]
- `libraries/utils/utils/models/shopping_list.py` [MODIFY]
- `services/api/tests/test_meal_calendar_xor_constraint.py` [NEW]

## Acceptance criteria

- `npx nx run migrator:migrate` clean on fresh DB.
- `npx nx run migrator:check-models` green (no model drift vs. migration).
- `npx nx run api:test` passes, 100% coverage on new model branches.
- `npx nx run api:lint` green.
- Downgrade + re-upgrade is idempotent (models + data identical before/after round-trip).
