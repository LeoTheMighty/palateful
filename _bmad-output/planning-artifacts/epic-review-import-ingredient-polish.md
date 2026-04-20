<!-- refined via party-mode 2026-04-18 -->
<!-- rescoped 2026-04-20 by epic-ingredients-string-simplification -->

> **⚠️ Rescope note — 2026-04-20.** `epic-ingredients-string-simplification` retires the `ingredients.pending_review` column and the `find_or_create` auto-create path that underpinned the pending-review annotation work in this epic. Therefore:
>
> - **riip-4** loses its pending-review-annotation half. The `GET /v1/units/aliases` endpoint half is **unchanged and still in scope**. All PRD and acceptance-criteria text below that references `pending_review_ingredient` is retracted; treat those bullets as "not applicable" for implementation.
> - **riip-7** (IngredientRowStateBadge) is **DELETED in full**. Its motivating data (pending_review) no longer exists in the schema. The widget + widget-test that landed ahead of plan (96 + 95 LOC) are removed by `str-ing-1` of the simplification epic.
> - **riip-1, riip-2, riip-3, riip-5, riip-6, riip-8** are **unchanged** — unit normalization + one-line row layout + regression smoke are orthogonal to ingredient identity.
>
> Sprint-status.yaml marks `riip-7-flutter-ingredient-row-state-badge` as `deleted` with an inline comment pointing here. riip-4 stays `backlog` with narrowed scope.
# Epic: Review Import Ingredient Polish — One-Line Rows + End-to-End Unit Normalization

## Overview

The Review Import screen's ingredient rows are a known irritant — each ingredient takes two rows (qty/unit/name on row 1, notes on row 2) and the extractor emits freeform units ("tablespoon" instead of "tbsp") that make a compact single-line layout impossible. Leo flagged this as a UI bug that points to a larger issue in the whole import: the extractor, backend, and UI are not aligned on a single canonical unit enum.

This epic fixes the symptom (two-row ingredient UX) by fixing the root cause (freeform units throughout the pipeline), then lands the compact one-line row.

Three layers, one slice:
1. **Extractor** prompts enumerate the canonical abbreviated unit tokens and instruct the model to use them literally.
2. **Backend** runs every write path through a `normalize_unit_display(raw: str) -> str` helper backed by a new `unit_aliases` table (tablespoon → tbsp, gram → g, …). Misses log to `error_logs` for later alias-table harvesting.
3. **Flutter** `UnitInput` widget fetches the alias map once per session and coerces typed text on blur.
4. **Flutter** `StructuredIngredientRow` is rewritten to a single line with notes + optional toggle behind a caret; auto-expanded caret on initial render if those fields have values.

Also adds an `IngredientRowStateBadge` for ingredients whose canonical was auto-created via the Story 13.3 find-or-create path — so Leo knows when a new row joined the ingredient catalog.

## Goal

Every ingredient in Review Import, the recipe wizard, and recipe edit fits on one tap-target line. Notes + optional stay out of the way unless they have content. Units are always the canonical enum (tbsp, tsp, cup, g, ml, kg, lb, oz, …) regardless of what the LLM emitted, because the backend normalizes on every write and the Flutter widget coerces on blur.

## End-User Flow

1. Leo photo-imports a cookbook page. Backend runs the usual pipeline: parser → extractor → matcher. The extractor prompt (new this epic) emits `"unit": "tbsp"` not `"tablespoon"`. If the LLM slips and emits "tablespoon", the backend's `normalize_unit_display` coerces it to "tbsp" before persisting `parsed_recipe`.
2. Leo opens the needs-review row in the Imports tab (from the prior two epics) and taps **Review →** in the expansion action row.
3. Review Import screen loads. Under **Ingredients**, each row reads like: `[2]  [tbsp▾]  butter, melted           ⌄  🗑`. One line. Units are already clean.
4. Row 3 has notes ("room temperature"). Its caret is auto-expanded — Leo sees the notes inline without having to discover them.
5. Row 5 shows a small badge (`✨`) next to the name — indicates the canonical ingredient was auto-created (pending_review). Tap the badge → tooltip: "Added to your pantry catalog".
6. Leo edits row 2's unit: taps the unit dropdown, starts typing "tablespoon". On blur (or typing space), the input coerces to "tbsp" — the dropdown closes, the field shows "tbsp". If Leo really wanted "tablespoon" freeform (e.g., for an obscure unit), he can long-press the unit dropdown to disable coercion — but that's power-user, no UI surface for it in v1.
7. Row 7 is fully optional. Caret auto-expanded on render because `is_optional = true`. The optional toggle is visible inside the expansion.
8. Leo taps Save Recipe. Payload sends canonical unit tokens to backend; backend re-runs `normalize_unit_display` on save (defensive). Recipe is created with `tbsp` in `unit_display`.

## Frontend Changes

**Required — medium.** Refactor the ingredient row + unit input; add alias fetch + cache; wire ingredient-state badge.

### `StructuredIngredientRow` rewrite

- **One-line layout:** `Row(children: [qty, unit, name(flex), caret, delete])` — all in a single `Row`.
  - `qty` field: 56pt wide, compact numeric-friendly text input (keyboard `decimal`), accepts fractions (1/2, 1 1/2) via existing client-side parser.
  - `unit` dropdown: 88pt wide, reads from `kCuratedUnits` + backend alias map.
  - `name` field: `Expanded` with `TextOverflow.ellipsis`.
  - `caret`: toggles expansion of notes + optional controls below the row.
  - `delete`: trailing 40pt icon button.
