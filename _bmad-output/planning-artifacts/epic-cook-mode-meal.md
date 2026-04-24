<!-- refined via party-mode 2026-04-22 -->
# Epic: Cook Mode for a Whole Meal (Flutter-only)

## Overview

A Meal is a user-curated list of component recipes (`meals` + `meal_components`, each component = `recipe_id` + `order_index`). Today, cooking a multi-component meal requires visiting each recipe individually — there is no unified cook flow. This epic introduces `MealCookModeScreen`, reachable via a bottom-right FAB "Start Cooking" on `meal_detail_screen.dart`, that walks the user through every step of every component recipe in order, with a combined ingredient strip at the top and a per-component rating sheet at the end.

The epic explicitly trades off smart scheduling for section-based traversal: steps stay grouped per recipe (cook all of Dressing, then all of Salad, then all of Main). A recipe-section header like `Dressing · 3 / 7` sits above each step card so the user always knows which recipe they're on and where they are within it. No reordering to interleave steps across recipes.

Ingredients, by contrast, ARE interlaced — one combined strip at the top shows every ingredient from every component recipe. No deduplication — two recipes with "1 cup flour" render as two rows; each chip carries a small tag chip naming its source recipe.

The scope includes extracting cook-mode widget atoms (`IngredientStrip`, `StepNavigator`, `StepTimersRow`, `ManualTimerSheet`, timer services) into a shared surface that both recipe cook mode and meal cook mode consume, plus a `CookPlan` abstraction that models single-recipe and multi-recipe cooks uniformly.

Grounded references (verified at refinement time):
- FAB pattern on recipe detail: `recipe_detail_screen.dart:594` — `FloatingActionButton.extended(onPressed: _startCooking, ...)` mounted conditionally. Mirror exactly.
- Cooking-log write path: `ApiClient.createCookingLog(data)` at `api_client.dart:884` posts `/v1/cooking-logs`. The existing recipe cook feedback sheet routes through `recipe_cache_service.logCook` at `:97` which wraps that call. Meal post-cook uses the same path per rating.
- Mutation event: `CookingLogCreated` at `mutation_event.dart:705`, `MutationType.createCookingLog` at `mutation_failure_copy.dart:69`. N meal-cook writes emit N events via `MutationBus`.
- Server-side `aggregate_meal_ingredients` is NOT exposed client-side (confirmed in `calendar_screen.dart:352` comment). Client replicates the one-row-per-recipe-ingredient behavior directly from N fetched recipes.
- `CookSessionPersister` + `WidgetsBindingObserver.paused` flush + recipe-version-drift-snackbar pattern + destructive-right + "N timers" ≤3/≥4 copy rule all inherited from `epic-cook-mode-resume` (locked).

## Goal

A user taps "Start Cooking" on any meal and walks through all component recipes end-to-end with a unified ingredient strip, sectioned step traversal, a meal-level timer row, a per-component rating sheet, full resume-on-kill support, and the ability to finish early via the overflow menu — without any of the recipe-cook-mode features regressing.

## End-user flow

