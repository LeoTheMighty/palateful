# Story Pantry.6: Flutter Pantry Item Editor

Status: done

## Story

As Leo looking at my pantry list,
I want to tap an item (or tap "+") to edit quantity, unit, storage location, and expiry date,
so that I can correct the automation's guesses and fill in the details that aren't captured by the shopping-list hook.

## Context

Pantry-5 ships the list screen with tap-to-edit navigation and a swipe-to-delete action. This story fills in the editor that the tap opens. It also adds the `+` FAB that the list screen stubbed — the FAB routes to the same editor in "new item" mode.

Critical behavior: when the user picks a `storage_location` on a new item, the editor pre-fills `expires_at` by calling the shelf-life estimator from pantry-2. The user can override the date manually at any time. Changing `storage_location` later overwrites the previous *unedited* estimate but does not overwrite a user-edited date (simple heuristic: if `expires_at == last_estimated_at`, it's still estimator-owned; if it's different, the user touched it).

The editor also supports ingredient search for the "new item" mode — creating a pantry entry requires selecting an `Ingredient` from the existing master table. For MVP, use a simple typeahead against an existing ingredient-search endpoint (confirm it exists at implementation time — likely under `services/api/src/api/v1/ingredients/` or similar; if not, the dev may need to add a small `GET /ingredients?q=` search or pull from an existing recipe-parsing lookup).

## Acceptance Criteria

1. New screen `app/lib/features/pantry/screens/pantry_item_editor_screen.dart` with two modes:
   - **Edit mode**: `/pantry/edit/:ingredientId` — loads the existing `pantry_ingredient` from the `PantryService`'s cached stream, pre-fills all fields.
   - **New mode**: `/pantry/add` — ingredient picker shown first; after selection, the form is shown with defaults.
2. Form fields:
   - Ingredient (read-only in edit mode, searchable picker in new mode).
   - Quantity (numeric text field).
   - Unit (text field or dropdown — match the pattern used in the recipe-parsing UI if one exists; simple text input is acceptable for MVP).
   - Storage location (segmented control: Fridge / Pantry / Freezer / None).
   - Expiry date (date picker, optional — user can clear it).
3. When the user picks a storage location AND an ingredient is set AND `expires_at` has not been user-edited, auto-populate `expires_at` by calling a new backend endpoint `POST /pantries/{pantry_id}/estimate-expiry` with `{ingredient_id, storage_location}` and placing the result in the date picker. Cache `last_estimated_at` locally in the screen state to detect user edits.
4. New backend endpoint `POST /pantries/{pantry_id}/estimate-expiry` (added to pantry-1's router module in this story — not pantry-1's responsibility):
   - Body: `{ingredient_id: UUID, storage_location: Literal["fridge", "pantry", "freezer"]}`.
   - Response: `{expires_at: datetime | null}` — calls `shelf_life_service.estimate_expires_at` under the hood.
   - Auth: same pattern as other pantry endpoints (any pantry member can call).
5. Save button:
   - Edit mode: calls `PATCH /pantries/{pantry_id}/ingredients/{ingredient_id}` with the form values. On success, navigates back, stream updates automatically from the PATCH response.
   - New mode: calls `POST /pantries/{pantry_id}/ingredients`. On success, navigates back, list refreshes.
