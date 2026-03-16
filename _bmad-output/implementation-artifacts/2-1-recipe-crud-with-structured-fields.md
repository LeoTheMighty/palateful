# Story 2.1: Recipe CRUD with Structured Fields

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to create and edit recipes with structured ingredients, steps, and metadata,
so that my recipes are organized and consistently formatted.

## Acceptance Criteria

1. Given I am signed in, when I tap "+" to create a new recipe, then I can enter title, description, ingredients (with quantity/unit), ordered steps, prep time, cook time, servings, source attribution, and tags
2. And the recipe is saved with auto-save (no save button)
3. And I can edit any field on an existing recipe I own
4. And the recipe detail screen displays all structured fields clearly
5. And ingredients and steps maintain their ordering

## Tasks / Subtasks

- [x] Task 1: Add tags column to Recipe model and create Alembic migration (AC: #1)
  - [x] Add `tags` column to Recipe model as `Column(ARRAY(String))` — simple string array, no join table needed at this scale
  - [x] Generate Alembic migration: `npx nx run migrator:revision -- -m "add_tags_to_recipes"`
  - [x] Verify migration runs cleanly: `npx nx run migrator:migrate-test`
  - [x] Run `npx nx run migrator:check-models` to confirm model/migration alignment

- [x] Task 2: Add steps and tags to recipe schemas and endpoints (AC: #1, #5)
  - [x] Add `RecipeStepCreate` schema (step_number, instruction, active_time_minutes?, timers?, wait_time_minutes?, wait_type?, can_prep_ahead?, is_optional?) — mirrors RecipeStep model fields
  - [x] Add `RecipeStepResponse` schema (id + all RecipeStepCreate fields)
  - [x] Add `steps: list[RecipeStepCreate]` to `CreateRecipe.Params` (default empty list)
  - [x] Add `tags: list[str]` to `CreateRecipe.Params` (default empty list)
  - [x] Add `source_url: str | None` to `CreateRecipe.Params` if not already present (verify)
  - [x] Update `create_recipe.py` endpoint to create RecipeStep records from `steps` param, setting recipe_id and preserving step_number ordering
  - [x] Add `steps: list[RecipeStepCreate] | None` and `tags: list[str] | None` to `UpdateRecipe.Params`
  - [x] Update `update_recipe.py` endpoint: when steps provided, delete existing steps and recreate (same pattern as ingredients); when tags provided, replace tags array
  - [x] Verify `GetRecipe.Response` already includes steps (it does via get_recipe.py lines 55-75) — add `tags` to response
  - [x] Add `tags` to `ListRecipes` response items

- [x] Task 3: Backend tests for steps and tags (AC: #1, #5)
  - [x] Test creating recipe with steps → steps returned in order
  - [x] Test creating recipe with tags → tags returned
  - [x] Test updating recipe steps (replace) → new steps replace old
  - [x] Test updating recipe tags → new tags replace old
  - [x] Test step ordering is preserved (step_number)
  - [x] Test creating recipe without steps/tags still works (backward compat)

- [x] Task 4: Enhance RecipeWizardScreen with structured steps, tags, and source attribution (AC: #1, #2)
  - [x] Replace single instructions `TextField` (step 3) with a dynamic ordered step list — each step has an instruction text field, reorderable via drag handles
  - [x] Add "Add Step" button below step list
  - [x] Add swipe-to-delete or remove button on each step
  - [x] Add tags input to step 4 (detail step) — chip input with free-text entry, displayed as `InputChip` widgets
  - [x] Add source URL field to step 4
  - [x] Update `_saveRecipe()` to include `steps` (as list of `{step_number, instruction}`) and `tags` (as list of strings) in the API payload
  - [x] Ensure ingredients still include quantity/unit parsing (existing behavior)

- [x] Task 5: Implement auto-save with debounce for recipe editing (AC: #2, #3)
  - [x] Create `EditRecipeScreen` that loads existing recipe data and populates same form fields as wizard
  - [x] Route: `/recipes/:id/edit` → `EditRecipeScreen` (add to app_router.dart)
  - [x] Implement debounced auto-save: on any field change, start a 2-second debounce timer; on timer fire, call `updateRecipe()` API
  - [x] Show subtle save indicator (e.g., "Saving..." / "Saved" text in app bar or bottom)
  - [x] Handle save errors gracefully — show snackbar, keep local state, retry on next change
  - [x] Add "Edit" button/icon to RecipeDetailScreen app bar (only for recipes the user owns)
  - [x] For new recipe creation (wizard), keep explicit save — auto-save only applies to edit mode (recipe must exist first to have an ID for updateRecipe)

- [x] Task 6: Enhance RecipeDetailScreen to display all structured fields (AC: #4)
  - [x] Display steps as numbered list with step instructions (replace plain-text instructions display)
  - [x] If recipe has RecipeStep records, show those; if only `instructions` text exists (legacy), fall back to displaying instructions as-is
  - [x] Display tags as `Chip` widgets in a `Wrap` below the description
  - [x] Display source URL as tappable link (using `url_launcher` if not already a dependency — check pubspec.yaml)
  - [x] Maintain existing ingredient display with checkboxes
  - [x] Maintain existing "Start Cooking" FAB

- [x] Task 7: Flutter widget tests for recipe CRUD (AC: #1-#5)
  - [x] Test RecipeWizardScreen renders step list with add/remove functionality
  - [x] Test RecipeWizardScreen renders tags input with chip creation/deletion
  - [x] Test RecipeDetailScreen renders numbered steps
  - [x] Test RecipeDetailScreen renders tags as chips
  - [x] Test RecipeDetailScreen renders source URL
  - [x] Test RecipeDetailScreen shows edit button
  - [x] Test EditRecipeScreen renders with pre-populated fields (mock data)

## Dev Notes

### Critical Context: This Is a Brownfield Project

**Backend CRUD largely exists.** The current recipe API has full create/read/update/delete endpoints following the project's Endpoint pattern (class-based with Params/Response inner classes). Key files:

- `services/api/src/api/v1/recipe/create_recipe.py` — Creates recipe + ingredients (delete-and-recreate pattern for ingredients)
- `services/api/src/api/v1/recipe/update_recipe.py` — Updates recipe fields + ingredients
- `services/api/src/api/v1/recipe/get_recipe.py` — Returns full recipe with ingredients AND steps (already queries steps)
- `services/api/src/api/v1/recipe/list_recipes.py` — Paginated list with search

**RecipeStep model exists** at `libraries/utils/utils/models/recipe_step.py` with fields: step_number, instruction, active_time_minutes, timers (JSONB), wait_time_minutes, wait_type, can_prep_ahead, is_optional. The relationship on Recipe model is configured with `cascade="all, delete-orphan"`.

**What's actually missing:**
1. **Tags** — No column, no model field, no schema, no endpoint support. Needs Alembic migration.
2. **Steps in create/update** — RecipeStep model/table exist, get_recipe returns them, but create_recipe and update_recipe don't accept steps input.
3. **Flutter edit screen** — `updateRecipe()` exists in ApiClient but nothing calls it. No edit UI.
4. **Auto-save** — Wizard uses explicit "Save Recipe" button. AC requires auto-save for editing.
5. **Structured step input** — Wizard step 3 is a single multiline text field for "instructions", not individual steps.
6. **Tags input** — No tag entry UI anywhere.
7. **Source attribution display** — source_url exists on model but isn't shown on detail screen.

### Endpoint Pattern

All endpoints follow the class-based pattern:
```python
class CreateRecipe(Endpoint):
    class Params(BaseModel): ...
    class Response(BaseModel): ...

    @staticmethod
    async def handler(params: Params, db: AsyncSession, user: User) -> Response: ...
```

Router registration is in `services/api/src/api/v1/recipe/router.py`.

### Flutter Architecture

- **State management**: Local `setState()` — no provider/BLoC/Riverpod
- **API client**: `app/lib/core/services/api_client.dart` with `createRecipe()`, `updateRecipe()`, `getRecipe()`, `deleteRecipe()` methods
- **Routing**: GoRouter in `app/lib/core/router/app_router.dart`
- **Test pattern**: Widget tests with `MaterialApp` wrapper, no mocking framework — tests render widgets directly with test data

### Auto-Save Design Decision

Auto-save applies to **edit mode only** (AC #2 + #3). For new recipe creation, the wizard keeps its explicit save flow — a recipe needs to exist (have an ID) before auto-save can call `updateRecipe()`. This avoids creating empty/partial recipe records.

Debounce implementation: Use a `Timer` with 2-second delay. On any field change callback, cancel existing timer and start new one. On timer fire, call `ApiClient.updateRecipe()` with current form state.

### Tags Implementation

Use a simple `ARRAY(String)` column on the recipes table rather than a separate tags/taggings join table. Rationale:
- Tags are user-defined free text, not a controlled taxonomy
- No need for cross-user tag aggregation at this stage
- Simpler queries and no N+1 concerns
- PostgreSQL ARRAY supports `@>` (contains) operator for filtering later

### Step Ordering

Steps use explicit `step_number` field (integer). On create/update, the backend should set `step_number` from the array index (0-based or 1-based — match existing RecipeStep convention). The Flutter UI uses `ReorderableListView` for drag-to-reorder.

### DO NOT:
- Change existing endpoint signatures that would break backward compatibility — add new fields as optional with defaults
- Add a separate tags table/model — use ARRAY column
- Implement recipe deletion UI — that's Story 2.5
- Add recipe book management — that's Story 2.2
- Add photo upload — that's Story 2.3
- Implement search by tags — that's Epic 5
- Touch cook mode screen — that's Epic 6

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 2, Story 2.1] — User story and acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Model] — Recipe entity with ingredients, steps, tags
- [Source: services/api/src/api/v1/recipe/create_recipe.py] — Existing create endpoint with ingredient handling
- [Source: services/api/src/api/v1/recipe/update_recipe.py] — Existing update endpoint with ingredient replace pattern
- [Source: services/api/src/api/v1/recipe/get_recipe.py] — Existing get endpoint already returns steps
- [Source: libraries/utils/utils/models/recipe.py] — Recipe SQLAlchemy model with steps relationship
- [Source: libraries/utils/utils/models/recipe_step.py] — RecipeStep model with full field set
- [Source: app/lib/features/recipes/add_recipe/recipe_wizard_screen.dart] — Existing 4-step wizard
- [Source: app/lib/features/recipes/recipe_detail_screen.dart] — Existing detail screen (view-only)
- [Source: app/lib/core/services/api_client.dart] — API client with updateRecipe() method

## QA Checklist

### Prerequisites
- [ ] Alembic migration runs cleanly on fresh and existing databases
- [ ] `npx nx run migrator:check-models` passes
- [ ] All existing recipe tests still pass

### Recipe Creation with Structured Fields (AC #1)
- [ ] Can enter title, description via wizard
- [ ] Can add multiple ingredients with quantity/unit parsing
- [ ] Can add ordered steps (individual instruction fields)
- [ ] Can reorder steps via drag
- [ ] Can remove individual steps
- [ ] Can enter prep time, cook time, servings
- [ ] Can enter source URL
- [ ] Can add tags (free-text chip input)
- [ ] Can remove tags
- [ ] Recipe saves successfully with all fields

### Auto-Save on Edit (AC #2)
- [ ] Changes auto-save after 2-second debounce
- [ ] Save indicator shows "Saving..." then "Saved"
- [ ] Save errors show snackbar without losing local changes
- [ ] Navigating away with pending changes still triggers save

### Edit Existing Recipe (AC #3)
- [ ] Edit button visible on detail screen for owned recipes
- [ ] Edit screen loads with all existing recipe data pre-populated
- [ ] Can modify any field (title, description, ingredients, steps, times, tags, source URL)
- [ ] Changes persist after navigating away and returning

### Detail Screen Display (AC #4)
- [ ] Steps displayed as numbered list
- [ ] Tags displayed as chips
- [ ] Source URL displayed as tappable link
- [ ] Ingredients displayed with checkboxes (existing behavior)
- [ ] Prep/cook time and servings displayed (existing behavior)
- [ ] Legacy recipes with only `instructions` text still display correctly

### Ordering Preserved (AC #5)
- [ ] Ingredients maintain insertion order
- [ ] Steps maintain their step_number order
- [ ] Reordering steps in edit mode updates step_numbers correctly

### Regression
- [ ] Existing recipe creation (without steps/tags) still works
- [ ] Existing recipe detail view still works for old recipes
- [ ] Cook mode still works
- [ ] Recipe book views still work
- [ ] All Flutter tests pass (52+ existing)
- [ ] All backend tests pass

## Review Action Items

- [x] [AI-Review][HIGH] `edit_recipe_screen.dart`: Missing description field — added `_descriptionController`, multiline `TextField`, and `'description'` in `_saveNow()` payload (sends `null` when empty).
- [x] [AI-Review][MEDIUM] `edit_recipe_screen.dart` + `recipe_detail_screen.dart`: Migrated all `AppColors.*` to `colorScheme.*` / `textTheme.*` and removed `import app_colors.dart` from both files.
- [x] [AI-Review][MEDIUM] `recipe_detail_screen.dart`: Edit button now conditional on `_recipe?['can_edit'] == true`. Added `can_edit: bool` field to `get_recipe.py` Response, derived from `membership.role in ("owner", "editor")`.
- [x] [AI-Review][LOW] `update_recipe.py:175`: Changed `self.db.query(...)` to `self.database.db.query(...)` for consistency.
- [x] [AI-Review][LOW] `edit_recipe_screen.dart`: Wrapped `_saveNow()` in `unawaited()` with explanatory comment in `dispose()`.

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- check-models target does not exist (pre-existing issue) — verified model/migration alignment manually via autogenerate
- MockRecipe needed `tags: []` default added to conftest.py to prevent 500 errors
- MockDatabase `set_where(RecipeStep, ...)` needed for update_recipe_steps test
- Flutter `DropdownButtonFormField` `value:` → `initialValue:` deprecation fix
- InputChip delete button tap in tests uses `IconTheme` finder (not `Icons.cancel`)

### Completion Notes List
- Task 1: Added tags ARRAY(String) column to Recipe model + Alembic migration
- Task 2: Added steps/tags to create, update, get, get_public, list recipe endpoints with StepInput/StepResponse schemas
- Task 3: 11 backend tests for steps/tags CRUD (create, update, backward compat, ordering, list)
- Task 4: Enhanced RecipeWizardScreen with structured step list (ReorderableListView), tags chip input, source URL field
- Task 5: Created EditRecipeScreen with 2-second debounce auto-save, save status indicator, route added, edit button on detail screen
- Task 6: Enhanced RecipeDetailScreen with numbered steps (fallback to legacy instructions), tag chips, tappable source URL via url_launcher
- Task 7: 13 Flutter widget tests covering steps, tags, source URL, edit button, form fields, save indicators

### File List
- `libraries/utils/utils/models/recipe.py` — Added tags column
- `services/migrator/migrations/versions/20260315000001_add_tags_to_recipes.py` — New migration
- `services/api/src/api/v1/recipe/create_recipe.py` — Steps/tags in create endpoint
- `services/api/src/api/v1/recipe/update_recipe.py` — Steps/tags in update endpoint
- `services/api/src/api/v1/recipe/get_recipe.py` — Tags in get response
- `services/api/src/api/v1/recipe/get_public_recipe.py` — Tags in public get response
- `services/api/src/api/v1/recipe/list_recipes.py` — Tags in list response
- `services/api/tests/conftest.py` — MockRecipe tags default
- `services/api/tests/test_recipe.py` — 11 new backend tests
- `app/lib/features/recipes/add_recipe/recipe_wizard_screen.dart` — Structured steps, tags, source URL
- `app/lib/features/recipes/edit_recipe_screen.dart` — New: auto-save edit screen
- `app/lib/features/recipes/recipe_detail_screen.dart` — Steps, tags, source URL display, edit button
- `app/lib/core/router/app_router.dart` — Edit recipe route
- `app/pubspec.yaml` — Added url_launcher dependency
- `app/test/recipe_crud_test.dart` — New: 13 widget tests
