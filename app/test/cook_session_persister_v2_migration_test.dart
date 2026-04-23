// cmmrf-2 — v1 → v2 migration contract for CookSessionPersister.
//
// Covers the migration invariant: after `fromJson`, state is either
// fully v2-shape (case a) or transitional meal-v1 (case b) awaiting
// `unpackLegacyMeal(plan)`. No other combination is valid.

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/recipes/cook_mode/services/cook_session_persister.dart';
import 'package:palateful/features/recipes/cook_mode/shared/cook_plan.dart';

Map<String, dynamic> _v1RecipePayload({
  String targetId = 'r1',
  int currentStep = 3,
  List<int> completedSteps = const [0, 1, 2],
}) {
  return {
    'schema_version': 1,
    'target_kind': 'recipe',
    'target_id': targetId,
    'started_at_ms': 1700000000000,
    'cumulative_elapsed_ms': 120000,
    'current_step': currentStep,
    'completed_steps': completedSteps,
    'checked_ingredients': const ['0:0', '0:1'],
    'active_timers': const [
      {
        'label': 'simmer',
        'deadline_ms': 1700000600000,
        'total_duration_s': 600,
        'source': 'extracted',
      },
    ],
    'updated_at_ms': 1700000180000,
  };
}

Map<String, dynamic> _v1MealPayload({
  String targetId = 'meal-1',
  int currentStep = 9,
  List<int> completedSteps = const [0, 1, 2, 3, 4, 5, 6, 7, 8],
}) {
  return {
    'schema_version': 1,
    'target_kind': 'meal',
    'target_id': targetId,
    'started_at_ms': 1700000000000,
    'cumulative_elapsed_ms': 240000,
    'current_step': currentStep,
    'completed_steps': completedSteps,
    'checked_ingredients': const [],
    'active_timers': const [],
    'updated_at_ms': 1700000300000,
  };
}

CookPlan _threeComponentPlan() {
  final meal = Meal(
    id: 'meal-1',
    name: 'Salad Night',
    recipeBookId: 'b1',
    createdAt: DateTime(2026),
    updatedAt: DateTime(2026),
    components: const [
      MealComponent(recipeId: 'rD', name: 'Dressing', orderIndex: 0),
      MealComponent(recipeId: 'rS', name: 'Salad', orderIndex: 1),
      MealComponent(recipeId: 'rC', name: 'Chicken', orderIndex: 2),
    ],
  );
  return CookPlan.fromMeal(meal, [
    {
      'id': 'rD',
      'name': 'Dressing',
      'steps': List.generate(
        7,
        (i) => {'step_number': i + 1, 'instruction': 'D step ${i + 1}'},
      ),
      'ingredients': const [],
    },
    {
      'id': 'rS',
      'name': 'Salad',
      'steps': List.generate(
        4,
        (i) => {'step_number': i + 1, 'instruction': 'S step ${i + 1}'},
      ),
      'ingredients': const [],
    },
    {
      'id': 'rC',
      'name': 'Chicken',
      'steps': List.generate(
        9,
        (i) => {'step_number': i + 1, 'instruction': 'C step ${i + 1}'},
      ),
      'ingredients': const [],
    },
  ]);
}

