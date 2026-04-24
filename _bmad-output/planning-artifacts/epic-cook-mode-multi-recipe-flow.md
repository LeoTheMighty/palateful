<!-- refined via party-mode 2026-04-22 -->
# Epic: Cook Mode Multi-Recipe Flow (meal mode, Flutter-only)

## Overview

Meal cook mode today walks the user through all steps of all component recipes sequentially (Dressing 1–7, then Salad 1–4, then Chicken 1–9). In the real kitchen, meals are interleaved: Dressing has a `let sit 5 min` phase, during which the user wants to start Salad prep, then come back. Today they can't — there's one flat `currentStep`, one progress bar across the whole meal, and no way to switch recipes mid-cook.

This epic reshapes meal cook mode around a **per-recipe step map** (`Map<recipeId, stepIndex>`) plus an `activeRecipeId` pointer, and surfaces a **recipe toggle bar** that lets the user swap between component recipes at will, resuming each one at its own step. Auto-advance at the end of a recipe, cross-recipe timer pulses, and recipe-name-prefixed timer chips round out the interaction.

This epic is **Flutter-only**. No backend, no schema, no infra. It depends on `epic-cook-mode-layout-polish` landing first.

## Inherited from epic-cook-mode-layout-polish

The prior epic locked the following. These are **closed** for this workshop — do not re-open:

1. **Chip typography tokens.** Name `14px w500 cookOnSurface / cookOnCompleted`. Quantity `14px w600 cookAccent / cookOnCompleted`. Padding `(12, 8)`. Radius `20`. Toggle-bar pills reuse (or wrap) these tokens — they do not redefine them.
2. **Chip width strategy.** `ConstrainedBox(minWidth: 72, maxWidth: 160)` — not `IntrinsicWidth`. Toggle-bar pills follow the same constraint pattern for their `{name} {cur}/{total}` label.
3. **Ingredient block scroll behavior.** No internal scroll region. Ingredients live in the outer `SingleChildScrollView`. The toggle bar, mounted below the ingredient block, does **not** introduce a nested scroll viewport; it scrolls horizontally but lives in the outer column.
4. **Group-header shape (meal mode).** `13px w600 letterSpacing 0.4 cookOnSurface.alpha(0.7)` + 1dp `cookDivider.alpha(0.5)` divider + 4dp spacer, `Semantics(header: true)`. Not reused by this epic — the toggle bar replaces section-header chrome — but the tokens stay available if any future per-recipe heading surfaces.
5. **Section-header-file lifecycle.** `recipe_section_header.dart` is **orphaned on disk** entering this epic (no imports, no render site). This epic's cmmrf-4 deletes the file as part of its own refactor. One atomic commit for the delete.
6. **Empty-ingredient behavior.** `IngredientStrip` returns `SizedBox.shrink()` when empty. The toggle bar adopts the same "render nothing when empty" posture: a 1-component meal renders no toggle bar at all.

## Goal

A user cooks a 3-recipe meal, starts a 5-minute rest timer mid-Dressing, switches to Salad, works three Salad steps, and returns to Dressing at the exact step they left — all without a resume gate, all without losing ingredient check state, with a timer chip that always says which recipe it belongs to, and with a bottom progress indicator that reflects whichever recipe is currently active.

## End-user flow

