// cmm-1 AC6 — unit tests for the CookPlan abstraction.
//
// Covers:
//   * 1-component plan factory + boundary (recipe-cook compatibility)
//   * 3-component plan ([2, 4, 3] / [7, 4, 9] step layouts) flat ↔
//     (componentIndex, stepIndex) round-trip
//   * out-of-range stepAt / flatIndexFor throw ArgumentError
//   * componentBoundaries shape ([0] for 1-comp; [0, 2, 6] for [2,4,3])
//   * loadFailed flag preserved through CookPlan.fromMeal
//   * CombinedIngredient.stableKey shape

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/recipes/cook_mode/shared/cook_plan.dart';

Map<String, dynamic> _recipe({
  required String id,
  required String name,
  required int stepCount,
  int ingredientCount = 0,
}) {
  return <String, dynamic>{
    'id': id,
    'name': name,
    'steps': [
      for (var i = 0; i < stepCount; i++)
        {'step_number': i + 1, 'instruction': 'Step ${i + 1} of $name'},
    ],
    'ingredients': [
      for (var i = 0; i < ingredientCount; i++)
        {
          'ingredient': {'canonical_name': 'ing_${name}_$i'},
          'quantity_display': '1',
          'unit_display': 'cup',
        },
    ],
  };
}

Meal _meal({required String id, required List<MealComponent> components}) =>
    Meal(
      id: id,
      name: 'Meal $id',
      recipeBookId: 'b1',
      createdAt: DateTime(2026, 1, 1),
      updatedAt: DateTime(2026, 1, 1),
      components: components,
    );

MealComponent _comp(String recipeId, String name, int order) => MealComponent(
      recipeId: recipeId,
      name: name,
      orderIndex: order,
    );

