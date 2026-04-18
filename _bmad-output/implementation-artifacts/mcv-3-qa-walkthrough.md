# QA Walkthrough: mcv-3

Backend-only story. Smoke-test via `httpie` / `curl` after docker compose.

## Setup

Assume `$TOKEN` is a valid JWT and a Meal `$M` exists (via mcv-2's
create endpoint) with 2 component recipes.

## Happy paths

1. **Add a third recipe.**
   ```
   POST /v1/meals/$M/recipes  {"recipe_id":"<r3>"}
   ```
   201. Response includes the 3 components, order_index 0/1/2.

2. **Reorder.**
   ```
   POST /v1/meals/$M/reorder  {"recipe_ids":["<r3>","<r1>","<r2>"]}
   ```
   200. GET the Meal again → order is r3 / r1 / r2.

3. **Remove one.**
   ```
   DELETE /v1/meals/$M/recipes/<r3>
   ```
   200. Remaining components are 2.

4. **Remove another (would drop to 1).**
   ```
   DELETE /v1/meals/$M/recipes/<r1>
   ```
   422 `MEAL_MIN_COMPONENTS`.

5. **Favorite + un-favorite.**
   ```
   POST   /v1/meals/$M/favorite     → 201 { is_favorite: true }
   POST   /v1/meals/$M/favorite     → 201 (idempotent, no new row)
   DELETE /v1/meals/$M/favorite     → 200 { is_favorite: false }
   DELETE /v1/meals/$M/favorite     → 200 (idempotent)
   ```

## Error matrix

- Duplicate add: `POST /recipes { "recipe_id": "<r1>" }` → 409.
- Unreadable recipe: add from an unshared book → 404.
- Non-writer (`viewer` role): any mutation → 403. `favorite` still works.
- Reorder with the wrong set: returns 422 `MEAL_REORDER_MISMATCH`.
- Reorder with duplicates in payload: 422 schema.
- Reorder with 1 id: 422 schema.

## Automated coverage

`npx nx run api:test` — 1890 tests pass, 100% coverage. New tests in
`test_meal_components.py`.