1. User taps **Start Cooking** on a 3-recipe meal (Dressing 7 steps, Salad 4 steps, Grilled Chicken 9 steps). `MealCookModeScreen` mounts.
2. Top bar unchanged from layout-polish epic. Below it: active-timers row (empty initially), full grouped ingredient list (Dressing / Salad / Grilled Chicken groups), then — new — a **recipe toggle bar**.
3. **Toggle bar** renders three pills: `Dressing 1/7` · `Salad 1/4` · `Grilled Chicken 1/9`. The leftmost (`Dressing`) is active by default (plan order). Active pill has a filled `cookAccent` background; inactive pills are outlined. A horizontally scrollable `Row`.
4. Below the toggle bar: the step card for Dressing step 1. No `Dressing · 1 / 7` section header above it — the toggle bar + bottom indicator carry that context now.
5. Bottom chrome: linear progress bar reads 1/7 (14%) of Dressing. `5 / 7` style numeric label sits next to the bar. Prev/Next/Done scoped to the active recipe.
6. User advances Dressing 1 → 2 → 3 → 4. At step 4: "Let rest 5 minutes." User taps the inline 5-min timer button. The chip lands in the active-timers row at the top: `Dressing · 5:00`. The toggle pill updates to `Dressing 4/7`.
7. User taps the **Salad** toggle pill. The screen content swaps: ingredient list groups stay visible (they're screen-permanent), toggle bar active-state moves to `Salad`, step card becomes Salad step 1, bottom progress reads 1/4. The Dressing timer chip at the top keeps ticking down — `Dressing · 4:37`, `Dressing · 4:22` …
8. User advances Salad 1 → 2 → 3. Taps the **Dressing** toggle pill → back to Dressing step 4 (exactly where they left). Taps Next — Dressing step 5. Continues.
9. **Timer fires on a non-active recipe.** User is on Salad step 3 when the Dressing rest-timer finishes. Completion snackbar appears: `Dressing · rest timer done`. The Dressing toggle pill pulses briefly (single pulse, 600ms round-trip; see Pulse animation below). No auto-switch; the user taps Dressing to return.
10. **End of a recipe.** User finishes Dressing step 7 and taps Next. Since Dressing has no step 8, the app finds the first unfinished recipe in plan order (Salad, since step 3 < 4). `activeRecipeId` updates to Salad, active toggle pill switches, step card shows Salad step 4 (the next one to do). Bottom progress reads 4/4 of Salad (100% after they advance through it).
11. **End of all recipes.** User advances through every recipe's last step. On the final Next, no unfinished recipe remains. The post-cook rating sheet opens with 3 rows (Dressing, Salad, Grilled Chicken). Rate and submit → 3 `POST /v1/cooking-logs` calls, same path as today. Reuses the existing `_finishCookingEarly` / post-cook entry point in `meal_cook_mode_screen.dart` — not a separate path.
12. **Early finish.** Overflow → `Finish cooking now` → confirm. Post-cook sheet fires with rows only for recipes whose `currentStepByRecipe[id] > 0` **OR** whose id appears in `_enteredRecipeIds`. Untouched recipes don't show up in the sheet.
13. **Kill / resume.** User on Salad step 2 backgrounds the app; OS kills it. Re-enters meal → FAB → Resume gate: `Picked up from Salad · step 2 of 4 · 3 ingredients checked · 1 timer running`. Tap Resume. `MealCookModeScreen` mounts with `activeRecipeId = Salad`, `currentStepByRecipe = {dressing: 4, salad: 1, chicken: 0}`, timers restored, ingredient checks restored. Same resume pattern as today — only the restored state shape differs. The gate-copy computation path (`_resumeStepSummary`) now reads from the v2 map; on a v1 payload it falls through the migration first then computes the same `{componentName} · step {N} of {total}` string.
14. **Single-recipe cook (regression guard).** User taps Start Cooking on a single-recipe meal (rare edge case) or the recipe-cook entry point. Toggle bar **is not rendered** (only one recipe → nothing to toggle). All other polish from this epic applies. No behavior regressions in recipe cook mode.

### End-user flow edge cases (lens-found)

- **User taps a not-yet-entered pill.** User is on Dressing step 3. They tap the Grilled Chicken pill (Chicken has never been entered — its `currentStepByRecipe[chicken] == 0`). Behavior: `_activeRecipeId` flips to `chicken`; step card shows Chicken step 1; bottom progress reads 1/9; Chicken is now considered "entered" (added to `_enteredRecipeIds`). The state change **does fire** even though the step index didn't move (was 0, is 0). Rationale: entering a recipe is the signal the post-cook sheet uses to decide whether to include its row on early finish.
- **User taps a fully-complete recipe's pill.** User finished Dressing earlier (completed set contains every step index 0–6, `currentStepByRecipe[dressing] == 6`). They tap Dressing. Behavior: `_activeRecipeId` flips to `dressing`; step card shows Dressing step 7 (the last step, the one they left from). They are **not** bounced to "the next unfinished recipe" — tapping a pill respects exactly what the pill label says, which is the last step they worked on. The checkmark on the pill remains. Prev still rewinds in-recipe; Next triggers `_autoAdvanceRecipe()` (they're already on the last step).
- **Rating sheet row count on early finish.** User finished Dressing and Salad (both `currentStepByRecipe > 0`), never entered Chicken. Rating sheet fires with **2 rows** (Dressing, Salad). Untouched Chicken is omitted. This matches the cmm-6 shipped behavior; confirmed survives the state-shape refactor.
- **Component still loading.** If a component recipe hasn't loaded yet (`component.loadFailed == true` or `component.steps` is the placeholder sentinel), its toggle pill renders **in an outlined-disabled style** with the label `{Name} …` and is **not tappable** (tap handler returns early, no state change, no haptic). Rationale: the existing `ComponentLoadPlaceholder` path still owns the step-card area if the user is on that component; disabling the pill prevents a tap-to-placeholder loop. Once the retry succeeds and the plan rebuilds, the pill renders normally with its real step count.

## Frontend changes

### `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`

- Replace `int _currentStep = 0;` (line 79) with `Map<String, int> _currentStepByRecipe = {};` keyed by `recipe_id` and `String _activeRecipeId;` (initialized to `plan.components.first.recipeId` on mount, after the plan lands).
- Replace `Set<int> _completedSteps = {};` (line 80) with `Map<String, Set<int>> _completedStepsByRecipe = {};`. Each recipe's completed-step indices live under its own key (local, not flat).
- Add `Set<String> _enteredRecipeIds = {};` — recipes the user has at any point made active. Used by early-finish row inclusion.
- Replace `_nextStep()`, `_previousStep()`, `_goToStep(int)` with equivalents that operate on the active recipe's entry in the maps.
  - `_nextStep()`: if `_currentStepByRecipe[_activeRecipeId]! < plan.stepsFor(_activeRecipeId).length - 1`, increment; else call `_autoAdvanceRecipe()`.
  - `_autoAdvanceRecipe()`: use `plan.nextUnfinishedRecipeAfter(_activeRecipeId, _currentStepByRecipe, _completedStepsByRecipe)`; if non-null, set `_activeRecipeId` + add to `_enteredRecipeIds`; if null, invoke the same post-cook entry point as `_finishCookingEarly` (not a separate path).
  - `_previousStep()`: if `_currentStepByRecipe[_activeRecipeId]! > 0`, decrement; else (if `plan.previousEnteredRecipe(_activeRecipeId, _enteredRecipeIds)` is non-null) switch `_activeRecipeId` to prior recipe and set its step to `stepsFor(prior).length - 1`. If at first-recipe step 0, no-op.
- `_setActiveRecipe(String recipeId)`: handler for toggle pill tap. Guard-clauses for (a) same recipe (no-op, no haptic), (b) `component.loadFailed` (no-op, no haptic). Otherwise: `HapticFeedback.selectionClick()`, updates `_activeRecipeId`, adds to `_enteredRecipeIds`, persists snapshot via the debouncer.
- Ingredient check-state (`_checkedIngredientKeys`) unchanged — stable keys (`componentIdx:orderIdx`) already work across recipe context.
- Pulse state: `Set<String> _pulsingRecipeIds = {}` — populated when a timer fires on a non-active recipe; auto-cleared on the `AnimatedScale.onEnd` callback.
- **State kept in `StatefulWidget`, not a `ChangeNotifier` / provider.** Rationale (from Flutter lens): the existing `_MealCookModeScreenState` already owns a tightly-coupled bundle of `_activeTimers`, `_cookingStopwatch`, `_restoredElapsedMs`, `_checkedIngredientKeys`, `_retryingRecipeIds`, `_rawRecipes`. Extracting only the per-recipe step map to a provider fragments the screen's state across two ownership models without buying testability (every test already mounts the whole screen). Defer a provider refactor to a future cook-mode restructure if one happens.

