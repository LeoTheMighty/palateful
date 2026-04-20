<!-- refined via party-mode 2026-04-20 -->
# Epic: Ingredients → Glorified String (rip out dedup, matching, substitution, pantry-check)

## Overview

Ingredients in Palateful today are modelled as a canonical catalog with (a) a 4-tier runtime matcher (cache → exact → `pg_trgm` fuzzy → auto-create) running on every recipe import, (b) a substitution graph (empty in prod), (c) an ingredient-hierarchy `parent_id` (unused), (d) a 384-dim pgvector embedding column + HNSW index (never queried), (e) a `pending_review` review-queue flag, and (f) a shared offline "ingredient-scraper" service that seeded ~5k canonical rows from TheMealDB/USDA/OpenFoodFacts. A lot of moving parts converging on the implicit goal: "same ingredient across recipes resolves to one id."

After a design re-evaluation 2026-04-20 the user decided: **every cross-recipe identity feature earned by that machinery is either not shipping or not worth the complexity.** Shopping-list sum-within-meal dedup is the single user-visible consumer, and the user explicitly opted into duplicate line items on the shopping list ("checking off oil twice while shopping is a totally fine UX"). Pantry check ("I already have this") is cut outright. Autocomplete is accepted as a future rebuild. Semantic closeness / substitutions, if ever needed, will come from LLM or vector queries at read time — not from a write-time knowledge graph that's never been populated.

**Goal.** Rewrite ingredients as a glorified string.
- `ingredients` table stays as a bag of rows — one row per unique name ever seen, no uniqueness, no canonical/pending_review/category/embedding concept.
- Every write path (extract, recipe create/update, import approve) creates a fresh `ingredients` row from the raw name. No matching, no `find_or_create`, no tiered lookup.
- `recipe_ingredients.ingredient_id`, `pantry_ingredients.ingredient_id`, `shopping_list_items.ingredient_id`, `pantry_ingredient_events.ingredient_id` FKs remain — they continue to give us referential integrity and a stable display-name lookup — but nothing cross-references them for identity semantics.
- `aggregate_meal_ingredients()` stops de-duping; each component ingredient flows through as its own shopping-list line item.
- Pantry check in shopping-list generation is deleted entirely.
- Ingredient search endpoint, pending-review annotation, substitution table, fuzzy PL/pgSQL function all go.
- `services/ingredient-scraper/` stays untouched (parked; may be re-used for a future feature) with a README note that its output has no live consumer. Its consumer (`services/migrator/seeds/ingredients.py`) is deleted.

**What this epic is NOT.** Not a rewrite to vector / LLM matching. Not a UX redesign of the shopping list. Not a data migration of existing production data — user accepts that existing rows with raw-string `canonical_name` values remain as-is. This is a code / schema / contract simplification.

## Design Principles (refined via party-mode 2026-04-20)

1. **Glorified string, not "delete the table."** FKs stay — they give us cheap referential integrity and the `recipe_detail.ingredients[].name` lookup stays on a proper relationship. Dropping FKs would force every render path to denormalize a name onto every child row. Keep the table; just strip its semantics.
2. **No backward-compat shim on the matcher.** Delete `match_ingredients_task` and `ingredient_resolver`; replace with a one-line inline INSERT at every call site. Imports on old clients that send an `ingredient_id` keep working because the create path still returns an id; clients that send a `name` also still work (via the mechanism landed in `bugs-imp-ing-5`).
3. **Delete, don't deprecate** schema objects that are empty or now-dead in prod: `ingredient_substitutions` table, `ingredients.embedding` column + `idx_ingredients_embedding` HNSW index, `ingredients.parent_id` column + self-FK, `ingredients.pending_review` column, `ingredients.is_canonical` column, `ingredients.aliases` column, `ingredients.category` column (confirmed DROP in party-mode), unique index on `canonical_name` (auto-named `ingredients_canonical_name_key`), `idx_ingredients_canonical_name_trgm` pg_trgm GIN index, `search_ingredients_fuzzy()` PL/pgSQL function, `ingredient_matches` cache table. One Alembic migration.
4. **Duplicate line items on the shopping list are the expected outcome**, not a regression. Captured in PRD addendum + sprint-status note so no future planner "fixes" it. Ordering is deterministic: `meal.components` order × each component's `recipe.ingredients` order — asserted in str-ing-2 test scope.
5. **Pantry check is gone, not muted.** The `check_pantry` param, its callers, and the `PantryIngredient` → `recipe_ingredients.ingredient_id` set-membership check all get deleted. `pantry_ingredient_events.ingredient_id` FK stays (audit trail of what user physically has, no cross-ref intent). `shopping_list_items.already_have_quantity` column is **retained** as an always-NULL placeholder for a possible future pantry-check revival — avoids a second migration if we ever bring it back.
6. **Coverage is load-bearing.** `services/api` is pinned at 100%. Every story enumerates its test-site deletions / rewrites by exact method / class name. No "verify later."
7. **Scraper is frozen, not deleted.** User keeps the option to repurpose it. The CSV-output → `migrator/seeds/ingredients.py` consumer goes; scraper source + README stay; README gains a dated note "output has no live consumer as of 2026-04-20."
8. **Flutter ingredient-search autocomplete goes dark.** The `/v1/ingredients/search` endpoint is deleted; the `app/lib/features/pantry/widgets/ingredient_search.dart` widget's server call is removed (it falls back to a free-text field); any recipe wizard / edit call to the endpoint is removed. The user accepted this regression.
9. **Cross-epic rescope is part of this epic.** `epic-review-import-ingredient-polish` (backlog) is rescoped in str-ing-5 — its `riip-4` annotation work drops the pending-review half, `riip-7` (IngredientRowStateBadge) is deleted in full, PRD FR141 + FR144 get addended. No "do it later" — either we rescope here or riip-4/riip-7 start life broken.
10. **No parallel matcher hiding in MCP.** `services/api/src/mcp_server/tools/recipes.py::_resolve_ingredient` (line 33) and `INGREDIENT_MATCH_THRESHOLD = 0.85` (line 30) run a pg_trgm similarity match from the MCP recipe-create + fork-recipe tools (call sites at lines 159, 253). When we gut matching from the Flutter/import path, we gut it from MCP too — otherwise the system ships half-matched, where AI-driven recipe creation dedups but user-driven creation doesn't. str-ing-2 scope owns this.
11. **`ingredient.category` reader deletion is coupled into str-ing-2**, not str-ing-4. Four live handlers read `ingredient.category` into downstream objects (`meal_event/add_to_shopping_list.py:148`, `shopping_list/populate_from_recipe.py:111`, `shopping_list/generate_from_meal_event.py:115`, `recipe/create_recipe.py:161`). If the schema migration (str-ing-4) drops the column before these four handlers stop reading it, the app breaks between the two deploys. Order: handlers stop reading → deploy → migration drops column → deploy. (Two other readers at `ingredient/create_ingredient.py:56` + `ingredient/get_ingredient.py:38` are inside files DELETED wholesale by str-ing-3.)

