# Story riip-5: Flutter — `UnitInput` coerce-on-blur + session alias map

**Status:** done
**Epic:** epic-review-import-ingredient-polish

## Goal
Typing "tablespoon" in the unit dropdown auto-snaps to "tbsp" on blur
(or when a trailing space is typed), so units match the canonical enum
even when Leo types full words out of habit. Synchronous, offline-safe
via a hardcoded fallback alias map; live `GET /v1/units/aliases` (riip-4)
replaces the seed when the response lands.

## Scope (from epic)
- New `SessionAliasMap` service in
  `app/lib/features/recipes/services/session_alias_map.dart`:
  - Seeded synchronously from `kFallbackUnitAliases` so `coerce()` works
    immediately at app start.
  - `init()` is fire-and-forget at startup; on success, swaps in the
    live alias map + canonical token set; on failure, silently keeps
    the seed.
  - `coerce(raw)` mirrors the backend `normalize_unit_display` rules:
    trim, lowercase, strip trailing `[.,;]+`, lookup in canonical set
    or alias map, return normalized input on miss.
  - Constructor takes an `ApiClient`; a `withFetcher(...)` named
    constructor lets tests inject a fake without spinning up the
    real `Environment.apiBaseUrl` lookup chain.
- Hardcoded fallback added to
  `app/lib/core/constants/ingredient_units.dart` as
  `kFallbackUnitAliases` — top ~20 aliases matching the migration seed.
- `app/lib/core/services/api_client.dart` gains `getUnitAliases()`.
- `app/lib/core/di/injection.dart` registers `SessionAliasMap` as a
  lazy singleton with get_it; `..init()` is chained at construction
  time so the live fetch fires without blocking the first widget.
- `UnitInput`:
  - `_onFocusChange` (blur path) now calls `aliasMap.coerce(typed)`.
    On a hit that changes the value, the controller text is replaced
    AND the cursor is set to end-of-field via
    `TextSelection.collapsed(offset: coerced.length)` — fixes the
    cursor-at-zero bug called out in the epic.
  - `_onTextChange` triggers the same coercion when the user types a
    trailing space. The `if text.endsWith(' ')` short-circuits the
    overlay rebuild path so the dropdown closes cleanly.
  - New optional `aliasMap` parameter is a test seam; production reads
    from `getIt<SessionAliasMap>()`.

## File List
- `app/lib/core/constants/ingredient_units.dart` — modified (export `kFallbackUnitAliases`)
- `app/lib/core/services/api_client.dart` — modified (add `getUnitAliases`)
- `app/lib/core/di/injection.dart` — modified (register `SessionAliasMap`)
- `app/lib/features/recipes/services/session_alias_map.dart` — new
- `app/lib/features/recipes/widgets/unit_input.dart` — modified (coerce paths)
- `app/test/features/recipes/widgets/unit_input_test.dart` — modified
  (existing tests passed `aliasMap` through; 4 new coerce-on-blur
  widget tests + 4 unit tests on `SessionAliasMap.coerce`)

## Notes
- The "coerce disabled in custom-text mode" rule in the epic is
  implicit here: if the user types a value the alias map doesn't know
  AND that isn't canonical, `coerce()` returns the trimmed/lowercased
  raw input — the field shows it, the row's state takes it, no snap.
- The qty-field paste handler (epic AC7) is **deferred** to
  `riip-6` where the qty field lives in the rewritten
  `StructuredIngredientRow`. The `_onTextChange` space-trigger here
  is enough to satisfy the unit-side ACs.
- `dotenv` initialization isn't needed in tests because
  `SessionAliasMap.withFetcher` skips the `ApiClient` construction
  path entirely.

## QA walkthrough
See `_bmad-output/implementation-artifacts/riip-5-qa-walkthrough.md`.
