/// cmm-1 — `CookPlan` is the unified shape consumed by both
/// `cook_mode_screen.dart` (single-recipe cook) and
/// `meal_cook_mode_screen.dart` (multi-component meal cook).
///
/// A plan models N components in section order; flat-step indexing
/// (`stepAt` / `flatIndexFor`) maps between the user-facing flat step
/// counter (and persisted resume snapshot) and the per-component
/// instruction list. Recipes lower to a 1-component plan; meals lower to
/// an N-component plan.

library;

import '../../../meals/models/meal.dart';
import 'util/timer_regex.dart';

/// One step entry inside a [CookComponent].
///
/// Mirrors the legacy `_StepData` shape from the recipe-only
/// implementation: instruction text plus an optional list of
/// extractor-supplied [StepTimer]s. Timer parsing happens once here
/// (factory) so the per-frame render path doesn't re-parse JSON on
/// every `setState` (cook mode rebuilds every second while a timer is
/// running).
class CookStep {
  final String instruction;
  final List<StepTimer> timers;

  const CookStep({required this.instruction, required this.timers});

  factory CookStep.fromJson(dynamic raw) {
    if (raw is! Map) return const CookStep(instruction: '', timers: []);
    final instruction = raw['instruction'] as String? ?? '';
    final rawTimers = raw['timers'];
    final parsed = <StepTimer>[];
    if (rawTimers is List) {
      for (final t in rawTimers) {
        final st = StepTimer.fromJson(t);
        if (st != null) parsed.add(st);
      }
    }
    return CookStep(instruction: instruction, timers: parsed);
  }
}

/// One component (a single source recipe) inside a [CookPlan].
///
/// In recipe-cook mode there is exactly one component; in meal-cook
/// mode there is one per `meal_components` row in `order_index` order.
/// `loadFailed == true` marks a component whose recipe fetch errored
/// during the parallel load phase — `meal_cook_mode_screen.dart`
/// (cmm-2) renders a placeholder instead of instructions for that
/// component's flat-step range.
class CookComponent {
  final String recipeId;
  final String name;
  final List<CookStep> steps;
  final List<dynamic> ingredients;
  final bool loadFailed;

  const CookComponent({
    required this.recipeId,
    required this.name,
    required this.steps,
    required this.ingredients,
    this.loadFailed = false,
  });
}

/// A single ingredient row inside [CookPlan.ingredients], tagged with
/// the source component so meal-cook mode can render per-chip source
/// tags + group dividers + a stable check-state key.
///
/// Recipe-cook plans tag every entry with `sourceComponentIndex == 0`
/// and the recipe name; the meal-cook UI hides the source tag when
/// the plan has only one component.
class CombinedIngredient {
  final int sourceComponentIndex;
  final String sourceComponentName;
  final dynamic raw;
  final int orderIndex;

  const CombinedIngredient({
    required this.sourceComponentIndex,
    required this.sourceComponentName,
    required this.raw,
    required this.orderIndex,
  });

  /// Stable string key used for resume restoration of "checked" state.
  /// `<componentIndex>:<orderIndex>` is resilient to flat-position drift
  /// when the underlying recipe is re-imported with a different
  /// ingredient order.
  String get stableKey => '$sourceComponentIndex:$orderIndex';
}

class CookPlan {
  final String sessionKey;
  final String title;
  final List<CookComponent> components;
  final List<CombinedIngredient> ingredients;

  const CookPlan({
    required this.sessionKey,
    required this.title,
    required this.components,
    required this.ingredients,
  });

  int get totalSteps =>
      components.fold(0, (sum, c) => sum + c.steps.length);

  /// True if any component's recipe fetch failed during plan
  /// construction. cmm-2 uses this to decide whether to render the
  /// partial-load banner over the cook UI.
  bool get hasAnyLoadFailures =>
      components.any((c) => c.loadFailed);

  /// Flat indices where each component starts.
  ///
  /// Length always equals `components.length`. For a 3-component plan
  /// with [7, 4, 9] steps, returns `[0, 7, 11]`. The first entry is
  /// always 0 — meal_cook_mode's StepNavigator skips drawing a
  /// vertical rule before index 0 because it's the first pill.
  List<int> get componentBoundaries {
    final out = <int>[];
    var running = 0;
    for (final c in components) {
      out.add(running);
      running += c.steps.length;
    }
    return out;
  }

  /// Map a flat step index → (componentIndex, stepIndexWithinComponent).
  ///
  /// Throws [ArgumentError] for indices outside `[0, totalSteps)`. The
  /// recipe-version-drift clamp in `_applyRestoredState` ensures we
  /// never call this with an out-of-range index in production.
  ({int componentIndex, int stepIndex}) stepAt(int flatIndex) {
    if (flatIndex < 0 || flatIndex >= totalSteps) {
      throw ArgumentError.value(
        flatIndex,
        'flatIndex',
        'must be in [0, $totalSteps)',
      );
    }
    var running = 0;
    for (var ci = 0; ci < components.length; ci++) {
      final len = components[ci].steps.length;
      if (flatIndex < running + len) {
        return (componentIndex: ci, stepIndex: flatIndex - running);
      }
      running += len;
    }
    // Unreachable — bounds check above guards this.
    throw ArgumentError.value(flatIndex, 'flatIndex', 'unreachable');
  }

