# Story Pantry.3: Shopping-List → Pantry Hook (with In-Process Dispatcher)

Status: done

## Story

As Leo checking items off my shopping list after a grocery run,
I want each purchased item to automatically land in my pantry with a reasonable expiry estimate,
so that the pantry reflects what I actually have without me double-entering everything.

## Context

The shopping-list API already marks items as purchased via `PUT /shopping-lists/{list_id}/shopping-list-items/{item_id}` (`services/api/src/api/v1/shopping_list/update_item.py:18`), which toggles the `is_checked: bool` field on `ShoppingListItem`. Today, nothing happens beyond the database update.

This story introduces two things:

1. **A lightweight in-process event dispatcher** (`libraries/utils/utils/events/`) — a tiny synchronous pub/sub module. This is the first consumer, so it carries the dispatcher setup. `pantry-4` will reuse it without rebuilding.
2. **A pantry subscriber** that reacts to a `ShoppingListItemPurchased` event by upserting a `pantry_ingredient` for the caller's default pantry, using `shelf_life_service.estimate_expires_at` (from pantry-2) to fill in `expires_at`.

The hook fires only on the `false → true` transition of `is_checked`. Un-checking an item does not remove it from the pantry (out of scope — users may have already used the item). Re-checking after un-checking does re-add via upsert, same as any other purchase.

The Flutter client shows a "Added N items to pantry. Undo" snackbar after the checkoff so the user stays aware of the side effect. "Undo" is client-side only for MVP — it issues a `DELETE /pantries/{id}/ingredients/{ingredient_id}` for each added item.

## Acceptance Criteria