### New widget — `app/lib/features/recipes/cook_mode/meal/widgets/recipe_toggle_bar.dart`

```dart
class RecipeToggleBar extends StatelessWidget {
  final List<ComponentSummary> components;
  final String activeRecipeId;
  final Set<String> pulsingRecipeIds;
  final ValueChanged<String> onTap;
  const RecipeToggleBar({
    super.key,
    required this.components,
    required this.activeRecipeId,
    required this.pulsingRecipeIds,
    required this.onTap,
  });
}
```

- **`ComponentSummary` is a net-new DTO** on `cook_plan.dart` (not pre-existing — flagged by Flutter lens). Fields: `String recipeId`, `String name`, `int currentStep` (local), `int totalSteps` (local), `bool isComplete`, `bool loadFailed`. Factory: `CookPlan.summaryFor(recipeId, currentStepByRecipe, completedStepsByRecipe)`.
- Horizontal scrollable `SingleChildScrollView(scrollDirection: Axis.horizontal)` wrapping a `Row` of pills. Not `ListView.builder` — pill count is ≤ typical-meal-size (3–5), and `Row` gives us natural intrinsic sizing without the viewport-capping surprises of a horizontal list inside an outer scroll view.
- **Pill height / layout readability at Dynamic Type 1.5x.** Outer `height: 44` is the *minimum* — the pill's internal column uses `mainAxisSize: MainAxisSize.min` so at 1.5x TextScaler the pill grows to ~56dp vertically; the outer row wraps in `IntrinsicHeight` so all pills match the tallest. Pill label is a single line `Text('${name} ${cur}/${total}', maxLines: 1, overflow: TextOverflow.ellipsis)`. At 1.5x with a long recipe name ("Grilled Chicken 1/9"), the label clips at the name end with an ellipsis; `maxWidth: 160` on the pill (inherited-decision 2) prevents runaway pill width. A recipe-name ellipsis is the accepted trade-off over a 2-line pill.
- Each pill: `AnimatedContainer(duration: 150ms)` for state transitions. Active state: filled `cookAccent` bg, `cookOnAccent` text. Inactive: outlined, `cookOnSurface` text. Complete state (`isComplete == true`): same as inactive but with a trailing `Icon(Icons.check, size: 14, color: cookCompleted)` — pill stays tappable (rewind/review). Loading-disabled state: outlined, `cookOnSurface.alpha(0.4)`, label suffix `…`, `onTap` returns early inside `_setActiveRecipe`.
- **Completed-but-tappable affordance discoverability** (UX lens): the checkmark icon alone isn't a clear "rewind by tapping" signal. Mitigation: the pill's visual state is identical to an inactive (non-complete) pill except for the trailing check — tappability is implicit from the pill shape. We do NOT add a tooltip or long-press hint; that's over-engineering for an affordance that the user only needs to discover once. This is an accepted trade-off.
- **Pulse animation** (finalized from UX lens + Flutter lens): single pulse, `AnimatedScale(scale: pulsing ? 1.08 : 1.0, duration: Duration(milliseconds: 300), curve: Curves.easeOutBack)`. Uses `AnimatedScale` over a custom `AnimationController` — fewer lifecycle bugs, no dispose dance. The `onEnd` callback scheduler-microtask-removes the id from `_pulsingRecipeIds`, letting the scale settle back to 1.0 on the next build. **No haptic on pulse** — the user isn't touching the device; the snackbar already owns the "hey look" signal. **No audible cue**. **Duration rationale**: a single 300ms out-and-ease-back totals ~600ms perceived motion, not the 1.2s of two pulses — the two-cycle version was louder than useful, and `Curves.easeOutBack` already gives the pulse a readable "pop" from its overshoot.
- **Cross-recipe swipe visual treatment** (UX lens): **no animation**. When `_setActiveRecipe` fires (via pill tap OR boundary swipe), the step card simply rebuilds with the new instruction text. Rationale: a slide animation on the step card would conflict with the forward/backward swipe gesture zones inherited from `cook_mode_gesture_test.dart`'s 25/50/25 rule — an animation in the swipe direction reads like a successful swipe regardless of whether it was a recipe switch. Explicit deliberate choice: rebuild is instantaneous; context comes from the toggle bar's active-state shift + the bottom progress indicator's number change. Same treatment whether switch-by-tap or switch-by-swipe.
- **Single-pill meal**: hidden entirely when `components.length <= 1`, per inherited-decision 6.
- **Outer padding**: `EdgeInsets.symmetric(horizontal: 16, vertical: 8)`.

### `app/lib/features/recipes/cook_mode/shared/widgets/active_timers_row.dart`

- Timer chip copy now always includes recipe-name prefix **in meal mode**: `Dressing · 0:17`. In recipe mode (single-recipe cook), no prefix (current behavior preserved).
- Prefix source: a new optional `String? Function(T timer) recipeNameForTimer` builder prop, populated by the meal screen based on the `SavedTimerState.sourceRecipeId` field (see persister section below). If the builder returns null, chip renders without prefix.
- **V1-restored timer fallback** (Flutter lens): timers lifted from a v1 session have no `sourceRecipeId`. The builder returns `null` for those entries → the chip renders without prefix (`0:17` not `Dressing · 0:17`). Rationale: guessing "active recipe at restore time" would be wrong on a meal where the v1 timer originated on a different recipe than the restored active one. A prefixless chip is honest; the user learns the recipe from the snackbar on completion. V2-native timers always have the prefix.
- Chip font: no layout change; prefix simply joins with a `·` separator in the same text style. At Dynamic Type 1.5x a long prefix + label (e.g., `Grilled Chicken · 12:00`) may clip inside the 44dp chip height — we `Text(..., overflow: TextOverflow.fade, softWrap: false)` so the tail gradient-fades rather than clipping sharply.
- Snackbar copy on timer completion: `Dressing · rest timer done` (meal, when recipe name available) vs `rest timer done` (recipe mode OR v1-restored timer with no `sourceRecipeId`).

