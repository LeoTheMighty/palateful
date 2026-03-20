# Story Perf.1: Backend Cost & Query Optimization

Status: done

## Story

As a platform operator,
I want to minimize unnecessary AI API costs and database query overhead,
so that the app scales efficiently and operating costs stay low.

## Acceptance Criteria

1. **Eager loading in UnifiedSearch** — The exact search tier eager-loads `Recipe.ingredients` via `selectinload` instead of triggering N lazy-load queries when serializing ingredient names. Verified by confirming no additional queries fire per recipe result.
2. **Eager loading in PopulateFromRecipe** — `populate_from_recipe.py` eager-loads recipe ingredients+ingredient relationship in a single query instead of lazy loading per ingredient.
3. **Embedding generation skipped when content unchanged** — `generate_recipe_embedding` is only called in `update_recipe.py` when the actual text values of name/description/tags differ from the existing values (not just when the keys are present in the update payload).
4. **Token cap checked per tool call** — `agent_loop.py` re-checks the monthly token cap before each tool resolution round, preventing users from exceeding the cap by 20%+ via multi-tool conversations.
5. **Tests pass** — All 1142+ backend tests pass. Coverage stays at 100%.

## Tasks / Subtasks

- [ ] Task 1: Eager load ingredients in UnifiedSearch exact tier (AC: 1)
  - [ ] In `unified_search.py` `_search_my_recipes()`: add `.options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient))` to the query
  - [ ] In `unified_search.py` `_search_public_recipes()`: add same eager loading
  - [ ] Verify ingredient serialization at line ~218 no longer triggers lazy loads

- [ ] Task 2: Eager load in PopulateFromRecipe (AC: 2)
  - [ ] In `populate_from_recipe.py`: add `selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient)` to the recipe query

- [ ] Task 3: Skip embedding regen when values unchanged (AC: 3)
  - [ ] In `update_recipe.py`: before calling `generate_recipe_embedding`, compare `recipe.name` vs `params.name` (if provided), `recipe.description` vs `params.description`, `recipe.tags` vs `params.tags`
  - [ ] Only call embedding generation when at least one value actually differs

- [ ] Task 4: Re-check token cap before tool resolution rounds (AC: 4)
  - [ ] In `agent_loop.py`: inside the `while response.finish_reason == "tool_calls"` loop, re-check `get_user_monthly_tokens()` before executing tool calls
  - [ ] If cap exceeded mid-conversation, yield a warning event and break the tool loop

- [ ] Task 5: Tests (AC: 5)
  - [ ] Add/update tests to verify new behavior
  - [ ] Run full suite — all tests pass at 100% coverage

## Dev Notes

### What Already Exists — Already Partially Fixed

**SentenceTransformer singleton** — Already fixed in previous commit. `_get_embedding_model()` with `@lru_cache(maxsize=1)` caches the model.

**Database indexes** — Already added in migration `n4o5p6q7r8s9`: `recipe_book_users.user_id`, `recipe_ingredients.ingredient_id`, `recipes.recipe_book_id`, `shopping_list_items.ingredient_id`.

**PopulateFromCalendar eager loading** — Already fixed in previous commit.

### UnifiedSearch Eager Loading

Current code (`unified_search.py` `_search_my_recipes` method):
```python
query = (
    self.db.query(Recipe, RecipeBook.name.label("book_name"))
    .join(RecipeBook, Recipe.recipe_book_id == RecipeBook.id)
    .join(RecipeBookUser, RecipeBook.id == RecipeBookUser.recipe_book_id)
    # NO selectinload — lazy loads when accessing recipe.ingredients
)
```

Fix: add `.options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient))`.

### PopulateFromRecipe

File: `services/api/src/api/v1/shopping_list/populate_from_recipe.py`
The recipe query needs eager loading of ingredients relationship.

### Embedding Diff Check

Current (`update_recipe.py` line 103-110):
```python
embedding_fields = {"name", "description", "tags"}
if updates and embedding_fields.intersection(updates.keys()):
    embedding = generate_recipe_embedding(...)
```

This triggers on ANY update that includes name/description/tags keys, even if the value is identical. Fix: compare actual values.

### Token Cap Re-check

Current (`agent_loop.py` line 89-170): the `while` loop executes tool calls without re-checking the cap. A multi-tool conversation could consume 5000+ tokens beyond the cap.

### File Locations

- `services/api/src/api/v1/search/unified_search.py`
- `services/api/src/api/v1/shopping_list/populate_from_recipe.py`
- `services/api/src/api/v1/recipe/update_recipe.py`
- `services/api/src/api/v1/chat/agent_loop.py`
- `services/api/tests/test_search.py`
- `services/api/tests/test_chat.py`
- `services/api/tests/test_recipe.py`

### References

- Performance audit findings (session context)
- SentenceTransformer singleton [Source: libraries/agent/agent/tools/recipes.py:14-18]
- Database indexes migration [Source: services/migrator/migrations/versions/20260320000002_add_performance_indexes.py]
- PopulateFromCalendar eager load [Source: services/api/src/api/v1/shopping_list/populate_from_calendar.py:80-93]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
