# Story eri-4b — Seed 15 plural→singular freeform unit aliases + verify Flutter cold-start refresh

**Status:** done
**Epic:** epic-extractor-richer-ingredients
**Branch:** main

## Goal

Layer on top of eri-4a: now that `stalk`, `bunch`, `can`, etc. are
canonical rows in `units`, seed the plural forms (`stalks`→`stalk`,
`cans`→`can`, …) as aliases so `normalize_unit_display` coerces them
correctly. Also reconcile the riip-1 `piece`/`pieces`→`each` aliases
which are now stale (piece became canonical in eri-4a). Verify the
Flutter `SessionAliasMap.init()` cold-start refresh picks up the new
aliases without an app reinstall.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Migration `20260422030000_seed_freeform_unit_aliases.py` inserts 16 alias rows (15 plural→singular + `packs→packet`) | ✅ Done |
| AC2 | All alias targets are seeded canonical rows from eri-4a (FK-safe) | ✅ Done — `test_every_alias_target_is_a_seeded_freeform_canonical` |
| AC3 | `piece→each` and `pieces→each` (riip-1 aliases rendered stale by eri-4a's canonical `piece` row) are dropped; `pieces→piece` replaces them | ✅ Done — `test_stale_piece_aliases_get_dropped`, `test_pieces_points_to_piece_not_each` |
| AC4 | Idempotent via `INSERT … ON CONFLICT (alias) DO NOTHING` | ✅ Done — `test_migration_uses_on_conflict_do_nothing_for_inserts` |
| AC5 | Revision chains from `erifrunits01` (eri-4a) | ✅ Done — `test_migration_revision_chains_from_eri_4a` |
| AC6 | Down-migration removes the 16 freeform aliases and restores the stale `piece/pieces→each` pair | ✅ Done — `test_downgrade_restores_stale_aliases` |
| AC7 | Flutter `SessionAliasMap` cold-start picks up live alias payload containing new seeds | ✅ Done — `session_alias_map_cold_start_test.dart` (5 tests) |
| AC8 | Flutter fallback seed still answers pre-init `coerce()` calls; failed live fetch degrades gracefully | ✅ Done |

## File List

### New
- `services/migrator/migrations/versions/20260422030000_seed_freeform_unit_aliases.py` (revision `erifraliases01`)
- `libraries/utils/test/test_freeform_unit_aliases_seed.py` — 10 regression tests
- `app/test/features/recipes/services/session_alias_map_cold_start_test.dart` — 5 Flutter tests for the cold-start refresh path

### Not modified
- `app/lib/features/recipes/services/session_alias_map.dart` — the
  existing `init()` path already fetches live aliases on cold-start
  and swaps the in-memory map. The 24h HTTP `Cache-Control` header on
  `GET /v1/units/aliases` is known and documented in the endpoint
  file; already-running clients converge over the next 24h. Backend
  `normalize_unit_display` is the authoritative normalization, so the
  transient window is invisible to the user.
- `services/api/src/api/v1/units/get_unit_aliases.py` — endpoint
  already returns both `aliases` and `canonical`; new seeds flow
  through unchanged.

## Aliases seeded

| alias | canonical |
|---|---|
| stalks | stalk |
| bunches | bunch |
| sprigs | sprig |
| heads | head |
| cans | can |
| packets | packet |
| packs | packet |
| sticks | stick |
| sheets | sheet |
| strips | strip |
| pieces | piece |
| sachets | sachet |
| jars | jar |
| bottles | bottle |
| bars | bar |
| drops | drop |

## Stale aliases dropped

| alias | old canonical | why dropped |
|---|---|---|
| piece | each | `piece` is canonical in its own right after eri-4a |
| pieces | each | replaced by `pieces→piece` |

## Implementation notes

- **FK safety.** `unit_aliases.canonical_unit` FKs to `units.name`.
  Every alias target in this migration exists in `units` by virtue of
  the eri-4a seed (pinned by the `test_every_alias_target_is_a_seeded_freeform_canonical`
  test). Revision ordering ensures the FK check never fails mid-run.
- **Cold-start refresh path.** DI registers `SessionAliasMap` as a
  lazy singleton constructed via `SessionAliasMap(apiClient)..init()`.
  Every process cold-start re-runs DI, which re-fires `init()`, which
  fetches fresh aliases. `init()` is guarded by `_initialized` so a
  second call in the same session is a no-op. Mobile app relaunch
  triggers the fresh fetch.
- **24 h HTTP cache.** `GET /v1/units/aliases` sends `Cache-Control: max-age=86400`.
  Clients on the edge-case of "kept running without relaunch for >24h"
  get the new aliases automatically when the cache expires. In the
  worst case (app never killed, HTTP cache never expires), the
  backend still normalizes on write — so a user who types "stalks"
  sees it normalized to "stalk" in the API response after save.
- **Fallback seed unchanged.** `kFallbackUnitAliases` in the Flutter
  client still has the riip-5 baseline (tablespoon→tbsp, etc.) and
  does NOT hardcode the new freeform aliases. That would be a
  maintenance landmine — the fallback is a minimum-viable seed; the
  live fetch is always the source of truth.

## Verification

- `poetry run pytest libraries/utils/test/test_freeform_unit_aliases_seed.py -v` — 10 passed
- `flutter test app/test/features/recipes/services/session_alias_map_cold_start_test.dart` — 5 passed
- `npx nx run utils:test` — 526 passed (was 516, +10)
- `npx nx run utils:lint` — clean
- `npx nx run migrator:lint` — clean