### `app/lib/features/recipes/cook_mode/shared/cook_plan.dart`

- New helper methods on `CookPlan`:
  - `List<CookStep> stepsFor(String recipeId)` — steps for a given component, by id. Throws if id not in plan.
  - `int stepIndexFor(String recipeId, Map<String, int> stepByRecipe)` — defensive read (returns 0 when absent), used for summary factory.
  - `ComponentSummary summaryFor(String recipeId, Map<String, int> stepByRecipe, Map<String, Set<int>> completedByRecipe)` — factory for toggle-bar pills.
  - `String? nextUnfinishedRecipeAfter(String activeId, Map<String, int> stepByRecipe, Map<String, Set<int>> completedByRecipe)` — next recipe in plan order whose `stepByRecipe[id] < stepsFor(id).length - 1` OR whose last step isn't in `completedByRecipe[id]`. Returns null if all complete.
  - `String? previousEnteredRecipe(String activeId, Set<String> enteredIds)` — prior-in-plan-order recipe id that appears in `enteredIds`, or null.
- The `stepAt(int flatIndex)` / `flatIndexFor(...)` helpers stay, for backward compat with the persister v1 read path.
- **New DTO** `ComponentSummary` (plain value class) as described above.

### `app/lib/features/recipes/cook_mode/services/cook_session_persister.dart`

- `CookSessionState` schema v1 → v2:

```dart
class CookSessionState {
  static const int currentSchemaVersion = 2;

  final CookTargetKind targetKind;
  final String targetId;
  final int startedAtMs;
  final int cumulativeElapsedMs;

  // v2 — primary per-recipe state.
  final String? activeRecipeId;                         // null on recipe-mode
  final Map<String, int> currentStepByRecipe;
  final Map<String, Set<int>> completedStepsByRecipe;

  final List<String> checkedIngredients;                // unchanged wire shape
  final List<SavedTimerState> activeTimers;             // SavedTimerState gains sourceRecipeId
  final int updatedAtMs;

  // Migration-only fields; see "Migration invariant" below.
  final int? legacyCurrentStep;
  final Set<int>? legacyCompletedSteps;
}
```

- **Migration invariant** (explicit, from Flutter lens):
  - After `fromJson` returns, **exactly one** of the following is true:
    - (a) `legacyCurrentStep == null && legacyCompletedSteps == null` — state is fully in v2 shape; `currentStepByRecipe` and `completedStepsByRecipe` are authoritative. Recipe-mode v1 payloads land here via the self-contained unpack; all v2 payloads land here directly.
    - (b) `legacyCurrentStep != null && legacyCompletedSteps != null && currentStepByRecipe.isEmpty && completedStepsByRecipe.isEmpty && targetKind == CookTargetKind.meal` — **transitional meal-v1 state**. The persister couldn't unpack flat → per-recipe without the plan, so it passed the legacy fields through. `_MealCookModeScreenState._initCookSession()` must call `CookSessionState.unpackLegacyMeal(plan)` before applying to in-memory state.
  - No other combination is valid. `_applyRestoredState` asserts this invariant and clears state on violation.
- **Migration path** (`fromJson`):
  - If payload `schema_version == 1`:
    - If `target_kind == "recipe"`: persister constructs `currentStepByRecipe = {targetId: legacyCurrentStep}`, `completedStepsByRecipe = {targetId: legacyCompletedSteps.toSet()}`, `activeRecipeId = targetId`. Fully self-contained; no plan needed. `legacyCurrentStep` / `legacyCompletedSteps` set to null on the returned state (invariant case a).
    - If `target_kind == "meal"`: transitional state per invariant case b. `legacyCurrentStep`/`legacyCompletedSteps` populated, maps empty, `activeRecipeId = null`.
  - If payload `schema_version == 2`: direct deserialize; legacy fields null.
  - Unparseable: clear silently (return null), same as today.
- **Serialization** (`toJson`): always writes `schema_version = 2`. Never writes v1 again. Old v1 sessions are one-shot-migrated on read; next save is v2. The legacy fields are **never serialized** (even when non-null during the transitional window — if the app is killed between load and screen-unpack, a v1 session on restart goes through the same migration path again, idempotently).
- `SavedTimerState`: gains `final String? sourceRecipeId;` (nullable for recipe-mode AND v1-restored-meal-mode back-compat). Populated at timer creation in v2 meal mode. V1-restored timers keep it null; v2 round-trip preserves it.
- `unpackLegacyMeal(CookPlan plan)` method on `CookSessionState`: uses `plan.stepAt(legacyCurrentStep)` to derive the active recipe + per-recipe step map, and distributes `legacyCompletedSteps` into `completedStepsByRecipe` via `plan.stepAt` on each flat index. Returns a new `CookSessionState` in invariant case (a).

### `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart` — bottom indicator

- Replace `LinearProgressIndicator(value: (_currentStep + 1) / plan.totalSteps)` (line 1373) with `LinearProgressIndicator(value: (_currentStepByRecipe[_activeRecipeId]! + 1) / plan.stepsFor(_activeRecipeId).length)`.
- Numeric label right of progress bar: `Text('${cur + 1} / ${total}')` in `cook.cookOnSurface` 12px.
- Progress bar margin inherits the 24dp horizontal value locked by the layout-polish epic.

### `app/lib/features/recipes/cook_mode/meal/widgets/recipe_section_header.dart`

- **File deleted in cmmrf-4**, along with its import in `meal_cook_mode_screen.dart`. This is the atomic-commit deletion the prior epic explicitly deferred.

### Swipe gestures

