---
hash: cartdec
type: debug
created: 2026-09-22T09:00:00-06:00
title: "Shopping cart unusable for months: quantities serialized as JSON strings crash the app's parser; a May fix landed on a dead class"
from: debug/debug-btri01-2026-07-27T17:31-legacy-bugs-triage.md
spawned: []
status: in-progress
owner: null
branch: fix/cart-decimal-json
---

## Goal

Leo: the shopping cart "has never worked in like months." `btri01` had closed
"shopping cart still broken" in July as *likely fixed by bas-1..4*, on the
grounds that the old `populate-from-…` path was no longer referenced in `app/`
(BUGS.md:117-127). That was true and irrelevant — the feature was failing on a
different path the whole time. Find what is actually true, then fix it.

## Findings

### Symptom (MEASURED — read-only prod via `bin/prod-script`, SELECT-only)

- **No cart write in five months.** Last `shopping_list_items` row created
  2026-04-23; last list 2026-04-26. **Zero** POST/PUT/DELETE to any shopping
  endpoint in 120 days.
- The app DOES open the cart: `GET /v1/shopping-lists` → 200 and
  `GET /v1/shopping-lists/{list_id}` → 200 on 2026-09-20.
- ~100 ms after each 200 the client reported a crash, twice:
  `service=client`, `_TypeError: type 'String' is not a subtype of type 'num?'
  in type cast`, `{"area": "shopping.cart", "operation": "loadList"}`, user
  34589ac4 (Leo), list ee31f0c4-….
- **Server `error_logs` for shopping: zero rows.** The HTTP call succeeded; the
  failure is entirely in the client's parse. Zero 5xx in 30 days (palateful-0e,
  cross-checked against API stdout).

### Root cause (MEASURED in code; reproduced locally against the real routes)

Pydantic v2 renders `Decimal` as a JSON **string**; the app's cart model does
`json['quantity'] as num?` (`app/lib/features/shopping_cart/models/
shopping_list_item.dart:56`). Every cart endpoint builds its OWN local response
model with `quantity: Decimal`, so every cart response carrying a quantity
crashed the parser. An empty list, or items with a null quantity, parse fine —
which is why it could look intermittent.

**All ten cart endpoints were affected — measured, not inferred.** A contract
test calling each real route failed on all ten before the fix: get list, add
item, update item, create list, update list, deadlines, populate-from-recipe,
generate-from-meal-event, and both add-to-shopping-list routes. Add and update
item also broadcast the same body to other list members over the WebSocket,
so shared lists broke for every member.

### Why it survived a fix (MEASURED)

Commit `a5c84386` (2026-05-03), "serialize Decimal as JSON number, not string",
was written for exactly this crash — its comment quotes `area=shopping.cart,
operation=loadList`. It added the serializer to
`schemas/shopping_list.py::ShoppingListItemResponse`, **a class no endpoint
used** (the entire module was dead: zero references to any of its nine classes
outside itself and its own test). Its test exercised that class directly and
passed. The fix is deployed — `a5c84386` is an ancestor of prod's running
`848311af` — and did nothing. This is not the deploy freeze.

Two independent verifications, each true about something adjacent to the
fact: May's test (the class serializes correctly) and July's triage (the old
code path is gone). Neither checked the thing that was broken: the JSON the
live endpoint returns.

### Why nothing alerted (MEASURED; detail in palateful-0e's dev-obsgap1)

Every server signal read healthy: 200s, normal latencies, zero server
`error_logs`. The only trace was a CLIENT row whose area lives in the
`stack_trace` column, not `path` or `error_type` — invisible to a detector
keyed on either — at a volume (2) no rate alert trips on.

### Not the cause

- **Two cart directories** (`features/cart`, `features/shopping_cart`): one
  feature, two screens (`/cart` index, `/shopping-lists/:id` detail), one
  `ShoppingCartService`. Neither is dead.
- **The 405/422 cluster on shopping routes (9/11, 9/14):** an unauthenticated
  route sweep across ~65 endpoints (palateful-4f, measured). Filed separately
  as debug-apisweep.

### A wire-contract finding that bounded the fix

There is no single `Decimal` contract across this API. The cart client casts
to `num?`; the **recipe** screen reads `quantity_display` with `as String?`;
pantry uses a tolerant `_asDouble()`. So an API-wide fix (in
`jsonable_encoder` / `success()`) would have **broken recipes** the way the
cart was broken. The fix is deliberately per-client.

## Fix

- `services/api/src/schemas/json_types.py`: one shared `JsonDecimal` type — a
  `Decimal` that serializes as a JSON number in JSON mode only (Python-side
  `Decimal` arithmetic untouched).
- All ten cart RESPONSE models use it (12 fields). Request models keep
  `Decimal` — Pydantic parses a JSON number into it.
- **The dead `schemas/shopping_list.py` is deleted** with its tests, so a
  future fix cannot land there again.
- `tests/test_shopping_list_json_contract.py`: calls every cart route and
  asserts every quantity in the JSON BODY (and the WS broadcast payload for add
  and update) is a JSON number — and that at least one non-null quantity is
  present, so an item-less fixture cannot pass vacuously. (The existing
  `test_get_shopping_list_success` used `items=[]` for the whole outage.)
- `tests/test_shopping_list_decimal_guard.py`: an AST guard failing any cart
  response model that declares a bare `Decimal`, including one added in a new
  file. Scoped to the cart on purpose (see the recipe finding above), with a
  self-test proving it fails on the exact outage shape.

## Acceptance criteria

- [x] Repro against the real endpoint, failing for the right reason.
- [x] Root cause measured, with the proxy chain documented.
- [x] All ten cart endpoints return quantities as JSON numbers (contract test).
- [x] A guard that fails on the next bare `Decimal` in a cart response model.
- [ ] Verified on prod after deploy: palateful-fb's Playwright walk
      `services/e2e/prod-walk/tests/10-cart.spec.ts` (open a list containing a
      quantity-bearing item, assert the item renders) goes from FAIL to PASS.
      **Note:** this is a `services/` change, so merging it triggers the first
      API deploy since 2026-07-31 and carries every `services/` change merged
      since then.

## Status log

- 2026-09-22T09:00-06:00 — filed and root-caused (coordinator track, Leo's
  hardening initiative). Prod evidence gathered read-only. Contract test red on
  all ten endpoints for the right reason before any fix, green after; guard
  and contract test mutation-verified (reverting one endpoint fails both the
  guard and that endpoint's contract test; breaking `JsonDecimal` fails all
  ten). Converged independently with palateful-4f on the same root cause.
