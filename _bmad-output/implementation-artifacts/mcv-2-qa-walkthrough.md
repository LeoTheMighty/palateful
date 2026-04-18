# QA Walkthrough: mcv-2

Backend CRUD. No UI path yet — smoke-test via `httpie` / `curl`.

## Setup

```
docker compose up -d
curl -X POST 'http://localhost:8000/v1/recipe-books' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"QA Dinners"}'
# Note the returned book_id.
# Create two recipes via the existing endpoints…
```

## Happy-path flow

1. **Create a Meal.**
   ```
   POST /v1/recipe-books/{book_id}/meals
     { "name": "Kale Salad Meal",
       "description": "tonight",
       "component_recipe_ids": ["<r1>", "<r2>"] }
   ```
   Expect 201 + Meal response with 2 hydrated components (available=true,
   book_name populated, order_index 0 and 1).

2. **Get it.** `GET /v1/meals/{id}` — 200, same shape.

3. **List it in the book.** `GET /v1/recipe-books/{book_id}/meals` —
   1 item; `component_count=2`; up to 4 `component_image_urls`.

4. **List across books.** `GET /v1/meals` — returns the same Meal if
   the user reads at least one book containing it.

5. **Rename.** `PATCH /v1/meals/{id} { "name": "Renamed" }` — 200.

6. **Archive.** `POST /v1/meals/{id}/archive` — 200, `archived_at` set.
   A second archive → 400 (`MEAL_ALREADY_ARCHIVED`).

7. **Restore.** `POST /v1/meals/{id}/restore` — 200. Second restore →
   400 (`MEAL_NOT_ARCHIVED`).

## Error-state coverage

- `component_recipe_ids=["r1"]` → 422 (Pydantic min_length).
- `component_recipe_ids=["r1","r1"]` → 422 (validator).
- Member of book but component is from a non-member book → 404
  (`MEAL_COMPONENT_UNREADABLE`).
- `viewer` role on the book → 403 on create/patch/archive/restore.
- No membership → 403 on GET, 403 on list.
- Archive a recipe used in a Meal, then GET the Meal — the component
  row appears with `available=false` + `last_known_name` populated,
  no 500.

## Audit trail

After archive + restore cycle:
```
docker compose exec db psql -U palateful -d palateful -c \
  "SELECT error_type, error_message FROM error_logs WHERE service='audit' ORDER BY created_at DESC LIMIT 4"
```
Expect two rows per cycle (`MealArchive`, `MealRestore`).

## Automated coverage

`npx nx run api:test` — 1857 tests pass with 100% coverage. The new
test files are `test_meal_router.py` (HTTP matrix) and
`test_meal_service.py` (service unit tests).