void main() {
  group('CookPlan.fromRecipe (1-component)', () {
    test('1-component plan: (0, 0) ↔ flat 0', () {
      final plan = CookPlan.fromRecipe(
        _recipe(id: 'r1', name: 'Solo', stepCount: 5),
      );
      expect(plan.totalSteps, 5);
      expect(plan.components, hasLength(1));
      expect(plan.componentBoundaries, [0]);
      final at0 = plan.stepAt(0);
      expect(at0.componentIndex, 0);
      expect(at0.stepIndex, 0);
      expect(plan.flatIndexFor(0, 0), 0);
    });

    test('1-component plan: last step ↔ totalSteps - 1', () {
      final plan = CookPlan.fromRecipe(
        _recipe(id: 'r1', name: 'Solo', stepCount: 5),
      );
      final last = plan.stepAt(plan.totalSteps - 1);
      expect(last.componentIndex, 0);
      expect(last.stepIndex, 4);
      expect(plan.flatIndexFor(0, 4), 4);
    });

    test('sessionKey uses recipe prefix', () {
      final plan = CookPlan.fromRecipe(
        _recipe(id: 'r1', name: 'Solo', stepCount: 1),
      );
      expect(plan.sessionKey, 'cook_session_recipe_r1');
    });

    test('out-of-range flatIndex throws ArgumentError', () {
      final plan = CookPlan.fromRecipe(
        _recipe(id: 'r1', name: 'Solo', stepCount: 3),
      );
      expect(() => plan.stepAt(-1), throwsArgumentError);
      expect(() => plan.stepAt(3), throwsArgumentError);
      expect(() => plan.flatIndexFor(0, -1), throwsArgumentError);
      expect(() => plan.flatIndexFor(0, 3), throwsArgumentError);
      expect(() => plan.flatIndexFor(1, 0), throwsArgumentError);
    });
  });

  group('CookPlan.fromMeal (multi-component)', () {
    test('3-component [2, 4, 3] plan: round-trip + boundaries', () {
      final meal = _meal(id: 'm1', components: [
        _comp('rA', 'A', 0),
        _comp('rB', 'B', 1),
        _comp('rC', 'C', 2),
      ]);
      final plan = CookPlan.fromMeal(meal, [
        _recipe(id: 'rA', name: 'A', stepCount: 2),
        _recipe(id: 'rB', name: 'B', stepCount: 4),
        _recipe(id: 'rC', name: 'C', stepCount: 3),
      ]);
      expect(plan.totalSteps, 9);
      expect(plan.componentBoundaries, [0, 2, 6]);
      // (1, 2) → flat 4 — second step of 4-step middle component.
      expect(plan.flatIndexFor(1, 2), 4);
      final at4 = plan.stepAt(4);
      expect(at4.componentIndex, 1);
      expect(at4.stepIndex, 2);
      // Last flat index → (2, 2)
      final last = plan.stepAt(8);
      expect(last.componentIndex, 2);
      expect(last.stepIndex, 2);
    });

    test('[7, 4, 9] plan: boundaries match epic example [0, 7, 11]', () {
      final meal = _meal(id: 'm1', components: [
        _comp('r1', 'Dressing', 0),
        _comp('r2', 'Salad', 1),
        _comp('r3', 'Grilled Chicken', 2),
      ]);
      final plan = CookPlan.fromMeal(meal, [
        _recipe(id: 'r1', name: 'Dressing', stepCount: 7),
        _recipe(id: 'r2', name: 'Salad', stepCount: 4),
        _recipe(id: 'r3', name: 'Grilled Chicken', stepCount: 9),
      ]);
      expect(plan.totalSteps, 20);
      expect(plan.componentBoundaries, [0, 7, 11]);
    });

    test(
        'loadFailed: null recipe → component flagged + reserved placeholder step',
        () {
      final meal = _meal(id: 'm1', components: [
        _comp('r1', 'Dressing', 0),
        _comp('r2', 'Salad', 1),
        _comp('r3', 'Grilled Chicken', 2),
      ]);
      final plan = CookPlan.fromMeal(meal, [
        _recipe(id: 'r1', name: 'Dressing', stepCount: 7),
        _recipe(id: 'r2', name: 'Salad', stepCount: 4),
        null, // simulated fetch failure for component 2
      ]);
      expect(plan.components[0].loadFailed, isFalse);
      expect(plan.components[1].loadFailed, isFalse);
      expect(plan.components[2].loadFailed, isTrue);
      // Failed components reserve exactly 1 placeholder slot so the
      // user can still navigate INTO the failed range and see Retry.
      expect(plan.components[2].steps, hasLength(1));
      expect(isLoadFailedStep(plan.components[2].steps.first), isTrue);
      expect(plan.hasAnyLoadFailures, isTrue);
      // totalSteps + boundaries reflect the placeholder slot.
      expect(plan.totalSteps, 12);
      expect(plan.componentBoundaries, [0, 7, 11]);
    });

    test('mismatched recipes.length throws', () {
      final meal = _meal(id: 'm1', components: [_comp('r1', 'A', 0)]);
      expect(
        () => CookPlan.fromMeal(meal, []),
        throwsArgumentError,
      );
    });

    test('sessionKey uses meal prefix', () {
      final meal = _meal(id: 'm-xyz', components: [_comp('r1', 'A', 0)]);
      final plan = CookPlan.fromMeal(
        meal,
        [_recipe(id: 'r1', name: 'A', stepCount: 1)],
      );
      expect(plan.sessionKey, 'cook_session_meal_m-xyz');
    });
  });

  group('CombinedIngredient', () {
    test('stableKey shape is "<componentIndex>:<orderIndex>"', () {
      final meal = _meal(id: 'm1', components: [
        _comp('r1', 'A', 0),
        _comp('r2', 'B', 1),
      ]);
      final plan = CookPlan.fromMeal(meal, [
        _recipe(id: 'r1', name: 'A', stepCount: 1, ingredientCount: 2),
        _recipe(id: 'r2', name: 'B', stepCount: 1, ingredientCount: 3),
      ]);
      // 2 + 3 = 5 ingredients flat.
      expect(plan.ingredients, hasLength(5));
      // First ingredient of A → "0:0"; last ingredient of B → "1:2".
      expect(plan.ingredients.first.stableKey, '0:0');
      expect(plan.ingredients.last.stableKey, '1:2');
      // All ingredients are tagged with their source name.
      expect(plan.ingredients[0].sourceComponentName, 'A');
      expect(plan.ingredients[3].sourceComponentName, 'B');
    });

    test('1-component plan: stableKey is always "0:<oi>"', () {
      final plan = CookPlan.fromRecipe(
        _recipe(id: 'r1', name: 'Solo', stepCount: 1, ingredientCount: 4),
      );
      expect(plan.ingredients.map((i) => i.stableKey).toList(),
          ['0:0', '0:1', '0:2', '0:3']);
    });
  });

  group('regression', () {
    test('recipe with empty/missing instruction is filtered', () {
      final raw = <String, dynamic>{
        'id': 'r1',
        'name': 'X',
        'steps': [
          {'step_number': 1, 'instruction': 'real step'},
          {'step_number': 2, 'instruction': ''},
          {'step_number': 3, 'instruction': 'another'},
        ],
      };
      final plan = CookPlan.fromRecipe(raw);
      expect(plan.totalSteps, 2);
      expect(plan.components.first.steps[0].instruction, 'real step');
      expect(plan.components.first.steps[1].instruction, 'another');
    });

    test('recipe steps sort by step_number (out of order in payload)', () {
      final raw = <String, dynamic>{
        'id': 'r1',
        'name': 'X',
        'steps': [
          {'step_number': 3, 'instruction': 'third'},
          {'step_number': 1, 'instruction': 'first'},
          {'step_number': 2, 'instruction': 'second'},
        ],
      };
      final plan = CookPlan.fromRecipe(raw);
      expect(
        plan.components.first.steps.map((s) => s.instruction).toList(),
        ['first', 'second', 'third'],
      );
    });
  });
}