- Existing 25% / 50% / 25% left/center/right gesture zones in `cook_mode_screen.dart` + meal variant stay. Forward swipe past the active recipe's last step triggers `_autoAdvanceRecipe()`. Backward swipe at step 0 of the first plan-order recipe no-ops (today). Backward swipe at step 0 of a later recipe rewinds to the previous entered recipe's last step (iff one exists), using `plan.previousEnteredRecipe(_activeRecipeId, _enteredRecipeIds)`.

## Backend changes

**None — confirmed.** No API shapes change, no migration, no write-path change. `/v1/cooking-logs` write path, `CookingLogCreated` mutation event shape, and meal / recipe fetch endpoints are all identical to cmm-6. The persister is a Flutter-local SharedPreferences payload; the schema bump is client-only.

## Infrastructure changes

**None — confirmed.** No env vars, no CI workflow changes, no Terraform, no `tools/no-cook-chat-check.sh` allowlist changes, no `tools/no-silent-catch-check.sh` allowlist changes. The `services/api` 100% coverage gate is Flutter-unaffected here. Pure client-side state refactor + UI.

## Design principles

- **Per-recipe state is the new primary.** `currentStepByRecipe` is the source of truth. `activeRecipeId` is a pointer. The old flat `currentStep` is legacy-compat only; nothing new writes to it.
- **Migration invariant is explicit.** After `CookSessionState.fromJson` returns, the state is either fully v2-shaped OR is a clearly-marked transitional meal-v1 state that requires plan-aware unpacking. No third state exists.
- **Ingredient check-state doesn't scope to active recipe.** Check state uses stable `componentIdx:orderIdx` keys across the whole meal; switching recipes doesn't hide what's been checked.
- **Timers are meal-global, labels are recipe-local.** One `_activeTimers` list at the meal level, each entry tags its owning recipe. Chip copy surfaces the tag. V1-restored timers tag null → chip renders without prefix (honesty over guessing).
- **Pulses, not auto-switches.** When a timer fires on a non-active recipe, the user learns about it via a snackbar + toggle-pill pulse (single 300ms `easeOutBack`). Auto-switching would be surprising and would disrupt whatever they're currently doing.
- **Pill tap respects its label.** Tapping a pill always lands on the step the pill says, not "the next unfinished step in this recipe." Completed pills rewind; not-yet-entered pills enter at step 1.
- **Auto-advance on recipe end keeps the "Next, Next, Next" momentum.** Users who don't toggle at all experience something very close to today's linear flow — the screen jumps them forward through recipes automatically when they hit the end of one.
- **One post-cook entry point.** Whether auto-advance runs out of recipes or the user picks "Finish cooking now," the same `_finishCookingEarly` path fires. Row inclusion uses `_enteredRecipeIds` as the filter, so both flows agree on row count.
- **No step-card switch animation.** Recipe switch is an instantaneous rebuild. Context comes from the toggle bar + bottom progress, not from motion. Avoids colliding with swipe-gesture semantics.
- **Resume gate behavior unchanged.** Same `CookSessionPersister` key, same gate sheet, same `Picked up from {component} · step {N} of {total}` copy — just driven by `_currentStepByRecipe[_activeRecipeId]` after unpack instead of the flat int.
- **v1 sessions are honored, not trashed.** A user mid-cook at the moment of app upgrade doesn't lose their session. One-shot migration on first read, then all saves are v2.
- **State stays in `StatefulWidget`.** No Riverpod provider extraction for the per-recipe maps. Existing harness mounts the whole screen; fragmenting ownership across a provider + state buys nothing testability-wise.

## File structure

New:
- `app/lib/features/recipes/cook_mode/meal/widgets/recipe_toggle_bar.dart`

Deleted:
- `app/lib/features/recipes/cook_mode/meal/widgets/recipe_section_header.dart` (the atomic-commit deletion inherited from the polish epic)