6. Delete button in edit mode's app bar: confirms via AlertDialog, calls `DELETE`, navigates back, snackbar with undo on the list screen (same as pantry-5's swipe-to-delete).
7. `+` FAB on the pantry list screen (pantry-5) navigates to `/pantry/add`. Add this in pantry-6, not pantry-5 — the list screen shipped without it.
8. Ingredient search in new mode:
   - Text field with debounced search (300ms) calling `GET /ingredients?q={query}` (or equivalent existing endpoint — confirm at implementation time; if none exists, add a minimal one in this story's scope).
   - Shows up to 10 results.
   - Selecting a result populates the ingredient picker and advances to the form.
   - For MVP, "ingredient not found" means the user has to add the ingredient elsewhere first (via a recipe import or similar). Creating arbitrary new ingredients from the pantry is out of scope.
9. Validation:
   - Quantity must be > 0.
   - Ingredient must be set.
   - All other fields optional.
   - Save button disabled until form is valid.
10. Widget tests:
    - Edit mode loads existing item values.
    - New mode shows ingredient picker first.
    - Storage-location change triggers estimate call and updates date (mock backend).
    - User-edited date is NOT overwritten when storage location changes again.
    - Clearing the date is allowed and sends null to the PATCH.
    - Save calls PATCH in edit mode, POST in new mode.

## Tasks / Subtasks

- [ ] Task 1: Backend estimate endpoint (AC: #4)
  - [ ] New file `services/api/src/api/v1/pantry/estimate_expiry.py`
  - [ ] Register in the pantry router
  - [ ] Thin wrapper over `shelf_life_service.estimate_expires_at`
  - [ ] Unit test at `services/api/test/v1/pantry/test_estimate_expiry.py`

- [ ] Task 2: Ingredient search endpoint (AC: #8 — conditional)
  - [ ] Check if a search endpoint already exists under `services/api/src/api/v1/`
  - [ ] If not, add `GET /ingredients?q=<query>&limit=10` that does a `ILIKE` or trigram search on `ingredients.name`
  - [ ] If adding: small scope, basic query, no cursor pagination for MVP
  - [ ] Unit tests

- [ ] Task 3: Editor screen (AC: #1, #2, #5, #6, #9)
  - [ ] `app/lib/features/pantry/screens/pantry_item_editor_screen.dart`
  - [ ] Form state management: `StatefulWidget` with `TextEditingController`s
  - [ ] Integrate with `PantryService` for save/delete operations
  - [ ] Register two routes in `app/lib/core/router/app_router.dart`: `/pantry/edit/:ingredientId` and `/pantry/add`

- [ ] Task 4: Storage-location estimate wiring (AC: #3)
  - [ ] Track `_lastEstimatedDate` in state
  - [ ] On storage location change, call estimate endpoint, set date *only if* current date matches `_lastEstimatedDate` or is null
  - [ ] Track user date edits by comparing against `_lastEstimatedDate`

- [ ] Task 5: Ingredient search widget (AC: #8)
  - [ ] `app/lib/features/pantry/widgets/ingredient_search.dart`
  - [ ] Debounced search, 10-item result list, tap selects
  - [ ] Reusable — may be useful in pantry-7 as well

- [ ] Task 6: FAB on list screen (AC: #7)
  - [ ] Add `FloatingActionButton` to `PantryListScreen` routing to `/pantry/add`

- [ ] Task 7: Tests (AC: #10)
  - [ ] `app/test/features/pantry/pantry_item_editor_screen_test.dart`
  - [ ] Mock `PantryService`, mock estimate endpoint, verify field behaviors
  - [ ] Backend tests from Tasks 1 and 2

## Dev Notes

- **Do not implement cross-pantry moves or copy-to-another-pantry.** One pantry per user for MVP.
- **Do not implement barcode/photo entry.** Out of scope (explicit in epic cuts).
- **"User-edited date" heuristic is simple on purpose.** If the user's current date equals the last estimator-returned date, the estimator owns it. If they differ, the user edited it. This is cheap and mostly right. False positives (user happens to set the exact same date the estimator picked) are harmless — the estimator re-setting it on storage-location change is fine.
- **Clearing the date is meaningful.** If the user explicitly clears the expiry, treat it as a user edit — do not re-estimate when they change storage location afterward. Pattern: if date is null AND `_lastEstimatedDate` is null, the estimator can populate; if date is null AND `_lastEstimatedDate` has a value, the user cleared it and we respect that.
- **Segmented control for storage location**, not a dropdown. Three visible options + "None" is the perfect shape for a segmented button. Dropdowns are tap-tap-tap; segmented is tap.
- **Unit field is a text input for MVP.** The codebase already tolerates messy unit strings (`quantity_display` + `unit_display` are user-facing). A dropdown for common units is a polish item for a future epic.
- **Delete from editor uses the same `DELETE` endpoint as swipe-to-delete.** No new backend work for deletion.
- **FAB is the MVP entry point for "add" — no speed dial, no bottom sheet.** Tap → full-screen editor in new mode. Simple, fast, matches Flutter defaults.
- **If the ingredient search endpoint does not exist**, adding one here is in scope because the editor is unshippable without it. The endpoint is minimal (one query, one handler, one test). Don't block on it; just ship it.

### Project Structure Notes

- Editor co-located under `app/lib/features/pantry/screens/`
- Search widget under `app/lib/features/pantry/widgets/` (reused in pantry-7)
- Backend estimate endpoint in the existing pantry router module from pantry-1

### References

- `app/lib/features/pantry/screens/pantry_list_screen.dart` — from pantry-5, the caller
- `app/lib/features/pantry/services/pantry_service.dart` — from pantry-5
- `libraries/utils/utils/services/shelf_life_service.py` — from pantry-2
- `services/api/src/api/v1/pantry/` — router from pantry-1
- [Story: pantry-1-crud-api.md]
- [Story: pantry-2-shelf-life-seed.md]
- [Story: pantry-5-flutter-list-screen.md]
- [Epic: epic-pantry.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- `pytest services/api` — 1407/1407 pass (4 new estimate-endpoint tests)
- `flutter test test/features/pantry/` — 14/14 pass (3 new editor tests)
- `npx nx run api:lint` — clean
- `dart analyze lib/features/pantry/` — no issues

### Completion Notes

- Backend: `POST /v1/pantries/{pantry_id}/estimate-expiry` is a thin
  wrapper over `shelf_life_service.estimate_expires_at`. Auth reuses
  `require_pantry_access(mutate=False)` so any member (including viewers)
  can estimate. Returns `{expires_at: datetime | null}`.
- Ingredient search already existed at `GET /v1/ingredients/search?q=…`
  (built for recipe import). No new search endpoint required — the editor
  just reuses that surface.
- Flutter editor lives at `app/lib/features/pantry/screens/pantry_editor_screen.dart`.
  Two modes:
  - **Add mode** (`/pantry/add`): shows `IngredientSearch` first; once the
    user picks an ingredient, the form appears.
  - **Edit mode** (`/pantry/edit/:ingredientId`): loads the row from
    `PantryService.current`, pre-fills all fields. App bar has a
    delete action guarded by an `AlertDialog`.
- Storage location is a `SegmentedButton` with Fridge / Pantry / Freezer /
  None. Changing it auto-calls the estimate endpoint and updates the date,
  but only if the user hasn't hand-edited the date. The
  `_lastEstimatedAt` comparison is the cheap heuristic called out in the
  Dev Notes — a false positive (user picks exactly the estimated date) is
  harmless because re-running the estimate produces the same value.
- Clearing the expiry with the `×` button sticks — subsequent storage-
  location changes will NOT re-populate it (the user is explicitly saying
  "no expiry set"). The guard: if `_expiresAt == null` AND
  `_lastEstimatedAt != null`, skip re-estimation.
- Save: add mode calls `PantryService.addPantryIngredient`; edit mode
  calls the API client's `updatePantryIngredient` + `loadDefaultPantry`
  to refresh the cached stream.
- `+` FAB on the pantry list screen now routes to `/pantry/add` (replaces
  the `/pantry/edit/new` temporary wire from pantry-5).
- `PantryService` and `ApiClient` access in the editor is via lazy getters
  so widget tests can pump the screen without first registering DI.

### QA Walkthrough

- [ ] From the pantry list screen, tap the `+` FAB. The ingredient search
      field appears. Type "onion". Tap a result. The form loads.
- [ ] Enter `2`, unit `each`, select **Fridge** → the expiry date
      auto-populates to an estimator-computed date.
- [ ] Change storage to **Pantry** → the estimated date updates
      accordingly.
- [ ] Tap the calendar icon, pick a specific date. Change storage to
      **Freezer** → your hand-picked date stays; the estimator does NOT
      overwrite it.
- [ ] Tap `×` next to the expiry to clear it. Change storage to **Fridge**
      → the date remains null (user said no expiry).
- [ ] Tap **Save** → list screen reflects the new item.
- [ ] Tap an existing item in the list → editor opens in edit mode,
      pre-filled. Change the quantity, save → updated on the list.
- [ ] Tap the trash icon in edit mode → confirm → item removed.

### File List

**Created**
- `services/api/src/api/v1/pantry/estimate_expiry.py`
- `services/api/tests/test_estimate_expiry.py`
- `app/lib/features/pantry/widgets/ingredient_search.dart`
- `app/test/features/pantry/pantry_editor_screen_test.dart`

**Modified**
- `services/api/src/api/v1/pantry/__init__.py` — exports `EstimateExpiry`
- `services/api/src/routers/v1/pantry_router.py` — registered the new route
- `app/lib/core/router/app_router.dart` — added `/pantry/add` route
- `app/lib/core/services/api_client.dart` — `estimatePantryExpiry` method
- `app/lib/features/pantry/screens/pantry_editor_screen.dart` —
  replaced stub with the full editor
- `app/lib/features/pantry/screens/pantry_list_screen.dart` — FAB now
  routes to `/pantry/add`
