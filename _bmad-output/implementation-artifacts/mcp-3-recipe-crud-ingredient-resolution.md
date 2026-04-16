# Story MCP.3: Recipe CRUD + Ingredient Resolution (8 tools)

Status: ready-for-dev

## Story

As a user talking to Claude,
I want Claude to create, read, update, delete, and organize my recipes using ingredient names,
so that I can manage my collection through natural conversation without handling UUIDs.

## Acceptance Criteria

1. `get_recipe(recipe_id)` — full recipe details including ingredients, steps, notes
2. `list_recipes(book_id?, limit?, offset?, search?)` — defaults to user's default book
3. `create_recipe(name, ..., ingredients=[{name, quantity, unit, notes?, is_optional?}], steps=[...], book_id?)` — accepts ingredient NAMES; resolves each via pg_trgm similarity >= 0.85 or auto-creates
4. Ingredient resolver: fuzzy search ingredients by name; match if top similarity >= 0.85 else create new ingredient
5. `update_recipe(recipe_id, ...)` — partial update, ingredients accept name strings when provided
6. `delete_recipe(recipe_id)` — archive via soft-delete
7. `toggle_favorite(recipe_id)` — returns new state
8. `list_favorites()` — user's favorited recipes
9. `fork_recipe(recipe_id, destination_book_id?)` — defaults to user's default book

## Technical Approach

- `resolve_ingredient(name, database)` → ingredient_id:
  1. Run `SearchIngredients` endpoint with name and top-1 limit
  2. If top result similarity >= 0.85: return that ID
  3. Else create via `CreateIngredient` and return new ID
- All endpoint wrappers use `call_endpoint()`
- `list_recipes` and `create_recipe`/`fork_recipe` default `book_id`/`destination_book_id` to user's `default_recipe_book_id`

## File List

- Create: `services/api/src/mcp_server/tools/recipes.py`
- Modify: `services/api/src/mcp_server/tools/__init__.py`
- Create: `services/api/tests/mcp_server/test_recipes.py`
