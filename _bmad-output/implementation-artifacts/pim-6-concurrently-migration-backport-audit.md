# Story pim-6 — CONCURRENTLY migration backport audit

**Status:** done
**Epic:** epic-perf-infra-and-measurement
**Depends on:** nothing.

## Scope

Audit-only story. Survey every file under
`services/migrator/migrations/versions/` for
`op.execute("CREATE INDEX ...")` without `CONCURRENTLY`, which is the
pattern flagged by the epic AC as a potential "blocks production
traffic on DDL" hazard.

Per the epic's explicit instruction:
> If the audit finds **nothing**, story closes with a commit
> `chore(migrations): audit — no legacy non-CONCURRENTLY indexes`
> and a paragraph listing the migrations surveyed. No empty
> migration committed.

## Findings — strict AC (`op.execute("CREATE INDEX ...")` without CONCURRENTLY)

**None.** Every raw `op.execute(...)` invocation that creates a
Postgres index in the migration history already uses
`CREATE INDEX CONCURRENTLY IF NOT EXISTS` inside an
`autocommit_block()`, per the pattern established by:

- `20260319000002_add_recipe_trgm_indexes.py`
- `20260320000002_add_performance_indexes.py` (in its upgrade, uses
  a mix — see the broader-scope note below)
- `20260418030000_add_archive_partial_indexes.py`
- `20260420000000_add_import_items_actionable_index.py`
- `20260420050000_add_see_all_partial_indexes.py`

## Broader-scope note (non-blocking context)

The audit also enumerated `op.create_index(...)` calls — the Alembic
helper, which generates non-CONCURRENTLY DDL. There are 18 of them
on tables that pre-existed the migration. None of these count as a
finding under the epic AC ("op.execute(CREATE INDEX)"), but they're
recorded here for future reference:

- `20260130000001_add_shared_shopping_cart.py:91, 164, 167` —
  `shopping_lists`, `shopping_list_items` (2)
- `20260130000002_add_friends_social_system.py:30` — `users`
- `20260320000001_add_recipe_share_token.py:22` — `recipes`
- `20260320000002_add_performance_indexes.py:21, 24, 27, 30` —
  `recipe_book_users`, `recipe_ingredients`, `recipes`,
  `shopping_list_items`
- `20260322200000_add_default_shopping_list_id.py:42, 69` — `users`
- `20260322210000_add_previous_recipe_book_id.py:39` — `users`
- `20260417000001_add_meal_recurrence_rules.py:101, 109` —
  `meal_events`
- `20260417000002_add_calendars.py:194, 209` — `meal_events`,
  `meal_recurrence_rules`
- `20260418090000_add_meal_id_to_calendar_and_cooking_logs.py:61, 86`
  — `meal_events`, `meal_recurrence_rules`

**Why no backport migration ships for these:**

1. Every one of these indexes already exists in prod — the
   migrations have run and the indexes are live. A forward
   `CREATE INDEX CONCURRENTLY IF NOT EXISTS` would be a no-op on
   prod (the `IF NOT EXISTS` clause short-circuits).
2. On a fresh-DB rebuild, Alembic runs migrations from the first
   forward. The historical `op.create_index()` calls execute on
   freshly-created empty tables (either the table was created in
   the same migration, OR the column was added first and the
   table was small at that point), so none of them block anything
   a retroactive CONCURRENTLY migration could help.
3. The epic's intent is "no new forward migration ever blocks
   prod on DDL." Going forward, every new index in the prod
   schema uses `CREATE INDEX CONCURRENTLY` via `op.execute()`
   inside an `autocommit_block()`. The locked decision in the
   epic + the pattern already present in the three most recent
   perf migrations (archive, see-all, actionable) enforces this.

This list is archived in the story file, not in any forward
migration. Any future concern prompts a surgical single-index
forward migration on-demand.

## Files surveyed

29 files under `services/migrator/migrations/versions/` containing
`op.create_index` or `op.execute("CREATE INDEX` were surveyed (plus
all other files to confirm no hidden CREATE INDEX patterns):

- 2026011704109_5b51adc124d5_initial_models_for_recipe_books.py
- 20260117041822_525891f38d8b_suggestion_and_notification_models.py
- 20260119000001_add_default_recipe_book_id.py
- 20260129000001_add_calendar_meal_planning_models.py
- 20260129000002_add_import_system_models.py
- 20260130000001_add_shared_shopping_cart.py
- 20260130000002_add_friends_social_system.py
- 20260131000001_add_parser_jobs.py
- 20260216000001_add_collaboration_system.py
- 20260315000002_add_user_favorites.py
- 20260317000001_add_recipe_versions.py
- 20260319000001_add_recipe_notes.py
- 20260319000002_add_recipe_trgm_indexes.py (CONCURRENTLY ✅)
- 20260320000001_add_recipe_share_token.py
- 20260320000002_add_performance_indexes.py (mixed — raw op.execute
  uses CONCURRENTLY ✅; 4 op.create_index helpers flagged above)
- 20260322181116_224dc8e7975c_.py
- 20260322200000_add_default_shopping_list_id.py
- 20260322210000_add_previous_recipe_book_id.py
- 20260322230000_create_user_activities.py
- 20260409000001_create_error_logs.py
- 20260412000000_add_parser_batches.py
- 20260416000001_create_pantry_ingredient_events.py
- 20260417000001_add_meal_recurrence_rules.py
- 20260417000002_add_calendars.py
- 20260418010000_add_latency_tables.py
- 20260418020000_add_user_feedbacks.py
- 20260418030000_add_archive_partial_indexes.py (CONCURRENTLY ✅)
- 20260418060000_add_error_logs_import_item_telemetry.py
- 20260418070000_add_import_item_s3_key.py
- 20260418080000_add_meals_and_meal_recipes_and_meal_favorites.py
- 20260418090000_add_meal_id_to_calendar_and_cooking_logs.py
- 20260420000000_add_import_items_actionable_index.py (CONCURRENTLY ✅)
- 20260420040000_drop_ingredient_canonicalization_infra.py
- 20260420050000_add_see_all_partial_indexes.py (CONCURRENTLY ✅)

## File list

- `_bmad-output/implementation-artifacts/pim-6-concurrently-migration-backport-audit.md` [NEW]
- `_bmad-output/implementation-artifacts/pim-6-qa-walkthrough.md` [NEW]
- `_bmad-output/implementation-artifacts/sprint-status.yaml` [MODIFY]

**No migration file committed** (per the epic's "audit empty" closure
path).

## Acceptance criteria — coverage

- AC1 ✅ Survey of `op.execute("CREATE INDEX ...")` without
  CONCURRENTLY — zero findings.
- AC2 — N/A (no findings, so no forward migration needed).
- AC3 ✅ Empty-audit closure path taken: commit summarizes + lists
  surveyed migrations + explains the broader-scope `op.create_index`
  context; no empty migration file committed.
- AC4 — N/A.
