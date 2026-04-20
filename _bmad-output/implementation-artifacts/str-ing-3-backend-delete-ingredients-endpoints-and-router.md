# Story str-ing-3 — Backend: delete `/v1/ingredients/*` endpoints + router

**Epic:** epic-ingredients-string-simplification
**Status:** done

## Scope delivered

### Deleted
- `services/api/src/api/v1/ingredient/` directory (5 files: `__init__.py`, `create_ingredient.py`, `get_ingredient.py`, `search_ingredients.py`, `__pycache__`). All three endpoints (`GET /v1/ingredients/search`, `POST /v1/ingredients`, `GET /v1/ingredients/{id}`) are gone at the handler layer.
- `services/api/src/routers/v1/ingredient_router.py` — router module retired wholesale.
- `services/api/tests/test_ingredient.py` (97 LOC) — tests for the retired endpoints.

### Modified
- `services/api/src/routers/v1_router.py` — dropped `from routers.v1.ingredient_router import ingredient_router` and the `v1_router.include_router(ingredient_router)` call. The other 22 v1 routers still mount.
- `services/api/src/mcp_server/tools/search.py` — removed the `@mcp.tool() search_ingredients` wrapper + the `SearchIngredients` import. `unified_search` stays.
- `services/api/tests/mcp_server/test_search_tools.py` — deleted `TestSearchIngredients` class; `TestRegistration::test_search_tools_registered` now asserts `search_ingredients` is **not** in the registered set (so a future regression that re-registers the tool fails loudly).
- `services/api/tests/mcp_server/test_integration.py` — dropped `search_ingredients` from `ALL_EXPECTED_TOOLS`; updated the module docstring tool count from 28 → 27.
- `services/api/tests/test_coverage_gaps.py` — deleted `TestSearchIngredientsFallback` class (the pg_trgm fallback path it covered no longer exists); replaced with a one-line historical note.

## Acceptance criteria status

| # | AC | Status |
|---|----|--------|
| 1 | `GET /v1/ingredients/search`, `POST /v1/ingredients`, `GET /v1/ingredients/{id}` return 404 | ✅ router no longer mounts the paths |
| 2 | No Python module at `services/api/src/api/v1/ingredient/*` exists | ✅ directory removed |
| 3 | `services/api/tests/test_ingredient.py` does not exist; suite passes | ✅ deleted; 2025 tests pass |
| 4 | `npx nx run api:test --coverage` at 100% | ✅ 100.00% |
| 5 | Grep acceptance `rg '/v1/ingredients' services/ app/ docs/` returns only planning-artifact matches | ✅ (Flutter already scrubbed in str-ing-1) |

## Tests

- Net-deletion story — no new positive tests required beyond the updated MCP assertions above.
- Coverage pin holds at 100% because the deleted modules took their uncovered surface with them.

## Hand-off to str-ing-4

- Runtime code no longer reads the columns str-ing-4 will drop (`embedding`, `parent_id`, `pending_review`, `is_canonical`, `aliases`, `category`) except through the SQLAlchemy model definition itself.
- Deploy sequence: str-ing-2 + str-ing-3 ship first (backend stops reading / serving dropped columns); str-ing-4's migration follows in a second deploy.
