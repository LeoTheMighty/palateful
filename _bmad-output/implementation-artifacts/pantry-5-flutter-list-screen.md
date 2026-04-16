# Story Pantry.5: Flutter Pantry List Screen

Status: done

## Story

As Leo opening the app to check what I've got in the kitchen,
I want a pantry screen that shows everything in it grouped by urgency with quick actions to fix mistakes,
so that I can trust what the automation thinks I have and correct it in one gesture when it's wrong.

## Context

The Flutter app has no pantry UI at all. This story introduces the first screen: a pantry list grouped by expiry urgency, with swipe-to-delete and tap-to-edit. The editor itself is a separate story (pantry-6).

The existing pattern for feature screens is in `app/lib/features/shopping_cart/`:
- `screens/shopping_list_screen.dart` — StatefulWidget, consumes a service's stream
- `services/shopping_cart_service.dart` — `StreamController<List<ShoppingListItem>>`-based state, not Bloc/Cubit/Riverpod
- Routing via `GoRouter` in `app/lib/core/router/app_router.dart`

This story matches that pattern. It adds:
- A `PantryService` with a `Stream<Pantry>` (where `Pantry` contains a list of `PantryIngredient`).
- A `PantryListScreen` that subscribes to the stream and renders grouped sections.
- A new `GoRouter` route for the pantry.
- Navigation entry point — an icon button on the home screen header (pattern: see `mvp-3-home-header-recipe-book-icon` for how the recipe-book icon was added).

"Use me up" CTA (pantry-7) and the item editor (pantry-6) are separate. Taps from this screen route to the editor (which must exist, even as a stub, for navigation to compile).

## Acceptance Criteria

1. New Dart model `app/lib/features/pantry/models/pantry_ingredient.dart` mirroring the backend `PantryIngredientRead` schema from pantry-1, including `storageLocation`, `expiresAt`, `quantityDisplay`, `unitDisplay`, `ingredient` (nested with `name`, `category`).
2. New Dart model `app/lib/features/pantry/models/pantry.dart` holding `id` and `List<PantryIngredient> ingredients`.
3. New service `app/lib/features/pantry/services/pantry_service.dart` with:
   - `Stream<Pantry?> get pantryStream` (nullable before first load).
   - `Future<void> loadDefaultPantry()` → `GET /pantries/default`.
   - `Future<void> deletePantryIngredient(String pantryId, String ingredientId)` → `DELETE /pantries/{pantryId}/ingredients/{ingredientId}`, updates the stream optimistically.
   - Uses whatever HTTP client / Dio instance the shopping_cart service uses — match the existing pattern.
4. New screen `app/lib/features/pantry/screens/pantry_list_screen.dart`:
   - Subscribes to `pantryService.pantryStream`.
   - Calls `loadDefaultPantry()` on first mount.
   - Shows a loading indicator before the stream emits.
   - Shows an empty-state with a friendly illustration/text when the pantry has zero non-archived ingredients.
5. List rendering: three grouped sections, in this order:
   - **Expiring Soon** — items with non-null `expiresAt` within 3 days.
   - **Fresh** — items with non-null `expiresAt` more than 3 days away.
   - **No Date** — items with null `expiresAt`.
   - Empty sections are hidden (do not render a section header with no items).
6. Each row shows:
   - Ingredient name (prominent).
   - `quantity_display + " " + unit_display` (secondary line).
   - Fuzzy expiry text: null → "No expiry set"; within 3 days → "Expires in X day(s)" or "Expires today" or "Expired"; otherwise → "Good for ~X days" where X is rounded days until expiry.
   - A thin color bar on the row's leading edge: red for expired or within 2 days, amber for 3-7 days, green for 7+ days, grey for null expiry.
7. Category chips row at the top of the screen: each unique category among current pantry items is a filter chip (multi-select OR filter). Tapping chips filters the visible items in all three sections. "All" chip clears filters.
8. Swipe-to-delete on each row (iOS/Android swipe action, same gesture library used in the shopping list). Swipe triggers `deletePantryIngredient`, shows a snackbar "Removed — Undo" for 4 seconds; Undo re-POSTs the item via `POST /pantries/{pantry_id}/ingredients`.
9. Tap a row opens the pantry item editor (pantry-6). For pantry-5 standalone, this stub can `context.push('/pantry/edit/{ingredientId}')`; the receiving screen is created in pantry-6.
10. New GoRouter route `/pantry` rendering `PantryListScreen`, registered in `app/lib/core/router/app_router.dart`.
11. Entry point from home screen: add a new pantry icon button (e.g., kitchen/fridge icon) to the home screen app bar next to the existing recipe-book icon. Tap navigates to `/pantry`. Follow the pattern in `_bmad-output/implementation-artifacts/mvp-3-home-header-recipe-book-icon.md` (or by inspecting the current state of `app/lib/features/home/home_screen.dart`).
12. Widget tests:
   - Three-section rendering with a mock `Pantry` containing items in all three urgency buckets.
   - Empty section is not rendered.
   - Fuzzy text matches expected strings across boundary dates (today, 1 day, 3 days, 7 days, null, past).
   - Swipe-to-delete triggers service call and shows undo snackbar.
   - Tap row calls navigator with expected route.
   - Category chip filtering narrows the list correctly.

