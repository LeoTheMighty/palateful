# Story aam-1: Async engine + RDS capacity

**Status**: done
**Epic**: epic-api-async-migration
**Phase**: 1 — Foundations

## Acceptance Criteria

1. `libraries/utils/utils/constants.py` adds `DB_ASYNC_POOL_SIZE` (default 20) + `DB_ASYNC_MAX_OVERFLOW` (default 40) with env override.
2. `libraries/utils/utils/services/database.py` (or sibling) exposes an async engine + `AsyncSessionLocal` built from the same DATABASE_URL (scheme rewritten to `postgresql+asyncpg://`).
3. `services/api/src/main.py` lifespan creates the async engine ordering-correct: sync engine first (writers / unit-alias pre-warm depend on it), async engine second. Dispose order reversed.
4. `services/api/src/dependencies.py` adds `async def get_async_database()` — stub yielding an `AsyncSession` (real `AsyncDatabase` arrives in aam-2).
5. ECS task definition env vars `DB_ASYNC_POOL_SIZE=20` + `DB_ASYNC_MAX_OVERFLOW=40` set explicitly in terraform.
6. **Terraform `max_connections` 80 → 100** — done 2026-04-23; verified live (`SHOW max_connections` = 100). Instance class also bumped to `db.t4g.small`. Reboot applied pending param-group values.
7. Test: one dummy async handler (not routed) exercises the dep at test-time.
8. Lands **dark** — no production handler uses the async engine yet.

## File List

- `libraries/utils/utils/constants.py` (modify)
- `libraries/utils/utils/services/database.py` (modify — add async engine + sessionmaker)
- `services/api/src/dependencies.py` (modify — add `get_async_database`)
- `services/api/src/main.py` (modify — lifespan startup/shutdown)
- `services/api/tests/test_async_engine_dep.py` (new — unit test)
- `terraform/modules/ecs/main.tf` or `terraform/environments/prod/main.tf` (modify — add env vars to API task def)
- `terraform/modules/rds/parameter_group.tf` (done — `max_connections=100`)

## Notes

- Pool math: sync API 20/40 + async API 20/40 + beat/worker/migrator 15 + headroom 25 = 100 during the migration. Post-aam-24 sync shrinks to 5/10, total peak drops to ~35 + 15 + 50 = 100 (still within budget, gains headroom).
- Async URL derivation: rewrite `postgresql://...` → `postgresql+asyncpg://...` in constants (keeps a single source of truth). Do NOT add a second env var for the async URL.
- ECS env vars: the task definition reads from terraform-defined inputs; add `DB_ASYNC_POOL_SIZE` + `DB_ASYNC_MAX_OVERFLOW` to the API task container env block.
