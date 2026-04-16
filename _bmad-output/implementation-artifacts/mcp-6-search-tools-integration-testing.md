# Story MCP.6: Search Tools + Integration Testing (2 tools + tests)

Status: ready-for-dev

## Story

As a developer,
I want search tools and a comprehensive integration test suite,
so that we can ship with confidence and catch regressions.

## Acceptance Criteria

1. `unified_search(q, limit?, book_id?, tags?, max_prep_time?, max_cook_time?)` → cross-entity search (recipes + public + users)
2. `search_ingredients(q, limit?)` → fuzzy + semantic ingredient search
3. Integration-level tests:
   - Tool listing: all 28 tools registered
   - Auth: valid bearer → 200, missing → 401, malformed → 401, expired → 401
   - Error handling: get_recipe with nonexistent ID returns "Error: ..." not a traceback
   - Tool description quality: every tool has a docstring (description)
4. All tests pass under `npx nx run api:test` with 100% coverage

## Technical Approach

- `unified_search` wraps `UnifiedSearch` via `call_endpoint()`; `q` is the user-facing param (maps to endpoint's `q`)
- `search_ingredients` wraps `SearchIngredients`
- Integration tests build the MCP ASGI app and drive it through the auth middleware using raw ASGI scopes (no network) — the same pattern used in test_auth.py

## File List

- Create: `services/api/src/mcp_server/tools/search.py`
- Modify: `services/api/src/mcp_server/tools/__init__.py`
- Create: `services/api/tests/mcp_server/test_search.py`
- Create: `services/api/tests/mcp_server/test_integration.py`
