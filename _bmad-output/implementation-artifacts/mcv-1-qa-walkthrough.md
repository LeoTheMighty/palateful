# QA Walkthrough: mcv-1

Backend-only story. No UI path to exercise. QA is:

1. **Migrations run clean locally.**
   - `docker compose --profile migrate up migrator` — runs to completion;
     last migration logged is `mcv1mealtables`.
   - `docker compose exec db psql -U palateful -d palateful -c "\dt meals; \dt meal_recipes; \dt meal_favorites"`
     — three tables exist.
   - `\d meals` — shows `recipe_book_id NOT NULL`, `share_token` nullable,
     partial unique index on share_token.
   - `\d meal_recipes` — `recipe_id` FK is RESTRICT, `meal_id` FK is CASCADE.
     Composite PK. order_index default 0.
   - `\d meal_favorites` — composite PK `(user_id, meal_id)`; both FKs CASCADE.

2. **Downgrade clean.**
   - `docker compose exec migrator alembic downgrade -1` — three tables
     disappear with no dangling indexes (`\di meals_*` returns nothing).

3. **ORM agrees with DB.**
   - `npx nx run migrator:check-models` — no drift, exits 0.

4. **Unit tests green.**
   - `npx nx run api:test -- -k test_meal_model` — 13 tests pass.

5. **Broader API test suite still green.**
   - `npx nx run api:test` — 100% branch coverage gate on new files must hold.

6. **No side effects on existing meal_events / recurrence rules.**
   - `\d meal_events` — columns unchanged. No `meal_id` column yet (that
     ships in the calendar epic).