## Locked decisions (carry forward to future planning)

- **Per-row identity over cross-row identity.** The ingredient table is a display cache, not an identity graph. Planners proposing cross-recipe matching / substitutions / "similar ingredients" must re-justify write-time canonicalization from scratch; past design docs (INGREDIENT_SCRAPER_DESIGN.md, architecture.md §"Smart matching") are frozen-in-time artifacts not current policy.
- **LLM / vector for similarity comes at read time, not write time.** If future epics need "what else could I use instead of olive oil" they run an inference call in that request's handler, not on every recipe import.
- **Duplicate shopping-list items are acceptable.** "Olive oil × 2" is a first-class outcome, not a bug to sum-dedupe. Ordering is `meal.components` × each component's `recipe.ingredients` — stable across runs so adjacent duplicates stay adjacent on screen.
- **Autocomplete without a canonical catalog is a future rebuild.** Options on the table when we pick it back up: user's own recent-history, frozen seed list, LLM-suggested completions. Out of this epic. str-ing-5 adds a placeholder line in `epics.md`'s backlog so this doesn't get lost.
- **Scraper stays parked.** Any future work that repurposes it must first re-evaluate the 2026-04-20 ripping-out of the canonical-matching goal. Don't silently re-wire it to a new destination without revisiting this epic's rationale.
- **MCP recipe tools follow the same "no matching" rule as Flutter recipe creation.** No AI-agent path gets a canonicalization superpower the user-facing path doesn't have.
- **Pantry screens are read-only with respect to shopping-list integration.** The pantry remains a "what I have" log; it does not filter / annotate / cross-reference the shopping list. A future epic can reintroduce cross-check — `shopping_list_items.already_have_quantity` is kept as a NULL placeholder to enable it without a new migration.
- **`category` is a recipe-ingredient-level display attribute now, not an ingredient-level canonical truth.** Where category is useful (shopping-list grouping), the four live handlers pass `None` post-str-ing-2; any future "smart grouping" feature derives category from the per-recipe name at request time, not from a canonical column.

## End-user flow

### Recipe import (happy path)

1. Leo photo-imports a cookbook page with olive oil on three different recipes. Backend extractor runs, emits `{"name": "olive oil", "quantity": 1, "unit": "tbsp"}` etc. per ingredient per recipe.
2. `create_recipe_task` for each parsed recipe does an inline `session.add(Ingredient(canonical_name="olive oil")); await session.flush()` per ingredient → fresh `ingredients` row (id=A for recipe 1, id=B for recipe 2, id=C for recipe 3). No matcher, no pending-review flag, no cache. Same behaviour for MCP-driven creation via `mcp_server/tools/recipes.py::create_recipe` and `fork_recipe`.
3. Recipe 1's `recipe_ingredients` row points at id=A; recipe 2 at id=B; recipe 3 at id=C. Each `canonical_name` is "olive oil" verbatim.
4. Review Import screen renders the parsed recipes. No IngredientRowStateBadge. Units still normalize (unchanged from `epic-review-import-ingredient-polish` riip-1/riip-2/riip-3/riip-5/riip-6 — those stories stay; only the pending-review pieces of riip-4/riip-7 are cut).
5. Leo approves. Recipes land in his book.

### Meal with shared-across-recipes ingredient

6. Leo creates a Meal with Recipe A (uses olive oil id=A) and Recipe B (uses olive oil id=B).
7. On the Meal detail screen he taps Add-to-Shopping-List. `aggregate_meal_ingredients(meal_id)` runs — **no dedup**. Returns every `recipe_ingredients` row from every component recipe as-is, in stable order: all of Recipe A's ingredients first (in their recipe order), then Recipe B's. Two "olive oil" entries appear adjacent because component ordering is preserved.
8. Shopping list gains two "olive oil" line items (adjacent, one per recipe). Leo checks each off as he shops. User accepts this by design.

### Adding a planned-meal event to shopping list

9. Leo plans the Meal on Thursday. Taps per-meal shopping-cart icon (cpms-1). `POST /v1/meal-events/{event_id}/add-to-shopping-list` — when the event is a Meal (not a Recipe), uses `aggregate_meal_ingredients` → same no-dedup behaviour. Same duplicate line items. Same accept.

### Pantry

10. Leo manually adds olive oil to his pantry (existing pantry UI; creates `pantry_ingredients` row + `pantry_ingredient_events` row with fresh `ingredient_id`). The pantry detail screen renders unchanged — quantities, events, all still there.
11. Tomorrow Leo plans a recipe that needs olive oil. Shopping-list gen does NOT check pantry — `check_pantry=True` path deleted. The olive oil line item shows up on the list regardless of pantry stock. Leo manually omits it if he doesn't need it. Pantry still serves as "here's what I have" read-only view; no cross-ref into shopping-list generation.

### Search / autocomplete

12. Recipe edit / create flows: the unit + structured-row widget stays (from `epic-bugs-import-structured-ingredients` + `epic-review-import-ingredient-polish` less the pending-review badge). Ingredient name field is a plain text field — no autocomplete-via-server. User types "olive oil". No network call.
13. The pantry `ingredient_search.dart` widget keeps its UI shell but its server call is removed — fallback free-text entry only.

### Admin

14. No admin page today surfaces pending-review ingredients, so nothing visible regresses there. The two admin notification-health dashboards are untouched.

## Frontend changes

**Required — medium.** Remove autocomplete server calls, remove pending-review badge (which **does exist in-tree today** as `ingredient_row_state_badge.dart` + test file, per party-mode audit — draft erroneously assumed backlog), remove ingredient-search UI hooks.

- `app/lib/features/pantry/widgets/ingredient_search.dart` — delete `searchIngredients(query)` server call + its debounce / spinner / "no results" empty-state sub-widgets. Replace with a plain `TextField` wrapped in `Semantics(label: "Ingredient name")` (or delete the widget wholesale and inline a `TextField` at its one caller; audit at impl).
- `app/lib/core/services/api_client.dart` — delete `searchIngredients`, `createIngredient`, `getIngredient` methods.
- `app/lib/features/recipes/add_recipe/widgets/structured_ingredient_row.dart` — remove the `pendingReviewIngredient` parameter and all wiring. The one-line row layout from riip-6 stays.
- `app/lib/features/recipes/add_recipe/widgets/ingredient_row_state_badge.dart` (96 LOC, confirmed present) — **DELETE**.
- `app/test/features/recipes/widgets/ingredient_row_state_badge_test.dart` (95 LOC, confirmed present) — **DELETE**.
- `app/lib/features/recipes/add_recipe/ingredient_edits_mapping.dart` — grep hit for `searchIngredients` and/or `pendingReviewIngredient`; audit + remove affected code paths at impl.
- `app/lib/features/recipes/add_recipe/import_item_review_screen.dart` — delete pending-review annotation wiring; audit that the row layout does not leave a stale empty slot where the badge used to render (re-run widget-test render at narrow width after the deletion).
- Import item payload decoding: drop the `pending_review_ingredient` field handling — `GetImportItem._annotate_pending_review_ingredients` exists today and populates this, so something in Flutter reads it. Audit the decoder at impl time.
- Any Riverpod / provider tied to ingredient-search debounce state: remove, after confirming it has no other subscribers.
- Any keyboard handler (down-arrow navigation into suggestion list) inside recipe create/edit ingredient-name fields: remove — there are no suggestions to navigate into.

