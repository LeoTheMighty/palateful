# QA Walkthrough — aam-11 Recipe Book Domain Async

## Regression probes (manual QA if you have staging access)

Each of these exercises a handler that flipped `def` → `async def` in
this chunk. Expected outcome: response shapes byte-identical to
pre-migration; no latency regression > 20% on the observation window.

### 1. List + get

- [ ] Open the app → home → "Books" carousel loads (`GET /v1/recipe-books`).
- [ ] Tap a book → detail screen renders with recipes + members
  (`GET /v1/recipe-books/{id}`). `last_opened_at` updated (recency
  sort survives).

### 2. Create

- [ ] "New book" sheet → name "Test AAM-11" → Save → 201 response →
  shows up in list (`POST /v1/recipe-books`).

### 3. Update

- [ ] Edit the book from step 2 → change description → Save → 200
  response → new description surfaces in detail screen
  (`PUT /v1/recipe-books/{id}`).

### 4. Archive + restore

- [ ] Archive the book → gone from main list → appears under
  `/v1/recipe-books/archived` (`POST /v1/recipe-books/{id}/archive`).
- [ ] From archived list → restore → returns to main list
  (`POST /v1/recipe-books/{id}/restore`).

### 5. Member add + notification

- [ ] From a shared book (create a `is_shared=True` one if none exist)
  → invite a second user as "editor" → 200 response → activity feed
  shows "… joined …" on the owner side
  (`POST /v1/recipe-books/{id}/members`).
- [ ] The invited user receives a `RECIPE_BOOK_SHARED` push
  (foreground + background). Delivery path is the
  `notify_via_threadpool` bridge → sync `notify_book_shared` on a
  fresh `Database(db=SessionLocal())` — no async-pool contention.
- [ ] Invited user's own detail screen for that book now shows them
  as a member with role=editor.

### 6. Member role update

- [ ] As owner, change the invitee's role from editor → viewer → 200
  response; invitee now only sees the book as read-only
  (`PATCH /v1/recipe-books/{id}/members/{user_id}`).

### 7. Member remove

- [ ] Remove the invitee → 200 response; invitee loses access (book
  disappears from their list)
  (`DELETE /v1/recipe-books/{id}/members/{user_id}`).

### 8. Delete

- [ ] Delete a book owned solo → 200 response → book + cascaded
  recipes gone (`DELETE /v1/recipe-books/{id}`).

### 9. MCP

- [ ] Via chat: "list my recipe books" → the MCP `list_recipe_books`
  tool fires `await call_endpoint_async(ListRecipeBooks, ...)` and
  the response shape matches what Claude/GPT sees today.
- [ ] Via chat: "create a book called Snacks" → `create_recipe_book`
  tool runs; new book shows up in the UI.

### 10. WebSocket (no-touch regression guard)

- [ ] Open two clients on the same book → client A creates a recipe
  → client B sees `recipe_added` event within ~100ms. The WS route
  stays on the sync dep; no behavior change expected. Reconnect
  burst (close + reopen 5× in 2s) should still land cleanly.

## Automated tests

- `npx nx run api:test -- tests/test_recipe_book.py tests/test_recipe_book_members.py tests/test_recipe_book_notifications.py tests/test_recipe_book_websocket.py`
  — **110 passed**, 0 failed.
- Lint — `poetry run ruff check src/api/v1/recipe_book/ src/routers/v1/recipe_book_router.py src/mcp_server/tools/recipe_books.py tests/test_recipe_book.py tests/test_recipe_book_members.py` → All checks passed.

## Lazy-load audit (per every Phase 3 story)

Grep pattern for ORM attribute access on a row returned by a SELECT
(outside `selectinload` / `joinedload`):

```bash
rg "\\b(recipe_book|recipe|membership)\\.[a-z_]+" \
    services/api/src/api/v1/recipe_book/ --type py \
    | grep -v "selectinload\|joinedload\|\\.id\\b\\|\\.name\\b\\|\\.description\\b\\|\\.is_\\|\\.role\\b\\|\\.user_id\\b\\|\\.recipe_book_id\\b\\|\\.archived_at\\b\\|\\.created_at\\b\\|\\.updated_at\\b"
```

Result: no relationship-attribute dot-chain on the response path. Every
endpoint either queries via `select()` directly (list + get) or reads
scalar columns (`.id`, `.name`, etc.) that are always loaded. No
`MissingGreenlet` surface.

## Observation window

Window opens on commit landing; watch:

- `GET /v1/recipe-books` client-side p95 (`route_paint` event on home
  "Books" strip).
- `GET /v1/recipe-books/{id}` client-side p95 (`route_paint` on book
  detail route).
- `POST /v1/recipe-books/{id}/members` server-side p95 — new commit +
  threadpool hop adds bounded latency (~1-2ms p50), not a regression.

Any > 20% regression on an owned path → revert fef2223, investigate,
re-land.
