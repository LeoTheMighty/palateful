---
hash: recid500
type: debug
created: 2026-09-24T16:30:00-06:00
title: Manual recipe creation 500s — RecipeIngredient has no `id`, and each retry leaves a partial recipe
from: leonidbelyi-41 (QA walkthrough of the browser flow)
status: in-progress
owner: null
branch: fix/create-recipe-ingredient-id
---

## Goal

`POST /v1/recipe-books/{book_id}/recipes` returns 200 with the created recipe,
for any manual creation that includes at least one ingredient.

## Symptom (measured, prod, 2026-09-24)

QA account, driving the browser by hand:

```
POST /v1/recipe-books/dff7cc6a-…/recipes   -> 500   (16:28:18 and again 16:28:34 UTC)
POST /v1/users/me/client-errors            -> 200
```

The UI shows "Couldn't save recipe" with a Retry button and no indication that
the fault is server-side. Payload was the plainest possible: two ingredients,
two steps, prep 15 / cook 55 / servings 8.

## Root cause (measured, not inferred)

`services/api/src/api/v1/recipe/create_recipe.py:156`:

```python
CreateRecipe.IngredientResponse(
    id=str(recipe_ingredient.id),   # <-- AttributeError
```

`RecipeIngredient` is a join table: it extends `JoinsBase` ("Base class for
join tables (no ID, just timestamps)") and has a **composite primary key**
`(recipe_id, ingredient_id)`. There is no `id` column and never was.

Prod's `error_logs` row says exactly this:
`api/AttributeError … 'RecipeIngredient' object has no attribute 'id'`.

**Universal, not account-specific.** The line is unconditional inside the
per-ingredient loop, so every manual creation carrying ≥1 ingredient fails,
for every user. Nothing about the QA account's auto-provisioned book is
involved. (Recipes created by the import pipeline do not pass through this
line.)

## Consequence worse than the 500: silent partial writes

The recipe row and the first `recipe_ingredients` row are **committed before**
the response is built, and the exception aborts the loop. Each attempt leaves:

- the recipe row, and
- one ingredient (of the two submitted), and
- **zero** steps.

Measured in prod: two `'Test Banana Bread'` rows, `ingredients=1, steps=0`,
one per attempt — the user pressed Retry once. The client reports failure, the
server keeps the debris, and nothing reconciles the two. A user retrying five
times gets five partial recipes and no success message.

## Why the tests did not catch it — the harness manufactures the attribute

`services/api/tests/conftest.py:806` (`_apply_column_defaults`, called by the
mock DB's `create()`):

```python
if getattr(obj, 'id', None) is None:
    obj.id = str(uuid.uuid4())
```

On a real `RecipeIngredient`, `getattr(obj, 'id', None)` returns `None`
because the attribute does not exist — so the mock **creates** it. Production
code then reads `recipe_ingredient.id` and the test passes. The harness
supplies the one thing whose absence is the defect.

This is not an unknown hazard in this repo. `conftest.py:203` defines
`MockRecipeIngredient` whose docstring says, verbatim:

> The base MockModel sets `id` by default, so strip it here — otherwise
> production code that accidentally reads `ri.id` passes tests but raises
> AttributeError in prod.

That mock defends the path it is used on. `create_recipe` constructs a **real**
`RecipeIngredient` and hands it to the mock DB, which re-adds the attribute the
mock class exists to remove.

## Fixed once already, on the sibling endpoint

`update_recipe.py:295` reads `str(ri.ingredient_id)`, and
`test_recipe.py:3024` pins it:

> Regression: `IngredientResponse.id` was previously `ri.id`, which
> AttributeErrored because RecipeIngredient has a composite PK (no `id`
> column). Confirm it now surfaces the ingredient_id instead.

So this exact defect was found, understood, fixed and regression-tested — on
`PUT /v1/recipes/{id}`. The identical line in `POST …/recipes` was left. The
regression test covers the endpoint that was fixed, which is why it is green.

## Acceptance criteria

- [ ] `POST /v1/recipe-books/{id}/recipes` with ≥1 ingredient returns 200 and a
      usable `ingredients[].id` (mirroring update_recipe: the ingredient id).
- [ ] A test that fails RED on current main **against a real
      `RecipeIngredient`**, not a mock that has been given an `id`.
- [ ] The harness hole is closed or made loud: `_apply_column_defaults` must
      not invent `id` on a model whose mapper has no `id` column. Closing it
      may turn other tests red — those are the same bug, not collateral.
- [ ] Decide the orphan rows: two partial `Test Banana Bread` recipes exist in
      prod. Deleting them is a **write** and needs Leo's approval.
- [ ] Sweep for the same shape on other join models (`CalendarUser`,
      `RecipeBookUser`, `ShoppingListUser`, …) reading `.id`.

## Technical notes

- The client mirror was the better instrument here: the `client-errors` row
  carried the server's own message (`'RecipeIngredient' object has no attribute
  'id'`), while the server's `error_logs` row had `stack_trace = "NoneType:
  None"` and null `path`/`method`. Worth its own item — a server 500 that
  records no traceback is most of a detector missing.
- Prod deployed revision at time of failure: `palateful-api-prod:65`
  (`9c626c5a`).

## Status log

- 2026-09-24T16:45 — filed from 41's QA walkthrough. Root cause measured in
  prod via read-only probes; traceback absent server-side, recovered from the
  client mirror row and confirmed against the model definition.