Modified:
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart` (state refactor + toggle bar mount + bottom indicator + swipe adaptation + post-cook single-entry-point + import cleanup for the deleted section-header file)
- `app/lib/features/recipes/cook_mode/shared/cook_plan.dart` (helpers + `ComponentSummary` DTO)
- `app/lib/features/recipes/cook_mode/services/cook_session_persister.dart` (schema v2 + migration + `SavedTimerState.sourceRecipeId`)
- `app/lib/features/recipes/cook_mode/shared/widgets/active_timers_row.dart` (optional recipe-name prefix builder)

New tests:
- `app/test/meal_cook_mode_toggles_test.dart` — toggle bar rendering (3+ recipes), active state, completed checkmark, single-recipe hides bar, loading-disabled pill, tap-to-switch, tap-to-not-yet-entered enters at step 1, step state isolation per recipe, Dynamic Type 1.5x label ellipsis.
- `app/test/meal_cook_mode_auto_advance_test.dart` — Next on last step advances to first unfinished recipe; all-complete fires post-cook sheet via single entry point; early-finish shows only recipes in `_enteredRecipeIds`; tap-a-pill-then-tap-Next auto-advance still respects the currently-active recipe.
- `app/test/meal_cook_mode_cross_recipe_timer_test.dart` — timer fires while on another recipe → pulse + snackbar; chip prefix copy (`Dressing · 0:17`); `AnimatedScale` onEnd clears pulse set; v1-restored timer chip renders without prefix.
- `app/test/cook_session_persister_v2_migration_test.dart` — v1 recipe session round-trip (self-contained unpack); v1 meal session read → transitional shape (invariant case b); v2 native round-trip; unparseable clears; `SavedTimerState.sourceRecipeId` serialization.

Modified tests (exact changes):
- `app/test/meal_cook_mode_test.dart` — add assertion that `RecipeToggleBar` mounts for 3-component meal, is absent for 1-component meal; per-recipe progress bar value = `(cur + 1) / stepsFor(activeId).length`.
- `app/test/meal_cook_mode_sectioning_test.dart` — the `cmm-3 — recipe section header` group was already deleted by the polish epic. This epic further reshapes the file: the "navigator boundary rules render at indices 7 and 11" test is **deleted** (StepNavigator's `componentBoundaries` prop is removed in cmmrf-4 — there are no flat boundaries anymore, each recipe has its own local-step navigator). The "flat-total progress bar at flat-step 9 of 20 ≈ 50%" test is **deleted** and replaced in `meal_cook_mode_test.dart` with a per-recipe progress assertion. After cmmrf-4, the file contains no tests and is **deleted entirely** (cleaner than an empty file).
- `app/test/meal_cook_mode_timers_test.dart` — chip prefix assertions (`Dressing · 0:17`); disambiguation rule still applies for duplicate-labeled timers across recipes; expired-while-away snackbar still uses `_expiredAwayCopy` which gets the recipe-name prefix via the same `sourceRecipeId` lookup.
- `app/test/meal_cook_mode_resume_test.dart` — the existing `Salad · step 3 of 4` assertion at line 218 stays correct; the resume-gate copy-computation path now flows through the v2 migration first. Add a new test: v1 meal payload → resume gate shows `Salad · step 3 of 4` (same string, post-unpack) — verifies the transitional-state migration path preserves gate copy.
- `app/test/cook_mode_gesture_test.dart` — add a test: "meal cook mode backward swipe at step 0 of a later entered recipe rewinds to prior recipe's last step" — mounts a 3-recipe meal, advances to Dressing step 3, taps Salad pill (enters Salad at step 1, which is stepIndex 0 local), performs a backward swipe in the left 25% zone → expects `_activeRecipeId == 'dressing'` and Dressing step card showing step 3 (last-visited). Backward swipe at step 0 of the first recipe still no-ops. The existing `IngredientStrip expand/collapse` test is already deleted by the polish epic; nothing to adjust there.
- `app/test/cook_session_persister_test.dart` — existing v1 tests **stay** (they verify the v1-era schema, which is still the input side of the migration). **Rename is not needed** — naming the v2-migration file `cook_session_persister_v2_migration_test.dart` keeps the existing `cook_session_persister_test.dart` focused on current-schema save/load/clear round-trips, and the new file owns the v1→v2 migration paths. One existing test in the current file will need adjustment: the `writes schema_version=1 on toJson` test (line 75) becomes `writes schema_version=2 on toJson`; `fromJson returns null for unknown schema_version` (line 80) keeps its intent but the "unknown" set excludes both 1 and 2 now.

## Stories

### cmmrf-1 — Per-recipe step-tracking state (in-memory only)

**Changes** (`meal_cook_mode_screen.dart`)
- Replace `_currentStep` (line 79) / `_completedSteps` (line 80) with `_currentStepByRecipe`, `_completedStepsByRecipe`, `_activeRecipeId`, `_enteredRecipeIds`.
- Rewire `_nextStep`, `_previousStep`, `_goToStep` to operate on the active recipe. Implement `_autoAdvanceRecipe`.
- Add `CookPlan.stepsFor`, `stepIndexFor`, `nextUnfinishedRecipeAfter`, `previousEnteredRecipe`, `summaryFor`, and the `ComponentSummary` DTO.
- Persister schema **unchanged** in this story — state still serializes via v1 flat int (via a translate-on-save helper `_flattenToV1(plan, stepByRecipe)` that flattens the map back through `plan.flatIndexFor`). Keeps behavior identical to today from persistence's POV.
- Dependencies: none internal. Blocks all other stories in this epic.

**Acceptance criteria**
- Unit test: starting on recipe A, advancing to step 3, calling `_setActiveRecipe(B)`, advancing B to step 2, calling `_setActiveRecipe(A)` → A's step is still 3 and B's is 2.
- `_autoAdvanceRecipe` test: on the last step of A with B and C unfinished, Next sets `_activeRecipeId == B`.
- `_previousStep` test: at Salad step 0 after Dressing was entered, Prev sets `_activeRecipeId == Dressing` and current step to Dressing's last.
- All existing meal-cook tests (`meal_cook_mode_test.dart`, `meal_cook_mode_timers_test.dart`, `meal_cook_mode_resume_test.dart`) pass **without modification** — v1 serialization compat is load-bearing here.

### cmmrf-2 — Persister schema v2 + migration

**Changes** (`cook_session_persister.dart`)
- `CookSessionState` schema_version 1 → 2. New fields `currentStepByRecipe`, `completedStepsByRecipe`, `activeRecipeId`. `SavedTimerState.sourceRecipeId` (nullable).
- Legacy fields `legacyCurrentStep`, `legacyCompletedSteps` on the class, populated only during the transitional-meal-v1 window.
- `fromJson` honors the migration invariant (recipe-v1 → self-contained unpack; meal-v1 → transitional; v2 → direct).
- `toJson` always writes v2; never serializes legacy fields.
- `CookSessionState.unpackLegacyMeal(plan)` method.
- `_MealCookModeScreenState._initCookSession` calls `unpackLegacyMeal(plan)` after `_loadMealAndRecipes` when the restored state is in invariant case (b).
- Drop the cmmrf-1 `_flattenToV1` save-path shim; save path is now natively v2.

**Acceptance criteria** (in `cook_session_persister_v2_migration_test.dart`)
- v1 recipe payload round-trip: `fromJson` returns `activeRecipeId = targetId`, `currentStepByRecipe = {targetId: n}`, legacy fields null, invariant (a).
- v1 meal payload: `fromJson` returns `legacyCurrentStep != null`, `currentStepByRecipe.isEmpty`, invariant (b). `unpackLegacyMeal(plan)` on a `[7,4,9]` plan with `legacyCurrentStep = 9` yields `activeRecipeId = salad`, `currentStepByRecipe = {dressing: 6, salad: 2, chicken: 0}` (6 is Dressing's last-reached step via completed-set promotion; 2 is Salad local), `completedStepsByRecipe = {dressing: {0..6}, salad: {0, 1}}`, invariant (a).
- v2 native payload: `fromJson` + `toJson` round-trips byte-identically (golden JSON pinned). `SavedTimerState.sourceRecipeId` preserved.
- Unparseable: `load` clears and returns null (existing test passes unchanged).
- Existing test at line 75 flipped: `writes schema_version=2 on toJson`.
- `meal_cook_mode_resume_test.dart` gets a new test: v1 meal payload → resume gate copy is still `Salad · step 3 of 4`.

### cmmrf-3 — Recipe toggle bar widget + mount

**Changes**
- New `recipe_toggle_bar.dart` per spec (horizontal `Row`, not `ListView.builder`; `IntrinsicHeight`; Dynamic Type 1.5x handling; single-pulse `AnimatedScale`).
- Mount in `MealCookModeScreen` between the ingredient list and the step card. Hidden when `plan.components.length <= 1`.
- Wire `onTap: (id) => _setActiveRecipe(id)`.
- `ComponentSummary` DTO on `cook_plan.dart`; `CookPlan.summaryFor` factory.

**Acceptance criteria** (in `meal_cook_mode_toggles_test.dart`)
- 3-component meal: 3 pills render with copy `Dressing 1/7`, `Salad 1/4`, `Grilled Chicken 1/9`. `find.byType(RecipeToggleBar)` → `findsOneWidget`.
- Active pill: background color equals `cookAccent`; inactive pills are outlined (border color `cookDivider` or similar token).
- Completed pill: trailing `Icon(Icons.check)` present (`find.descendant(of: find.byKey(Key('toggle_pill_$id')), matching: find.byIcon(Icons.check))` → `findsOneWidget`); pill is still tappable (tap fires `_setActiveRecipe`).
- Loading-disabled pill: `component.loadFailed == true` → pill label contains `…`, tap is a no-op (no `setState`, no haptic, asserted via a spy).
- Single-component meal: `find.byType(RecipeToggleBar)` → `findsNothing`.
- Tap-to-switch: tap `Salad` pill → `tester.widget<LinearProgressIndicator>(...).value == 1/4`.
- Tap-to-not-yet-entered: tap `Grilled Chicken` pill before entering it → `_enteredRecipeIds.contains('r3')` is true on the state; step card shows Chicken step 1.
- Dynamic Type 1.5x: `MediaQuery(textScaler: TextScaler.linear(1.5))` wrapping the widget → no `RenderFlex overflowed` warnings; pill label clips via ellipsis at the name end when needed.

### cmmrf-4 — Per-recipe bottom progress indicator + delete section header file

**Changes**
- Bottom progress bar reads from `plan.stepsFor(_activeRecipeId)` / `_currentStepByRecipe[_activeRecipeId]`. Numeric `5 / 7` label next to it.
- **Delete the file** `app/lib/features/recipes/cook_mode/meal/widgets/recipe_section_header.dart`. Remove its import in `meal_cook_mode_screen.dart:47`.
- `StepNavigator.componentBoundaries` prop **removed** (no more flat-progress pill row spanning recipes; each recipe's step navigator is local by construction now). Adjust `step_navigator.dart` signature.
- Delete `app/test/meal_cook_mode_sectioning_test.dart` in its entirety (every remaining test assertion is about flat-boundary or flat-progress semantics that no longer exist). Replacement assertions live in `meal_cook_mode_test.dart` (per-recipe progress) and `meal_cook_mode_toggles_test.dart` (toggle-bar per-recipe context).

**Acceptance criteria**
- `find.byType(LinearProgressIndicator)` in a meal cook with `_activeRecipeId == 'salad'` and `_currentStepByRecipe['salad'] == 1` → value is `closeTo(2/4, 1e-9)`.
- Numeric `2 / 4` text visible next to the progress bar.
- `File('app/lib/features/recipes/cook_mode/meal/widgets/recipe_section_header.dart').existsSync() == false` (repo-integrity smoke).
- No imports of `recipe_section_header.dart` anywhere (grep returns nothing).
- `step_navigator.dart` no longer takes `componentBoundaries` (grep confirms; call sites updated).
- `meal_cook_mode_sectioning_test.dart` is deleted.

### cmmrf-5 — Auto-advance on recipe end + one post-cook entry point

**Changes**
- `_autoAdvanceRecipe()` implemented per spec. Hooked into forward swipe + Next button at active recipe's last step.
- Post-cook sheet opens when no unfinished recipes remain via the **same** `_finishCookingEarly` entry point (not a parallel path). The path filters rows by `_enteredRecipeIds` (recipes the user made active at any point) rather than `currentStepByRecipe > 0` — pills tapped without advancing still count.

**Acceptance criteria** (in `meal_cook_mode_auto_advance_test.dart`)
- Advance through all 7 Dressing steps + tap Next → `_activeRecipeId == 'salad'`, step card shows Salad step 1.
- Advance through all 4 Salad steps + tap Next → `_activeRecipeId == 'grilled-chicken'`.
- Advance through all 9 Chicken steps + tap Next → post-cook sheet opens with 3 rows (one per component).
- Early finish after tapping only Dressing pill (step 1) and Salad pill (never advanced beyond step 1): overflow `Finish cooking now` → sheet has 2 rows (Dressing + Salad). Chicken absent.
- The post-cook entry point is a single function — no duplicate sheet-mounting code. Test asserts `finish_now` overflow menu item and "all recipes finished" both call the same `_openPostCookSheet(rows)` function (verified by ensuring row-building logic is in one place — grep assertion or shared helper).

### cmmrf-6 — Active-timers row recipe-name prefix + cross-recipe pulse

**Changes**
- `active_timers_row.dart` — optional `recipeNameForTimer(T timer) → String?` builder; chip copy becomes `{RecipeName} · {MM:SS}` when the builder returns non-null, else `{MM:SS}`.
- Timer creation in `meal_cook_mode_screen.dart` stamps `sourceRecipeId: _activeRecipeId` on `SavedTimerState` at creation.
- Timer completion callback: if the firing timer's `sourceRecipeId != _activeRecipeId`, add its recipe id to `_pulsingRecipeIds`. Completion snackbar copy gains `{RecipeName} · ` prefix when `sourceRecipeId` resolves; otherwise prefixless.
- Toggle bar reads `_pulsingRecipeIds` → single `AnimatedScale` pulse, 300ms `easeOutBack`, `onEnd` removes the id.

**Acceptance criteria** (in `meal_cook_mode_cross_recipe_timer_test.dart`)
- Start a timer on Dressing (active), tap Salad pill, fast-forward time past Dressing timer's deadline → snackbar text contains `Dressing · `; `_pulsingRecipeIds.contains('dressing')` is true immediately after fire; `_activeRecipeId == 'salad'` unchanged.
- Pulse ends: after pumping 300ms + microtask, `_pulsingRecipeIds.isEmpty` is true; pill's `AnimatedScale.scale` back to 1.0.
- Chip copy: active-timers row shows `Dressing · 0:17` while Dressing timer runs and user is on Salad.
- V1-restored timer (no `sourceRecipeId`): chip renders without prefix (`0:17`); on completion, snackbar reads `rest timer done` (no recipe prefix). Asserted via a v1 payload fixture loaded through the persister.

### cmmrf-7 — Cross-recipe backward-swipe rewind

**Changes**
- `_previousStep()` at active recipe's step 0: check `plan.previousEnteredRecipe(_activeRecipeId, _enteredRecipeIds)`; if non-null, switch active to prior + set step to its last-visited (`_currentStepByRecipe[prior]`). If null, no-op (unchanged).
- Swipe gesture in the left 25% zone at step 0 of a later recipe invokes `_previousStep` — same path as the Prev button.
- No visual animation on the step card (deliberate choice per UX lens — see Design principles).

**Acceptance criteria** (in `cook_mode_gesture_test.dart`)
- 3-recipe meal: advance Dressing to step 3; tap Salad pill; swipe backward (left 25% zone tap / drag) at Salad step 1 → `_activeRecipeId == 'dressing'`, step card shows Dressing step 3, bottom progress reads `3 / 7`.
- Backward swipe at step 0 of the first-plan-order recipe → no state change.
- Backward swipe at step 0 of a later recipe that's **in `_enteredRecipeIds` but whose `currentStep` is 0** (user tapped the pill but never advanced) → rewinds to prior entered recipe (still a valid case since the pill tap entered it).
- Prev button path and swipe path share the same `_previousStep` call (no duplicate logic — single entry point).

## Dependencies

- **Depends on** `epic-cook-mode-layout-polish` — the ingredient-strip simplification, section-header render-site removal, and padding cleanup must land first. The multi-recipe epic inserts the toggle bar into space that the polish epic has cleared, and deletes the now-orphaned section-header file.
- **Depends on** `epic-cook-mode-meal` (shipped) — `CookPlan`, shared widgets, meal-level timers, partial-load handling all foundational.
- **Depends on** `epic-cook-mode-resume` (shipped) — `CookSessionPersister`, resume gate, debouncer, paused-flush all foundational; this epic just evolves the payload schema and the gate-copy computation path.

## Open questions for the user

None. All user-visible surface shapes are locked by the 2026-04-22 PRD addendum. The 2026-04-22 party-mode refinement captured above resolved the technical-trade-off deferrals (pulse duration + cycles, `AnimatedScale` over `AnimationController`, migration invariant, `sourceRecipeId` v1 fallback, no step-card switch animation, single post-cook entry point, state-ownership in `StatefulWidget` over provider).

## Validation against PRD addendum (2026-04-22)

Each of the 8 locked user decisions from the PRD addendum maps to specific stories in this epic:

1. **Toggle bar placement** (below ingredient list, above step card; hidden in single-recipe mode) → **cmmrf-3** (mount site + single-component hide).
2. **Ingredient list shape** (always expanded, grouped by recipe, no compact/expanded toggle) → **inherited from `epic-cook-mode-layout-polish` cmlp-2 + cmlp-4** (landed upstream; re-verified here by cmmrf-3's toggle-bar-mount test also asserting ingredient groups still render).
3. **Chip readability** (no `INGREDIENTS` header, no per-chip source tag, bigger quantities) → **inherited from `epic-cook-mode-layout-polish` cmlp-3 + cmlp-4** (landed upstream).
4. **Section header above step card dropped** → **cmmrf-4** (delete `recipe_section_header.dart` file + import + `StepNavigator.componentBoundaries` prop).
5. **Bottom progress indicator scoped to active recipe** → **cmmrf-4** (per-recipe progress + `5 / 7` numeric label).
6. **End-of-recipe behavior** (auto-advance; post-cook sheet once at meal-end with one row per cooked recipe) → **cmmrf-5** (auto-advance + single post-cook entry point; row filtering by `_enteredRecipeIds`).
7. **Cross-recipe timer completion** (snackbar + pulse, no auto-switch; `Dressing · 0:17` continuous prefix) → **cmmrf-6** (prefix builder + pulse).
8. **X button in cook-mode header removed** → **inherited from `epic-cook-mode-layout-polish` cmlp-1** (landed upstream; no work in this epic).

Beyond the 8 locked decisions, the addendum's non-functional constraints all trace to stories:
- **Persistence schema v1 → v2 bump with one-shot migration** → **cmmrf-2**.
- **Recipe cook mode unchanged** → **cmmrf-1** (regression guard: existing tests pass unmodified; `_flattenToV1` shim preserves wire format until cmmrf-2).
- **New meal-cook-toggle test file + per-recipe step map unit tests + v1→v2 migration test** → **cmmrf-2, cmmrf-3, cmmrf-6** (three new test files per the File structure section).
- **No backend changes** → Backend changes section, "None — confirmed".
- **Real-kitchen usability: swipe-zone behavior preserved; cross-recipe rewind on back-swipe at step 0** → **cmmrf-7**.