1. User taps a meal tile → lands on `meal_detail_screen` for a 3-component meal: Dressing (7 steps), Salad (4 steps), Grilled Chicken (9 steps).
2. Bottom-right **FAB "Start Cooking"** (same position, shape, and affordance as recipe-detail's FAB at `recipe_detail_screen.dart:594`). Tap → `context.push('/meals/<mealId>/cook')`.
3. Loading scaffold (cook-palette) appears briefly while `MealCookModeScreen` issues: (a) `GET /v1/meals/<mealId>` + (b) `GET /v1/recipes/<rid>` × 3 in parallel via `Future.wait`.
4. Cook mode mounts. At the top: a **combined `IngredientStrip`** showing every ingredient from every component recipe, each chip labeled with a small source-recipe tag chip ("from Dressing", "from Salad", "from Grilled Chicken"). Totals: 24 ingredients across 3 recipes. Expanded grid view groups by recipe with "--- From Dressing ---"-style dividers; compact horizontal strip keeps per-chip tags.
5. Below the strip: a step card with a **section header** reading **Dressing · 1 / 7**. The step card body is pure instruction text (the old "Step N of M" internal subtitle is removed to prevent redundancy). If step 1 has extracted or regex-matched timers, inline timer buttons appear below the instruction exactly as in recipe cook mode.
6. User taps a 3-min timer button → it lands in the **meal-level active-timers row** (single horizontal-scroll row at the top, same as recipe cook mode). User advances to step 2, then 3, then 4 of Dressing. Ingredient checks persist across steps.
7. User swipes past Dressing's step 7. Section header updates to **Salad · 1 / 4**. The step pill navigator below the card shows a **visual separator** between Dressing's completed pills and Salad's fresh pills (16dp gap + 1px vertical rule). Flat-total progress bar reads 7/20 = 35%.
8. User starts another timer on Salad step 2 with extracted label "simmer". The first Dressing timer also had label "simmer". Disambiguation fires: the new timer's display label is **"Salad · simmer"**; the original "simmer" stays unchanged (first-come-first-served).
9. User realizes they've decided not to make Grilled Chicken today. Opens the cook-mode **overflow menu** (same PopupMenuButton from `epic-cook-mode-resume`, now with two items): **Reset cook** + **Finish cooking now**. Taps **Finish cooking now** → confirmation "Finish this meal early? You'll be asked to rate the components you've cooked so far." → confirm.
10. Multi-component post-cook sheet opens with **2 rows** (Dressing + Salad — both started; Grilled Chicken omitted since user never advanced into it). User rates Dressing 5, Salad 4, optional notes. Tap Done.
11. Backend receives 2 `POST /v1/cooking-logs` calls — Dressing rating 5, Salad rating 4. Each emits a `CookingLogCreated` via `MutationBus` so `cooking_history_provider` and meal detail "upcoming plans" surfaces reactively refresh. Cook-session key `cook_session_meal_<mealId>` cleared. User returns to meal detail; favorite ratings + cook timestamps on Dressing + Salad reflect the new logs; Grilled Chicken unchanged.
12. **Alt path — mid-cook kill:** User was on Salad step 2, backgrounded. OS killed the app. User re-opens Meal X → FAB → Resume gate sheet appears with "Picked up from **Salad · step 2 of 4** · started 45 min ago · 8 ingredients checked · 1 timer" + Resume / Start Over buttons. Tap Resume → `MealCookModeScreen` mounts restored. Expired timers fire consolidated snackbar per the resume epic's ≤3-list / ≥4-count rule.
13. **Alt path — partial load failure mid-session:** User has saved meal cook state. Re-enters meal. Meal fetch succeeds. Of the 3 component recipes, 2 fetch successfully from cache/API, 1 fails. Instead of blocking at the error scaffold, `MealCookModeScreen` shows the Resume gate + a persistent inline banner at the top of the cook UI: **"Grilled Chicken couldn't load — some steps may be unavailable · Retry"**. The user can still cook Dressing + Salad steps; tapping into Grilled Chicken's step range shows a placeholder card "This component couldn't load · Retry" instead of crashing.

## Frontend changes

**New:** `app/lib/features/recipes/cook_mode/shared/` (directory) — the shared-widget home.

Files moved/extracted into shared/:
- `shared/widgets/ingredient_strip.dart` (MOVED from `widgets/ingredient_strip.dart`; extended with source-tag support)
- `shared/widgets/step_navigator.dart` (MOVED; extended with `componentBoundaries` support)
- `shared/widgets/step_timers_row.dart` (MOVED)
- `shared/widgets/manual_timer_sheet.dart` (MOVED)
- `shared/widgets/timer_completion_overlay.dart` (MOVED)
- `shared/widgets/active_timers_row.dart` (NEW — extracted from the inline `_buildActiveTimers` in `cook_mode_screen.dart`)
- `shared/widgets/post_cook_feedback_sheet.dart` (MOVED + refactored to accept `List<ComponentRatable>`, single-length = recipe cook)
- `shared/services/cook_timer_notification_service.dart` (if not already there — confirm current path at cmm-1 time)
- `shared/util/timer_regex.dart` (MOVED)
- `shared/util/cook_timer_token.dart` (MOVED)

**Import-path migration:** Before the move, grep `grep -RE "cook_mode/widgets/(ingredient_strip|step_navigator|step_timers_row|manual_timer_sheet|timer_completion_overlay|post_cook_feedback_sheet|timer_regex|cook_timer_token)" app/lib/ app/test/` for any external consumers (outside `cook_mode/`). Update imports wholesale.

**New:** `app/lib/features/recipes/cook_mode/shared/cook_plan.dart`

```dart
class CookPlan {
  final String sessionKey;                // CookSessionKey.forRecipe(id) | forMeal(id)
  final String title;                     // recipe or meal name (header text)
  final List<CookComponent> components;   // size 1 for recipe cook; N for meal
  final List<CombinedIngredient> ingredients;  // flat, tagged with sourceComponentIndex

  int get totalSteps => components.fold(0, (sum, c) => sum + c.steps.length);
  List<int> get componentBoundaries;      // flat indices where each component starts (e.g., [0, 7, 11])
  ({int componentIndex, int stepIndex}) stepAt(int flatIndex);
  int flatIndexFor(int componentIndex, int stepIndex);

  factory CookPlan.fromRecipe(Map<String, dynamic> recipe);
  factory CookPlan.fromMeal(Meal meal, List<Map<String, dynamic>> recipes);
}

class CookComponent {
  final String recipeId;
  final String name;            // "Dressing"
  final List<_StepData> steps;  // per-component step list (retains timers)
  final List<dynamic> ingredients;  // raw; combined into plan.ingredients with sourceComponentIndex
  final bool loadFailed;        // true if this component's recipe fetch failed (partial-load handling)
}

class CombinedIngredient {
  final int sourceComponentIndex;
  final String sourceComponentName;
  final dynamic raw;                     // shape matches existing IngredientStrip input
  final int orderIndex;                  // within-component order
  String get stableKey => '$sourceComponentIndex:$orderIndex';  // check-state key
}
```

**New:** `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
- Top-level route target; signature `MealCookModeScreen({required String mealId})`.
- `_MealCookModeScreenState extends State<MealCookModeScreen> with WidgetsBindingObserver` (for paused-flush, same pattern as resume epic).
- Loads meal + N recipes in parallel; builds `CookPlan.fromMeal(meal, recipes)`; mounts the same underlying cook UI shell (header, active-timers row, ingredient strip, step card, step navigator) but configured from the plan.
- On entry, checks `CookSessionPersister().load(CookSessionKey.forMeal(mealId))` — same gate-sheet flow as recipe cook. Recipe-version-drift on resume: if `persisted.current_step >= plan.totalSteps`, clamp + snackbar.
- Overflow menu has **two items**: "Reset cook" (inherited from resume epic) + "Finish cooking now" (meal-only; hidden on 1-component plans).

**New:** `app/lib/features/recipes/cook_mode/meal/widgets/recipe_section_header.dart`
- Thin widget rendered above each step card: **"<ComponentName> · <localStep> / <componentTotal>"**. Uses `cookOnSurface.withAlpha(0.7)` for label, `cookAccent` for the number fraction. Semantics: "Step 3 of 7 in Dressing".
- In 1-component plans (recipe cook), the header is **hidden** — redundant with app-bar recipe name.

**New:** `app/lib/features/recipes/cook_mode/meal/widgets/component_load_placeholder.dart`
- Shown inside the step card when the current `_currentStep` falls within a component whose `loadFailed == true`. Content: "This component couldn't load · Retry". Retry button re-fetches the one failing recipe and patches `plan.components[idx]` in place.

**Extension:** `shared/widgets/post_cook_feedback_sheet.dart`
- Signature accepts `List<ComponentRatable>` (where `ComponentRatable` = `{recipeId, displayName}`).
- Single-component list (recipe cook): renders exactly one row — pixel-identical to today.
- N-component list: renders N rating rows inside a `ListView` (scrollable when N rows overflow viewport). Each row: component name + 5-star `RatingBar` + optional note `TextField`.
- Submit callback: `List<({String recipeId, int rating, String? note})>`. Caller filters `rating > 0` entries and fires N `POST /v1/cooking-logs` sequentially (not parallel — simpler per-request failure handling; N is small).
- Each successful POST emits `CookingLogCreated` via `MutationBus` so `cooking_history_provider` invalidates. Partial failure → consolidated snackbar "Cooked X of Y components logged · [Retry failed]".

**Modified:** `app/lib/features/meals/meal_detail_screen.dart`
- Add bottom-right `FloatingActionButton.extended(label: const Text('Start Cooking'), icon: Icon(Icons.restaurant_menu), onPressed: ...)` using the same factory as `recipe_detail_screen.dart:594`. Visible when `meal.components.isNotEmpty` AND at least one component is `available: true`. Disabled with tooltip "Add a recipe to start cooking" when all unavailable; hidden when zero components. Single-component meal: FAB visible (cook is still valid).
- On tap: `context.push('/meals/${meal.id}/cook')`.

**Modified:** `app/lib/core/router/app_router.dart`
- New `GoRoute(path: '/meals/:id/cook', parentNavigatorKey: _rootNavigatorKey, pageBuilder: …)` mounting `MealCookModeScreen(mealId: id)`. Mirror the recipe-cook route at `:257–270`.

**Modified:** `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- Refactor to consume `CookPlan.fromRecipe(recipeData)` internally. `_loadRecipe()` builds a 1-component plan; all state logic (step traversal, ingredient check-off, timer lifecycle) operates on the plan.
- Step card body: remove the internal "Step N of M" subtitle (the new `recipe_section_header` covers this in meal mode; in recipe mode, the app-bar already holds the recipe name and step count is already in the progress bar). Behavior-equivalent in recipe mode.
- File shrinks — widget building paths that moved to `shared/` are imported, not duplicated. Every existing cook-mode test passes without behavioral change (import-path updates only).

**Ingredient-strip extension:** `IngredientStrip` gains optional `sourceTagBuilder(int index) → String?` parameter. When non-null, each chip renders a tag chip under the name; when null, rendering is identical to today. For 1-component plans (recipe cook), `sourceTagBuilder` is null.
- Expanded grid view: when `sourceTagBuilder` is non-null, group chips by source component with a "--- From <ComponentName> ---"-style divider between groups.
- Compact horizontal strip: per-chip tag chip (source component name, truncated to 10 chars + ellipsis if longer). No inter-group dividers in compact view (scroll direction makes them visually confusing).

**Step-navigator extension:** `StepNavigator` gains optional `componentBoundaries: List<int>` parameter. When non-null and length > 1, pills at the boundary indices get a 16dp-wider left margin + a 1px `cookDivider`-coloured vertical rule. Semantics on each pill include the component name when boundaries are active: "Step 3 of 7, Dressing, current". When null/empty (recipe cook), rendering is unchanged from today.

**Mutation integration:** On each successful `cooking_logs` POST from the meal post-cook sheet, `MutationBus().emit(CookingLogCreated(recipeId: ..., ...))` fires. `cooking_history_provider` already subscribes (`cooking_history_provider.dart:13`) and invalidates. No new bus plumbing.

**Tests (new):**
- `app/test/cook_plan_test.dart` — `stepAt` / `flatIndexFor` / boundary indexing / `loadFailed` edge cases / 1-component plan (recipe cook compatibility)
- `app/test/meal_cook_mode_test.dart` — load + mount + basic traversal + partial-load banner
- `app/test/meal_cook_mode_ingredients_test.dart` — combined strip, source tags, stable-key check-state, aggregation parity with backend, expanded-vs-compact tag rendering
- `app/test/meal_cook_mode_sectioning_test.dart` — section-header updates, navigator separators, Semantics, flat-total progress bar
- `app/test/meal_cook_mode_timers_test.dart` — meal-level timer row across boundaries, first-come-first-served disambiguation, notification copy with component name
- `app/test/meal_post_cook_feedback_test.dart` — N-component rating, skip logic (rating=0), partial-failure snackbar, `CookingLogCreated` mutation event emission, scrollable sheet with many components, early-finish subset
- `app/test/meal_cook_mode_resume_test.dart` — Resume path under `CookSessionKey.forMeal(id)`, stable-key check-state restoration, recipe-version-drift clamp, expired-timer consolidated snackbar
- `app/test/meal_cook_mode_partial_load_test.dart` — one-component-load-failure behavior (banner + placeholder + retry)

**Tests (modified):** Existing cook-mode tests get import-path updates after shared extraction; no behavior changes. Icon-count assertions on the header reflect the `epic-cook-mode-resume`-added overflow menu (+1). The `tools/no-cook-chat-check.sh` grep gate from `epic-cook-mode-remove-chat` continues to pass on the moved paths (scoped to `cook_mode/` root, which covers `shared/` and `meal/`).

## Backend changes

None. Rationale:
- `GET /v1/meals/{id}` already returns the meal + thin components.
- `GET /v1/recipes/{id}` already returns full recipe with steps + ingredients.
- `aggregate_meal_ingredients(meal)` (in `libraries/utils/utils/services/meal_service.py`) is **not invoked** by this flow. The Flutter client replicates the one-row-per-recipe-ingredient behavior directly from the N fetched recipes, tagging each row with `sourceComponentIndex` + `sourceComponentName`. Parity with backend behavior is validated by cmm-4 AC8.
- `POST /v1/cooking-logs` already supports per-recipe rating writes (`api_client.dart:884`); the meal cook sheet calls it N times sequentially.
- No new endpoints, no schema changes, no new SQLAlchemy models, no migrations.

**Deferred to a future epic:** a `GET /v1/meals/{id}?hydrate=true` batch endpoint that returns the meal + all component recipes in one round-trip. Not needed for meals with 2-5 components; client fan-out with `Future.wait` completes in ~400ms on warm network. Revisit if meals routinely exceed 8 components.

## Infrastructure changes

None. Rationale: no env vars, no new AWS resources, no CI workflow changes. Grep gate from `epic-cook-mode-remove-chat` continues to pass on the expanded `cook_mode/` tree (shared/ + meal/ are covered by the same script scope).

## Design principles

- **Meal cook is a generalization of recipe cook, not a parallel screen.** Both screens construct a `CookPlan` and mount the same underlying shell. The only difference is the plan shape.
- **Sectioned traversal, not scheduled interleaving.** Smart "start the sauce while the pasta boils" is explicitly deferred. Today: cook all of A, then all of B, then all of C. Future epic territory.
- **Combined, not deduped.** The user can see two "1 cup flour" rows because that tells them something — they need a cup for the dressing and another for the bread. Summing loses that.
- **Source tags make it legible.** Every ingredient chip in meal mode carries "from <Component>". Per-chip in compact view; group headers in expanded view. Users who asked for no dedup still need to know which recipe an ingredient belongs to.
- **Per-component rating is first-class.** The post-cook sheet collapses to one row in recipe mode; expands to N rows (scrollable) in meal mode. Same widget, different plan.
- **N parallel fetches are acceptable; batching is premature.** If meals commonly had >10 components, a batch endpoint would be worth building. Today's meals are 2–5 components; N parallel GETs against a warm API are <500ms combined.
- **Persistent resume comes from `CookSessionPersister`, not a meal-specific service.** Same schema, same gate, same flow. Recipe-version-drift clamp extends to meal-version-drift (component added/removed).
- **First-come-first-served on timer disambiguation.** Don't retroactively rename the first "simmer" when a second "simmer" arrives. Predictable, not clever.
- **Partial failures degrade, don't block.** A single component fetch failure doesn't prevent cooking the others. Placeholder + retry, not error-scaffold lockout.
- **Flat-total progress, per-component header.** Progress bar shows 10/20 = 50%. Section header shows "Salad · 3 / 4" so the user knows where they are within the current component. Two complementary signals.
- **No chat, no AI** — inherited from `epic-cook-mode-remove-chat`. Meal cook has no new chat surface by construction.
- **Destructive right** — Reset cook and Finish cooking now both put the destructive/significant action on the right per platform convention (locked from resume epic).
- **Mutation bus integration.** Every `cooking_logs` write emits `CookingLogCreated` — the already-live MutationBus infrastructure picks it up and invalidates `cooking_history_provider` + meal-detail derived surfaces automatically. No manual invalidation plumbing.

## File structure

Anticipated touched paths:
- `app/lib/features/recipes/cook_mode/shared/` (NEW directory)
  - `shared/cook_plan.dart` (NEW)
  - `shared/widgets/ingredient_strip.dart` (MOVED + extended)
  - `shared/widgets/step_navigator.dart` (MOVED + extended)
  - `shared/widgets/step_timers_row.dart` (MOVED)
  - `shared/widgets/manual_timer_sheet.dart` (MOVED)
  - `shared/widgets/timer_completion_overlay.dart` (MOVED)
  - `shared/widgets/active_timers_row.dart` (NEW)
  - `shared/widgets/post_cook_feedback_sheet.dart` (MOVED + refactored)
  - `shared/util/timer_regex.dart` (MOVED)
  - `shared/util/cook_timer_token.dart` (MOVED)
- `app/lib/features/recipes/cook_mode/meal/` (NEW directory)
  - `meal/meal_cook_mode_screen.dart` (NEW)
  - `meal/widgets/recipe_section_header.dart` (NEW)
  - `meal/widgets/component_load_placeholder.dart` (NEW)
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` (MODIFIED — consume shared widgets + `CookPlan.fromRecipe` + remove internal step-subtitle)
- `app/lib/features/meals/meal_detail_screen.dart` (MODIFIED — FAB)
- `app/lib/core/router/app_router.dart` (MODIFIED — new route)
- `app/test/cook_plan_test.dart` (NEW)
- `app/test/meal_cook_mode_test.dart` (NEW)
- `app/test/meal_cook_mode_ingredients_test.dart` (NEW)
- `app/test/meal_cook_mode_sectioning_test.dart` (NEW)
- `app/test/meal_cook_mode_timers_test.dart` (NEW)
- `app/test/meal_post_cook_feedback_test.dart` (NEW)
- `app/test/meal_cook_mode_resume_test.dart` (NEW)
- `app/test/meal_cook_mode_partial_load_test.dart` (NEW)

## Stories

### Story cmm-1 — Shared widget extraction + `CookPlan` abstraction + recipe-cook refactor

**AC1** — New `app/lib/features/recipes/cook_mode/shared/` directory exists with all moved widget files (`ingredient_strip`, `step_navigator`, `step_timers_row`, `manual_timer_sheet`, `timer_completion_overlay`, `active_timers_row`, `post_cook_feedback_sheet`) + `util/timer_regex.dart` + `util/cook_timer_token.dart`. Source files are removed from `widgets/`.
**AC2** — External consumers of the moved files (grep `grep -RE "cook_mode/widgets/(ingredient_strip|step_navigator|…)" app/lib/ app/test/`) have their imports updated to `shared/widgets/…`. Zero dangling imports.
**AC3** — `cook_plan.dart` defines `CookPlan`, `CookComponent`, `CombinedIngredient` with `fromRecipe(recipe)` and `fromMeal(meal, recipes)` factory methods. `CookPlan.stepAt(flatIndex)` and `flatIndexFor(ci, si)` unit-tested with boundary values. `CookComponent.loadFailed` defaults to `false`; `fromMeal` passes `true` only for recipes whose fetch failed (partial-load case, wired in cmm-2).
**AC4** — `cook_mode_screen.dart` is refactored to consume a `CookPlan` internally. `_loadRecipe` builds `CookPlan.fromRecipe(data)`; all state logic operates on plan flat indices. Internal "Step N of M" subtitle inside the step card is removed (progress bar + app-bar already carry that info in recipe mode).
**AC5** — Every existing cook-mode test (`cook_mode_test.dart`, `cook_mode_gesture_test.dart`, `cook_mode_timer_test.dart`, `offline_cook_mode_test.dart`, `post_cook_feedback_test.dart`, `cook_mode_live_activity_test.dart`, `step_navigator_test.dart`, `ingredient_strip_test.dart`, `cook_mode_timers_integration_test.dart`) passes with no behavioral change — imports updated for the new paths.
**AC6** — `cook_plan_test.dart` covers: 1-component plan maps (0, 0) ↔ 0, last step ↔ totalSteps-1; 3-component plan ([2, 4, 3] steps) maps (1, 2) ↔ 4 correctly; out-of-range indices throw `ArgumentError`; `componentBoundaries` for 1-component plan is `[0]` (single entry), for 3-component is `[0, 2, 6]`; `loadFailed` preserved through factory; `stableKey` correctness on `CombinedIngredient`.
**AC7** — `IngredientStrip` gains an optional `sourceTagBuilder(int index) → String?` parameter. When non-null, each chip renders a tag chip; when null, rendering is identical to today. Expanded grid view groups by source component with "--- From <ComponentName> ---" dividers when builder is non-null. Compact horizontal strip: per-chip tag only (no inter-group dividers). Single new test case covers the tagged rendering.
**AC8** — `StepNavigator` gains an optional `componentBoundaries: List<int>` parameter. When non-null AND length > 1, pills at the boundary indices have a 16dp-wider left margin + a 1px `cookDivider`-coloured vertical rule. Semantics on each pill include the component name when boundaries active. When null/empty or length 1 (single-component list), rendering is identical to today. Existing `step_navigator_test.dart` adds one case for boundaries.
**AC9** — `post_cook_feedback_sheet.dart` signature changes to accept `List<ComponentRatable>`. The single-recipe caller passes a list of length 1. Sheet rendering in 1-component mode is pixel-identical; in N-component mode renders N stacked rating rows inside a scrollable container. Existing `post_cook_feedback_test.dart` passes.
**AC10** — `grep` of `app/lib/features/recipes/cook_mode/widgets/` confirms the folder is empty or only contains non-shared, recipe-specific widgets if any (none expected). `tools/no-cook-chat-check.sh` continues to pass on the expanded tree.
**AC11** — `npx nx run app:test` green; `npx nx run app:analyze` clean; existing cook-mode UX manually verified unchanged via walkthrough (screenshot in PR).

### Story cmm-2 — `MealCookModeScreen` loader + route + FAB on meal detail + partial-load degrade

**AC1** — New `GoRoute` `/meals/:id/cook` in `app_router.dart` mounts `MealCookModeScreen(mealId: id)`. Route style matches existing `/recipes/:id/cook` at `:257–270` (parentNavigatorKey, reduceMotion page builder).
**AC2** — `_MealCookModeScreenState` mixes in `WidgetsBindingObserver`. On `initState`:
  - `addObserver(this)`; construct `CookSessionDebouncer`.
  - Fetches `GET /v1/meals/{mealId}` via `meal_service` / `mealByIdProvider`.
  - Fetches `GET /v1/recipes/{rid}` for each component ordered by `orderIndex`, in parallel (`Future.wait`).
  - Builds `CookPlan.fromMeal(meal, recipes)` with `loadFailed` flag set per-component based on fetch outcome.
  - Calls `CookSessionPersister().load(CookSessionKey.forMeal(mealId))` and runs the Resume / Start Over gate if state exists.
  - Starts `_cookingStopwatch` AFTER gate resolves (same deferral as recipe cook).
**AC3** — Error / partial-failure handling:
  - Meal fetch fails: render the cook-palette error scaffold ("Couldn't load this meal · Retry"). No Resume gate.
  - All N recipe fetches fail: error scaffold per-component ("Dressing ✗ · Salad ✗ · Grilled Chicken ✗ · Retry all").
  - **Partial: meal + some recipes succeed, at least one recipe fails** — cook UI renders. Inline banner at top: "<ComponentName> couldn't load — some steps may be unavailable · Retry". When current step is in a failed component, show `component_load_placeholder.dart` inside the step card (placeholder + Retry button). Retry re-fetches the one failing component and patches `plan.components[idx]` in place.
  - Offline (`DioException`, network unavailable): per component, try `RecipeCache.loadCachedRecipe(rid)`. If all cached: proceed with `_isOffline = true` banner + gate flow runs normally. If any uncacheable: go through the partial-failure path above (not a blocker — cook what you can).
**AC4** — FAB "Start Cooking" added to `meal_detail_screen.dart`, bottom-right, using `FloatingActionButton.extended` factory matching `recipe_detail_screen.dart:594`. Visibility rules:
  - Hidden when `meal.components.isEmpty`.
  - Enabled + visible when ≥1 component `available: true` (including single-component meals).
  - Disabled + tooltip "Add a recipe to start cooking" when meal has components but all are `available: false`.
**AC5** — Widget test: mount `MealDetailScreen` with a 3-component meal (all available), assert FAB visible and enabled; mount with 0 components, assert FAB hidden; mount with 2 components but both `available: false`, assert FAB disabled with tooltip; mount with 1 component, assert FAB visible (single-component meal case).
**AC6** — Widget test: mount `MealCookModeScreen` with mocked `ApiClient` returning meal + 3 recipes successfully. Assert cook UI renders, header shows meal name, step card shows "Dressing · 1 / 7" (assuming Dressing is first component by `order_index`).
**AC7** — Widget test: mount with meal fetch succeeding, one recipe fetch failing. Assert:
  - Banner visible: "Grilled Chicken couldn't load — some steps may be unavailable · Retry".
  - Cook UI still mounts.
  - Step card at an unaffected component (Dressing) renders normally.
  - Advancing to a step in the failed component shows `component_load_placeholder.dart` instead of instruction text.
  - Retry button on the banner re-fetches the one failing recipe.
**AC8** — Widget test: mount fully offline with cached entries for all 3 recipes. Assert cook UI renders with offline banner; no error scaffold.
**AC9** — Widget test: mount offline with 1 uncacheable component + 2 cached. Assert: partial-failure banner, cook UI mounts, placeholder in the failed component's step range.
**AC10** — Performance: in a mocked environment with 200ms per recipe fetch, assert `Future.wait` completes in ≤ 400ms (parallelism verified; sequential would be 600ms).
**AC11** — `didChangeAppLifecycleState(paused)` override calls `debouncer.flushNow()` (same pattern as resume epic cmr-2 AC2).

### Story cmm-3 — Sectioned step traversal + recipe-section header + navigator boundaries

**AC1** — `recipe_section_header.dart` renders the component name + "N / M" fraction above the step card. Uses `CookModeTheme` tokens with fallback. Semantics: `"Step N of M in <ComponentName>"`.
**AC2** — `meal_cook_mode_screen.dart` places the header above the step card. In 1-component plans (recipe cook), the header is **hidden**. In N>1 plans, always shown.
**AC3** — Step traversal: when the user advances past the last step of component K via swipe / tap-zone / Next button, the next step is (K+1, 0). Going back from (K+1, 0) lands on (K, lastStep). Navigation is flat-index-based internally via `CookPlan.stepAt`.
**AC4** — `StepNavigator` receives `componentBoundaries: List<int>` from the plan (e.g., `[0, 7, 11]` for [7, 4, 9]-step components). Renders 16dp-wider margin + 1px vertical rule at boundaries (excluding index 0, which is the first pill — no rule before it).
**AC5** — `StepNavigator` pill Semantics in meal mode announce the component name: "Step 3 of 7, Dressing, current". Recipe mode Semantics unchanged.
**AC6** — Widget test `meal_cook_mode_sectioning_test.dart`: mount with [7, 4, 9]-step plan. Assert header at flat-step 0 reads "Dressing · 1 / 7". Advance 7 times → "Salad · 1 / 4". Advance 4 more → "Grilled Chicken · 1 / 9". Go back once → "Salad · 4 / 4". Go forward to "Grilled Chicken · 1 / 9" again, then finish the component → assert the "Finish meal" button appears at last flat-step (cmm-6 AC1).
**AC7** — Widget test: mount same plan. Assert `StepNavigator` renders 20 pills with boundary rules before indices 7 and 11 (not 0). Visual QA screenshot in the PR description confirms the separator styling.
**AC8** — Widget test: pump recipe cook mode with a 1-component plan. Assert `recipe_section_header` is NOT in the tree. Assert `StepNavigator` has no boundary rules (or exactly the trivial boundary `[0]`).
**AC9** — Flat-total progress bar: at flat-step 10 of 20, progress reads 50%. Locked decision (D from user batch).
**AC10** — Widget test: Semantics assertion — tap step pill index 9 via accessibility-tap. Verify screen reader announcement includes "Salad" (the component name for that pill).

### Story cmm-4 — Interlaced combined ingredient strip with source tags

**AC1** — `CookPlan.fromMeal` builds `plan.ingredients` as a flat list: iterate `meal.components` in `orderIndex`, then iterate each recipe's `ingredients` in `order_index`. Each entry tagged with `sourceComponentIndex` and `sourceComponentName`. No dedup.
**AC2** — The combined strip is the single `IngredientStrip` at the top, fed `plan.ingredients.map((i) => i.raw).toList()` + a `sourceTagBuilder(idx) => plan.ingredients[idx].sourceComponentName`. Compact view: per-chip tag chip (10-char truncated). Expanded grid view: grouped with "--- From <ComponentName> ---" dividers between groups.
**AC3** — Check-off state uses stable key format `'${sourceComponentIndex}:${orderIndex}'` per `CombinedIngredient.stableKey`. Persisted via `CookSessionPersister`'s `checked_ingredients` list (List<String>). Resume restoration uses these keys — resilient to flat-index drift if a component is re-imported with different ingredient order.
**AC4** — **No deduplication.** Two recipes with "1 cup flour" render as two chips, each with its own tag. Explicit test.
**AC5** — Widget test `meal_cook_mode_ingredients_test.dart`:
  - Mount a 3-component meal with known ingredient lists. Assert the strip shows the total count (sum across components).
  - Assert each chip carries the right source tag in compact view.
  - In expanded view, assert group headers "--- From Dressing ---", "--- From Salad ---", "--- From Grilled Chicken ---" appear between chip groups.
  - Check off chip at stable key "1:3" (Salad's 4th ingredient). Assert another mount with a persisted state restores that chip as checked via stable-key lookup, not flat-position.
  - Dedup NOT applied — two "1 cup flour" rows render as two.
  - Compact view: tag chip truncated to "Grilled Ch…" when component name exceeds 10 chars.
**AC6** — Widget test: single-component recipe cook — no source tags, no group dividers. Pixel-identical to pre-epic rendering.
**AC7** — Parity test: Flutter-side client aggregation output equals what backend's `aggregate_meal_ingredients(meal)` produces for a given meal fixture. Use an existing backend test fixture, assert same list in same order with same per-ingredient fields. (Verifies the client replication is faithful.)
**AC8** — Widget test: ingredient-order drift. Seed a meal resume state with checked_ingredients = `["0:2", "1:0"]`. Mutate the meal plan in-test so component 1's ingredient list no longer has orderIndex 0 (simulating re-import with different order). Restore: chip "0:2" is checked; "1:0" is silently dropped (no crash, no stale check). One-shot snackbar "Ingredients changed since your last session" appears. Same pattern as recipe-version-drift from resume epic.

### Story cmm-5 — Meal-level active timers + component-name label disambiguation

**AC1** — `active_timers_row.dart` (extracted in cmm-1) is shared. In meal cook, mounted at the top of the screen above the ingredient strip (matching recipe-cook's position relative to the scaffold). Timer chips persist across component boundaries.
**AC2** — Label-disambiguation rule: when starting a new timer whose `label` already matches an active timer's label, the new timer's display label becomes `"<ComponentName> · <label>"`. The existing active timer's label is NOT retroactively renamed (first-come-first-served; clearer than retroactive edits).
**AC3** — Manual-timer sheet in meal cook mode: label field defaults to empty, placeholder "Optional label". On submit with empty: default label becomes the current component name (e.g., "Dressing"). If two same-component manual timers collide ("Dressing" and "Dressing" again), append `" 2"`, `" 3"`, etc. — reuses `_disambiguateTimerLabel` from `epic-cook-mode-timers`.
**AC4** — OS notification body includes component name: "Your **Dressing** simmer timer is done". Snackbar completion copy uses the same format.
**AC5** — Widget test `meal_cook_mode_timers_test.dart`:
  - Start 3-min timer on Dressing step 2 with extracted label "simmer". Advance flat-step to Salad step 1. Assert "simmer" chip still visible.
  - Start second 5-min timer on Salad step 3 with extracted label "simmer". Assert second chip renders as "Salad · simmer"; first chip stays "simmer".
  - Manual timer on Dressing with empty label → chip renders "Dressing".
**AC6** — Widget test: mock notification service, start an extracted timer on Dressing ("simmer"). Assert the scheduled notification body == "Your **Dressing** simmer timer is done".
**AC7** — Widget test: single-recipe cook mode (1-component plan) — no component-name prefixing even for same-label timers. Pre-existing `_disambiguateTimerLabel` (`" 2"`, `" 3"` suffix) preserved.
**AC8** — Widget test (resume interaction): seed state with an expired timer "simmer" from Dressing. Resume. Assert the "while you were away" snackbar body == "While you were away: **Dressing** simmer timer finished" (singular form, component-name prefixed per meal-cook convention). For N=2 expired from different components: "While you were away: Dressing simmer, Salad boil timers finished" (Oxford-style, ≤3 list per resume epic rule). For N=4: consolidated count "While you were away: **4 timers** finished".

### Story cmm-6 — Per-component multi-row post-cook sheet + N `cooking_logs` writes + early finish

**AC1** — The "Finish meal" button replaces the "Next" button on the final flat-step of the final component. Tap → opens the multi-row post-cook sheet.
**AC2a** — **Early finish:** Overflow menu (the same `PopupMenuButton` that hosts "Reset cook" from `epic-cook-mode-resume`) gains a second item **"Finish cooking now"** in meal cook mode only (hidden in 1-component recipe cook). Tap → confirmation sheet: "Finish this meal early? You'll be asked to rate the components you've cooked so far." Buttons **Cancel** (left) / **Finish** (right, destructive `FilledButton` with `colorScheme.error`). On Finish: open the post-cook sheet seeded **only with components that satisfy `_currentStep >= plan.flatIndexFor(componentIndex, 0)`** — i.e., the user has at least reached that component's first step. Uncooked components are omitted from the sheet. After submission, clear session and pop.
**AC2** — Post-cook sheet (whether reached normally or via early-finish):
  - Renders one row per included component: component name (16pt, weight-600) + 5-star `RatingBar` + optional note field. Scrollable when rows overflow viewport (uses `ListView` internally, not `Column` — prevents layout issues for 6+ component meals).
  - On Done:
    - For every component with `rating > 0`, call `POST /v1/cooking-logs` with `{recipe_id, rating, cooked_at, notes}` — sequential (simpler partial-failure handling; N is small).
    - Each successful write emits `MutationBus().emit(CookingLogCreated(...))`.
    - `rating == 0` components skipped — no log row, no request, no event.
  - On any per-request failure, remaining requests still proceed. Consolidated snackbar at the end: "Cooked X of Y components logged · Retry failed". Retry re-posts the failed ones.
**AC3** — After all writes attempt (success or partial), call `CookSessionPersister().clear(CookSessionKey.forMeal(mealId))`. Clears even on partial failure — user has already rated; blocking clear behind full success traps them.
**AC4** — Tapping Done with all zeroes is allowed — valid "I cooked it, didn't feel like rating" signal. No POSTs, persister cleared, snackbar "Meal finished", pop.
**AC5** — Widget test `meal_post_cook_feedback_test.dart`:
  - Mount sheet with 3 `ComponentRatable`s. Assert 3 rating rows visible.
  - Rate 5 / 4 / 0. Tap Done. Assert 2 `POST /v1/cooking-logs` calls (for the 5 and 4), none for the 0. Assert 2 `CookingLogCreated` mutation events emitted (verifiable via `MutationBus` test spy).
  - Mock one of the 2 POSTs to fail. Assert snackbar "Cooked 1 of 3 components logged · Retry failed". Persister still cleared.
  - Rate 0 / 0 / 0 + Done. Assert 0 POSTs, 0 mutation events, persister cleared, "Meal finished" snackbar.
  - Early-finish: mount 3-component meal at flat-step 10 (into Salad). Open overflow → "Finish cooking now" → confirm. Assert sheet shows **2 rows** (Dressing + Salad — both started), not 3. Rate them, tap Done. Assert 2 POSTs; Grilled Chicken not written. Persister cleared, screen popped.
  - Scrolling: mount sheet with 8 `ComponentRatable`s. Assert ListView scrolls to row 8 via `tester.drag`.
**AC6** — Widget test: recipe-cook mode (1 component) — sheet renders one row identical to today. Existing `post_cook_feedback_test.dart` passes unmodified.
**AC7** — Semantics: each star row announces "<ComponentName>, rate <N> of 5 stars". Optional-note field Semantics "Notes for <ComponentName>".
**AC8** — Widget test: tap early-finish confirmation Cancel. Assert cook UI intact, no state changes, user on same flat-step.

### Story cmm-7 — Meal cook resume wiring + end-to-end regression sweep

**AC1** — `CookSessionPersister` is wired to `meal_cook_mode_screen.dart` using `CookSessionKey.forMeal(mealId)`. Every state mutation (step advance, ingredient toggle with stable key `<ci>:<oi>`, timer start/stop/complete) triggers a debounced write. `didChangeAppLifecycleState(paused)` flushes. `dispose` flushes (belt-and-suspenders). Mirror cmr-2's pattern.
**AC2** — Resume gate on entry mirrors cmr-3 with meal-cook-specific copy: "Picked up from **<ComponentName> · step N of M** · started <relative> · K ingredients checked · L timer(s) [(done while away)]". Shows the current-component's section positioning (not the flat index).
**AC3** — On Resume: restore flat `_currentStep`, `_completedSteps`, `_checkedIngredients` (using stable-key format `<ci>:<oi>`), `_activeTimers` (via absolute `deadline_ms`), `_restoredElapsedMs`. Expired timers fire "While you were away" snackbar with component-name prefix per cmm-5 AC8 + resume-epic's ≤3-list/≥4-count rule.
**AC4** — Meal-version-drift on Resume (analogue of cmr-3 AC10 for recipe cook):
  - If `persisted.current_step >= plan.totalSteps`: clamp to `plan.totalSteps - 1`; one-shot snackbar "Meal changed since your last session — picking up at the last step".
  - If a persisted `checked_ingredients` stable-key references a `<componentIdx>:<orderIdx>` that no longer exists in the refreshed plan: silently drop that key from the check set; log a warning.
  - If a persisted `active_timer` references a component that no longer exists (component removed from the meal): drop that timer; include in expired-while-away aggregation.
**AC5** — Start Over clears `cook_session_meal_<id>` and mounts the cook UI at flat-step 0 (first step of first component).
**AC6** — In-cook Reset (overflow menu "Reset cook") clears the meal session key; same behavior as recipe cook. "Finish cooking now" clears the key after post-cook submission (cmm-6 AC3).
**AC7** — Widget test `meal_cook_mode_resume_test.dart`:
  - Seed SharedPreferences with meal cook state at flat-step 10 (Salad · step 3 of 4), 5 ingredients checked via stable keys, 1 active timer with future deadline. Mount `MealCookModeScreen`. Assert gate sheet visible with expected copy. Tap Resume. Assert cook mode mounts at flat-step 10, header reads "Salad · 3 / 4", 5 ingredients checked, timer chip restored with correct remaining time.
  - Same seed + expired timer from Dressing. Resume. Assert expired snackbar "While you were away: **Dressing** simmer timer finished".
  - Start Over from gate. Assert mounted at flat-step 0, "Dressing · 1 / 7" header.
  - Meal-drift: seed state with `current_step = 20` but refreshed plan has `totalSteps = 15`. Resume. Assert clamp to 14, drift snackbar visible.
  - Stable-key drift: seed with `checked_ingredients = ["0:2", "1:99"]` (1:99 is invalid in refreshed plan). Resume. Assert "0:2" checked, "1:99" silently dropped.
**AC8** — End-to-end widget test: mount `MealCookModeScreen` with a 3-component mock meal. Walk through every step. Start a timer on Dressing step 2, advance, start another on Salad step 3 (same label → disambiguation), advance across boundary to Grilled Chicken, cancel one. Reach last step. Open post-cook sheet, rate 5/4/0. Tap Done. Assert 2 POSTs, 2 `CookingLogCreated` events, persister cleared, pop triggered. Use `FakeAsync` to compress timer ticks.
**AC9** — Regression sweep: every existing cook-mode test passes unchanged after cmm-1..cmm-7 lands. `tools/no-cook-chat-check.sh` green on the expanded `cook_mode/` tree. `npx nx run app:lint` + `npx nx run app:test` green.
**AC10** — Manual QA checklist (walkthrough file in the story):
  - (a) Full meal cook end-to-end with per-component ratings on real device/emulator — verify `cooking_history_provider` reactive update on meal detail after return.
  - (b) Kill-mid-cook + Resume.
  - (c) Early-finish at flat-step 10 (into Salad) — assert 2-row post-cook sheet, not 3.
  - (d) Offline meal cook with all components cached.
  - (e) Offline meal cook with one uncacheable component → partial-load banner + placeholder.
  - (f) Meal with 1 component (single-component meal case) — meal cook still functions.
  - (g) Meal with 6+ components — rating sheet scrolls.
  - Screenshots posted to the PR.

## Dependencies

- **Internal ordering:**
  - cmm-1 (shared extraction + `CookPlan`) blocks all others — every downstream story uses the plan abstraction and shared widgets.
  - cmm-2 (loader + route + FAB + partial-load) should land before cmm-3..cmm-6 for end-to-end mount coverage.
  - cmm-3 (section header) and cmm-4 (ingredients) touch different widgets; parallelizable.
  - cmm-5 (timers) independent of cmm-3/cmm-4 within the screen.
  - cmm-6 (post-cook + early-finish) independent; can parallelize with cmm-5.
  - cmm-7 (resume + sweep) depends on cmm-1..cmm-6 all in.

- **Cross-epic:**
  - `epic-cook-mode-resume` (planned): **hard dependency.** `CookSessionPersister`, `CookSessionDebouncer`, `cook_resume_gate_sheet.dart`, `cook_reset_confirm_sheet.dart`, `relative_time.dart`, `WidgetsBindingObserver.paused` flush pattern, recipe-version-drift snackbar pattern, destructive-right, "while you were away" ≤3/≥4 copy rule — all inherited.
  - `epic-cook-mode-remove-chat` (planned): soft dep. Meal cook has no chat by construction. If chat-removal ships first: clean. Otherwise: cmm-1's shared extraction skips any chat-related widget explicitly.
  - `epic-cook-mode-polish` (backlog): `CookModeTheme` extension. Meal cook uses the same `_resolveCookTimer` fallback pattern; whichever ships first, the other inherits.
  - **Merge risks:**
    - cmm-1 moves files from `widgets/` to `shared/widgets/`. In-flight PRs editing old paths will conflict trivially.
    - cmm-2 adds a FAB to `meal_detail_screen.dart`. If `epic-meals-home-promotion` (in-progress) edits the same screen, rebase needed.
    - cmm-5 extracts the header's active-timers row via cmm-1. `epic-cook-mode-polish` cmp-2 also edits `_buildHeader`. Sequence whichever ships second to do the reconciliation.

- **Out of scope / future:**
  - Batch endpoint `GET /v1/meals/{id}?hydrate=true` — not needed for 2-5 component meals; client fan-out is <500ms.
  - Skip-a-component mid-meal ("I don't want to make Grilled Chicken, jump straight to Salad"). Early-finish covers the "stop partway" case. Mid-meal-skip is a future improvement.
  - Concurrent-mutation handling (component archived while user is mid-cook). N fetches happen at mount time; mid-session refetch isn't done, so this edge doesn't manifest in v1.

## Open questions for the user

- **None outstanding.** Party-mode batched seven questions; six resolved within the epic (section header placement — header above, internal step subtitle removed to avoid redundancy; source tags — per-chip compact + group headers expanded; scrollable post-cook sheet for 6+ components; partial-load banner + placeholder degrade; single-component meals show FAB; mid-session skip deferred to a future epic). The seventh (concurrent-mutation edge) is explicitly out of scope, not a question for the user.
