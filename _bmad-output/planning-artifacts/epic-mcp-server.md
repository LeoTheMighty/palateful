# Epic MCP: MCP Server Integration

## Overview

Palateful has a rich API (60+ endpoints) and an existing AI agent with 5 tools, but no way for external MCP clients (Claude Desktop, Claude Code, etc.) to interact with it. Adding an MCP server at `api.palateful.app/mcp` will let Claude act as a full kitchen management assistant — searching recipes, creating them, importing from photos/URLs, managing shopping lists, and planning meals — all through tool calls.

**Goal:** Mount an MCP server on the existing FastAPI app at `/mcp` exposing 28 tools that wrap existing business logic. Authenticated via Auth0 JWT. Zero business logic duplication.

**Key Design Decisions (from party mode review):**
- Integrated into existing API service (not a separate service) — same DB pool, same auth infra
- Streamable HTTP transport via Python `mcp` SDK's `StreamableHTTPSessionManager`
- Auth via Starlette middleware + `contextvars` for context propagation (with `copy_context()` for thread boundaries)
- Standardized `call_endpoint()` wrapper — one function, not 28 custom serializers
- Tool descriptions are the UX — write them like product copy, not API docs
- `create_recipe` accepts ingredient names (strings) with auto-resolution, not UUIDs
- Import tools are async: return job_id immediately, poll with `get_import_status`
- Rate limiting via API Gateway must include `/mcp` path

## File Structure

```
services/api/src/mcp/
├── __init__.py
├── server.py              # FastMCP instance, tool registration, ASGI mount helper
├── auth.py                # JWT middleware + contextvars (current_user, current_database)
└── tools/
    ├── __init__.py        # Registers all tools on the server
    ├── recipes.py         # search, get, list, create, update, delete, favorite, fork
    ├── recipe_books.py    # list, get, create
    ├── import_tools.py    # import_recipe, get_import_status, approve_import
    ├── shopping.py        # list, get, create, add_item, check_item, populate_from_recipe
    ├── meal_planning.py   # list_events, create_event, get_event
    ├── pantry.py          # get_pantry (wraps existing agent tool)
    ├── user.py            # get_profile, get_preferences
    └── search.py          # unified_search, search_ingredients
```

**Modified files:**
- `services/api/src/main.py` — mount MCP ASGI app at `/mcp`
- `services/api/pyproject.toml` — add `mcp[cli]>=1.9`

## Tool Inventory (28 tools)

### From Existing Agent (5)
| Tool | Description | Wraps |
|------|-------------|-------|
| `search_recipes` | Semantic search across user's recipes by query text | `agent.tools.SearchRecipesTool` |
| `suggest_recipe` | AI-generate a new recipe idea from ingredients/constraints | `agent.tools.SuggestRecipeTool` |
| `add_note_to_recipe` | Add a note or tip to a recipe | `agent.tools.AddNoteToRecipeTool` |
| `get_pantry` | Get user's pantry contents with expiry tracking | `agent.tools.GetPantryTool` |
| `get_user_preferences` | Get dietary preferences and cooking settings | `agent.tools.GetUserPreferencesTool` |