## Backend changes

**Required — large.** Matcher + resolver gone; schema drops; endpoint deletes; aggregate dedup gutted; pantry check gone.

### Runtime logic

- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py` — **DELETE** (467 LOC) in favor of an inline "create one row per parsed ingredient" INSERT inside `create_recipe_task.py`. No tiered matching. No cache table read.
- **`libraries/utils/utils/services/ingredient_resolver.py`** (88 LOC, **corrected path** from party-mode — draft had wrong location) — **DELETE** and inline. Every call site uses `session.add(Ingredient(canonical_name=name)); await session.flush()` then reads `.id`.
- `services/api/src/mcp_server/tools/recipes.py` — **DELETE** module-level `INGREDIENT_MATCH_THRESHOLD = 0.85` (line 30) and `_resolve_ingredient(name, database, user)` function (line 33). Update both call sites (lines 159 in `create_recipe`, 253 in `fork_recipe`) to do the inline INSERT pattern. Remove both names from the module's `__all__` list (lines 329, 330).
- `libraries/utils/utils/services/meal_service.py::aggregate_meal_ingredients` — **strip the dedup logic entirely**. Return `[AggregatedIngredient(...)]` one-per-row, no summing, no `(ingredient_id, normalized_unit)` key. The function shape stays (callers keep working) but the summing branch is removed. Ordering: `meal.components` order × each component's `recipe.ingredients` order — stable across runs, duplicates stay adjacent.
- `services/api/src/api/v1/shopping_list/generate_from_meal_event.py` — delete `check_pantry` parameter, delete the `pantry_ingredients` lookup block (lines ~69–108), keep the rest of the populate path. Stop reading `recipe_ing.ingredient.category` at line 115; pass `category=None` into the `ShoppingListItem` constructor.
- `services/api/src/api/v1/shopping_list/populate_from_recipe.py` — stop reading `ingredient.category` at line 111; pass `category=None`.
- `services/api/src/api/v1/meal_event/add_to_shopping_list.py` — uses aggregate; inherits the no-dedup behaviour for free. Stop reading `ingredient.category` at line 148; pass `category=None`.
- `services/api/src/api/v1/recipe/create_recipe.py` — stop reading `ingredient.category` at line 161; pass `category=None`.
- `services/api/src/api/v1/meal/add_meal_to_shopping_list.py` (mcal-5) — inherits no-dedup from aggregate; audit for any category read and fix similarly.
- `services/api/src/api/v1/import_job/get_import_item.py::_annotate_pending_review_ingredients` — **DELETE** function and its call sites. Batched lookup of pending-review flag goes with the column.
- `services/api/src/api/v1/import_job/list_import_jobs.py` — audit & remove any pending-review annotation hook.
- `services/api/src/schemas/shopping_list.py` — delete `check_pantry` field from the `GenerateFromMealEvent` request schema; set `model_config = ConfigDict(extra="forbid")` on the Params class so AC 4 (422 response for unknown `check_pantry`) is enforceable. Without `extra="forbid"`, Pydantic silently ignores unknown fields and AC 4 silently passes as 201.

### Endpoints

- `GET /v1/ingredients/search` — **DELETE**.
- `POST /v1/ingredients` — **DELETE** (no runtime need once matcher is gone; imports create rows internally via task code).
- `GET /v1/ingredients/{id}` — **DELETE** unless there's an in-app caller that needs it for a detail view; audit at impl time. Flutter recipe-detail reads ingredient names via the parent recipe response (batched), not via this endpoint, based on the architecture doc's response shape.
- Router cleanup in `services/api/src/routers/v1/` — delete the ingredient router registration.

### Schema migration (single Alembic revision, lands AFTER str-ing-2 + str-ing-3 are deployed)

1. DROP TABLE `ingredient_substitutions` (empty in prod; `TRUNCATE` first as safety).
2. DROP TABLE `ingredient_matches` (cache for the matcher that no longer runs).
3. DROP INDEX `idx_ingredients_embedding` (HNSW — **verified name** from `libraries/utils/utils/models/ingredient.py` line 27; draft had `ix_` prefix wrong).
4. DROP INDEX `idx_ingredients_canonical_name_trgm` (pg_trgm GIN — **verified `idx_` prefix**, draft had `ix_` wrong).
5. DROP CONSTRAINT `ingredients_canonical_name_key` (auto-named unique constraint from `unique=True` on `canonical_name`). Use `op.drop_constraint` by explicit name; do not use `drop_index`.
6. DROP COLUMN `ingredients.embedding` (vector(384)).
7. DROP COLUMN `ingredients.parent_id` (DROP FK constraint first, then column).
8. DROP COLUMN `ingredients.pending_review`.
9. DROP COLUMN `ingredients.is_canonical`.
10. DROP COLUMN `ingredients.aliases`.
11. DROP COLUMN `ingredients.category` — **confirmed DROP in party-mode** (closed the draft's Q1). The four handlers that read `ingredient.category` are updated in str-ing-2 to pass `None`; this migration only lands after str-ing-2 is in prod.
12. DROP FUNCTION `search_ingredients_fuzzy(text)` (PL/pgSQL).
13. **`shopping_list_items.already_have_quantity`** is **RETAINED** as an always-NULL placeholder for a possible future pantry-check revival. A code comment on the column in the model documents the retention with a dated note.
14. Down-migration re-creates all dropped columns/tables as empty + re-creates indexes. Rollback caveat documented in story notes: reverting the app to a version that reads `pending_review` NOT NULL requires also restoring data (not attempted by the migration); acceptable in the dogfood-only regime per user preview.

### SQLAlchemy model + schema changes

- `libraries/utils/utils/models/ingredient.py` — strip dropped columns + self-ref relationship.
- `libraries/utils/utils/models/ingredient_substitution.py` — **DELETE**.
- `libraries/utils/utils/models/ingredient_match.py` — **DELETE**.
- `libraries/utils/utils/models/__init__.py` — remove exports.
- `services/api/src/schemas/ingredient.py` — strip dropped fields from response/request schemas.
- `services/api/src/schemas/import_job.py` — strip `pending_review_ingredient` field from parsed-recipe ingredient sub-schema.

### Scraper + seeder

- `services/ingredient-scraper/` — **UNTOUCHED**. README gains a dated note at top: "As of 2026-04-20, this service's CSV output has no live consumer. Retained for possible future reuse."
- `services/migrator/seeds/ingredients.py` — **DELETE** (seeder consumed the scraper CSV, wrote canonical rows; with no uniqueness and no canonicalization, the seeder's semantics are moot). Any CI or docker-compose step that calls it goes with it.

### Eval

- `services/eval/src/evaluators/ingredient_matching_evaluator.py` — **DELETE**. No matcher → no matching metric.
- `services/eval/eval.config.yaml` — remove the evaluator entry.
- `services/eval/src/runner.py`, `main.py`, `config.py` — remove any import/registration of the ingredient-matching evaluator.

## Infrastructure changes

**None.**

- No new AWS resources, no new IAM, no new secrets, no env vars, no Terraform.
- No new Docker images; existing `api` and `migrator` images pick up the code changes on rebuild.
- Deploy is standard `npx nx run api:docker-build` + standard migration apply + standard Flutter release.
- Rollback: schema down-migration re-creates empty columns / tables / indexes (no prod data to preserve on those).

## File structure — touched paths

```
libraries/utils/utils/tasks/import_tasks/
├── match_ingredients_task.py                    # DELETED (467 LOC)
└── create_recipe_task.py                        # MODIFIED — inline one-line ingredient INSERT

