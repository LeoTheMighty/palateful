# Story eri-4a — Seed 15 freeform-canonical rows into `units` (FK-preserving)

**Status:** done
**Epic:** epic-extractor-richer-ingredients
**Branch:** main

## Goal

Add 15 freeform canonical rows to the `units` table so the softened
prompt rule (eri-1) has somewhere to land when it emits words like
`stalk`, `bunch`, `can`, `head`. These rows are what eri-4b's
plural→singular aliases will FK into (`unit_aliases.canonical_unit →
units.name`). Without them, the existing FK would reject alias seeds.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Migration `20260422020000_seed_freeform_units.py` inserts 15 rows into `units` | ✅ Done |
| AC2 | Names: stalk, bunch, sprig, head, can, packet, stick, sheet, strip, piece, sachet, jar, bottle, bar, drop | ✅ Done |
| AC3 | Pattern matches pinch/dash/clove/slice: `type="other"`, `to_base_factor="1"`, `base_unit=<self>`, `abbreviation=<self>` | ✅ Done — asserted by `test_freeform_seed_type_and_factor_match_pinch_dash_pattern` |
| AC4 | Idempotent via `INSERT … ON CONFLICT (name) DO NOTHING` | ✅ Done — asserted by `test_migration_file_uses_on_conflict_do_nothing` |
| AC5 | `unit_aliases.canonical_unit` FK remains intact (never dropped) | ✅ Done — FK is untouched; new rows just populate the table |
| AC6 | Revision chains correctly from `schdrem001` (latest head) | ✅ Done — revision `erifrunits01`, down_revision `schdrem001` |
| AC7 | Down-migration removes the 15 rows only if no `unit_aliases` row still references them | ✅ Done — explicit FK-reference guard raises with actionable error if alias downgrade hasn't run first |
| AC8 | Seed list is pinned against `_FREEFORM_ALLOWED` in `unit_prompt.py` so they cannot drift | ✅ Done — `test_freeform_seed_names_match_prompt_allowlist` |

## File List

### New
- `services/migrator/migrations/versions/20260422020000_seed_freeform_units.py`
  - Revision: `erifrunits01`, down_revision: `schdrem001`
  - Upgrade: inserts 15 rows with `ON CONFLICT DO NOTHING`
  - Downgrade: refuses to run if any alias still references a freeform row (abort with explicit operator guidance), otherwise deletes the 15 rows
- `libraries/utils/test/test_freeform_units_seed.py` — 5 regression tests

### Not modified
- `libraries/utils/utils/services/units/normalize.py` — no code change; the cache load reads from `units.name` automatically on next process start.
- `unit_aliases` FK — preserved.

## Freeform units seeded

| name | type | to_base_factor | base_unit |
|---|---|---|---|
| stalk | other | 1 | stalk |
| bunch | other | 1 | bunch |
| sprig | other | 1 | sprig |
| head | other | 1 | head |
| can | other | 1 | can |
| packet | other | 1 | packet |
| stick | other | 1 | stick |
| sheet | other | 1 | sheet |
| strip | other | 1 | strip |
| piece | other | 1 | piece |
| sachet | other | 1 | sachet |
| jar | other | 1 | jar |
| bottle | other | 1 | bottle |
| bar | other | 1 | bar |
| drop | other | 1 | drop |

## Implementation notes

- **`piece` collision with existing alias.** The riip-1 alias seed
  included `("piece", "each")` and `("pieces", "each")`. After this
  migration runs, `normalize_unit_display("piece")` returns `"piece"`
  (canonical lookup wins before alias lookup). The stale aliases become
  dead code — eri-4b refreshes the alias map to drop `piece→each`
  and `pieces→each`, replacing with `pieces→piece`.
- **Down-migration safety.** Naive `DELETE FROM units WHERE name = ANY(...)`
  would silently hit the `unit_aliases.canonical_unit` FK with
  `ondelete=RESTRICT` and fail mid-transaction. The explicit guard up
  front raises a clear "downgrade eri-4b first" error instead.
- **Sync contract.** The 15 names are pinned against
  `_FREEFORM_ALLOWED` in `unit_prompt.py` — if a future PR adds a new
  freeform word to the prompt without also adding a migration row, the
  test `test_freeform_seed_names_match_prompt_allowlist` fails loudly.
- **No model change.** `units` already exists; this migration just
  adds data. `migrator:check-models` (alembic drift check) is not
  affected.

## Known local-env wrinkle

`npx nx run migrator:check-models` fails locally with
`invalid dsn: invalid connection option "schema"` — this is a pre-existing
env issue (reproduces on `main` without my changes) and does not block
this story. Remote CI runs check-models against a fresh DB.

## Verification

- `poetry run pytest libraries/utils/test/test_freeform_units_seed.py -v` — 5 passed
- `npx nx run utils:test` — 516 passed (was 511; +5 new tests)
- `npx nx run utils:lint` — clean
- `npx nx run migrator:lint` — clean
- Migration chain confirmed head: `heads: ['erifrunits01']`