### Recipe Management (8)
| Tool | Description | Wraps |
|------|-------------|-------|
| `get_recipe` | Get full recipe details including ingredients, steps, notes | `api.v1.recipe.GetRecipe` |
| `list_recipes` | List recipes in a book (defaults to user's default book) | `api.v1.recipe.ListRecipes` |
| `create_recipe` | Create recipe — accepts ingredient names, auto-resolves to IDs | `api.v1.recipe.CreateRecipe` + ingredient resolver |
| `update_recipe` | Update an existing recipe's fields | `api.v1.recipe.UpdateRecipe` |
| `delete_recipe` | Archive/delete a recipe | `api.v1.recipe.DeleteRecipe` |
| `toggle_favorite` | Toggle favorite status on a recipe | `api.v1.recipe.ToggleFavorite` |
| `list_favorites` | List user's favorited recipes | `api.v1.recipe.ListFavorites` |
| `fork_recipe` | Fork a shared recipe into your own book | `api.v1.recipe.ForkRecipe` |

### Import & OCR (3)
| Tool | Description | Wraps |
|------|-------------|-------|
| `import_recipe` | Import from URL, text, or photo with optional context | `api.v1.import_job.StartImport` |
| `get_import_status` | Check import job progress and item statuses | `api.v1.import_job.GetImportJob` + `ListImportItems` |
| `approve_import` | Approve a pending import item to create the recipe | `api.v1.import_job.ApproveImportItem` |

### Recipe Books (3)
| Tool | Description | Wraps |
|------|-------------|-------|
| `list_recipe_books` | List user's recipe books | `api.v1.recipe_book.ListRecipeBooks` |
| `get_recipe_book` | Get book details with member list | `api.v1.recipe_book.GetRecipeBook` |
| `create_recipe_book` | Create a new recipe book | `api.v1.recipe_book.CreateRecipeBook` |

### Shopping Lists (6)
| Tool | Description | Wraps |
|------|-------------|-------|
| `list_shopping_lists` | List user's shopping lists | `api.v1.shopping_list.ListShoppingLists` |
| `get_shopping_list` | Get shopping list with all items | `api.v1.shopping_list.GetShoppingList` |
| `create_shopping_list` | Create a new shopping list | `api.v1.shopping_list.CreateShoppingList` |
| `add_shopping_list_item` | Add an item to a shopping list | `api.v1.shopping_list.AddShoppingListItem` |
| `update_shopping_list_item` | Check/uncheck or update a shopping list item | `api.v1.shopping_list.UpdateShoppingListItem` |
| `populate_from_recipe` | Add all recipe ingredients to a shopping list | `api.v1.shopping_list.PopulateFromRecipe` |

### Meal Planning (3)
| Tool | Description | Wraps |
|------|-------------|-------|
| `list_meal_events` | List upcoming meal events (calendar view) | `api.v1.meal_event.ListMealEvents` |
| `create_meal_event` | Schedule a recipe to the meal calendar | `api.v1.meal_event.CreateMealEvent` |
| `get_meal_event` | Get meal event details | `api.v1.meal_event.GetMealEvent` |

### Search & Discovery (2)
| Tool | Description | Wraps |
|------|-------------|-------|
| `unified_search` | Search across recipes and users | `api.v1.search.UnifiedSearch` |
| `search_ingredients` | Find ingredients by name (fuzzy + semantic) | `api.v1.ingredient.SearchIngredients` |

## Story Map

| Story | Title | Est | Dependencies |
|-------|-------|-----|-------------|
| MCP.1 | MCP Infrastructure — Server, Auth, Mount | 1 day | None (foundational) |
| MCP.2 | Core Agent Tools (5 tools) | 0.5 day | MCP.1 |
| MCP.3 | Recipe CRUD + Ingredient Resolution (8 tools) | 1.5 days | MCP.1 |
| MCP.4 | Import & OCR Tools (3 tools) | 1 day | MCP.1 |
| MCP.5 | Recipe Books + Shopping Lists + Meal Planning (12 tools) | 1 day | MCP.1 |
| MCP.6 | Search Tools + Integration Testing (2 tools + tests) | 1 day | MCP.1-5 |

**Total: ~6 days**

**Parallel tracks:**
```
MCP.1 (foundation)
  ├→ MCP.2 (agent tools)
  ├→ MCP.3 (recipe CRUD + ingredient resolution)
  ├→ MCP.4 (import/OCR)
  ├→ MCP.5 (books + shopping + meals)
  └→ MCP.6 (search + integration tests) — depends on all above
```

---

## Story MCP.1: MCP Infrastructure — Server, Auth, Mount

As a developer,
I want a working MCP server mounted at `/mcp` with JWT authentication,
so that MCP clients can connect and call tools securely.

### Acceptance Criteria

1. `mcp[cli]>=1.9` added to `services/api/pyproject.toml` and lock file regenerated
2. FastMCP server instance created in `services/api/src/mcp/server.py` with name "Palateful" and helpful instructions string
3. Auth middleware in `services/api/src/mcp/auth.py` extracts Bearer JWT from Authorization header, verifies via `Auth0Verifier`, stores authenticated `User` and `Database` in Python `contextvars`
4. Auth middleware returns 401 JSON response for missing/invalid/expired tokens
5. MCP ASGI app mounted at `/mcp` in `services/api/src/main.py` — existing `/v1/*` routes unaffected
6. A test `get_profile` tool returns the authenticated user's name, email, and default recipe book — proving auth pipeline works end-to-end
7. Standardized `call_endpoint()` helper function wraps any `Endpoint` subclass: instantiates with user/database, calls `.run()`, returns JSON string on success or error message on failure
8. `contextvars` propagation works correctly when tools use `asyncio.to_thread()` via `copy_context().run()`

### Technical Approach

- Use `FastMCP` from `mcp.server.fastmcp` for high-level tool definition with `@mcp.tool()` decorators
- `StreamableHTTPSessionManager` produces the ASGI app for mounting
- Auth middleware is a Starlette middleware wrapping the MCP ASGI app — intercepts before MCP protocol processes
- Reuse `utils.services.auth0.get_auth0_verifier` for JWT verification (same as `dependencies.py`)
- Reuse `utils.services.database.Database` for DB session management
- `call_endpoint()` in `mcp/server.py`:
  ```python
  def call_endpoint(cls, *args, **kwargs):
      user = current_user.get()
      database = current_database.get()
      result = cls(database=database, user=user).run(*args, **kwargs)
      if result["success"]:
          return json.dumps(jsonable_encoder(result["data"]), default=str)
      return f"Error: {result['error_message']}"
  ```

### Key Files
- Create: `services/api/src/mcp/__init__.py`, `server.py`, `auth.py`, `tools/__init__.py`
- Modify: `services/api/src/main.py`, `services/api/pyproject.toml`
- Reuse: `libraries/utils/utils/services/auth0.py`, `services/api/src/dependencies.py`

---

## Story MCP.2: Core Agent Tools (5 tools)

As a user talking to Claude,
I want Claude to search my recipes, suggest new ones, add notes, check my pantry, and know my preferences,
so that Claude can be a knowledgeable cooking assistant without me opening the app.

### Acceptance Criteria

1. `search_recipes` tool: accepts `query` (required), `max_results`, `max_cook_time`, `pantry_match` — returns recipes with relevance scores, ingredients, and cook times
2. `suggest_recipe` tool: accepts `ingredients` (required), `cuisine`, `meal_type`, `dietary_restrictions`, `difficulty` — returns AI-generated recipe with name, description, ingredients, steps
3. `add_note_to_recipe` tool: accepts `note_body` (required), `recipe_id` or `recipe_name` — creates note, returns confirmation with recipe name
4. `get_pantry` tool: accepts `include_expired`, `expiring_within_days`, `category` — returns pantry items sorted by expiration
5. `get_user_preferences` tool: returns dietary restrictions, cuisine preferences, cooking level, household size
6. All 5 tools visible in MCP tool listing and callable with valid JWT
7. Each tool returns meaningful error messages (not stack traces) on failure
8. Tool descriptions are clear, specific, and guide the LLM on when/how to use each tool

### Technical Approach

- Each tool wraps existing `BaseTool.execute(db, user_id, **kwargs)` from `libraries/agent/agent/tools/`
- Since agent tools use sync SQLAlchemy, wrap calls in `asyncio.to_thread()` with `copy_context()`
- Tool descriptions should be product-copy quality (e.g., "Search your recipe collection by ingredients, cuisine, or any natural language query. Returns the most relevant matches with ingredients and cook times.")
- Register all tools in `mcp/tools/__init__.py`

### Key Files
- Create: `services/api/src/mcp/tools/pantry.py`, `user.py`, initial `recipes.py` (search, suggest, add_note)
- Reuse: `libraries/agent/agent/tools/recipes.py`, `pantry.py`, `preferences.py`

---

## Story MCP.3: Recipe CRUD + Ingredient Resolution (8 tools)

As a user talking to Claude,
I want Claude to create, read, update, delete, and organize my recipes using ingredient names (not database IDs),
so that I can manage my entire recipe collection through natural conversation.

### Acceptance Criteria

1. `get_recipe` tool: accepts `recipe_id` — returns full recipe with ingredients (names + quantities), steps, notes, tags, vibes, times
2. `list_recipes` tool: accepts `book_id` (optional, defaults to user's `default_recipe_book_id`), `limit`, `offset`, `search` — returns paginated recipe list with summary info
3. `create_recipe` tool: accepts `name` (required), `description`, `servings`, `prep_time`, `cook_time`, `tags`, `ingredients` (list of `{name, quantity, unit, notes?, is_optional?}`), `steps` (list of `{instruction, active_time_minutes?, wait_time_minutes?}`), `book_id` (optional, defaults to user's default book) — creates recipe with full ingredient name resolution
4. **Ingredient resolution layer**: for each ingredient name string, fuzzy-searches existing ingredients via `pg_trgm` (similarity >= 0.85 = auto-match), auto-creates new `Ingredient` if no match found — user never needs to know ingredient UUIDs
5. `update_recipe` tool: accepts `recipe_id` and any updatable fields — partial update supported
6. `delete_recipe` tool: accepts `recipe_id` — soft-deletes (archives) the recipe
7. `toggle_favorite` tool: accepts `recipe_id` — toggles favorite status, returns new state
8. `list_favorites` tool: returns user's favorited recipes
9. `fork_recipe` tool: accepts `recipe_id`, optional `destination_book_id` (defaults to user's default book) — creates an independent copy

### Technical Approach

- Ingredient resolution function in `mcp/tools/recipes.py`:
  ```
  resolve_ingredient(name, database) -> ingredient_id:
    1. Search via SearchIngredients (fuzzy pg_trgm)
    2. If top result similarity >= 0.85 → return that ID
    3. Else → CreateIngredient(canonical_name=name) → return new ID
  ```
- `create_recipe` builds `CreateRecipe.Params` with resolved `ingredient_id`s, delegates to `CreateRecipe.run()`
- `list_recipes` defaults `book_id` to `user.default_recipe_book_id` when not provided
- All tools use standardized `call_endpoint()` from MCP.1

### Key Files
- Expand: `services/api/src/mcp/tools/recipes.py`
- Reuse: `services/api/src/api/v1/recipe/create_recipe.py`, `get_recipe.py`, `update_recipe.py`, `delete_recipe.py`, `toggle_favorite.py`, `list_favorites.py`, `fork_recipe.py`
- Reuse: `services/api/src/api/v1/ingredient/search_ingredients.py`, `create_ingredient.py`

---

## Story MCP.4: Import & OCR Tools (3 tools)

As a user talking to Claude,
I want to tell Claude "import this recipe from [URL/text/photo]" and have it handle the full pipeline,
so that I can add recipes from any source through conversation.

### Acceptance Criteria

1. `import_recipe` tool: accepts `source_type` ("url", "text", "photo"), `url` (for URL imports), `text` (for text imports), `image_base64` (for server-side OCR), `additional_context` (optional user notes to enrich extraction), `book_id` (optional, defaults to user's default) — returns `{job_id, status, message}` immediately
2. For `source_type: "url"`: delegates to `StartImport` with URL, kicks off scraping pipeline
3. For `source_type: "text"`: delegates with raw text + `additional_context` appended. This is the primary path for Claude-assisted OCR (Claude reads the image, extracts text, sends it here)
4. For `source_type: "photo"`: accepts `image_base64`, runs through server-side OCR pipeline (AWS Batch), returns job_id for async polling
5. `get_import_status` tool: accepts `job_id` — returns job status, item count breakdown, and per-item details (name, status, error if failed)
6. `approve_import` tool: accepts `item_id` — approves a pending import item, triggers recipe creation, returns created recipe summary
7. Tool descriptions clearly explain the async pattern: "This starts the import process and returns immediately. Use get_import_status to check progress. When items show 'awaiting_review', use approve_import to finalize."
8. Error cases handled: invalid URL format, empty text, oversized image, job not found

### Technical Approach

- `import_recipe` maps parameters to `StartImport.Params` format:
  - `url` → `source_type="url", url=url`
  - `text` → `source_type="text", raw_text=text + "\n\nAdditional context: " + additional_context`
  - `photo` → `source_type="photo", ocr_texts=[image_text]` (if pre-extracted) or trigger parser batch
- For photo with `image_base64`: upload to S3 via presigned URL, create parser batch, return job_id
- `get_import_status` combines `GetImportJob` + `ListImportItems` into a single response
- `approve_import` wraps `ApproveImportItem`

### Key Files
- Create: `services/api/src/mcp/tools/import_tools.py`
- Reuse: `services/api/src/api/v1/import_job/start_import.py`, `get_import_job.py`, `list_import_items.py`, `approve_import_item.py`
- Reuse: `services/api/src/api/v1/parser/get_upload_url.py` (for S3 presigned URLs)

---

## Story MCP.5: Recipe Books + Shopping Lists + Meal Planning (12 tools)

As a user talking to Claude,
I want Claude to manage my recipe books, shopping lists, and meal calendar,
so that I can plan my entire kitchen workflow through conversation.

### Acceptance Criteria

**Recipe Books (3 tools):**
1. `list_recipe_books` tool: returns user's recipe books with member counts and recipe counts
2. `get_recipe_book` tool: accepts `book_id` — returns book details including member list and roles
3. `create_recipe_book` tool: accepts `name`, optional `description` — creates book, returns details

**Shopping Lists (6 tools):**
4. `list_shopping_lists` tool: returns user's shopping lists with item counts and checked status
5. `get_shopping_list` tool: accepts `list_id` (optional, defaults to user's `default_shopping_list_id`) — returns list with all items grouped by category
6. `create_shopping_list` tool: accepts `name` — creates list, returns details
7. `add_shopping_list_item` tool: accepts `list_id` (optional, defaults to default), `name`, optional `quantity`, `unit`, `category` — adds item
8. `update_shopping_list_item` tool: accepts `list_id`, `item_id`, optional `is_checked`, `quantity` — updates item (primary use: check/uncheck)
9. `populate_from_recipe` tool: accepts `list_id` (optional, defaults to default), `recipe_id`, optional `scale_factor` — adds all recipe ingredients to the list

**Meal Planning (3 tools):**
10. `list_meal_events` tool: accepts optional `start_date`, `end_date` (ISO format), `meal_type`, `limit` — returns upcoming meals with recipe info
11. `create_meal_event` tool: accepts `title`, `scheduled_at` (ISO datetime), `meal_type` ("breakfast"/"lunch"/"dinner"/"snack"), optional `recipe_id` — schedules meal
12. `get_meal_event` tool: accepts `event_id` — returns event details with recipe and participants

### Technical Approach

- Each tool wraps existing endpoint via `call_endpoint()`
- Shopping list tools default `list_id` to `user.default_shopping_list_id` for convenience
- `populate_from_recipe` is high-value — lets Claude say "I've added all the ingredients for that chicken parmesan to your shopping list"
- Meal event tools use ISO 8601 datetime strings for `scheduled_at`

### Key Files
- Create: `services/api/src/mcp/tools/recipe_books.py`, `shopping.py`, `meal_planning.py`
- Reuse: All corresponding endpoint handlers in `services/api/src/api/v1/`

---

## Story MCP.6: Search Tools + Integration Testing (2 tools + tests)

As a developer,
I want search tools and a comprehensive test suite proving the MCP server works end-to-end,
so that we can ship with confidence and catch regressions.

### Acceptance Criteria

**Search Tools (2):**
1. `unified_search` tool: accepts `query`, optional `limit` — searches across recipes and users, returns categorized results
2. `search_ingredients` tool: accepts `query`, optional `limit` — fuzzy + semantic ingredient search, useful for "do I have X?" type queries

**Integration Tests:**
3. Auth tests: valid JWT → 200, expired JWT → 401, missing JWT → 401, malformed JWT → 401
4. Tool listing test: connect via MCP client, verify all 28 tools are listed with correct names and descriptions
5. Recipe CRUD flow: `create_recipe` (with ingredient name resolution) → `get_recipe` → `update_recipe` → `delete_recipe`
6. Import flow: `import_recipe` (URL) → `get_import_status` (poll until complete) → `approve_import`
7. Shopping list flow: `create_shopping_list` → `populate_from_recipe` → `get_shopping_list` → `update_shopping_list_item` (check off)
8. Agent tool test: `search_recipes` returns results for known recipe, `get_pantry` returns pantry items
9. Error handling test: `get_recipe` with nonexistent ID returns error message (not 500/traceback)
10. All tests pass in CI via `npx nx run api:test`

### Technical Approach

- Test directory: `services/api/tests/mcp/`
- Use `httpx.AsyncClient` with ASGI transport to test MCP endpoints directly
- For MCP protocol tests, use the `mcp` client SDK to connect programmatically
- Mock Auth0 verification in tests (existing test patterns in the codebase)
- Test the `call_endpoint()` helper independently with mock endpoints

### Key Files
- Create: `services/api/src/mcp/tools/search.py`
- Create: `services/api/tests/mcp/__init__.py`, `test_auth.py`, `test_tools.py`, `test_flows.py`
