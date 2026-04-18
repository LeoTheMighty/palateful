# cpms-2 QA Walkthrough

This story is a pure backend deletion. There is no new feature surface
to exercise; the walkthrough is focused on confirming the endpoint and
its test artifacts are gone and that nothing downstream regressed.

## Sanity — endpoint is gone

- [ ] `curl -i -X POST https://<api-host>/v1/shopping-lists/<any-id>/populate-from-calendar -H 'Authorization: Bearer <token>' -d '{}'`
      → returns **404 Not Found** with a FastAPI "Not Found" body, not
      400/500. (In local dev, the 404 comes from the router; in prod,
      the API Gateway mapping will surface the same 404.)

## Sanity — per-meal path still works

- [ ] Tap an event in the Flutter calendar → the per-meal "add to
      shopping list" path still succeeds end-to-end (this exercises
      `populate-from-recipe`, which is untouched).

## Sanity — local build/test

- [ ] `npx nx run api:lint` → passes.
- [ ] `npx nx run api:test` → passes at 100% coverage.
- [ ] `npx nx run migrator:lint` → passes.

## Sanity — grep

- [ ] `rg 'populate[-_]from[-_]calendar|PopulateFromCalendar' services/ docs/`
      returns **no runtime hits**. Remaining hits are all for the
      unrelated `auto_populate_from_calendar` settings column on
      `shopping_lists` (kept — it's a flag, not the endpoint) or
      the dated strikethrough note in `docs/SHARED_SHOPPING_CART.md`.

## Regression

- [ ] Shared shopping lists continue to receive real-time `item_added`
      WebSocket events from adds performed via `populate-from-recipe`.
- [ ] `auto_populate_from_calendar` settings flag on a ShoppingList is
      still configurable via `PATCH /v1/shopping-lists/{id}` (the
      column survives; only the bulk expansion endpoint is gone).

## Rollback (if needed)

- [ ] `git revert` the cpms-2 commit on `main`. The endpoint returns
      idempotently (no migrations to unwind). Old clients (none in
      dogfood today) would start working again at the next API
      deploy.
