# eri-4a QA walkthrough — seed freeform units

DB migration; no Flutter UI impact. Backend-only.

## Pre-reqs
- Python 3.13, Poetry, NX.
- Postgres reachable via `DATABASE_URL` for the manual upgrade smoke.

## Smoke

1. **Regression tests pass.**
   ```bash
   poetry run pytest libraries/utils/test/test_freeform_units_seed.py -v
   ```
   Expected: 5 passed.

2. **Full utils suite + lint clean.**
   ```bash
   npx nx run utils:test
   npx nx run utils:lint
   npx nx run migrator:lint
   ```

## Migration sanity

3. **Revision chain.**
   ```bash
   cd services/migrator && poetry run alembic heads
   ```
   Expected: `erifrunits01 (head)`.

4. **Dry-run upgrade SQL (without hitting DB).**
   ```bash
   cd services/migrator && poetry run alembic upgrade erifrunits01 --sql | head -80
   ```
   Expected: 15 `INSERT INTO units (...) VALUES (...) ON CONFLICT (name) DO NOTHING` statements.

## Post-upgrade DB sanity (manual, against a live DB)

5. **All 15 rows are present.**
   ```sql
   SELECT name, type, to_base_factor, base_unit FROM units
   WHERE name IN ('stalk','bunch','sprig','head','can','packet','stick',
                  'sheet','strip','piece','sachet','jar','bottle','bar','drop')
   ORDER BY name;
   ```
   Expected: 15 rows, `type='other'`, `to_base_factor=1`, `base_unit=<name>`.

6. **Idempotency — re-run is a no-op.**
   ```bash
   cd services/migrator && poetry run alembic upgrade head
   ```
   Second run should log "already at head" and make no changes.

7. **`normalize_unit_display("stalk")` → `"stalk"` (canonical hit).**
   After process restart (cache reload):
   ```python
   from utils.services.units.normalize import normalize_unit_display
   # with a live session
   normalize_unit_display("stalk", session)  # -> "stalk"
   ```

## Rollback drill

8. **Down to schdrem001 with no alias references.**
   ```bash
   cd services/migrator && poetry run alembic downgrade schdrem001
   ```
   Expected: 15 rows removed cleanly. If eri-4b has been applied, expect
   an explicit error: `seed_freeform_units downgrade blocked: unit_aliases
   still references ...` — follow the message's instruction to downgrade
   eri-4b first.

## What's deferred
- **Flutter cache refresh verification** — eri-4b.
- **Alias seeds (stalks→stalk, etc.)** — eri-4b.
- **Production flip runbook** — eri-6.
