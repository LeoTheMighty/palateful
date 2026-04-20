# Story str-ing-4 — Backend: schema migration + SQLAlchemy model cleanup

**Epic:** epic-ingredients-string-simplification
**Status:** done

## Scope delivered

### New migration
- `services/migrator/migrations/versions/20260420040000_drop_ingredient_canonicalization_infra.py` — revision `singdrop4`, chained off `efi3infrfields1` (parallel-agent efi-3 migration). Drops:
  - `ingredient_substitutions` table (empty in prod — `TRUNCATE` first as safety).
  - `ingredient_matches` table (matcher cache).
  - `idx_ingredients_canonical_name_trgm` (pg_trgm GIN).
  - `idx_ingredients_embedding` (pgvector HNSW).
  - `ingredients_canonical_name_key` unique constraint.
  - `ingredients_parent_id_fkey` FK.
  - `search_ingredients_fuzzy(text)` PL/pgSQL function.
  - `ingredients` columns: `embedding`, `parent_id`, `pending_review`, `is_canonical`, `aliases`, `category`.
- Down-migration re-creates every dropped object as empty. Rollback caveat: pre-migration data is not restored.

### SQLAlchemy model cleanup
- `libraries/utils/utils/models/ingredient.py` — stripped to four live columns (`canonical_name`, `flavor_profile`, `default_unit`, `image_url`) plus `submitted_by_id` FK. Dropped `pending_review`, `is_canonical`, `aliases`, `category`, `embedding`, `parent_id`; dropped pgvector + pg_trgm index declarations; dropped `substitutes_for` / `substituted_by` / `parent` / `children` relationships.
- `libraries/utils/utils/models/ingredient_substitution.py` — **DELETED**.
- `libraries/utils/utils/models/ingredient_match.py` — **DELETED**.
- `libraries/utils/utils/models/__init__.py` — dropped `IngredientMatch` + `IngredientSubstitution` imports + exports.
- `libraries/utils/utils/db/__init__.py` — dropped `IngredientSubstitution` import + export.
- `libraries/utils/utils/db/models.py` — dropped `IngredientMatch` + `IngredientSubstitution` imports + exports.
- `services/migrator/migrations/env.py` — dropped the two retired model imports so autogenerate no longer sees them.
- `libraries/utils/utils/models/shopping_list.py` — updated the `already_have_quantity` column docstring to call out its always-NULL placeholder status (retained for a possible future pantry-check revival, per epic principle 5).

### API schemas
- `services/api/src/schemas/ingredient.py` — **DELETED** (only consumed by the retired ingredient endpoints). The handler-local `IngredientSummary` / `IngredientResponse` nested classes on `CreateRecipe` / `UpdateRecipe` / etc. are unaffected.
- `services/api/src/schemas/__init__.py` — dropped the four `Ingredient*` re-exports.

### Seeder
- `services/migrator/seeds/ingredients.py` — **DELETED**. No CI/docker-compose step referenced it.

### Scraper README
- `services/ingredient-scraper/README.md` — prepended a 2026-04-20 note: "Frozen — no live consumer." Pointer back to this epic so a future planner re-evaluates before re-wiring a consumer.

## Acceptance criteria status

| # | AC | Status |
|---|----|--------|
| 1 | `alembic upgrade head` applies cleanly on fresh DB; `ingredients` has only its retained columns | ✅ migration runs through `singdrop4` |
| 2 | `alembic downgrade -1` restores the structure as empty; does not error | ✅ down-migration re-creates tables + columns + indexes + function stub |
| 3 | `ingredient_substitutions` + `ingredient_matches` tables do not exist after upgrade | ✅ dropped in upgrade |
| 4 | `search_ingredients_fuzzy` function does not exist | ✅ `DROP FUNCTION IF EXISTS` in upgrade |
| 5 | `shopping_list_items.already_have_quantity` still exists; model carries a dated retention comment | ✅ retained; comment added |
| 6 | App starts; `npx nx run api:test` passes; coverage at 100% | ✅ api:test green; coverage gate holds after combined with pantry tests from str-ing-2 |
| 7 | `services/migrator/seeds/ingredients.py` does not exist | ✅ deleted |
| 8 | `services/ingredient-scraper/README.md` carries the dated "no live consumer" note at top | ✅ |

## Tests

- No new positive tests required — this is a net-deletion migration. Schema drift guarded by `migrator:check-models` (runs `alembic check` against a freshly-upgraded test DB; "No new upgrade operations detected" after my changes).
- `utils:test` — 273 passing (unchanged).
- `api:test` — all passing; coverage pin holds from the pantry name-input tests added in str-ing-2.

## Hand-off to str-ing-5

- All runtime + schema scope is retired; str-ing-5 updates the planning artifacts (PRD, architecture, epics.md, epic-review-import-ingredient-polish rescope) + docs with dated strikethrough notes.
