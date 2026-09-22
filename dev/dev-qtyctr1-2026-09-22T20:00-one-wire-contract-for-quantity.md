---
hash: qtyctr1
type: dev
created: 2026-09-22T20:00:00-06:00
title: One wire contract for quantity — clients disagree on whether it is a number or a string
from: debug/debug-cartdec-2026-09-22T09:00-shopping-cart-decimal-quantity-crash.md
status: ready
owner: null
branch: null
---

## Goal

The API has no single wire type for quantities. Each Flutter screen assumes its
own type, and two of those assumptions are strict casts that crash on the other
type. That is how the cart broke for months (cartdec): the server sent a string
and the cart cast to `num`. cartdec fixed the cart by sending numbers **only on
cart endpoints**, because an API-wide change would have broken recipes. The
hazard is still there: change any serializer and whichever screen assumed the
other type crashes silently. The server returns 200, so nothing server-side
notices.

## Measured inventory (app/lib, 2026-09-22, at cartdec's branch)

| Site | Field | Contract | On the wrong type |
|---|---|---|---|
| `shopping_cart/models/shopping_list_item.dart:56` | `quantity` | `as num?` (strict number) | `_TypeError` (cartdec) |
| `recipes/recipe_detail_screen.dart:1045` | `quantity_display` | `as String?` (strict string) | `_TypeError` |
| `recipes/cook_mode/shared/widgets/ingredient_strip.dart:365` | `quantity_display` | `as String?` (strict string) | `_TypeError` |
| `pantry/models/pantry_ingredient.dart:40` | `quantity_display` | `_asDouble` (tolerant) | ok |
| `recipes/add_recipe/ingredient_edits_mapping.dart:29,101` | `quantity`, `quantity_display` | `is num` / `is String` (tolerant) | ok |
| `recipes/public_recipe_screen.dart:159`, `recipe_version_diff_screen.dart:220-239` | `quantity_display` | `?.toString()` (tolerant) | ok |

The two strict `as String?` sites share **one** source: recipe detail and
both cook modes (single recipe via `cook_plan.dart:289`, and meal via
`meal_cook_mode_screen.dart:369-381`, which fetches each component's recipe)
all read `GET /v1/recipes/{id}`, which declares `quantity_display: str`
(`get_recipe.py:152`). So one serializer change on that endpoint crashes all of
them at once. They are two cast sites, not two independent risks.

Inferred, not measured: the grep covers only direct `json['…']` reads.
Generated or indirect parsers were not swept.

## Acceptance criteria

- [ ] Decide one wire type per field (`quantity`: number; `quantity_display`:
      string or number, stated explicitly) and write it down where the
      serializers live.
- [ ] Every client read of these fields uses a tolerant parser (a shared
      helper, not a copy per screen), so a server-side serializer change
      degrades instead of crashing.
- [ ] Server-side contract tests on the real response bodies of the recipe,
      pantry and cook-mode endpoints, like cartdec's
      `test_shopping_list_json_contract.py`, pinning the decided types. Each
      must fail red before it goes green.
- [ ] Re-run the inventory, including indirect parsers, and record it in the
      Status log.

## Technical notes

- cartdec introduced `schemas.json_types.JsonDecimal` (Decimal in Python,
  float in JSON). Reuse it; don't write a second one.
- Order matters (see LESSONS: silent-to-loud sequencing). Make the clients
  tolerant **and ship that build** before changing any server serializer. The
  server deploys in minutes; installed apps lag by weeks.
- Detection is a separate story: `dev-prsal1` (client parse-failure alert).

## Status log

- 2026-09-22T20:00 — filed from cartdec (PR #40) at leonidbelyi-41's request.
  Inventory measured by grep over `app/lib`.
- 2026-09-22T20:30 — corrected the inventory: the two strict `as String?` sites read the same endpoint (`GET /v1/recipes/{id}`), so it's one shared risk, not two. Confirmed that PR #40 changes no recipe route, so it can't regress them.
