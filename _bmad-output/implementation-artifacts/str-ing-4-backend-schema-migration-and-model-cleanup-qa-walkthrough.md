# QA Walkthrough — str-ing-4 (Schema migration + SQLAlchemy model cleanup)

**Epic:** epic-ingredients-string-simplification
**Deploy order:** ship AFTER str-ing-2 + str-ing-3 are in prod so runtime code stops reading the dropped columns.

## Pre-flight
- [ ] `git log --oneline origin/main..HEAD` shows the `feat(backend): str-ing-4 — Alembic migration + model cleanup` commit.
- [ ] `npx nx run utils:lint` passes.
- [ ] `npx nx run api:lint` passes.
- [ ] `npx nx run utils:test` passes (273 tests).
- [ ] `npx nx run api:test` passes with the existing test count.
- [ ] `rg 'IngredientSubstitution|IngredientMatch|ingredient_substitutions|ingredient_matches|search_ingredients_fuzzy' services/api/src libraries/utils/utils/` returns only the migration file itself.
- [ ] `rg 'Ingredient\.(pending_review|is_canonical|aliases|embedding|parent_id|category)|ingredient\.(pending_review|is_canonical|aliases|embedding)' services/api/src libraries/utils/utils/` returns zero matches.

## Smoke — migration upgrade
1. Reset the local test DB: `docker exec palateful-db-1 psql -U postgres -d test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"`.
2. `cd services/migrator && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test poetry run alembic upgrade head`.
3. Verify: `docker exec palateful-db-1 psql -U postgres -d test -c "\d ingredients"`. Columns should be: `id`, `canonical_name`, `flavor_profile`, `default_unit`, `image_url`, `submitted_by_id`, `created_at`, `updated_at`, `archived_at`. No `category`, `pending_review`, `is_canonical`, `aliases`, `parent_id`, `embedding`.
4. `docker exec palateful-db-1 psql -U postgres -d test -c "SELECT table_name FROM information_schema.tables WHERE table_name IN ('ingredient_substitutions', 'ingredient_matches');"` → empty.
5. `docker exec palateful-db-1 psql -U postgres -d test -c "SELECT proname FROM pg_proc WHERE proname = 'search_ingredients_fuzzy';"` → empty.

## Smoke — migration downgrade (optional, developer-only)
1. `DATABASE_URL=... poetry run alembic downgrade -1` — should re-create the dropped tables, columns, indexes, and function stub (all empty / NULL).
2. Upgrade back to head: `DATABASE_URL=... poetry run alembic upgrade head`.

## Smoke — check-models drift
1. `npx nx run migrator:check-models` — should report "No new upgrade operations detected." (If it doesn't, a model field was missed or a new one drifted in after the migration.)

## Regression guard
- [ ] `POST /v1/recipes` with a `name`-only ingredient still works end-to-end (inline INSERT persists a fresh row; created recipe's `ingredients[].ingredient.canonical_name` reflects the submitted text).
- [ ] `GET /v1/shopping-lists/{id}` — `items[].category` is `null` on new rows.
- [ ] Pantry add / remove / events still work — pantry_ingredient_events keep their `ingredient_id` FK.
- [ ] Import pipeline happy path runs through `awaiting_review` without hitting a retired matcher or cached-match lookup.

## Known caveats
- `shopping_list_items.already_have_quantity` column is retained but always NULL on new writes — reserved for a possible future pantry-check revival.
- Scraper under `services/ingredient-scraper/` is frozen; its CSV output has no live consumer. README carries the dated freeze note.

## Hand-off to str-ing-5
- Schema + code are in their final shape. str-ing-5 updates the planning artifacts + docs + sprint-status to reflect the completed retirement, rescopes riip-4 / deletes riip-7 references in the polish epic.
