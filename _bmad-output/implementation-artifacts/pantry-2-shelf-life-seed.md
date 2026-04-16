# Story Pantry.2: Shelf-Life Seed Data + Estimator Service

Status: done

## Story

As Leo using Palateful's pantry,
I want the system to estimate how long each ingredient will last given its storage location,
so that `expires_at` gets a reasonable default whenever an item enters the pantry (manually or via the shopping-list hook) without me having to think about it.

## Context

The `pantry_ingredients.expires_at` column is nullable and currently only populated when the user or AI agent sets it explicitly. There is no shelf-life knowledge in the system at all — no lookup table, no heuristic, no defaults by ingredient category.

Per the epic's design principle, shelf-life is a **display feature, not a tracking feature**. Ship a static JSON seed keyed by `ingredient.category` × storage location (`fridge | pantry | freezer`) with day counts based on common food-safety references. The estimator returns an `expires_at` timestamp given `(ingredient, storage_location, added_at)`. Accuracy is not promised — the UI will always show fuzzy text like "~5 days."

This story is standalone backend work. It has no HTTP surface of its own; it exposes a Python service that pantry-3, pantry-4, and pantry-6 will call.

The `ingredient.category` field already exists (`libraries/utils/utils/models/ingredient.py:33`, `Mapped[str | None]`). Categories are free-form strings populated at ingredient-create time. This story uses them as lookup keys with sensible fallbacks for unknown categories.

## Acceptance Criteria

