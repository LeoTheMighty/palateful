# Story MCP.5: Recipe Books + Shopping Lists + Meal Planning (12 tools)

Status: ready-for-dev

## Story

As a user talking to Claude,
I want Claude to manage my recipe books, shopping lists, and meal calendar,
so that I can plan my entire kitchen workflow through conversation.

## Acceptance Criteria

**Recipe Books (3):**
1. `list_recipe_books()`
2. `get_recipe_book(book_id)`
3. `create_recipe_book(name, description?)`

**Shopping Lists (6):**
4. `list_shopping_lists()`
5. `get_shopping_list(list_id?)` — defaults to user's `default_shopping_list_id`
6. `create_shopping_list(name)`
7. `add_shopping_list_item(list_id?, name, quantity?, unit?, category?)`
8. `update_shopping_list_item(list_id, item_id, is_checked?, quantity?, unit?, category?)`
9. `populate_from_recipe(list_id?, recipe_id, scale_factor=1.0)`

**Meal Planning (3):**
10. `list_meal_events(start_date?, end_date?, meal_type?, limit?)`
11. `create_meal_event(title, scheduled_at, meal_type, recipe_id?)`
12. `get_meal_event(event_id)`

All tools use `call_endpoint()`. `list_id` defaults to `user.default_shopping_list_id` when omitted. `scheduled_at` accepts ISO 8601 datetime strings.

## File List

- Create: `services/api/src/mcp_server/tools/recipe_books.py`
- Create: `services/api/src/mcp_server/tools/shopping.py`
- Create: `services/api/src/mcp_server/tools/meal_planning.py`
- Modify: `services/api/src/mcp_server/tools/__init__.py`
- Create: tests for each