libraries/utils/utils/services/meal_service.py   # MODIFIED — aggregate dedup removed

libraries/utils/utils/models/
├── ingredient.py                                # MODIFIED — strip columns
├── ingredient_substitution.py                   # DELETED
├── ingredient_match.py                          # DELETED
└── __init__.py                                  # MODIFIED — remove exports

libraries/utils/test/
├── test_match_ingredients_task.py               # DELETED
└── test_aggregate_meal_ingredients.py           # MODIFIED — dedup-case tests deleted, happy-path kept

services/api/src/utils/
└── ingredient_resolver.py                       # DELETED (or simplified to single INSERT helper)

services/api/src/api/v1/ingredient/              # DIRECTORY — all files DELETED (search/create/get)
services/api/src/api/v1/import_job/
├── get_import_item.py                           # MODIFIED — remove _annotate_pending_review_ingredients
└── list_import_jobs.py                          # MODIFIED — remove any pending-review hook

services/api/src/api/v1/shopping_list/
└── generate_from_meal_event.py                  # MODIFIED — remove check_pantry + pantry lookup

services/api/src/schemas/
├── ingredient.py                                # MODIFIED — strip fields
└── import_job.py                                # MODIFIED — drop pending_review_ingredient

services/api/src/routers/v1/
└── ingredient_router.py                         # DELETED (or router registration removed)

services/api/tests/
├── test_ingredient.py                           # DELETED
├── test_coverage_gaps.py                        # MODIFIED — enumerate per-story deletions
└── test_shopping_list.py                        # MODIFIED — pantry-check tests deleted

services/migrator/migrations/versions/
└── XXXX_drop_ingredient_canonicalization_infra.py   # NEW migration

services/migrator/seeds/
└── ingredients.py                               # DELETED

services/ingredient-scraper/
└── README.md                                    # MODIFIED — dated "no live consumer" note at top

services/eval/
├── eval.config.yaml                             # MODIFIED — drop evaluator entry
├── src/runner.py                                # MODIFIED — drop import
├── src/main.py                                  # MODIFIED — drop import if wired
├── src/config.py                                # MODIFIED — drop entry
└── src/evaluators/ingredient_matching_evaluator.py  # DELETED

app/lib/core/services/api_client.dart            # MODIFIED — delete searchIngredients, createIngredient, getIngredient
app/lib/features/pantry/widgets/ingredient_search.dart   # MODIFIED — remove server call (or widget deleted)
app/lib/features/recipes/add_recipe/widgets/
├── structured_ingredient_row.dart               # MODIFIED — drop any pendingReviewIngredient wiring if present
└── ingredient_row_state_badge.dart              # DELETED if present (likely does not exist yet)
app/lib/features/recipes/add_recipe/import_item_review_screen.dart   # MODIFIED — drop badge wiring

_bmad-output/planning-artifacts/
├── prd.md                                       # MODIFIED — dated addendum
├── architecture.md                              # MODIFIED — dated strikethroughs on §"Smart matching" + pgvector ingredient references
├── epics.md                                     # MODIFIED — dated addendum entry + rescope note on epic-review-import-ingredient-polish
├── epic-review-import-ingredient-polish.md      # MODIFIED — riip-4 partially rescoped, riip-7 deleted, dated note
└── epic-ingredients-string-simplification.md    # THIS FILE

_bmad-output/implementation-artifacts/
└── sprint-status.yaml                           # MODIFIED — new epic + stories; riip-7 deleted; riip-4 descoped