- **Expansion below the row:** when caret is toggled open, renders `Row(children: [notesField(flex), optionalToggle])` under the main row. Height-animated via `AnimatedSize`.
- **Auto-expand rule:** on initial widget render, if `initialNotes.isNotEmpty || initialIsOptional == true`, the caret starts expanded. User can collapse manually.
- **Collapsed caret with hidden content indicator:** when caret is collapsed AND (notes has value OR is_optional == true), the caret icon renders with a small filled-dot indicator (8pt dot overlaid on the chevron).
- **Tap-target compliance:** full row height ≥44pt; delete + caret are each ≥40pt tap targets.
- **Narrow-screen behavior:** on screens < 360pt wide, `name` field is allowed to ellipsize to as narrow as 80pt before the layout cracks. Below that (shouldn't happen on supported devices), the row falls back to the old two-row layout as a defensive escape hatch — logged as a warning if it ever fires.
- **Semantics:** row semantics label reads "Ingredient: {qty} {unit} {name}{, optional}{, notes: {notes}}" for screen readers.

### `UnitInput` coerce-on-blur + alias fetch

- New method `_coerceUnit(String raw) → String`:
  - Trim + lowercase.
  - Lookup in cached alias map.
  - Hit → return canonical.
  - Miss → return raw unchanged.
- Coercion fires on: `FocusNode` loses focus, user types trailing space.
- **Alias fetch:** on first widget mount this session, call `GET /v1/units/aliases`. Cache result in a `SessionAliasMapProvider` (Riverpod). On fetch-error or pre-fetch, use a hardcoded fallback map of top ~20 aliases (tablespoon→tbsp, teaspoon→tsp, gram→g, kilogram→kg, pound→lb, ounce→oz, fluid ounce→fl oz, liter→l, milliliter→ml, cup→cup, each→each, pinch→pinch, dash→dash, clove→clove, slice→slice, gallon→gallon, quart→quart, pint→pint, mg→mg, milligram→mg).
- Coerced unit values write back to the row's state. If coerced value is not in `kCuratedUnits`, the row's unit dropdown falls into the "custom" free-text display path (unchanged existing behavior).

### `IngredientRowStateBadge`

- Small icon (a 14pt sparkle `✨` glyph or similar) rendered inline between `name` and `caret` in the row.
- Visible when the ingredient's canonical record has `pending_review = true` (the find-or-create auto-created it).
- Tap shows a tooltip or a small bottom-sheet with a short explainer ("New ingredient — added to your catalog for review. You can rename or merge it later.").
- Data source: the ingredient entity on the parsed_recipe payload gains a `pending_review_ingredient: bool` field (populated at response-serialization time by the backend — see below).

### Wiring across surfaces

- The rewritten `StructuredIngredientRow` is consumed by all three surfaces established in `epic-bugs-import-structured-ingredients`:
  - **Review Import** (`import_item_review_screen.dart`)
  - **Recipe wizard** (new-recipe flow)
  - **Recipe edit** (existing recipe edit flow)
- Each surface is touched to verify layout integrity — no surface is allowed to regress to the two-row layout. A widget test per surface asserts the one-line render.

## Backend Changes

**Required — medium.** New alias table + normalizer helper + prompt rewrites + endpoint for alias fetch.

### `unit_aliases` table + seed

- New migration creates:
  ```sql
  CREATE TABLE unit_aliases (
    alias VARCHAR(80) PRIMARY KEY,
    canonical_unit VARCHAR(32) NOT NULL REFERENCES units(name),
    created_at TIMESTAMPTZ DEFAULT NOW()
  );
  ```
- Seed rows committed in the migration itself (not a separate seed script) covering the top ~40 aliases:
  - Volume full-names: tablespoon→tbsp, teaspoon→tsp, cup→cup, fluid ounce→fl oz, fluid_ounce→fl oz, milliliter→ml, millilitre→ml, liter→l, litre→l, gallon→gallon, quart→quart, pint→pint
  - Weight full-names: gram→g, grams→g, kilogram→kg, kilograms→kg, kilo→kg, pound→lb, pounds→lb, lbs→lb, ounce→oz, ounces→oz, milligram→mg, milligrams→mg
  - Count full-names: cloves→clove, slices→slice, pinches→pinch, dashes→dash, ea→each
  - Common typos: tbsps→tbsp, tsps→tsp, tblsp→tbsp, teasp→tsp, Tbsp.→tbsp, Tbsp→tbsp, tblspn→tbsp
- `canonical_unit` FK references `units.name` — every seeded canonical must exist in `units` already (migration asserts at the top).

### `normalize_unit_display` helper

- New module `libraries/utils/utils/services/units/normalize.py` exposes:
  ```python
  def normalize_unit_display(raw: str | None, session: Session) -> str | None:
      """Coerce a freeform unit string to its canonical display token."""
  ```
- Implementation:
  - `None` or empty input returns unchanged.
  - Trim + lowercase.
  - If input is already in `units.name` (canonical set), return as-is.
  - Else lookup in `unit_aliases`; hit → return `canonical_unit`.
  - Miss → log an `error_logs` row with `service="audit"`, `error_type="UnitAliasMiss"`, `metadata={"raw": raw}`. Return `raw` unchanged.
- In-process cache: alias map loaded once per worker process on startup (Celery `@worker_process_init.connect`); cache is a dict. TTL infinite within a process; process restart picks up seed changes.
- Query-per-lookup fallback path used only if cache hasn't initialized yet (e.g., in unit tests without worker init). Normal production flow is O(1).

### Write-path wiring

- **`extract_recipe_task.py`:** after extractor runs, iterate `parsed_recipe["ingredients"]` and normalize each `unit` before persist. Apply `normalize_unit_display` pass.
- **`match_ingredients_task.py`:** no change (operates on names, not units).
- **`create_recipe_task.py`:** unit_display passed to `RecipeIngredient` is normalized (currently uses parsed or edited value as-is).
- **`approve_import_item.py`:** on user edits, normalize each ingredient's unit before persisting `user_edits` back.
- **Recipe create/update endpoints:** `CreateRecipe`, `UpdateRecipe` normalize ingredient units on input, before creating/updating `RecipeIngredient` rows.
- **Wizard draft save** (if a draft endpoint exists; confirm in workshop): same rule.
- Every wired path gets a unit test: "input with `tablespoon` produces stored `tbsp`."

### `GET /v1/units/aliases` endpoint

- New endpoint returns the full alias → canonical map as JSON:
  ```json
  { "aliases": { "tablespoon": "tbsp", "teaspoon": "tsp", "gram": "g", ... },
    "canonical": ["tsp", "tbsp", "cup", ...] }
  ```
- Response set with `Cache-Control: max-age=86400, public` so clients (and any intermediate caches) can cache for 24h.
- Authentication: require auth (mirror existing `/v1/*` policy) but not admin-only.
- P95 < 100ms (reads in-memory cache on the server side).

### `pending_review_ingredient` annotation on parsed_recipe responses

- When serializing `parsed_recipe.ingredients` in `GetImportItem` + `list_import_items`, for each ingredient emit `pending_review_ingredient: true` when EITHER `matched_ingredient_id IS NULL` OR the referenced `ingredients` row has `pending_review = true`. Otherwise omit the key entirely (smaller payload; Flutter treats null == false). Single batched query for all ingredients of an item — no N+1.
- This enables the Flutter `IngredientRowStateBadge` without a second fetch.
- Implementation: add a single `selectinload(ImportItem.parsed_recipe_ingredients_join)` or equivalent so the per-item ingredient lookup is a batched query, not N+1.

### Extractor prompt rewrites

- `ai_extractor.py`, `vision_extractor.py`, `text_extractor.py` prompts — the "unit:" instruction is rewritten:
  - **Before:** *"unit: the measurement unit ONLY (e.g. 'cup', 'tablespoon', 'pound', 'ounce', 'clove', 'can')"*
  - **After:** *"unit: use EXACTLY one of these tokens: `tsp, tbsp, cup, fl oz, ml, l, g, kg, oz, lb, each, pinch, dash, clove, slice, mg, gallon, quart, pint`. Do not write out full words. Do not add trailing punctuation."*
- Test: eval suite (epic 13.5) adds a check that ≥95% of extracted units on fixtures are in the canonical set. Below threshold fails the eval; deploy gates kick in when eval epic 13.8's gates are fully enforced (already done).

## Infrastructure Changes

**None.**

- One Alembic migration for `unit_aliases` table + seed rows + any supporting indexes.
- No new AWS resources, no env vars, no IAM, no Terraform changes.
- Extractor prompt changes and alias endpoint are code-only.

## Design Principles (refined via party-mode 2026-04-18)

1. **One-line is the only layout on supported devices.** No defensive two-row fallback — a debug assertion fires if `width < 320`, and a release-build telemetry event logs the edge case for later investigation.
2. **Locked layout math** for iPhone SE 1st-gen (320×568): `qty=48pt, unit=72pt, caret=40pt, delete=40pt, name=flex≥96pt`. These widths are asserted in widget tests.
3. **Notes + optional belong behind a caret.** They're present per AC but not in the default scan path. Auto-expand when they have content so data isn't hidden. **Expansion state lives on `IngredientRowData._expanded` (not widget state)** so manual collapse persists across auto-save rebuilds.
4. **Three layers, one source of truth.** Extractor emits enum; backend normalizes everything on write; frontend coerces on blur. No layer trusts the others blindly.
5. **Snapshots are immutable historical records.** `_create_version_snapshot` does NOT normalize unit_display (preserves history). `restore_version`-produced new rows DO normalize (the restored live row gets the canonical treatment).
6. **Alias table is a growing, human-curated resource.** Missed aliases log to `error_logs` via `log_unit_alias_miss(raw_unit, context)` helper; AST-lint test enforces the helper (no bare log calls).
7. **Every live write path normalizes.** Extract, approve-import, create/update recipe, restore-version, wizard save, fork-recipe. No exceptions on live writes. Snapshots are the only carve-out.
8. **Pending-review ingredient badge covers both cases.** Shown when `matched_ingredient_id IS NULL` (match not yet resolved) OR when the linked canonical ingredient has `pending_review = true`. Both are "user should know a new ingredient is entering the catalog."
9. **Client-side alias mirror is a synchronous value seeded with a hardcoded fallback.** `Provider<AliasMap>` with immediate hardcoded seed + side-effect fetch that replaces via state mutation. NOT a `FutureProvider` — coerce-on-blur must resolve synchronously.
10. **Feature flag the extractor prompt change.** `EXTRACTOR_EMIT_CANONICAL_UNITS` env var (default true; flippable via ECS task def without redeploy). This epic's flag flips FIRST (deterministic; lower risk); `EXTRACTOR_EMIT_CONFIDENCE` (rich-detail epic) flips second.
11. **Cursor behavior on coerce.** After `_coerceUnit` replaces controller.text, explicitly set `selection = TextSelection.collapsed(offset: coerced.length)` so the cursor lands at end-of-field. Strip trailing punctuation (`. , ;`) before alias lookup.

## File Structure (anticipated)

```
app/lib/features/recipes/add_recipe/widgets/
├── structured_ingredient_row.dart            # MAJOR REWRITE — one-line + caret expansion
├── unit_input.dart                           # MODIFIED — coerce-on-blur + on-space
└── ingredient_row_state_badge.dart           # NEW — ✨ badge for pending_review

app/lib/features/recipes/add_recipe/providers/
└── session_alias_map_provider.dart           # NEW — fetches + caches alias map

app/lib/core/constants/
└── ingredient_units.dart                     # MODIFIED — export hardcoded-fallback alias map

app/lib/core/api_client/
└── api_client.dart                           # MODIFIED — getUnitAliases method

services/api/src/api/v1/units/
├── __init__.py                               # NEW
└── get_unit_aliases.py                       # NEW — GET /v1/units/aliases

services/api/src/api/v1/import_job/
├── get_import_item.py                        # MODIFIED — emit pending_review_ingredient
└── list_import_items.py                      # MODIFIED — same

libraries/utils/utils/models/
└── unit_alias.py                             # NEW — UnitAlias SQLAlchemy model

libraries/utils/utils/services/units/
├── normalize.py                              # NEW — normalize_unit_display + alias cache
└── __init__.py                               # MODIFIED — export

libraries/utils/utils/services/recipe_extractors/
├── ai_extractor.py                           # MODIFIED — prompt rewrite
├── vision_extractor.py                       # MODIFIED — prompt rewrite
└── text_extractor.py                         # MODIFIED — prompt rewrite

libraries/utils/utils/tasks/import_tasks/
├── extract_recipe_task.py                    # MODIFIED — normalize after extract
├── create_recipe_task.py                     # MODIFIED — normalize on create
└── approve_import_item.py                    # MODIFIED — normalize on user-edits save

services/api/src/api/v1/recipes/
├── create_recipe.py                          # MODIFIED — normalize on input
└── update_recipe.py                          # MODIFIED — normalize on input

services/migrator/migrations/versions/
└── XXXX_create_unit_aliases_table_and_seed.py   # NEW migration + seed

eval/                                         # (if eval dir exists)
└── metrics/unit_enum_compliance.py           # NEW — assert ≥95% canonical in extracted units
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| riip-1 | Backend: `unit_aliases` table + seed + `UnitAlias` model + `normalize_unit_display` helper + in-process cache | 🔴 P0 | 1 d | None |
| riip-2 | Backend: wire `normalize_unit_display` into every write path (extract, create, approve, recipe CRUD) + unit tests per path | 🔴 P0 | 1 d | riip-1 |
| riip-3 | Backend: extractor prompt rewrites + eval-suite check for ≥95% canonical compliance | 🔴 P0 | 0.5 d | riip-1 |
| riip-4 | Backend: `GET /v1/units/aliases` endpoint + `pending_review_ingredient` annotation on import-item responses | 🟡 P1 | 0.5 d | riip-1 |
| riip-5 | Flutter: `UnitInput` coerce-on-blur + session alias fetch + hardcoded fallback | 🔴 P0 | 0.5 d | riip-4 (for endpoint) |
| riip-6 | Flutter: `StructuredIngredientRow` rewrite to one-line + caret expansion + auto-expand rule + collapsed-dot indicator | 🔴 P0 | 1.5 d | riip-5 |
| riip-7 | Flutter: `IngredientRowStateBadge` + tooltip + wire into row | 🟡 P1 | 0.5 d | riip-4, riip-6 |
| riip-8 | Regression pass across three surfaces (Review Import, wizard, recipe edit) + widget tests per surface | 🔴 P0 | 0.5 d | riip-6, riip-7 |

**Total estimated effort: 6 days**

**Parallel tracks:**
- Track A (backend data): riip-1 → riip-2 (serial)
- Track B (backend prompt): riip-3 parallel with A
- Track C (backend API): riip-4 parallel with A/B
- Track D (frontend): riip-5 → riip-6 → riip-7 → riip-8 (serial, blocked on backend tracks' completion)

---

## Story riip-1: Backend — `unit_aliases` table + seed + `normalize_unit_display` helper + cache

As the units backend,
I want an alias table that maps freeform unit strings to the canonical enum, and an O(1) helper that coerces inputs,
so every write path can normalize without a DB round trip per lookup.

### Acceptance Criteria

1. Migration creates `unit_aliases` table with columns: `alias` (VARCHAR(80), PK), `canonical_unit` (VARCHAR(32), NOT NULL, FK → `units.name`), `created_at` (TIMESTAMPTZ, default NOW()).
2. **Pre-condition check at migration head:** assert `units.name` has a `UNIQUE` constraint. If not, add `UNIQUE(name)` as a no-op-on-already-unique `ALTER TABLE` before creating the FK. Assert that every `canonical_unit` value in the seed exists in the `units` table up-front (query-based, not a Python set). Historical `units` rows with unexpected values (e.g., "teaspoon" alongside "tsp") are tolerated — the seed doesn't fail if other rows exist.
3. Migration seeds ≥40 alias rows covering the top aliases listed in the epic. Migration is idempotent (uses `INSERT ... ON CONFLICT DO NOTHING`).
4. `UnitAlias` SQLAlchemy model added in `libraries/utils/utils/models/unit_alias.py`.
5. `normalize_unit_display(raw: str | None, session: Session) -> str | None` in `libraries/utils/utils/services/units/normalize.py`:
    - `None` or empty → unchanged
    - Trim + lowercase + strip trailing punctuation (`. , ;`)
    - If input ∈ canonical `units.name` set → return as-is
    - Else lookup `unit_aliases` → hit returns `canonical_unit`, miss routes through `log_unit_alias_miss(raw, context)` helper; returns input unchanged
6. **`log_unit_alias_miss(raw: str, context: dict | None)` helper** in `libraries/utils/utils/logging/unit_logging.py` — writes to `error_logs` with `service="audit"`, `error_type="UnitAliasMiss"`, `metadata={"raw": raw, **context}`. This is the only sanctioned way to log alias misses.
7. **AST-lint enforcement test** in `libraries/utils/tests/logging/test_unit_alias_miss_enforcement.py` scans for any call that writes `error_type='UnitAliasMiss'` outside of `log_unit_alias_miss`. Fails CI if bare log calls slip in.
8. In-process cache initialized via Celery `@worker_process_init.connect`. FastAPI app also initializes on startup (`@app.on_event("startup")`). Cache is a plain dict mapping alias → canonical.
9. `reload_unit_alias_cache(session)` helper exposed for tests. Admin-endpoint wiring (`POST /v1/admin/units/reload-cache`) is **deferred** — helper exists unused in production until an admin alias-editing tool ships; tests call it directly to reset between test cases.
10. Unit tests: input `tablespoon` → output `tbsp`. Input `tbsp` → output `tbsp`. Input `Tbsp.` → output `tbsp` (punctuation-stripped + case-folded). Input `weirdunit` → output `weirdunit` + error_log row created via `log_unit_alias_miss`. Input `None` → output `None`.
11. Down-migration drops the table cleanly (leaves the `UNIQUE(name)` on `units` alone — it's not owned by this migration).

### Key Files

- Create: `services/migrator/migrations/versions/XXXX_create_unit_aliases_table_and_seed.py`
- Create: `libraries/utils/utils/models/unit_alias.py`
- Create: `libraries/utils/utils/services/units/normalize.py`
- Modify: `libraries/utils/utils/services/units/__init__.py`
- Modify: `services/api/src/main.py` (startup hook)
- Modify: `services/worker/celery_app.py` (worker init)
- Tests: `libraries/utils/tests/services/units/test_normalize.py`

---

## Story riip-2: Backend — normalize on every write path

As the imports + recipes backend,
I want every path that persists a unit to run through `normalize_unit_display` first,
so a downstream LLM or user typo can't pollute the canonical set.

### Acceptance Criteria

1. `extract_recipe_task.py` — after extractor emits `parsed_recipe`, iterate each `ingredient["unit"]` and apply `normalize_unit_display`. Persist normalized value. Add test: mock extractor emitting `tablespoon` → persisted `parsed_recipe` has `tbsp`.
2. `create_recipe_task.py` — when mapping `ing_data["unit"]` to `RecipeIngredient.unit_display`, normalize. Test: create recipe with `tablespoon` unit input → stored row has `unit_display = "tbsp"`.
3. `approve_import_item.py` — when persisting `user_edits.ingredients[*].unit`, normalize. Test: user-edit with `teaspoon` → stored `tsp`.
4. `CreateRecipe` / `UpdateRecipe` API handlers — normalize each `RecipeIngredientInput.unit` before persisting. Test per endpoint.
5. Wizard draft save — if a draft-save endpoint exists in the recipe wizard flow, normalize on save. Code audit at story kickoff locates the path (likely in `services/api/src/api/v1/recipes/` drafts). If no such endpoint exists today, this AC is a no-op and story notes record the audit.
6. **`restore_version` endpoint** — when the historical snapshot is being restored to a live row, normalize each unit_display. Snapshot rows themselves stay un-normalized (immutable history).
7. **`fork_recipe` endpoint** — when forking creates a new row with copied ingredients, normalize unit_display on the new row.
8. **`_create_version_snapshot` is explicitly EXCLUDED** — snapshots preserve history. An AC bullet says "Snapshot writes do NOT call `normalize_unit_display`; a code comment at the snapshot function explains why."
9. Each write-path test uses a fresh in-process alias cache to avoid cross-test pollution.
10. A single parametrized test table across `(path, input_unit, expected_stored_unit)` covers the happy path for all seven live write paths at once.
11. Regression: existing tests that assert `unit_display == "tablespoon"` are updated to expect `tbsp` (or the canonical equivalent); story notes list every test updated.
12. **Round-trip integration test** (one fixture, seven paths): sends `"tablespoon"` through each write path and asserts `tbsp` at every persistence read. Non-flaky — no real LLM call; extractor path uses a fake extractor that emits `tablespoon` deterministically.

### Key Files

- Modify: `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`
- Modify: `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`
- Modify: `libraries/utils/utils/tasks/import_tasks/approve_import_item.py`
- Modify: `services/api/src/api/v1/recipes/create_recipe.py`, `update_recipe.py`
- Tests: integration tests per path + the parametrized cross-path suite

---

## Story riip-3: Backend — extractor prompt rewrites + eval compliance metric

As the extractors,
I want my prompts to enumerate the canonical unit tokens explicitly so the LLM stops emitting full words,
so the backend normalizer has less work and the pipeline is more predictable.

### Acceptance Criteria

1. `ai_extractor.py`, `vision_extractor.py`, `text_extractor.py` prompt templates are updated to enumerate the canonical token list verbatim:
   `tsp, tbsp, cup, fl oz, ml, l, g, kg, oz, lb, each, pinch, dash, clove, slice, mg, gallon, quart, pint`
2. Prompt instruction explicitly forbids: full-word spellings, trailing punctuation, unit aliases.
3. Prompt template version bumped (if templates are versioned) or a comment at the top references this story.
4. **Feature flag `EXTRACTOR_EMIT_CANONICAL_UNITS`** env var (default `true`; flippable via ECS task def without redeploy). When `false`, extractors use the prior prompt (freeform units). The flag is read at extractor-call time, not at process-startup, so flips apply to the next request.
5. Eval fixtures in `services/eval/fixtures/` are re-run; eval runner reports a new metric `unit_enum_compliance` = fraction of extracted ingredients with `unit ∈ canonical_set`. Target ≥95% across the existing ~15 fixtures.
6. Below-threshold extractions are surfaced in the eval report with per-unit breakdown so we can see which tokens the LLM struggles with.
7. **Gate wiring is deferred to companion story `riip-3a` after ≥1 week of baseline data.** This story establishes the metric but doesn't block deploys on it.
8. Unit tests on each extractor verify:
    - With `EXTRACTOR_EMIT_CANONICAL_UNITS=true`, the prompt string contains the canonical token list.
    - With `EXTRACTOR_EMIT_CANONICAL_UNITS=false`, the prompt is the prior freeform version.
9. **Coordination with rich-detail epic:** the same prompt templates are touched by `irrd-3` (confidence score emission). The two changes land in a single combined PR that adds both the enum list AND the confidence-score emit instruction. Coordinate merge order — this epic's flag (`EXTRACTOR_EMIT_CANONICAL_UNITS`) flips on first; rich-detail's (`EXTRACTOR_EMIT_CONFIDENCE`) flips on second.

### Key Files

- Modify: `libraries/utils/utils/services/recipe_extractors/ai_extractor.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/vision_extractor.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/text_extractor.py`
- Create / modify: `services/eval/metrics/unit_enum_compliance.py`
- Modify: eval runner entry to include the new metric in reports

---

## Story riip-4: Backend — `GET /v1/units/aliases` endpoint + `pending_review_ingredient` annotation

As the Flutter client,
I want a cacheable endpoint returning the full alias map and I want import-item responses to flag pending-review ingredients,
so I can coerce-on-blur offline-friendly and render the ✨ badge without a second fetch.

### Acceptance Criteria

1. New `GET /v1/units/aliases` endpoint returns:
    ```json
    { "aliases": {"tablespoon": "tbsp", ...},
      "canonical": ["tsp", "tbsp", ...] }
    ```
2. Response headers include `Cache-Control: max-age=86400, public`. Client caching is explicit.
3. Endpoint requires auth (consistent with other `/v1/*` routes).
4. Endpoint reads from the in-process alias cache — P95 < 50ms.
5. `GetImportItem` and `list_import_items` — when serializing `parsed_recipe.ingredients`, **for each ingredient (regardless of whether `matched_ingredient_id` is set)**, emit `pending_review_ingredient: true` when EITHER:
    - `matched_ingredient_id IS NULL` (match not yet resolved / auto-create pending), OR
    - `matched_ingredient_id` resolves to a canonical `ingredients` row with `pending_review = true`.
    Otherwise omit the key entirely (smaller payload; Flutter treats null == false).
6. Join is batched (single query for all ingredients of an import item — no N+1).
7. Integration tests:
    - `GET /v1/units/aliases` returns expected shape + 200.
    - Seed an import item whose parsed_recipe references a pending-review canonical → response flags it.
    - Seed one whose ingredient has `matched_ingredient_id IS NULL` → response flags it.
    - Seed one fully matched to an already-reviewed canonical → response omits the flag.

### Key Files

- Create: `services/api/src/api/v1/units/__init__.py`
- Create: `services/api/src/api/v1/units/get_unit_aliases.py`
- Wire into FastAPI router
- Modify: `services/api/src/api/v1/import_job/get_import_item.py`, `list_import_items.py`
- Tests: per-endpoint integration tests

---

## Story riip-5: Flutter — `UnitInput` coerce-on-blur + session alias map

As Leo,
I want typing "tablespoon" in the unit dropdown to auto-snap to "tbsp",
so my units match the canonical enum even when I type full words out of habit.

### Acceptance Criteria

1. `UnitInput` widget adds a private `_coerceUnit(String raw) → String` method:
    - Trim + lowercase.
    - **Strip trailing punctuation** (`.`, `,`, `;`) via `.replaceAll(RegExp(r'[.,;]+$'), '')`.
    - If raw ∈ canonical set, return raw.
    - Lookup in `SessionAliasMapProvider`'s cached map, return canonical on hit.
    - Miss returns raw unchanged.
2. Coerce fires on:
    - `FocusNode` loses focus (blur).
    - User presses space inside the input (or types `" "`).
3. On coerce-hit that changes the value:
    - `controller.text = coerced`
    - `controller.selection = TextSelection.collapsed(offset: coerced.length)` (prevents cursor-at-zero bug)
    - `onChanged` callback fires with the canonical value so the parent row state updates.
4. **`SessionAliasMapProvider` is a `Provider<AliasMap>` (not `FutureProvider`)** — seeded synchronously with the hardcoded fallback map so `_coerceUnit` always has something to read. A side-effect fetch (e.g., via `ref.read(apiClientProvider).getUnitAliases()` in an `init()` method at app startup) replaces the seed via state mutation when the server response lands. The provider never returns Future/AsyncValue.
5. Hardcoded fallback map is defined in `app/lib/core/constants/ingredient_units.dart` alongside `kCuratedUnits`.
6. Coerce is disabled when the `UnitInput` is in "custom" free-text mode (user picked a unit not in `kCuratedUnits`) — so power-users can still type a freeform value without having it squashed. **Default is coerce-on.**
7. **Paste handler on qty field** (not the unit field, but co-located concern): if the user pastes a multi-token string (e.g., "2 tablespoons") into the qty field, the paste handler strips to the leading numeric-or-fraction token. Anything after whitespace drops with a snackbar "Trimmed to quantity only — unit dropped".
8. Widget tests:
    - Typing "tablespoon" + blur → field value becomes "tbsp", cursor at end.
    - Typing "Tbsp." + blur → "tbsp" (punctuation + case stripped).
    - Typing "weirdunit" + blur → stays "weirdunit".
    - Typing "Tablespoon " (mixed-case + space) → "tbsp" on space trigger.
    - Pasting "2 tablespoons" into qty field → qty becomes "2", snackbar fires.
9. Integration test: mount a `StructuredIngredientRow` with `UnitInput`, type "tablespoon", tab out, assert field text = "tbsp" AND the row's state map has the canonical value AND cursor is at end-of-field.

### Key Files

- Modify: `app/lib/features/recipes/add_recipe/widgets/unit_input.dart`
- Create: `app/lib/features/recipes/add_recipe/providers/session_alias_map_provider.dart`
- Modify: `app/lib/core/constants/ingredient_units.dart`
- Modify: `app/lib/core/api_client/api_client.dart` (add `getUnitAliases`)
- Tests: `app/test/features/recipes/add_recipe/widgets/unit_input_test.dart`

---

## Story riip-6: Flutter — `StructuredIngredientRow` one-line rewrite + caret + auto-expand

As Leo,
I want every ingredient in Review Import, the wizard, and recipe edit to fit on one line with notes and optional hidden behind a caret,
so my review flow doesn't feel like scrolling through a wall of two-row entries.

### Acceptance Criteria

1. `StructuredIngredientRow` rewritten to render as a single `Row`: `[qty: 48pt] [unit: 72pt] [name: flex, ellipsis ≥96pt on 320pt-width] [caret: 40pt] [delete: 40pt]`. Locked layout math; widths asserted in widget tests.
2. Caret button toggles expansion of a secondary row below, containing: `[notes: flex] [optional: toggle]`.
3. Auto-expand rule: on `initState`, if `widget.initialNotes != null && initialNotes.isNotEmpty` OR `widget.initialIsOptional == true`, the caret starts expanded. **Expansion state lives on `IngredientRowData._expanded` (source of truth) — NOT ephemeral widget state** — so manual collapse persists across auto-save rebuilds of the screen.
4. Collapsed-state indicator: when `_expanded == false` AND (notes has value OR is_optional == true), the caret icon overlays a 6–8pt filled dot. Dot uses `colorScheme.tertiary` (attention signal — **NOT** `ImportStateColors`, which is import-state-specific per workshop 1 lock).
5. Tap-target compliance: every interactive element (qty, unit, caret, delete) has ≥40pt tap target height; parent row is ≥48dp (Material tap target minimum) total.
6. Name `Expanded` with `TextOverflow.ellipsis` on overflow. No wrapping.
7. **No defensive two-row fallback.** A `assert(constraints.maxWidth >= 320, 'ingredient row requires ≥320pt width')` in debug builds. In release builds, if width < 320, log `error_logs service='app' error_type='IngredientRowNarrowScreen'` via the existing error-logging helper; row still renders (clipping accepted) — we observe the edge case, not hide it.
8. Semantics label on the row reads: "Ingredient: {qty} {unit} {name}{, optional}{, notes: {notes}}"; caret semantic label: "Show notes and options" ↔ "Hide notes and options".
9. Swipe-to-delete and delete-icon behavior from the existing widget is preserved.
10. Widget tests:
    - Default state (no notes, not optional) → caret collapsed, no dot.
    - Initial notes present → caret auto-expanded.
    - Initial is_optional = true → caret auto-expanded.
    - Manual collapse after auto-expand → caret shows dot.
    - Manual collapse survives a simulated auto-save rebuild (force `setState` on parent).
    - Tap caret → expansion toggles.
    - Name overflow → renders with ellipsis.
    - At 320pt parent width, assert qty is exactly 48pt, unit exactly 72pt, caret+delete each 40pt, name ≥96pt.

### Key Files

- Major rewrite: `app/lib/features/recipes/add_recipe/widgets/structured_ingredient_row.dart`
- Tests: `app/test/features/recipes/add_recipe/widgets/structured_ingredient_row_test.dart`

---

## Story riip-7: Flutter — `IngredientRowStateBadge`

As Leo,
I want a small badge on ingredient rows whose canonical ingredient was auto-created so I know a new item joined my catalog,
so I can review/rename/merge it later without it happening silently.

### Acceptance Criteria

1. New `IngredientRowStateBadge` widget: 14pt sparkle glyph (`Icons.auto_awesome` or equivalent).
2. Rendered inline in `StructuredIngredientRow` between `name` and `caret`, only when `ingredient.pendingReviewIngredient == true`.
3. Tap opens a tooltip (on hover-capable) or a small bottom-sheet (on tap-only): "New ingredient — '{name}' was added to your catalog. You can rename or merge it later in Settings › Pantry."
4. Badge color is `ImportStateColors.inProgress` (subtle blue, not alarming).
5. `StructuredIngredientRow` gains a `pendingReviewIngredient: bool?` parameter (defaults to false/null = badge hidden).
6. Review Import + recipe wizard + recipe edit surfaces pass this flag from the parsed_recipe / recipe payload (using the new `pending_review_ingredient` annotation from riip-4).
7. Widget test: row rendered with flag = true shows the badge; tap opens sheet; row rendered with flag = false hides the badge.

### Key Files

- Create: `app/lib/features/recipes/add_recipe/widgets/ingredient_row_state_badge.dart`
- Modify: `app/lib/features/recipes/add_recipe/widgets/structured_ingredient_row.dart` (accept + wire flag)
- Modify: `app/lib/features/recipes/add_recipe/import_item_review_screen.dart` (pass flag)
- Modify: recipe wizard + recipe edit screens (pass flag where data is available)
- Tests: `app/test/features/recipes/add_recipe/widgets/ingredient_row_state_badge_test.dart`

---

## Story riip-8: Regression pass — three surfaces + end-to-end photo-import smoke test

As Leo,
I want to know the one-line ingredient row works in every place it shows up, and I want a real-device smoke that a photo-imported recipe lands with canonical units everywhere,
so this epic's promise is delivered, not just "shipped in one screen".

### Acceptance Criteria

1. Three surfaces confirmed to render `StructuredIngredientRow` in one-line layout:
    - **Review Import** (`import_item_review_screen.dart`).
    - **Recipe wizard** (new-recipe flow).
    - **Recipe edit** (existing-recipe edit flow).
2. A widget test per surface pumps a recipe with mixed ingredient shapes (some with notes, some optional, some plain) and asserts one-line render + correct auto-expand behavior.
3. Regression: cooking-mode read-only display of ingredients is unchanged (not in scope, but audit confirms it).
4. End-to-end smoke on a real device:
    - Photo-import a real cookbook page (fixture from eval suite).
    - Open Review Import.
    - Assert: every ingredient is one-line; units are canonical (no "tablespoon"); any row with notes has them auto-expanded; the ✨ badge shows where expected.
    - Save the recipe.
    - Open the saved recipe in Recipe Detail.
    - Assert units render as canonical there too.
5. Story notes include screenshots or a short video of the smoke result.
6. Any regressions found in the three surfaces OR the read-only view are fixed in this story (they would have slipped through unit tests).
7. **Golden tests at iPhone SE 1st-gen (320×568) for each of the three surfaces**, with two fixtures per surface: (a) a row with notes + optional present (auto-expanded), (b) a row with neither (collapsed, no dot). Tolerance tight enough to catch a `Row`→`Column` accidental swap.
8. **Accessibility-tree snapshot test per surface** asserting the ingredient row is structurally one `Row`, not a `Column`-of-`Row`s. Structural drift here is exactly how a two-row regression sneaks back in.

### Key Files

- Modify: `app/lib/features/recipes/add_recipe/import_item_review_screen.dart` — layout sanity check
- Modify: recipe wizard + recipe edit — layout sanity check
- Tests: widget tests per surface; story notes + artifacts for manual smoke

---

## Dependencies

- **Cross-epic:** Independent. Can ship in parallel with `epic-activity-hub-redesign` and `epic-import-row-rich-detail`.
- **Cross-cutting:** Touches extractors (shared with epic-import-row-rich-detail's confidence work) — coordinate file changes in `libraries/utils/utils/services/recipe_extractors/` if the two epics ship concurrently.
- **No merge-freeze collisions:** different files from the other two epics.
- **Inherits from:** `epic-bugs-import-structured-ingredients` (already shipped — that epic established the three-surface structured row; this epic refactors its internal layout + adds unit normalization).

## Open Questions for the User

- **Extractor prompt coordination:** epic-import-row-rich-detail also rewrites extractor prompts (to add `confidence_score`). Do both prompt changes land in one combined PR, or separate? Recommended: combined, since they touch the same prompt templates. Workshop resolution.
- **"Custom mode" disable-coerce:** does Leo want a visible toggle to disable coerce-on-blur for power users, or is the implicit behavior (coerce disabled when unit is in custom mode) enough? Recommended: implicit. Keep UI clean.
- **`pending_review_ingredient` false vs. omit:** response-shape question. Emit `false` explicitly, or omit the key entirely? Recommended: omit when false — smaller payloads, Flutter code treats null same as false.

(All three default if not raised in workshop.)

## Definition of Done (Epic Level)

- `unit_aliases` table shipped with ≥40 seed rows; `normalize_unit_display` runs on every write path; unit tests cover every path.
- `GET /v1/units/aliases` returns the full map with 24h `Cache-Control`.
- Extractor prompts enumerate the canonical token list; eval suite reports ≥95% unit_enum_compliance.
- Flutter `UnitInput` coerces typed text on blur using the session-cached alias map; hardcoded fallback works offline/pre-fetch.
- `StructuredIngredientRow` renders one-line across Review Import, wizard, and recipe edit. Notes + optional behind the caret. Auto-expand rule fires when those fields have values. Collapsed indicator dot shows when hidden content exists.
- `IngredientRowStateBadge` renders on rows whose ingredient was auto-created via find-or-create.
- End-to-end photo-import smoke test passes on a real device: every unit is canonical, every row is one line.
- No regressions in cooking-mode read-only ingredient rendering.
