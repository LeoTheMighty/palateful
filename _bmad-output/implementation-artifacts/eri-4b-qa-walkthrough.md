# eri-4b QA walkthrough — freeform unit aliases + Flutter cold-start

DB migration + Flutter cold-start verification. Backend + thin client path.

## Pre-reqs
- Python 3.13, Poetry, NX.
- Flutter SDK (for the cold-start test).
- Postgres reachable via `DATABASE_URL` for the manual upgrade smoke.

## Smoke

1. **Alias regression tests pass.**
   ```bash
   poetry run pytest libraries/utils/test/test_freeform_unit_aliases_seed.py -v
   ```
   Expected: 10 passed.

2. **Flutter cold-start test passes.**
   ```bash
   cd app && flutter test test/features/recipes/services/session_alias_map_cold_start_test.dart
   ```
   Expected: 5 passed.

3. **Full suite + lints clean.**
   ```bash
   npx nx run utils:test
   npx nx run utils:lint
   npx nx run migrator:lint
   ```

## Migration sanity

4. **Revision chain.**
   ```bash
   cd services/migrator && poetry run alembic heads
   ```
   Expected: `erifraliases01 (head)`.

5. **Dry-run SQL shows INSERT + DELETE ordering.**
   ```bash
   cd services/migrator && poetry run alembic upgrade erifraliases01 --sql | tail -60
   ```
   Expected:
   - 2 `DELETE FROM unit_aliases ... WHERE alias=...` statements (piece, pieces).
   - 16 `INSERT INTO unit_aliases ... ON CONFLICT (alias) DO NOTHING` statements.

## Post-upgrade DB sanity (manual, live DB)

6. **All 16 aliases present.**
   ```sql
   SELECT alias, canonical_unit FROM unit_aliases
   WHERE alias IN (
     'stalks','bunches','sprigs','heads','cans','packets','packs',
     'sticks','sheets','strips','pieces','sachets','jars','bottles','bars','drops'
   ) ORDER BY alias;
   ```
   Expected: 16 rows, each pointing at its singular freeform canonical.

7. **`piece→each` and `pieces→each` are GONE.**
   ```sql
   SELECT * FROM unit_aliases WHERE alias IN ('piece','pieces') AND canonical_unit = 'each';
   ```
   Expected: 0 rows.

8. **`normalize_unit_display` behavior** (after process restart so
   cache reloads):
   ```python
   normalize_unit_display("stalks", session)   # -> "stalk"
   normalize_unit_display("cans", session)     # -> "can"
   normalize_unit_display("pieces", session)   # -> "piece" (was "each" pre-4b)
   normalize_unit_display("piece", session)    # -> "piece" (canonical hit)
   ```

## Flutter cold-start walk

9. **Manual smoke (device / simulator):**
   - Logged-in user taps Add Recipe → URL → pastes a cookbook URL
     with "2 stalks celery, chopped" in JSON-LD.
   - After import + Review Import renders: field shows `[2] [stalk] [celery]`.
   - If `[2] [stalks] [celery]` — kill the app, relaunch, re-import.
     Cold-start re-fetches `/v1/units/aliases` (DI construct-time
     `..init()`), new alias map installs.

## Known 24 h staleness window

After production flip, clients with a live HTTP cache on
`GET /v1/units/aliases` may see the pre-deploy alias map for up to
24 h. Backend `normalize_unit_display` is authoritative: a user who
types `stalks` in the UnitInput will see it normalized to `stalk` in
the API response after save, regardless of client cache state.

## Rollback drill

10. **Downgrade eri-4b.**
    ```bash
    cd services/migrator && poetry run alembic downgrade erifrunits01
    ```
    Expected: 16 freeform aliases removed; `piece→each` and `pieces→each`
    restored.

## What's deferred
- **Eval metric + fixtures** — eri-5.
- **Production flip runbook** — eri-6.