1. New seed file `libraries/utils/utils/data/shelf_life.json` contains a JSON object mapping category strings to a nested object with three numeric keys: `fridge_days`, `pantry_days`, `freezer_days`. Each value is a positive integer or `null` (meaning "not commonly stored this way"). At least **40 categories** are seeded covering common pantry staples: produce (leafy greens, root vegetables, citrus, berries, stone fruit, apples, bananas, tomatoes, avocados, onions, garlic, potatoes, mushrooms, herbs), proteins (raw chicken, raw beef, raw pork, raw fish, cooked meat, tofu, eggs), dairy (milk, yogurt, butter, hard cheese, soft cheese, cream), pantry staples (rice, pasta, flour, sugar, oil, canned goods, dried beans, nuts), bread/bakery (bread, tortillas), condiments (opened sauces, unopened sauces), frozen items.
2. A `DEFAULT_SHELF_LIFE` fallback is defined in the same file under a `"_default"` key: `{"fridge_days": 5, "pantry_days": 14, "freezer_days": 60}`. Used when `ingredient.category` is `None` or not found in the seed map.
3. New service file `libraries/utils/utils/services/shelf_life_service.py` exposes:
   - `load_shelf_life_data() -> dict` — loads and caches the JSON (module-level cache, read-once). Raises at startup if the JSON is malformed.
   - `estimate_expires_at(ingredient: Ingredient, storage_location: str | None, added_at: datetime | None = None) -> datetime | None` — returns `added_at + timedelta(days=N)` where `N` is resolved from `shelf_life[ingredient.category or "_default"][f"{storage_location}_days"]`. If `storage_location` is `None`, returns `None` (the caller can store the item without an expiry). If the looked-up value is `null` in the JSON (ingredient shouldn't be stored that way), also returns `None`. `added_at` defaults to `datetime.now(timezone.utc)`.
4. `estimate_expires_at` is fully deterministic given its inputs — no I/O beyond the one-time JSON load.
5. Unit tests cover: happy path for each storage location, unknown-category fallback to `_default`, `null` value returned as `None`, `None` storage_location returned as `None`, `added_at` override, caching behavior (load called once across multiple invocations).
6. The JSON file is valid and parseable at service-startup (add a simple sanity check in the `api` service startup that calls `load_shelf_life_data()` once so a malformed JSON fails fast, not on first request).

## Tasks / Subtasks

- [ ] Task 1: Seed the JSON (AC: #1, #2)
  - [ ] Create `libraries/utils/utils/data/` directory if missing
  - [ ] Write `libraries/utils/utils/data/shelf_life.json` with at least 40 categories + `_default` key
  - [ ] Research reference: USDA FoodKeeper app tables, StillTasty.com — but these are guidance only; exact numbers are a judgment call and will be tuned based on Leo's dogfooding feedback
  - [ ] Ensure `null` is used (not `0`) for "should not be stored this way" (e.g., `"leafy_greens": {"pantry_days": null, "fridge_days": 7, "freezer_days": 30}`)

- [ ] Task 2: Estimator service (AC: #3, #4)
  - [ ] `libraries/utils/utils/services/shelf_life_service.py` with the two functions described in AC #3
  - [ ] Use `importlib.resources` or `pathlib.Path(__file__).parent.parent / "data" / "shelf_life.json"` for the load — pick whichever pattern the codebase already uses for data-file access
  - [ ] Module-level `_CACHE: dict | None = None` with first-call-wins load

- [ ] Task 3: Startup sanity check (AC: #6)
  - [ ] In the API service's FastAPI startup (find `services/api/src/api/app.py` or lifespan handler), call `load_shelf_life_data()` so a malformed JSON crashes the container at boot rather than at first request

- [ ] Task 4: Tests (AC: #5)
  - [ ] `libraries/utils/test/test_shelf_life_service.py`
  - [ ] Include a test that validates the seed file parses (basic schema check: every value is either int or null)
  - [ ] Include a test listing a spot-check of known categories to catch regressions if someone edits the JSON (e.g., "eggs fridge_days must be between 14 and 45")

## Dev Notes

- **Do not build a UI for editing shelf-life values.** The JSON is code-owned for MVP. Future epics may add admin tooling.
- **Do not use AI to generate or refine the JSON at runtime.** The principle in the epic is "static seed, no AI calls on hot paths." Generating the initial JSON *offline* with AI assistance is fine, but the runtime path must not call OpenAI.
- **Category matching is exact-string.** No fuzzy matching, no synonyms. If `ingredient.category == "greens"` and the JSON has `"leafy_greens"`, the fallback to `_default` is the correct behavior. We accept this will be inaccurate for some ingredients — "display feature, not tracking feature."
- **Do not try to be smart about date-only vs. datetime.** Return a `datetime` set to `added_at + timedelta(days=N)`. The Flutter layer will format it as "in X days."
- **`ingredient.category` is nullable in the DB.** Imported recipes may have ingredients with no category. The `_default` fallback handles this.
- **Future-proofing note for pantry-6 dev**: the Flutter editor will call a thin API endpoint that wraps `estimate_expires_at` (or inline via an existing endpoint). That's pantry-6's problem, not this story's — this story just exposes the Python service.

### Project Structure Notes

- `libraries/utils/utils/data/` is a new subdirectory. Include an `__init__.py` if required by the project's package conventions (check existing `libraries/utils/utils/` subdirectories for the pattern).
- The service follows the `libraries/utils/utils/services/` pattern used by `activity_service.py` and others.
- The seed JSON is committed to the repo — this is not a runtime-loaded config, it's code-adjacent data.

### References

- `libraries/utils/utils/models/ingredient.py` (line 33) — the `category` field this service reads
- `libraries/utils/utils/models/pantry_ingredient.py` — the `expires_at` field this service produces values for
- `libraries/agent/agent/tools/pantry.py` — shows how `days_until_expiry` is consumed downstream (context for how fuzzy the estimate needs to be)
- [Epic: epic-pantry.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- `poetry run pytest libraries/utils/test/test_shelf_life_service.py` — 15/15 pass
- `poetry run pytest services/api` — 1388/1388 pass (regression check with the
  new `load_shelf_life_data()` call in the lifespan handler)
- `poetry run ruff check libraries/utils/utils/` — clean
- `npx nx run api:lint` — clean

### Completion Notes

- Seeded 46 categories in `libraries/utils/utils/data/shelf_life.json` plus a
  `_default` entry. Uses `null` (not 0) when a category shouldn't be stored a
  given way (e.g. leafy_greens at pantry temp, rice in the freezer).
- `shelf_life_service.py` exposes `load_shelf_life_data()` (module-level cache)
  and `estimate_expires_at(ingredient, storage_location, added_at)`.
- `_validate_shape` runs at load time and raises on malformed JSON so a bad
  deploy fails at boot rather than on first ingredient create.
- `load_shelf_life_data()` is now called from the FastAPI lifespan in
  `services/api/src/main.py` — the crash-at-boot requirement from AC #6.
- Added `_reset_cache_for_tests()` so tests can force a re-load between cases
  without depending on Python import ordering.

### QA Walkthrough

- [ ] Start the API service with a known-good JSON → lifespan completes normally.
- [ ] Temporarily corrupt `shelf_life.json` (e.g. drop `_default`) → service fails
      to start with a ValueError.
- [ ] `estimate_expires_at(eggs-ingredient, "fridge", datetime(2026,4,16 UTC))`
      returns `datetime(2026,5,21 UTC)` (35 days).
- [ ] `estimate_expires_at(leafy_greens, "pantry", ...)` returns `None`
      (category × location has null).
- [ ] `estimate_expires_at(unknown_category, "fridge", ...)` returns
      `added_at + 5 days` (from `_default`).
- [ ] `estimate_expires_at(..., None, ...)` returns `None`.

### File List

**Created**
- `libraries/utils/utils/data/__init__.py`
- `libraries/utils/utils/data/shelf_life.json`
- `libraries/utils/utils/services/shelf_life_service.py`
- `libraries/utils/test/test_shelf_life_service.py`

**Modified**
- `services/api/src/main.py` — lifespan calls `load_shelf_life_data()`