  /// Inverse of [stepAt]: (componentIndex, stepIndex) → flat index.
  int flatIndexFor(int componentIndex, int stepIndex) {
    if (componentIndex < 0 || componentIndex >= components.length) {
      throw ArgumentError.value(
        componentIndex,
        'componentIndex',
        'must be in [0, ${components.length})',
      );
    }
    final stepLen = components[componentIndex].steps.length;
    if (stepIndex < 0 || stepIndex >= stepLen) {
      throw ArgumentError.value(
        stepIndex,
        'stepIndex',
        'must be in [0, $stepLen)',
      );
    }
    var running = 0;
    for (var ci = 0; ci < componentIndex; ci++) {
      running += components[ci].steps.length;
    }
    return running + stepIndex;
  }

  /// Build a 1-component plan from a single recipe payload (the shape
  /// returned by `GET /v1/recipes/{id}`). Used by `cook_mode_screen.dart`.
  factory CookPlan.fromRecipe(Map<String, dynamic> recipe) {
    final id = recipe['id'] as String? ?? '';
    final name = recipe['name'] as String? ?? 'Recipe';
    final component = _componentFromRecipe(recipe, fallbackName: name);
    final ingredients = _flattenIngredients([component]);
    return CookPlan(
      sessionKey: 'cook_session_recipe_$id',
      title: name,
      components: [component],
      ingredients: ingredients,
    );
  }

  /// Build an N-component plan from a meal + the parallel recipe
  /// fetches. `recipes[i]` corresponds to `meal.components[i]`; pass
  /// `null` when that component's fetch failed (cmm-2 partial-load
  /// case) and the plan flags it as `loadFailed`.
  factory CookPlan.fromMeal(Meal meal, List<Map<String, dynamic>?> recipes) {
    if (meal.components.length != recipes.length) {
      throw ArgumentError(
        'recipes.length (${recipes.length}) must equal '
        'meal.components.length (${meal.components.length})',
      );
    }
    final components = <CookComponent>[];
    for (var i = 0; i < meal.components.length; i++) {
      final mc = meal.components[i];
      final raw = recipes[i];
      final compName = mc.displayName.isNotEmpty
          ? mc.displayName
          : 'Component ${i + 1}';
      if (raw == null) {
        // Reserve a single placeholder step so the user can still
        // navigate INTO the failed component and see the retry UI
        // (cmm-2 AC7). Without this, totalSteps would skip over the
        // failed component entirely and the placeholder would be
        // unreachable. The instruction sentinel is used by the cook
        // screen to swap in `ComponentLoadPlaceholder` when rendering
        // this slot.
        components.add(CookComponent(
          recipeId: mc.recipeId,
          name: compName,
          steps: const [
            CookStep(instruction: _kLoadFailedSentinel, timers: []),
          ],
          ingredients: const [],
          loadFailed: true,
        ));
      } else {
        components.add(_componentFromRecipe(raw, fallbackName: compName));
      }
    }
    final ingredients = _flattenIngredients(components);
    return CookPlan(
      sessionKey: 'cook_session_meal_${meal.id}',
      title: meal.name,
      components: components,
      ingredients: ingredients,
    );
  }

  static CookComponent _componentFromRecipe(
    Map<String, dynamic> recipe, {
    required String fallbackName,
  }) {
    final rawSteps = List<dynamic>.from(recipe['steps'] as List? ?? const []);
    rawSteps.sort((a, b) {
      final aN = a is Map ? (a['step_number'] as int? ?? 0) : 0;
      final bN = b is Map ? (b['step_number'] as int? ?? 0) : 0;
      return aN.compareTo(bN);
    });
    final steps = rawSteps
        .map(CookStep.fromJson)
        .where((s) => s.instruction.isNotEmpty)
        .toList();
    final ingredients =
        List<dynamic>.from(recipe['ingredients'] as List? ?? const []);
    final name = recipe['name'] as String? ?? fallbackName;
    final id = recipe['id'] as String? ?? '';
    return CookComponent(
      recipeId: id,
      name: name,
      steps: steps,
      ingredients: ingredients,
    );
  }

  static List<CombinedIngredient> _flattenIngredients(
    List<CookComponent> components,
  ) {
    final out = <CombinedIngredient>[];
    for (var ci = 0; ci < components.length; ci++) {
      final c = components[ci];
      for (var oi = 0; oi < c.ingredients.length; oi++) {
        out.add(CombinedIngredient(
          sourceComponentIndex: ci,
          sourceComponentName: c.name,
          raw: c.ingredients[oi],
          orderIndex: oi,
        ));
      }
    }
    return out;
  }
}

/// One row in the post-cook feedback sheet. Recipe-cook passes a
/// list of length 1; meal-cook passes one per started component.
class ComponentRatable {
  final String recipeId;
  final String displayName;

  const ComponentRatable({required this.recipeId, required this.displayName});
}

/// Sentinel instruction string written into the placeholder step of a
/// `loadFailed` component. The cook screen detects this exact value
/// and renders [ComponentLoadPlaceholder] instead of regular step text.
const String _kLoadFailedSentinel = '__cook_plan_load_failed__';

bool isLoadFailedStep(CookStep step) =>
    step.instruction == _kLoadFailedSentinel;