void main() {
  group('v1 recipe payload — self-contained unpack (invariant a)', () {
    test('fromJson unpacks current_step into {targetId: n}', () {
      final state = CookSessionState.fromJson(
        _v1RecipePayload(targetId: 'r1', currentStep: 3),
      );
      expect(state, isNotNull);
      expect(state!.targetKind, CookTargetKind.recipe);
      expect(state.activeRecipeId, isNull);
      expect(state.currentStepByRecipe, {'r1': 3});
      expect(state.completedStepsByRecipe, {
        'r1': {0, 1, 2},
      });
      expect(state.legacyCurrentStep, isNull);
      expect(state.legacyCompletedSteps, isNull);
      expect(state.isTransitionalMealLegacy, isFalse);
    });

    test('empty completed_steps parses as an empty set', () {
      final state = CookSessionState.fromJson(
        _v1RecipePayload(currentStep: 0, completedSteps: const []),
      );
      expect(state, isNotNull);
      expect(state!.completedStepsByRecipe, {
        'r1': <int>{},
      });
    });

    test('SavedTimerState inherits null sourceRecipeId from v1 wire', () {
      final state = CookSessionState.fromJson(_v1RecipePayload());
      expect(state!.activeTimers, hasLength(1));
      expect(state.activeTimers.first.sourceRecipeId, isNull);
    });
  });

  group('v1 meal payload — transitional shape (invariant b)', () {
    test('fromJson returns transitional state with legacy fields set', () {
      final state = CookSessionState.fromJson(_v1MealPayload());
      expect(state, isNotNull);
      expect(state!.targetKind, CookTargetKind.meal);
      expect(state.activeRecipeId, isNull);
      expect(state.currentStepByRecipe, isEmpty);
      expect(state.completedStepsByRecipe, isEmpty);
      expect(state.legacyCurrentStep, 9);
      expect(state.legacyCompletedSteps, {0, 1, 2, 3, 4, 5, 6, 7, 8});
      expect(state.isTransitionalMealLegacy, isTrue);
    });

    test('unpackLegacyMeal distributes flat indices via plan.stepAt', () {
      final state = CookSessionState.fromJson(_v1MealPayload())!;
      final plan = _threeComponentPlan();
      final unpacked = state.unpackLegacyMeal(plan);
      // flat 9 in a [7, 4, 9] plan = Salad local 2. activeRecipeId = rS.
      expect(unpacked.activeRecipeId, 'rS');
      expect(unpacked.currentStepByRecipe, {
        'rD': 0,
        'rS': 2,
        'rC': 0,
      });
      // Completed flat indices 0..8 = all 7 Dressing steps + Salad
      // local 0, 1.
      expect(unpacked.completedStepsByRecipe, {
        'rD': {0, 1, 2, 3, 4, 5, 6},
        'rS': {0, 1},
        'rC': <int>{},
      });
      expect(unpacked.legacyCurrentStep, isNull);
      expect(unpacked.legacyCompletedSteps, isNull);
      expect(unpacked.isTransitionalMealLegacy, isFalse);
    });

    test('unpackLegacyMeal is a no-op on already-unpacked state', () {
      final state = CookSessionState.fromJson(_v1MealPayload())!;
      final plan = _threeComponentPlan();
      final unpacked = state.unpackLegacyMeal(plan);
      final twice = unpacked.unpackLegacyMeal(plan);
      expect(twice.currentStepByRecipe, unpacked.currentStepByRecipe);
      expect(twice.completedStepsByRecipe, unpacked.completedStepsByRecipe);
    });

    test('flat index clamp: drift beyond plan.totalSteps lands on last', () {
      final state = CookSessionState.fromJson(
        _v1MealPayload(currentStep: 500),
      )!;
      final plan = _threeComponentPlan();
      final unpacked = state.unpackLegacyMeal(plan);
      // Total = 20; last flat index = 19 (Chicken local 8).
      expect(unpacked.activeRecipeId, 'rC');
      expect(unpacked.currentStepByRecipe['rC'], 8);
    });
  });

  group('v2 native payload — round-trip (invariant a)', () {
    test('toJson + fromJson is lossless', () {
      final original = CookSessionState(
        targetKind: CookTargetKind.meal,
        targetId: 'meal-1',
        startedAtMs: 1700000000000,
        cumulativeElapsedMs: 240000,
        activeRecipeId: 'rS',
        currentStepByRecipe: const {'rD': 6, 'rS': 2, 'rC': 0},
        completedStepsByRecipe: {
          'rD': {0, 1, 2, 3, 4, 5, 6},
          'rS': {0, 1},
          'rC': <int>{},
        },
        checkedIngredients: const ['0:0', '1:0'],
        activeTimers: const [
          SavedTimerState(
            label: 'rest',
            deadlineMs: 1700000600000,
            totalDurationSeconds: 300,
            source: 'manual',
            sourceRecipeId: 'rD',
          ),
        ],
        updatedAtMs: 1700000300000,
      );
      final decoded =
          CookSessionState.fromJson(jsonDecode(jsonEncode(original.toJson())));
      expect(decoded, isNotNull);
      expect(decoded!.activeRecipeId, 'rS');
      expect(decoded.currentStepByRecipe, original.currentStepByRecipe);
      expect(decoded.completedStepsByRecipe, original.completedStepsByRecipe);
      expect(decoded.activeTimers, original.activeTimers);
      expect(decoded.activeTimers.first.sourceRecipeId, 'rD');
    });

    test('toJson always writes schema_version=2 (never writes v1 again)', () {
      final state = CookSessionState(
        targetKind: CookTargetKind.recipe,
        targetId: 'r1',
        startedAtMs: 0,
        cumulativeElapsedMs: 0,
        currentStepByRecipe: const {'r1': 0},
        completedStepsByRecipe: const {'r1': <int>{}},
        checkedIngredients: const [],
        activeTimers: const [],
        updatedAtMs: 0,
      );
      final json = state.toJson();
      expect(json['schema_version'], 2);
      expect(json.containsKey('current_step'), isFalse);
      expect(json.containsKey('completed_steps'), isFalse);
    });

    test('toJson skips legacy fields even when present on state', () {
      // Build a transitional state manually and serialize — legacy
      // fields must NOT round-trip to JSON.
      final transitional = CookSessionState(
        targetKind: CookTargetKind.meal,
        targetId: 'meal-1',
        startedAtMs: 0,
        cumulativeElapsedMs: 0,
        currentStepByRecipe: const {},
        completedStepsByRecipe: const {},
        checkedIngredients: const [],
        activeTimers: const [],
        updatedAtMs: 0,
        legacyCurrentStep: 5,
        legacyCompletedSteps: const {0, 1, 2},
      );
      final json = transitional.toJson();
      expect(json['schema_version'], 2);
      expect(json.containsKey('current_step'), isFalse);
      expect(json.containsKey('completed_steps'), isFalse);
    });
  });

  group('malformed / unparseable inputs', () {
    test('fromJson returns null when schema_version absent', () {
      final broken = _v1RecipePayload()..remove('schema_version');
      expect(CookSessionState.fromJson(broken), isNull);
    });

    test('fromJson returns null on unknown schema_version', () {
      final stale = {..._v1RecipePayload(), 'schema_version': 999};
      expect(CookSessionState.fromJson(stale), isNull);
    });

    test('fromJson returns null when v1 recipe payload lacks current_step',
        () {
      final broken = _v1RecipePayload()..remove('current_step');
      expect(CookSessionState.fromJson(broken), isNull);
    });
  });
}