docs/
├── MVP.md                                       # MODIFIED — strike canonical-matching references
├── RECIPE_IMPORT_SYSTEM.md                      # MODIFIED — strike matcher tier references
└── INGREDIENT_SCRAPER_DESIGN.md                 # MODIFIED — prepend dated "design frozen, see epic-ingredients-string-simplification" note
```

## Stories

### str-ing-1 — Flutter: stop calling `/v1/ingredients/*` + drop pending-review UI + delete badge widget

**Why first.** Flutter unships endpoint callers before the backend deletes the endpoints, so the rollout window has zero 404-generating call paths on any shipped client.

**Scope**
- `app/lib/core/services/api_client.dart` — delete `searchIngredients`, `createIngredient`, `getIngredient` methods. Grep for callers, remove.
- `app/lib/features/pantry/widgets/ingredient_search.dart` — delete the server-backed search path + its debounce / spinner / "no results" empty-state sub-widgets; replace with a plain `TextField` wrapped in `Semantics(label: "Ingredient name", hint: "Type an ingredient")`. Audit at impl whether to keep the widget shell or inline a field at its one caller.
- `app/lib/features/recipes/add_recipe/widgets/structured_ingredient_row.dart` — remove the `pendingReviewIngredient` parameter and every caller's wiring. The one-line row layout from riip-6 stays; verify after deletion that the row does not leave an empty slot at narrow widths.
- `app/lib/features/recipes/add_recipe/widgets/ingredient_row_state_badge.dart` — **DELETE** (96 LOC, confirmed present).
- `app/test/features/recipes/widgets/ingredient_row_state_badge_test.dart` — **DELETE** (95 LOC, confirmed present; would otherwise fail to compile after widget deletion).
- `app/lib/features/recipes/add_recipe/ingredient_edits_mapping.dart` — grep hit for `searchIngredients` / `pendingReviewIngredient`; audit + remove affected code paths at impl.
- `app/lib/features/recipes/add_recipe/import_item_review_screen.dart` — remove badge-wiring code and the `pending_review_ingredient` field decoder; run its widget test to verify the row still renders cleanly at narrow width.
- Import-item model class (wherever it decodes `parsed_recipe.ingredients`) — drop the `pendingReviewIngredient` field.
- Any Riverpod / provider tied to ingredient-search debounce state: remove, after confirming it has no other subscribers.
- Any keyboard handler (down-arrow navigation into suggestion list) inside recipe create/edit ingredient-name fields: remove — no suggestions to navigate.
- Run `rg 'searchIngredients|createIngredient\b|getIngredient\b|pendingReviewIngredient|IngredientRowStateBadge' app/` — must return zero hits after this story.
- Run `flutter analyze` + `flutter test` — must pass.

**Acceptance criteria**
1. No Flutter code path calls `GET /v1/ingredients/search`, `POST /v1/ingredients`, or `GET /v1/ingredients/{id}`.
2. The pantry ingredient-search UI renders without server calls; typing a name in the field creates a plain-text value that the pantry add flow accepts.
3. No widget renders an IngredientRowStateBadge; no Flutter model decodes `pending_review_ingredient`.
4. `flutter analyze` passes with zero warnings from this story's edits.
5. `flutter test` passes.
6. Acceptance greps (above) return empty.

**Tests**
- Widget test: `pantry/ingredient_search.dart` renders a free-text field and calls `onIngredientSelected` (or equivalent) with a plain string, without any HTTP mock.
- Widget test: `structured_ingredient_row.dart` renders without the badge for both `pendingReviewIngredient=true` and `=false` fixtures (fixtures removed).
- Regression: any existing widget test that mocked `searchIngredients` is deleted or rewritten against the free-text path.

---

### str-ing-2 — Backend: gut the matcher + resolver + MCP matcher + aggregate-dedup + pantry check + category reads

**Why this story is large and cohesive.** Splitting would leave an interim state where some handlers match and others don't. The thesis — "matching doesn't exist anywhere in the backend" — must ship atomically. Workshop confirmed keep-as-one.

**Scope**
- Delete `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py` entirely.
- Delete `libraries/utils/utils/services/ingredient_resolver.py` (**corrected path**; 88 LOC); every call site uses inline `session.add(Ingredient(canonical_name=name)); await session.flush(); return new_row.id`.
- Modify `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py` to do inline create-per-name for each parsed ingredient. No cache read, no match, no pending-review write.
- **MCP parallel matcher removal** (new in this refinement):
  - Modify `services/api/src/mcp_server/tools/recipes.py` — delete `INGREDIENT_MATCH_THRESHOLD = 0.85` (line 30), delete `_resolve_ingredient(name, database, user)` (line 33). Remove both from the module's `__all__` list (lines 329, 330).
  - Rewrite call sites at line 159 (`create_recipe`) and line 253 (`fork_recipe`) to do the inline INSERT pattern.
  - Modify `services/api/tests/mcp_server/test_recipes.py` — delete every test case that asserted the resolver's pg_trgm matching behavior. Add positive assertions: `test_mcp_create_recipe_always_creates_new_ingredient_rows`, `test_mcp_fork_recipe_always_creates_new_ingredient_rows`.
- Modify `libraries/utils/utils/services/meal_service.py::aggregate_meal_ingredients`:
  - Remove the `(ingredient_id, normalized_unit) → AggregatedIngredient` dict accumulator.
  - Return a flat list: one `AggregatedIngredient` per `recipe_ingredients` row across all component recipes, preserving order (meal.components order × recipe.ingredients order). Duplicates appear adjacent (not summed).
  - Keep the function signature so `meal_event/add_to_shopping_list.py` and `meal/add_meal_to_shopping_list.py` keep working.
- Modify `services/api/src/api/v1/shopping_list/generate_from_meal_event.py`:
  - Delete `check_pantry` parameter from the handler signature.
  - Delete the `pantry_ingredients = {pi.ingredient_id: pi for pi in pantry_items}` block and the `if params.check_pantry and recipe_ing.ingredient_id in pantry_ingredients:` branch (~lines 69–108).
  - Line 115 — stop reading `recipe_ing.ingredient.category`; pass `category=None` into `ShoppingListItem`.
- Modify `services/api/src/schemas/shopping_list.py` — delete `check_pantry` field from `GenerateFromMealEvent` Params; add `model_config = ConfigDict(extra="forbid")` on the Params class so unknown-field rejection is enforced (required for AC 4).
- Modify `services/api/src/api/v1/shopping_list/populate_from_recipe.py` — line 111: stop reading `ingredient.category`; pass `category=None`.
- Modify `services/api/src/api/v1/meal_event/add_to_shopping_list.py` — line 148: stop reading `ingredient.category`; pass `category=None`.
- Modify `services/api/src/api/v1/recipe/create_recipe.py` — line 161: stop reading `ingredient.category`; pass `category=None`.
- Modify `services/api/src/api/v1/meal/add_meal_to_shopping_list.py` — audit for any `.category` read; apply same pattern if found.
- Modify `services/api/src/api/v1/import_job/get_import_item.py` — delete `_annotate_pending_review_ingredients` function + its call site. Response shape loses `pending_review_ingredient` on each ingredient.
- Modify `services/api/src/api/v1/import_job/list_import_jobs.py` — audit and remove any pending-review hook.
- Modify `services/api/src/schemas/import_job.py` — drop `pending_review_ingredient` field from the parsed-recipe ingredient sub-schema.
- Delete `libraries/utils/test/test_ingredient_find_or_create.py` (**corrected filename** from party-mode; 317 LOC — draft had wrong filename `test_match_ingredients_task.py`).
- Modify `libraries/utils/test/test_aggregate_meal_ingredients.py`:
  - Delete tests asserting dedup: `test_same_unit_merges_quantities`, `test_cross_unit_keeps_separate_rows`, `test_null_unit_dedupes_on_empty_key`, and related fixtures.
  - Add positive test `test_aggregate_emits_one_row_per_recipe_ingredient_even_on_overlap` — assert `len(result) == sum(len(r.ingredients) for r in components)`.
  - Add positive test `test_aggregate_preserves_component_then_ingredient_order` — fixture with 3 components, each with 2 ingredients; assert result order matches concatenation of `c1.ings + c2.ings + c3.ings`.
- Modify `services/api/tests/test_shopping_list.py` — delete the five pantry-check test bodies. Workshop confirmed these live inside `TestGenerateFromMealEvent` (not a separate `TestCheckPantry` class); the five `json={"check_pantry": ...}` sites are at lines 1649, 1682, 1721, 1760, 1798. Enumerate the five containing test methods by name in the story's implementation notes (audit at kickoff).
- Add positive test `test_generate_from_meal_event_ignores_pantry_stock` — seed pantry with olive oil, plan a recipe needing olive oil, assert shopping list still has the olive oil line item (proves pantry check is truly gone, not just tests deleted).
- Modify `services/api/tests/test_coverage_gaps.py` — enumerate at kickoff which class/method entries map to: deleted `_resolve_ingredient` (app + MCP), deleted `_annotate_pending_review_ingredients`, deleted pantry-check path, deleted `ingredient_matches` helpers. Strip every matching entry.
- Delete `services/eval/src/evaluators/ingredient_matching_evaluator.py`.
- Modify `services/eval/eval.config.yaml`, `src/runner.py`, `src/main.py`, `src/config.py` — drop every import / entry for the matching evaluator.

**Acceptance criteria**
1. `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py` does not exist. `from utils.tasks.import_tasks.match_ingredients_task import ...` raises `ImportError`.
2. Running an import (URL or photo fixture, via the existing `test_integration_*` harness) creates one `ingredients` row per parsed name; repeated names create repeated rows (no dedup, no `find_or_create`); no `ingredient_matches` rows are written.
3. `aggregate_meal_ingredients(meal_id)` returns one `AggregatedIngredient` per `recipe_ingredients` row across all components, in stable `components × ingredients` order. Duplicate (name, unit) pairs appear as adjacent distinct list entries.
4. `POST /v1/shopping-lists/{id}/populate-from-meal-event` with `{"check_pantry": true}` in body returns **422** (Pydantic `extra="forbid"` rejects the unknown field). Without the field entirely, returns 201 as before. Test asserts both branches.
5. Shopping lists generated from a meal-event with 2 recipes each using "olive oil" produce **2 adjacent "olive oil" line items**, not 1 merged.
6. `GetImportItem` response no longer contains `pending_review_ingredient` on any ingredient (integration test asserts absence).
7. MCP `create_recipe` and `fork_recipe` tool call paths do **not** go through `_resolve_ingredient`; each call creates a fresh `ingredients` row per ingredient name. MCP test file asserts this.
8. All four `ingredient.category` reader handlers pass `category=None` into their downstream objects. Integration test: create recipe → list shopping items; `shopping_list_items.category` is NULL.
9. `npx nx run api:test` passes. `npx nx run api:lint` passes. `npx nx run api:test --coverage` passes the pinned 100% threshold.
10. `services/eval/eval.config.yaml` has no `ingredient_matching_evaluator` entry. Eval runner imports cleanly.
11. Grep `rg '_resolve_ingredient|INGREDIENT_MATCH_THRESHOLD|find_or_create_ingredient|check_pantry' services/ libraries/` returns zero matches.
12. Positive test `test_generate_from_meal_event_ignores_pantry_stock` passes, proving the deletion is behavioural, not just test-file-deletion.

**Tests** (all named positively — this story must assert new behaviour, not only "tests were removed")
- Integration: full import happy-path with a 5-ingredient fixture using the same name 3× (e.g., "olive oil", "olive oil", "olive oil", "salt", "pepper"); assert exactly 5 `ingredients` rows created.
- Integration: shopping-list populate from a Meal with overlapping component ingredients; assert duplicate adjacent line items and a stable order.
- Integration: `test_generate_from_meal_event_ignores_pantry_stock` (above).
- Integration: MCP positive tests (above).
- Integration: `category=None` assertion on shopping-list-item output.
- Regression: dedup tests in `test_aggregate_meal_ingredients.py` DELETED in same commit as the code change; the happy-path tests kept are rewritten to not assert dedup.
- Regression: all five pantry-check test-method bodies in `TestGenerateFromMealEvent` DELETED (names enumerated in story notes at kickoff).

---

### str-ing-3 — Backend: delete `/v1/ingredients/*` endpoints + router registration

**Scope**
- Delete `services/api/src/api/v1/ingredient/` directory entirely (all handlers: `search_ingredients.py`, `create_ingredient.py`, `get_ingredient.py` — confirm file names at impl time).
- Delete the ingredient router registration in `services/api/src/routers/v1/` (file or block).
- Delete `services/api/tests/test_ingredient.py`.
- Delete any OpenAPI spec fragment referencing these endpoints (auto-regenerated, but verify).
- Grep `rg '/v1/ingredients' services/ app/ docs/` — must return only planning-artifact matches after this story.

**Acceptance criteria**
1. `GET /v1/ingredients/search`, `POST /v1/ingredients`, `GET /v1/ingredients/{id}` all return 404 from FastAPI (route not registered).
2. No Python module at `services/api/src/api/v1/ingredient/*` exists.
3. `services/api/tests/test_ingredient.py` does not exist. The remaining test suite passes.
4. `npx nx run api:test --coverage` passes the 100% threshold with no orphaned coverage lines from the deleted router.
5. Grep acceptance returns empty outside `_bmad-output/**`.

**Tests**
- No new tests (net deletion). Verify coverage doesn't regress.

---

### str-ing-4 — Backend: schema migration + SQLAlchemy model cleanup

**Why after str-ing-2 and str-ing-3.** No runtime code references the columns / tables / function once str-ing-2 and str-ing-3 have landed, so the migration drops clean. Deploy sequence: land str-ing-2 + str-ing-3 in one prod deploy (app stops reading / writing the dropped columns); then a follow-up deploy applies str-ing-4's migration.

**Scope**
- New Alembic migration `services/migrator/migrations/versions/XXXX_drop_ingredient_canonicalization_infra.py`:
  - `op.execute("TRUNCATE TABLE ingredient_substitutions")` (empty in prod anyway; safety).
  - `op.drop_table("ingredient_substitutions")`.
  - `op.drop_table("ingredient_matches")`.
  - `op.drop_index("idx_ingredients_embedding", table_name="ingredients")` — **verified `idx_` prefix** from model file (draft had `ix_` wrong).
  - `op.drop_index("idx_ingredients_canonical_name_trgm", table_name="ingredients")` — **verified `idx_` prefix**.
  - `op.drop_constraint("ingredients_canonical_name_key", "ingredients", type_="unique")` — auto-named from `unique=True` in the model.
  - `op.execute("DROP FUNCTION IF EXISTS search_ingredients_fuzzy(text)")`.
  - `op.drop_constraint(<parent_id_fk_name>, "ingredients", type_="foreignkey")` — verify the FK name at impl via migration history or `\d+ ingredients`.
  - `op.drop_column("ingredients", "embedding")`.
  - `op.drop_column("ingredients", "parent_id")`.
  - `op.drop_column("ingredients", "pending_review")`.
  - `op.drop_column("ingredients", "is_canonical")`.
  - `op.drop_column("ingredients", "aliases")`.
  - `op.drop_column("ingredients", "category")` — **closed in party-mode: DROP.**
- Down-migration re-creates each as empty columns / tables / indexes / function stub. Rollback caveat documented in story notes: reverting the app to a version that reads `pending_review` NOT NULL requires also populating data (not attempted by the migration); acceptable in dogfood-only regime.
- Modify `libraries/utils/utils/models/ingredient.py` — strip dropped columns + `parent` self-ref relationship + any removed index definitions.
- Modify `libraries/utils/utils/models/shopping_list_item.py` — add a dated code comment on `already_have_quantity` documenting the retention ("Kept as placeholder for possible future pantry-check revival; always NULL as of 2026-04-20 per epic-ingredients-string-simplification.").
- Delete `libraries/utils/utils/models/ingredient_substitution.py`.
- Delete `libraries/utils/utils/models/ingredient_match.py`.
- Modify `libraries/utils/utils/models/__init__.py` — drop `IngredientSubstitution` and `IngredientMatch` exports.
- Modify `services/api/src/schemas/ingredient.py` — strip fields now absent from the model.
- Delete `services/migrator/seeds/ingredients.py`.
- Grep `rg 'seeds/ingredients|seed_ingredients' .github/ docker-compose*.yaml Makefile services/` and remove any invocation.
- Add dated "no live consumer" note to top of `services/ingredient-scraper/README.md`.

**Acceptance criteria**
1. `alembic upgrade head` on a fresh dev DB applies cleanly; `ingredients` table has only `(id, canonical_name, created_at, updated_at)` columns — no `category`, `embedding`, `parent_id`, `pending_review`, `is_canonical`, `aliases`.
2. `alembic downgrade -1` restores the structure as empty columns/tables/indexes/function; does not error.
3. `ingredient_substitutions`, `ingredient_matches` tables do not exist after upgrade (verify via `information_schema.tables`).
4. `search_ingredients_fuzzy` function does not exist (verify via `pg_proc`).
5. `shopping_list_items.already_have_quantity` column still exists after upgrade; model carries a dated retention comment.
6. Application starts; `npx nx run api:test` passes; coverage holds at the 100% threshold.
7. `services/migrator/seeds/ingredients.py` does not exist. Grep acceptance (above) returns zero.
8. `services/ingredient-scraper/README.md` top line reads (approximately) "As of 2026-04-20, this service's CSV output has no live consumer. Retained for possible future reuse. See `_bmad-output/planning-artifacts/epic-ingredients-string-simplification.md` for the canonical-matching retirement rationale."

**Tests**
- Apply migration on a seeded dev DB; verify no FK violation, no orphan rows.
- Integration: post-migration, `POST /v1/recipes` with a new ingredient name creates an `ingredients` row with only the four retained columns populated.
- `test_ingredient_substitution.py` / `test_ingredient_match.py` — DELETED if they exist as standalone files (audit at impl; verified via `rg 'class Test.*IngredientSubstitution\|class Test.*IngredientMatch' services/api/tests/ libraries/utils/test/`).

---

### str-ing-5 — Planning artifacts + rescope `epic-review-import-ingredient-polish`

**Scope**
- `_bmad-output/planning-artifacts/prd.md` — append dated addendum `## Addendum — 2026-04-20 — Ingredient canonicalization retired`:
  - Strike FR37's "semantic" axis when scoped to ingredients (FR37 still covers recipe semantic search).
  - Strike the "Ingredient search (exact + fuzzy + semantic)" entry in the epics-status table (line 353).
  - Strike the "Ingredient scraper service" listing (line 384).
  - Strike "Smart substitution suggestions" from the AI features list (line 396).
  - Update FR141 (if present) to remove the per-ingredient confidence expansion dependency on pending_review.
  - DELETE FR144 (IngredientRowStateBadge) entirely — replaced with a dated strikethrough + pointer to this epic.
  - Update NFR-MEAL-4 / FR-MEAL-12 to note sum-within-meal dedup is **retracted**; duplicate line items expected.
- `_bmad-output/planning-artifacts/architecture.md` — dated strikethroughs on:
  - §"Smart matching" bullet (line 46).
  - PostgreSQL 16 + pgvector + pg_trgm row — strike the "semantic ingredient search" / "pgvector for ingredient embeddings" language but preserve the pgvector + pg_trgm facts for recipe-level search (which stays).
  - Embedding Pipeline row (line 245) — note ingredients are out of scope.
  - Tiered AI cost management bullet referring to ingredient-matching tiers (line 124).
- `_bmad-output/planning-artifacts/epics.md` — dated addendum describing this epic + the cross-epic rescope.
- `_bmad-output/planning-artifacts/epic-review-import-ingredient-polish.md`:
  - Add dated note at top: "Rescoped 2026-04-20 by epic-ingredients-string-simplification. riip-4 loses its pending-review annotation half (keeps the `/v1/units/aliases` endpoint half). riip-7 (IngredientRowStateBadge) is DELETED — its motivating data (pending_review) is gone."
  - Update riip-4's scope bullets + acceptance criteria to drop every mention of `pending_review_ingredient`.
  - Mark riip-7 stories/body as "DELETED — see 2026-04-20 note".
- `docs/MVP.md` — strike canonical-matching language; keep recipe-level search language.
- `docs/RECIPE_IMPORT_SYSTEM.md` — strike matcher-tier references; describe imports as one-row-per-name.
- `docs/INGREDIENT_SCRAPER_DESIGN.md` — prepend dated note: "Design frozen 2026-04-20. Scraper service retained for possible future reuse; canonical-matching goal retired in epic-ingredients-string-simplification. Implementation below is historical."
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — append new epic block + all five stories; mark `riip-7-flutter-ingredient-row-state-badge` as `deleted` with an inline comment; leave `riip-4` status as-is but the story body is now narrower.

**Acceptance criteria**
1. PRD addendum exists with every bullet above.
2. architecture.md carries dated strikethroughs in every called-out line.
3. epics.md has the dated addendum entry.
4. epic-review-import-ingredient-polish.md has the dated top-of-file note + riip-4 scope tightening + riip-7 marked deleted.
5. sprint-status.yaml reflects the new epic and the riip-7 deletion with an inline dated comment.
6. Grep `rg 'pending_review|IngredientRowStateBadge|ingredient_substitution|ingredient_matches|search_ingredients_fuzzy' docs/ _bmad-output/planning-artifacts/` returns only results that are inside dated strikethroughs or inside a note explicitly pointing to this epic's retirement.
7. No planning artifact still recommends canonical-matching or pending-review work as active scope.

**Tests**
- Manual: reviewer reads the PRD addendum + architecture strikethroughs end-to-end + confirms no active FR/NFR depends on dropped infrastructure.
- Manual: reviewer opens epic-review-import-ingredient-polish and confirms the dated note is the first thing in the file.

## Dependencies

- **Internal (in this epic).** Ordering is `str-ing-1 → str-ing-2 → str-ing-3 → str-ing-4 → str-ing-5` — Flutter unships endpoint callers first; backend guts runtime logic; backend drops endpoints; schema migration drops columns/tables; docs + cross-epic rescope last.
  - str-ing-1 can theoretically land before the backend changes if we accept the rollout window (Flutter without endpoints calling still works; pending-review badge wiring being removed is additive-delete). Recommended: land str-ing-1 Flutter release before the str-ing-3 endpoint deletion reaches prod so no client 404s.
- **Cross-epic.**
  - `epic-review-import-ingredient-polish` (backlog) is rescoped in str-ing-5. riip-4 narrows, riip-7 dies. riip-1/riip-2/riip-3/riip-5/riip-6/riip-8 are unaffected (they're unit-normalization work orthogonal to ingredient identity).
  - `epic-calendar-per-meal-shopping-add` (done) — already inherited the no-dedup behaviour for free; no change needed.
  - `epic-meals-calendar` (done) — mcal-2's aggregate-meal-ingredients tests lose their dedup-assertion subset. Noted in str-ing-2 scope.
  - `epic-pantry` (done) — pantry check deletion is part of str-ing-2. Pantry add / event flows are untouched; pantry remains as a read-only "what I have" log.
  - `epic-notifications-*` — unaffected.

## Risks

- **Prod data with raw-string `canonical_name` values remains as-is.** Not in scope to clean up. Some meals will show ugly line items on shopping list. User already accepted this in epic-calendar-per-meal-shopping-add's §Risks; carried forward unchanged.
- **Pantry-check loss is user-visible.** Users whose mental model is "my shopping list already knows what's in my pantry" will see items they have in stock on the list. Mitigation: user explicitly opted in (2026-04-20). No release-note copy in dogfood regime (per closed Q5).
- **Aggregate dedup loss is user-visible.** Shopping lists from Meals or overlapping recipes gain duplicate lines. Mitigation: user explicitly opted in. Stable ordering (str-ing-2 AC 3) keeps duplicates adjacent so the UX is "obvious two-ness" not "shuffled noise."
- **Coverage-pin drift.** Removing ~720 LOC of matcher / resolver / dedup / pantry code leaves shared helpers as potential orphans. Mitigation: str-ing-2's AC 9 runs `npx nx run api:test --coverage` and holds the pin; scope enumerates coverage-gap entries at impl kickoff.
- **Alembic down-migration data loss.** Down recreates empty columns / tables. Production data in `pending_review`, `embedding`, `ingredient_substitutions` is lost on down. Acceptable per user preview — these columns' values have no meaning in the new world.
- **Eval config drift.** Removing the `ingredient_matching_evaluator` without removing references anywhere else will break the eval runner's import list. Mitigation: str-ing-2's AC 10 explicitly runs the eval entrypoint and asserts clean import.
- **Future planning confusion.** Someone reading `INGREDIENT_SCRAPER_DESIGN.md` months from now may re-architect against a retired goal. Mitigation: dated note at top of every retired doc pointing here.
- **Scraper rot.** The scraper sits unused; its deps may drift. Out of scope to maintain; flagged in its README that it's parked. Accept.
- **Workshop-surfaced: Split-system period between deploys.** str-ing-2 + str-ing-3 must ship in the same prod deploy; if the Flutter str-ing-1 release lags the backend deploy, nothing breaks (Flutter simply stops calling endpoints that still exist). If the backend deploy lands without str-ing-1 on device, Flutter still works because the ingredient-search endpoint deletion is additive-only from the client's perspective (it hasn't been called yet on the in-store build). Deploy order documented in story notes.
- **Workshop-surfaced: `extra="forbid"` silent-pass risk.** Without explicitly setting `ConfigDict(extra="forbid")` on `GenerateFromMealEvent.Params`, str-ing-2 AC 4 (422 on stray `check_pantry`) will silently pass as 201. Scope bullet + AC 4 test now explicitly verify both branches.
- **Workshop-surfaced: Index-name prefix drift.** Draft had `ix_` prefix on indexes; actual model uses `idx_`. An `op.drop_index("ix_...")` would fail at migration time. Fixed in str-ing-4 scope; workshop surfaced and corrected before implementation.
- **Workshop-surfaced: Badge widget already in tree.** `ingredient_row_state_badge.dart` + test are 96 + 95 LOC that exist today (draft erroneously assumed backlog). str-ing-1 scope updated to delete both; widget-test file wouldn't otherwise compile after str-ing-1's row-widget edits.
- **Workshop-surfaced: `shopping_list_items.category` becomes always-NULL.** Consumers (Flutter shopping-list grouping, if any) may render a blank group header. Audit at str-ing-1 impl time; acceptable regression in dogfood.
- **Workshop-surfaced: OpenAPI client drift.** Any downstream consumer generating clients off the OpenAPI spec will see the removed `/v1/ingredients/*` endpoints + the shrunken schemas. Internal Flutter client is rebuilt from the spec (no risk); external consumers (MCP clients, any third-party integration) would see the change. Default: no external consumers to coordinate with. Flag in MCP tool docstring (per open question 2).

## Open questions for the user (post-party-mode)

The workshop closed all five draft open questions: Q1 (drop `category`) → **DROP**. Q2 (`GET /v1/ingredients/{id}`) → **DELETE**. Q3 (drop `search_ingredients_fuzzy`) → **DELETE**. Q4 (scraper bit-rot ownership) → **accept, no owner, future epic absorbs re-wiring cost**. Q5 (release-note copy) → **defer; dogfood-only regime**.

Two remaining questions surfaced by the workshop that are worth a user call before kicking off `/dev`:

1. **Drop `shopping_list_items.already_have_quantity` or retain as always-NULL placeholder?** Workshop recommendation (taken in str-ing-4): **RETAIN** with a dated model-comment. A future epic that reintroduces any form of pantry cross-check can write into this column without an extra migration. Cost of keeping: one unused column; zero runtime cost; zero UI surface today. If you'd rather have a truly clean schema, flip to DROP and accept the follow-up migration cost.
2. **Any external consumers of the MCP `create_recipe` / `fork_recipe` fuzzy-match behavior?** The current MCP path dedups via pg_trgm at ingredient-name level; after str-ing-2 every MCP-driven recipe create lands with fresh per-name rows (same as the Flutter/import path). If you have downstream agents or integrations that rely on the current matcher semantics, they'll see a behaviour change. Default assumption: **no external consumers; proceed**. Flag the change in the MCP tool's docstring so any future agent reading it sees the history.
