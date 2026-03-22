# Story Defaults.1: Default Shopping List — Backend & State

Status: complete

## Story

As a user,
I want the system to track my default shopping list,
so that "Add to Cart" actions can skip the list picker and go straight to my preferred list.

## Acceptance Criteria

1. `users` table has `default_shopping_list_id` (UUID FK, nullable, ON DELETE SET NULL) and `previous_shopping_list_id` (UUID FK, nullable, ON DELETE SET NULL)
2. `GET /me` response includes `default_shopping_list_id` and `previous_shopping_list_id`
3. `PUT /me/default-shopping-list` endpoint sets the default (and shifts old default to previous)
4. `GET /shopping-lists` response indicates which list is the default
5. When a user creates their first shopping list, it is automatically set as their default
6. Migration follows the exact pattern of `20260119000001_add_default_recipe_book_id.py`
7. Flutter state: `UserDefaultsProvider` exposes `defaultShoppingListId` and methods to set/restore

## Tasks / Subtasks

- [x] Task 1: Database migration (AC: #1, #6)
  - [x] Create migration adding `default_shopping_list_id` UUID FK to `users` table
  - [x] Add `previous_shopping_list_id` UUID FK to `users` table
  - [x] Both nullable, `ON DELETE SET NULL`, indexed
  - [x] Follow pattern from `20260119000001_add_default_recipe_book_id.py` exactly

- [x] Task 2: Update User model (AC: #2)
  - [x] Add `default_shopping_list_id` and `previous_shopping_list_id` to `libraries/utils/utils/models/user.py`
  - [x] Add relationships to ShoppingList

- [x] Task 3: Update GET /me endpoint (AC: #2)
  - [x] Include `default_shopping_list_id` and `previous_shopping_list_id` in response
  - [x] Update response schema if needed

- [x] Task 4: Create PUT /me/default-shopping-list endpoint (AC: #3)
  - [x] Accept `{ shopping_list_id: UUID | null }`
  - [x] When setting new default: move current default to `previous_shopping_list_id`
  - [x] When setting to null: clear both default and previous
  - [x] Validate the list exists and user has access

- [x] Task 5: Update GET /shopping-lists (AC: #4)
  - [x] Add `is_default: boolean` field to each list in the response
  - [x] Compare against user's `default_shopping_list_id`

- [x] Task 6: Auto-set default on first list creation (AC: #5)
  - [x] In `POST /shopping-lists` handler: if user has no default, auto-set the new list
  - [x] Also auto-set when creating via any flow (including onboarding)

- [x] Task 7: Flutter state management (AC: #7)
  - [x] Create or extend a provider to expose `defaultShoppingListId`
  - [x] Method: `setDefaultShoppingList(id)` — calls PUT endpoint, updates local state
  - [x] Method: `restorePreviousDefault()` — swaps previous back to default
  - [x] Sync with `GET /me` on app startup

## Dev Notes

- Exact migration template: `services/migrator/migrations/versions/20260119000001_add_default_recipe_book_id.py`
- User model: `libraries/utils/utils/models/user.py`
- GET /me: `services/api/src/api/v1/users/get_me.py`
- Shopping list router: `services/api/src/routers/v1/shopping_list_router.py`
- The `previous_shopping_list_id` enables the "pop back" pattern — when a temporary list is completed, the app can auto-restore the previous default

### References

- [Investigation: 05-shopping-list-default-cart.md]
- [Epic: epic-smart-defaults.md]