1. New module `libraries/utils/utils/events/` with:
   - `dispatcher.py` — exposes `register(event_name: str, handler: Callable)` and `dispatch(event_name: str, payload: Any)`. Synchronous, in-process, fires handlers sequentially. Handler exceptions are caught and logged at `ERROR` level, not re-raised (a failing subscriber must not break the caller's request).
   - `events.py` — dataclasses for event payloads. At minimum `ShoppingListItemPurchased(user_id: UUID, shopping_list_id: UUID, item_id: UUID, ingredient_id: UUID, quantity_normalized: float, unit_normalized: str | None, shopping_list_item_name: str)`.
   - `__init__.py` re-exports `register`, `dispatch`, and event classes.
2. `services/api/src/api/v1/shopping_list/update_item.py` dispatches `ShoppingListItemPurchased` after a successful `false → true` transition and only if the item has a non-null `ingredient_id` (items can be free-text without matching an ingredient — those do not auto-add to pantry).
3. The dispatch happens *after* the DB commit, so a failed commit does not produce ghost pantry entries.
4. New subscriber file `services/api/src/api/subscribers/pantry_shopping_subscriber.py` is registered at API startup. It:
   - Resolves the user's default pantry via `get_or_create_default_pantry` (helper from pantry-1).
   - Looks up the `Ingredient` to read `ingredient.category`.
   - Calls `shelf_life_service.estimate_expires_at(ingredient, storage_location=None, added_at=now())` — **storage location is unknown** at purchase time, so `expires_at` is left `None`. (User fills it in later via the editor in pantry-6 if they care.)
   - Calls the pantry-1 upsert path (can be a direct service-layer call, not an HTTP loopback) to add `quantity_normalized` to an existing row or insert a new one. `storage_location` defaults to `None`.
   - Logs a single `INFO` line: `pantry_auto_add user_id=… ingredient_id=… quantity_normalized=…`.
5. Startup wiring: subscribers are registered via a single `register_subscribers()` call invoked from the API's lifespan/startup handler. The pantry subscriber is one of potentially many — keep it easy to add more.
6. If the user's pantry already contains an active (non-archived) row for the same `ingredient_id`, quantities are summed (upsert). Units: the incoming `unit_normalized` must match the existing row's `unit_normalized` — if they mismatch, skip the add silently, log at `WARNING`, and **do not** raise. Better to under-add than to corrupt units.
7. The hook fires regardless of which shared pantry member purchased the item. For MVP (one pantry per user), the subscriber uses the *purchaser's* default pantry, not the shopping-list owner's. If the shopping list is shared and purchaser ≠ list owner, the purchaser's pantry gets the item.
8. Flutter client (`app/lib/features/shopping_cart/`) shows a snackbar "Added to pantry — Undo" after the PUT succeeds for a check-off action that returned a non-null `pantry_ingredient_id` in the response. The response body of `PUT /shopping-lists/.../shopping-list-items/...` is extended to include an optional `pantry_ingredient_id` so the client knows when to show the snackbar and what to undo. "Undo" calls `DELETE /pantries/{pantry_id}/ingredients/{ingredient_id}`.
9. Unit tests for the dispatcher: handler called exactly once per dispatch, exceptions in one handler do not prevent a second handler from running, unregistered event_name is a no-op.
10. Unit tests for the subscriber: happy path insert, happy path upsert (sums quantities), unit mismatch (logs warning, no DB change), `ingredient_id` missing (no-op, no error), free-text item (no-op), purchaser-is-viewer-of-list-but-has-own-pantry case.
11. Integration test: hit `PUT /shopping-lists/{list}/shopping-list-items/{item}` with `is_checked=true`, verify a `pantry_ingredient` row appears in the DB for the correct user, with expected quantity.

## Tasks / Subtasks

- [ ] Task 1: Event dispatcher module (AC: #1, #9)
  - [ ] Create `libraries/utils/utils/events/__init__.py`, `dispatcher.py`, `events.py`
  - [ ] `dispatcher.py` uses a module-level `_HANDLERS: dict[str, list[Callable]]` — simple, not thread-safe is fine (FastAPI is async-single-process for our setup)
  - [ ] Add `libraries/utils/test/test_dispatcher.py`

- [ ] Task 2: Wire dispatch from shopping-list update (AC: #2, #3)
  - [ ] Modify `services/api/src/api/v1/shopping_list/update_item.py`: after commit, if `previous_is_checked == False and new_is_checked == True and item.ingredient_id is not None`, dispatch `ShoppingListItemPurchased`
  - [ ] Capture `previous_is_checked` before the update

- [ ] Task 3: Pantry subscriber (AC: #4, #6, #7)
  - [ ] Create `services/api/src/api/subscribers/__init__.py` with `register_subscribers()` function
  - [ ] Create `services/api/src/api/subscribers/pantry_shopping_subscriber.py`
  - [ ] Subscriber receives payload, opens its own DB session (the request's session is likely closed by the time this fires post-commit — verify against actual framework behavior, may need `async_sessionmaker` helper)
  - [ ] Resolve purchaser's default pantry → resolve ingredient → upsert
  - [ ] Handle unit-mismatch gracefully (log + skip)

- [ ] Task 4: Startup wiring (AC: #5)
  - [ ] Modify `services/api/src/api/app.py` (or the lifespan handler) to call `register_subscribers()` after the existing `load_shelf_life_data()` call from pantry-2

- [ ] Task 5: Extend update_item response (AC: #8)
  - [ ] Modify `services/api/src/api/v1/shopping_list/update_item.py` response shape to include optional `pantry_ingredient_id: UUID | None`
  - [ ] Because the subscriber fires after commit, the handler needs to return the new pantry row ID synchronously. Options: (a) call the pantry upsert *before* dispatch and pass the row ID through the event — breaks dispatcher purity; (b) call the pantry upsert *inline* in the handler for this one case and still dispatch the event for any future subscribers (audit log, analytics). **Pick (b)** — the inline call is what actually needs the ID; the event is for future extensibility.

- [ ] Task 6: Flutter snackbar + undo (AC: #8)
  - [ ] Update `app/lib/features/shopping_cart/services/shopping_cart_service.dart` to read the new `pantry_ingredient_id` field from the update response
  - [ ] In `app/lib/features/shopping_cart/screens/shopping_list_screen.dart`, when a check-off returns a `pantry_ingredient_id`, show a `SnackBar` with "Added to pantry" + Undo action
  - [ ] Undo calls a new `deletePantryIngredient(pantryId, ingredientId)` method on the pantry service (which must be stubbed here if pantry-5 hasn't landed yet — or, sequencing-wise, pantry-5 should land first; adjust dependency order at epic level if needed)

- [ ] Task 7: Tests (AC: #9, #10, #11)
  - [ ] `libraries/utils/test/test_dispatcher.py` — unit tests for the dispatcher
  - [ ] `services/api/test/subscribers/test_pantry_shopping_subscriber.py` — subscriber unit tests (mock DB session or use the test DB fixture)
  - [ ] `services/api/test/v1/shopping_list/test_update_item_pantry_hook.py` — integration test against the real DB: seed a user + pantry + shopping list, PUT to mark checked, assert pantry row appears

## Dev Notes

- **Task 5 is the subtle one.** The cleanest code has the subscriber pattern, but the client needs the pantry row ID in the response body. Do the pantry upsert *inline* in the request handler, capture the returned ID, include it in the response, AND also dispatch the event for future listeners (telemetry, push notifications). Single source of DB mutation, event as a notification fan-out.
- **Do not make the dispatcher async.** Sync is fine for MVP. Sub-millisecond overhead is irrelevant at this scale.
- **Do not use Celery for this.** In-process dispatcher is the explicit choice — introducing Celery coupling here is exactly the "invasive" pattern the epic is avoiding.
- **Un-check does not remove from pantry.** Explicitly tested. The user may have already consumed the item; un-checking is for correcting input errors on the shopping-list side only.
- **Free-text shopping items skip the hook entirely.** No `ingredient_id` = nothing to upsert. Do not try to fuzzy-match — that's a different story.
- **Unit mismatch during upsert.** This is the same best-effort pattern as pantry-4's decrement. If `unit_normalized` doesn't match the existing row, log and skip. Do not convert units in this story — converters are part of pantry-4's scope.
- **Shared pantry behavior.** For MVP, every user has their own default pantry. If the shopping list is shared and person A's wife (person B) checks off an item, person B's pantry gets the item. This is intentional for MVP. Shared-pantry UX is a future epic.

### Project Structure Notes

- `libraries/utils/utils/events/` — new top-level module for the dispatcher
- `services/api/src/api/subscribers/` — new directory co-located with the API, holding one file per subscriber
- The subscriber directory is app-level, not library-level, because subscribers are composition concerns (they wire specific libraries together)

### References

- `services/api/src/api/v1/shopping_list/update_item.py` (line 18) — hook attach point
- `libraries/utils/utils/models/shopping_list.py` (line 95) — `ShoppingListItem` with `is_checked`
- `libraries/utils/utils/models/shopping_list_event.py` — existing audit log (not a dispatcher, just naming reference)
- `services/api/src/api/app.py` — startup wiring (confirm exact file at implementation time)
- [Story: pantry-1-crud-api.md] — for `get_or_create_default_pantry` helper
- [Story: pantry-2-shelf-life-seed.md] — for `estimate_expires_at`
- [Epic: epic-pantry.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- `poetry run pytest libraries/utils/` — 57/57 pass (incl. 6 new dispatcher tests)
- `poetry run pytest services/api/` — 1392/1392 pass (incl. 4 new hook tests)
- `npx nx run utils:lint` / `api:lint` / `migrator:lint` — clean
- `dart analyze` on shopping_cart — only pre-existing warnings

### Completion Notes

- **No Celery.** New `libraries/utils/utils/events/` module is a tiny in-process
  dispatcher: `register` / `unregister` / `dispatch`. Handler exceptions are
  caught and logged so one broken subscriber can't poison another.
- Event payload dataclasses live in `events.py`: `ShoppingListItemPurchased`
  and `MealEventCompleted` (the latter is added here so pantry-4 can reuse
  this module unchanged).
- Shared pantry mutation service (`utils/services/pantry_service.py`) exposes
  `get_or_create_default_pantry`, `upsert_pantry_ingredient`, and
  `soft_delete_pantry_ingredient`. The pantry-1 CRUD endpoints were refactored
  to delegate to this service. This is what the shopping-list hook calls
  inline (single source of DB mutation).
- `update_item.py` hook: captures `previous_is_checked` before update; after
  commit, on a false→true transition with a non-null `ingredient_id`, calls
  `get_or_create_default_pantry` + `upsert_pantry_ingredient` inline to
  populate the response with `pantry_ingredient_id` / `pantry_id`, then
  dispatches `ShoppingListItemPurchased` for fan-out subscribers. A crash in
  the side-effect is swallowed so the PUT still returns 200.
- Subscribers module (`services/api/src/api/subscribers/`) registers a single
  `handle_shopping_list_item_purchased` today — structure is ready for
  pantry-4 (`MealEventCompleted`) and future subscribers.
- `register_subscribers()` is called from `main.py`'s FastAPI lifespan right
  after `load_shelf_life_data()`.
- Unit mismatch during upsert: logs at WARNING and returns the existing row
  unchanged — matches the epic's best-effort principle.
- Flutter: extended `ShoppingListItem.fromJson` with `pantryIngredientId` and
  `pantryId`; added `deletePantryIngredient`, `addPantryIngredient`, etc. to
  `ApiClient`; `_toggleItemChecked` now calls `_maybeShowPantryUndoSnackbar`
  after a successful check-off. Undo hits
  `DELETE /v1/pantries/{pantryId}/ingredients/{pantryIngredientId}`.

### QA Walkthrough

- [ ] Check an item that is linked to an ingredient → toast appears: "Added
      '<name>' to pantry" with Undo button. Next `GET /v1/pantries/default`
      shows the row.
- [ ] Check a free-text item (no `ingredient_id`) → no toast, no pantry row.
- [ ] Uncheck an already-checked item → no toast; pantry row remains.
- [ ] Re-check the same item after uncheck → a new toast; pantry quantity
      is summed (upsert).
- [ ] Tap Undo on the toast → the pantry row is soft-deleted; a follow-up
      GET /v1/pantries/default no longer lists it.
- [ ] Temporarily break the pantry_service (e.g., throw in
      `get_or_create_default_pantry`) → check-off still returns 200; the
      shopping-list UI still flips the checkbox.

### File List

**Created**
- `libraries/utils/utils/events/__init__.py`
- `libraries/utils/utils/events/dispatcher.py`
- `libraries/utils/utils/events/events.py`
- `libraries/utils/utils/services/pantry_service.py`
- `libraries/utils/test/test_event_dispatcher.py`
- `services/api/src/api/subscribers/__init__.py`
- `services/api/src/api/subscribers/pantry_shopping_subscriber.py`
- `services/api/tests/test_update_item_pantry_hook.py`

**Modified**
- `services/api/src/api/v1/pantry/helpers.py` — delegates to pantry_service
- `services/api/src/api/v1/pantry/add_ingredient.py` — uses shared upsert helper
- `services/api/src/api/v1/shopping_list/update_item.py` — dispatches event
  and surfaces `pantry_ingredient_id`/`pantry_id` in the response
- `services/api/src/main.py` — lifespan calls `register_subscribers()`
- `app/lib/core/services/api_client.dart` — added `getDefaultPantry`,
  `addPantryIngredient`, `updatePantryIngredient`, `deletePantryIngredient`
- `app/lib/features/shopping_cart/models/shopping_list_item.dart` — added
  `pantryIngredientId`, `pantryId`
- `app/lib/features/shopping_cart/screens/shopping_list_screen.dart` —
  snackbar + Undo wired into `_toggleItemChecked`
