# Story riip-1: Backend — `unit_aliases` table + seed + `normalize_unit_display` helper + cache

**Status:** done
**Epic:** epic-review-import-ingredient-polish

## Goal
Land the alias/normalizer foundation for the epic. New `unit_aliases` table
maps freeform unit strings (e.g., "tablespoon", "Tbsp.", "grams") to the
canonical token set used everywhere downstream ("tbsp", "g", …). Normalizer
helper is O(1) via an in-process cache loaded once per worker / FastAPI
process. Misses log to `error_logs` via a single helper so the alias table
can grow as we observe real LLM output. No write-path wiring yet (riip-2).

## Scope (from epic)
- Migration creates `unit_aliases` (`alias` PK, `canonical_unit` FK →
  `units.name`, `created_at`). Seeds ≥40 alias rows covering volume / weight
  / count / typo aliases. Idempotent via `INSERT … ON CONFLICT DO NOTHING`.
- Pre-condition check at migration head: `units.name` already has a
  `UNIQUE` constraint (added by initial migration), and every seeded
  `canonical_unit` exists in `units` — query-based assertion.
- `UnitAlias` SQLAlchemy model in `libraries/utils/utils/models/unit_alias.py`.
- `normalize_unit_display(raw, session)` in
  `libraries/utils/utils/services/units/normalize.py`.
  - `None`/empty → unchanged.
  - Trim + lowercase + strip trailing `[.,;]+`.
  - Already in canonical (`units.name`) → returned as-is.
  - Else lookup in alias map → canonical on hit.
  - Miss routes through `log_unit_alias_miss(raw, context)` and returns the
    *trimmed/normalized* input unchanged so downstream still gets a stable
    token to persist.
- `log_unit_alias_miss(raw, context)` in
  `libraries/utils/utils/logging/unit_logging.py` writes one `error_logs`
  row with `service="audit"`, `error_type="UnitAliasMiss"`. The only
  sanctioned way to log alias misses.
- AST-lint enforcement test in
  `libraries/utils/test/test_unit_alias_miss_enforcement.py` walks the repo
  for any string literal `"UnitAliasMiss"` outside `unit_logging.py` and
  fails CI.
- In-process cache initialized via Celery `@worker_process_init.connect`
  and FastAPI startup. Lazy-loads on first call as a fallback so unit
  tests work without worker init. `reload_unit_alias_cache(session)`
  exposed for tests.
- Unit tests cover: tablespoon→tbsp, tbsp→tbsp, "Tbsp." → tbsp, weirdunit
  → log + unchanged, None → None.

## File List
- `services/migrator/migrations/versions/20260418030000_create_unit_aliases.py` — new
- `libraries/utils/utils/models/unit_alias.py` — new
- `libraries/utils/utils/models/__init__.py` — modified (export)
- `libraries/utils/utils/services/units/__init__.py` — modified (export)
- `libraries/utils/utils/services/units/normalize.py` — new
- `libraries/utils/utils/logging/__init__.py` — new
- `libraries/utils/utils/logging/unit_logging.py` — new
- `libraries/utils/utils/services/celery.py` — modified (worker_process_init hook)
- `services/api/src/main.py` — modified (FastAPI startup hook)
- `libraries/utils/test/test_unit_normalize.py` — new
- `libraries/utils/test/test_unit_alias_miss_enforcement.py` — new

## Notes
- `UnitAlias` extends `JoinsBase` (no UUID `id`); `alias` itself is the PK.
- Cache loads from `units.name` (canonical set) and `unit_aliases` (alias
  → canonical). Lazy fallback if not initialized at call time.
- Snapshot writes are NOT part of this story — riip-2 wires the helper
  into live write paths.
- `log_unit_alias_miss` opens its own short-lived `Database()` so the
  caller's transaction can roll back without losing the audit row.

## QA walkthrough
See `_bmad-output/implementation-artifacts/riip-1-qa-walkthrough.md`.