## Tasks / Subtasks

- [ ] Task 1: Models (AC: #1, #2)
  - [ ] `app/lib/features/pantry/models/pantry_ingredient.dart` with `fromJson`/`toJson`
  - [ ] `app/lib/features/pantry/models/pantry.dart` with `fromJson`

- [ ] Task 2: Service (AC: #3)
  - [ ] `app/lib/features/pantry/services/pantry_service.dart` with `StreamController<Pantry?>`
  - [ ] `loadDefaultPantry`, `deletePantryIngredient`, helper `addPantryIngredient` (even if unused in this story, pantry-6 and undo snackbar both need it)
  - [ ] Register in the app's dependency injection setup (match the pattern used by `ShoppingCartService` — check `app/lib/core/` for service registration)

- [ ] Task 3: Screen scaffold (AC: #4, #10)
  - [ ] `app/lib/features/pantry/screens/pantry_list_screen.dart`
  - [ ] Register route in `app/lib/core/router/app_router.dart`
  - [ ] StatefulWidget, StreamBuilder on pantryStream, loading + empty + populated states

- [ ] Task 4: Grouping + fuzzy text (AC: #5, #6)
  - [ ] Helper file `app/lib/features/pantry/widgets/urgency_grouper.dart` or inline private function
  - [ ] Helper `app/lib/features/pantry/widgets/fuzzy_expiry_text.dart` — single function that takes `DateTime? expiresAt` and returns a display string
  - [ ] Row widget `app/lib/features/pantry/widgets/pantry_ingredient_tile.dart` with color bar + text layout

- [ ] Task 5: Category filtering (AC: #7)
  - [ ] `PantryFilterBar` widget with `FilterChip`s
  - [ ] State lives in `PantryListScreen`; filter is local to this view (not persisted)

- [ ] Task 6: Swipe-to-delete (AC: #8)
  - [ ] Use `Dismissible` (standard Flutter) following the shopping_list pattern
  - [ ] Undo snackbar calls `addPantryIngredient` to re-insert

- [ ] Task 7: Navigation + home entry (AC: #9, #11)
  - [ ] Add home-screen app-bar icon in `app/lib/features/home/home_screen.dart`
  - [ ] Route push/pop wiring

- [ ] Task 8: Tests (AC: #12)
  - [ ] `app/test/features/pantry/pantry_list_screen_test.dart`
  - [ ] `app/test/features/pantry/fuzzy_expiry_text_test.dart` — unit test the date math helper independently (boundary cases)

## Dev Notes

- **Urgency grouping is the emotional hook.** Per the Party Mode principle, the user opens this screen wondering "what's about to go bad?" If the ordering or labels make that unclear, the screen has failed. Err toward more urgent copy ("Expires in 2 days!") rather than polite copy.
- **Fuzzy text rules**:
  - `< 0 days` → "Expired" (red)
  - `0 days` → "Expires today" (red)
  - `1 day` → "Expires tomorrow" (red)
  - `2–3 days` → "Expires in N days" (red/amber border)
  - `4–7 days` → "Good for ~N days" (amber)
  - `> 7 days` → "Good for ~N days" (green)
  - `null` → "No expiry set" (grey)
- **Color bar on the leading edge, not the whole row.** Subtle visual, not alarming. Use the existing theme's palette where possible.
- **Do not show absolute timestamps.** Ever. Not even in tooltips for this story. If users want precision they can edit the item (pantry-6).
- **"No expiry set" is not a bug to fix.** Items added via the shopping-list hook (pantry-3) have `storage_location = null` at creation time and therefore no expiry. The user adds a storage location later via the editor (pantry-6) and then sees an expiry estimate. That's the intended flow.
- **Category chips are OR, not AND.** Selecting "produce" and "dairy" shows items from either category, not the intersection. Standard filter pattern.
- **Empty state copy**: friendly, not instructional. Something like "Your pantry is empty. Start shopping, or tap + to add something." The `+` button is not implemented in this story; pantry-6 adds it. You can stub the `+` button with a navigation to `/pantry/edit/new` or similar — coordinate with the pantry-6 dev.
- **Backward sort within sections**: within each urgency group, sort by `expiresAt ASC` so the most-urgent item in "Fresh" is first. "No Date" sorts alphabetically by ingredient name.

### Project Structure Notes

- All pantry Flutter code lives under `app/lib/features/pantry/`
- Match the `features/shopping_cart/` structure: `models/`, `services/`, `screens/`, `widgets/`
- No Bloc/Riverpod — the project uses StreamController-based services

### References

- `app/lib/features/shopping_cart/screens/shopping_list_screen.dart` — pattern to follow
- `app/lib/features/shopping_cart/services/shopping_cart_service.dart` — StreamController-based state pattern
- `app/lib/core/router/app_router.dart` — GoRouter config
- `app/lib/features/home/home_screen.dart` — where to add the pantry icon
- `_bmad-output/implementation-artifacts/mvp-3-home-header-recipe-book-icon.md` — recent precedent for adding a home-screen app-bar icon
- [Story: pantry-1-crud-api.md] — for backend endpoints
- [Epic: epic-pantry.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- `flutter test` — 317/317 tests pass (11 new pantry tests added)
- `dart analyze lib/features/pantry/` — clean
- No new pubspec deps required

### Completion Notes

- `app/lib/features/pantry/` introduces `models/`, `services/`, `widgets/`,
  and `screens/` directories following the `shopping_cart/` pattern.
- Service: StreamController-based `PantryService` exposing
  `Stream<Pantry?> pantryStream`, `loadDefaultPantry`,
  `addPantryIngredient`, `deletePantryIngredient`. Optimistic-update cache.
- Screen: three urgency sections (Expiring Soon / Fresh / No Date).
  Empty sections hide entirely. Sorted by `expiresAt ASC` within each;
  "No Date" sorts alphabetically.
- Fuzzy expiry helper is pure (takes `DateTime? now` for deterministic
  testing) — full boundary coverage in `fuzzy_expiry_text_test.dart`.
- Color bar on the leading edge uses `AppColors.success|warning|error` via
  `FuzzyExpiry.barColor`.
- Category filter chips use OR semantics: empty selection = show all.
  Filter state is local to the screen.
- Swipe-to-delete via `Dismissible`; shows a "Removed — Undo" snackbar for
  4s that re-POSTs the item through `addPantryIngredient`.
- Tap routes to `/pantry/edit/:ingredientId`. For this story the editor is
  a minimal stub (`PantryEditorScreen`) that pantry-6 will replace.
- New GoRoute `/pantry` (plus nested `/pantry/edit/:ingredientId`) lives in
  the home branch of the StatefulShellRoute.
- Home screen gains a `kitchen_outlined` `CircleIconButton` between Recipe
  Books and AI Assistant; `onPressed` pushes `/pantry`.

### QA Walkthrough

- [ ] Tap the new kitchen icon on the home screen → pantry list opens.
- [ ] Fresh user (no pantry yet) → screen shows "Your pantry is empty"
      empty-state (the backend lazy-creates the pantry behind the scenes).
- [ ] Check off a shopping-list item that maps to an ingredient. Open the
      pantry → the item appears in "No Date" (expires_at is null because
      storage_location is unknown at purchase time).
- [ ] Swipe left on an item → the row slides away, a snackbar appears
      with Undo. Tap Undo → the row returns.
- [ ] Items with `expires_at` within 3 days render under "Expiring Soon"
      with a red bar and red label; 4–7 days render under "Fresh" with
      amber; >7 days render green.
- [ ] Category chips: tap one chip → the visible items narrow to that
      category. Tap "All" → filters clear.
- [ ] Tap a row → navigates to the pantry-6 stub (full editor lands next).

### File List

**Created**
- `app/lib/features/pantry/models/pantry.dart`
- `app/lib/features/pantry/models/pantry_ingredient.dart`
- `app/lib/features/pantry/services/pantry_service.dart`
- `app/lib/features/pantry/widgets/fuzzy_expiry_text.dart`
- `app/lib/features/pantry/widgets/pantry_ingredient_tile.dart`
- `app/lib/features/pantry/widgets/pantry_filter_bar.dart`
- `app/lib/features/pantry/screens/pantry_list_screen.dart`
- `app/lib/features/pantry/screens/pantry_editor_screen.dart` (stub for pantry-6)
- `app/test/features/pantry/fuzzy_expiry_text_test.dart`
- `app/test/features/pantry/pantry_ingredient_tile_test.dart`

**Modified**
- `app/lib/core/di/injection.dart` — registered `PantryService` singleton
- `app/lib/core/router/app_router.dart` — added `/pantry` routes
- `app/lib/features/home/home_screen.dart` — added kitchen icon
