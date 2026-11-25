---
hash: storesec
type: debug
created: 2026-09-22T09:00:00-06:00
title: "GET /shopping-lists/store-sections is unreachable — shadowed by /shopping-lists/{list_id} declared earlier"
from: debug/debug-cartdec-2026-09-22T09:00-shopping-cart-decimal-quantity-crash.md
spawned: []
status: ready
owner: null
branch: null
---

## Goal

In `services/api/src/routers/v1/shopping_list_router.py`,
`GET /shopping-lists/{list_id}` (line 81) is declared before
`GET /shopping-lists/store-sections` (line 196). FastAPI matches the first
route that fits, so a request to `/shopping-lists/store-sections` is served by
`get_shopping_list` with `list_id="store-sections"`. The store-sections
endpoint can never run.

Found while root-causing debug-cartdec; **not** the cart failure — the app
never calls it (measured: no reference in `app/lib`). Latent: the moment a
client calls it, it gets a list-not-found instead of store sections.

## Acceptance criteria

1. `GET /v1/shopping-lists/store-sections` reaches its own handler (declare it
   before the parameterised route, or give it a non-colliding path).
2. A test that calls it and asserts the store-sections response shape — FAILS
   on current `main`.
3. Audit the router for any other literal path declared after a
   parameterised sibling.

## Status log

- 2026-09-22T09:00-06:00 — filed from debug-cartdec. Measured by reading route
  declaration order; not exercised against the running API.
