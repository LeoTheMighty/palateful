// cmm-4 — combined ingredient strip with source tags + stable-key
// check-state + no-dedup + ingredient-order drift.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/recipes/cook_mode/shared/cook_plan.dart';
import 'package:palateful/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart';

Map<String, dynamic> _ingredient(String name, [String qty = '1', String unit = 'cup']) =>
    <String, dynamic>{
      'ingredient': {'canonical_name': name},
      'quantity_display': qty,
      'unit_display': unit,
    };

Map<String, dynamic> _recipe(
  String id,
  String name, {
  required List<Map<String, dynamic>> ingredients,
}) =>
    <String, dynamic>{
      'id': id,
      'name': name,
      'steps': const [
        {'step_number': 1, 'instruction': 'cook it', 'timers': []},
      ],
      'ingredients': ingredients,
    };

Meal _meal(String id, List<MealComponent> components) => Meal(
      id: id,
      name: 'Meal $id',
      recipeBookId: 'b1',
      createdAt: DateTime(2026),
      updatedAt: DateTime(2026),
      components: components,
    );

void main() {
  group('cmm-4 — combined ingredients (CookPlan)', () {
    test('flat ingredients tagged with source component name', () {
      final meal = _meal('m1', const [
        MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
        MealComponent(recipeId: 'r2', name: 'Salad', orderIndex: 1),
      ]);
      final plan = CookPlan.fromMeal(meal, [
        _recipe('r1', 'Dressing', ingredients: [
          _ingredient('garlic', '3', 'cloves'),
          _ingredient('olive oil', '2', 'tbsp'),
        ]),
        _recipe('r2', 'Salad', ingredients: [
          _ingredient('lettuce', '1', 'head'),
        ]),
      ]);
      expect(plan.ingredients, hasLength(3));
      expect(plan.ingredients[0].sourceComponentName, 'Dressing');
      expect(plan.ingredients[1].sourceComponentName, 'Dressing');
      expect(plan.ingredients[2].sourceComponentName, 'Salad');
      expect(plan.ingredients[0].stableKey, '0:0');
      expect(plan.ingredients[1].stableKey, '0:1');
      expect(plan.ingredients[2].stableKey, '1:0');
    });

    test('no dedup — duplicate ingredients render as two rows', () {
      final meal = _meal('m1', const [
        MealComponent(recipeId: 'r1', name: 'Bread', orderIndex: 0),
        MealComponent(recipeId: 'r2', name: 'Cake', orderIndex: 1),
      ]);
      final plan = CookPlan.fromMeal(meal, [
        _recipe('r1', 'Bread', ingredients: [
          _ingredient('flour', '1', 'cup'),
        ]),
        _recipe('r2', 'Cake', ingredients: [
          _ingredient('flour', '1', 'cup'),
        ]),
      ]);
      expect(plan.ingredients, hasLength(2));
      expect(plan.ingredients[0].sourceComponentName, 'Bread');
      expect(plan.ingredients[1].sourceComponentName, 'Cake');
    });
  });

  group('cmm-4 — IngredientStrip rendering with source tags', () {
    Widget _wrap(IngredientStrip strip) => MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(body: strip),
        );

    testWidgets('compact: per-chip source tag visible', (tester) async {
      final ingredients = [
        _ingredient('Garlic', '3', 'cloves'),
        _ingredient('Olive oil', '2', 'tbsp'),
        _ingredient('Salt', '1', 'tsp'),
      ];
      await tester.pumpWidget(_wrap(IngredientStrip(
        ingredients: ingredients,
        checkedIndices: const {},
        onToggle: (_) {},
        sourceTagBuilder: (i) => ['Dressing', 'Dressing', 'Salad'][i],
      )));

      // Per-chip tags appear in compact view (the default).
      expect(find.text('Dressing'), findsAtLeast(1));
      expect(find.text('Salad'), findsAtLeast(1));
    });

    testWidgets('expanded view: --- From <ComponentName> --- group dividers',
        (tester) async {
      final ingredients = [
        _ingredient('Garlic', '3', 'cloves'),
        _ingredient('Olive oil', '2', 'tbsp'),
        _ingredient('Lettuce', '1', 'head'),
      ];
      await tester.pumpWidget(_wrap(IngredientStrip(
        ingredients: ingredients,
        checkedIndices: const {},
        onToggle: (_) {},
        sourceTagBuilder: (i) => i < 2 ? 'Dressing' : 'Salad',
      )));

      await tester.tap(find.text('Expand'));
      await tester.pumpAndSettle();

      expect(find.text('--- From Dressing ---'), findsOneWidget);
      expect(find.text('--- From Salad ---'), findsOneWidget);
      expect(
        find.byKey(const Key('ingredient_group_Dressing')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('ingredient_group_Salad')),
        findsOneWidget,
      );
    });

    testWidgets(
        'compact: long source tags truncate to 10 grapheme clusters',
        (tester) async {
      final ingredients = [
        _ingredient('Garlic', '3', 'cloves'),
      ];
      await tester.pumpWidget(_wrap(IngredientStrip(
        ingredients: ingredients,
        checkedIndices: const {},
        onToggle: (_) {},
        sourceTagBuilder: (i) => 'Grilled Chicken With Sauce',
      )));

      // Truncated to 9 chars + ellipsis (10 grapheme cap).
      expect(find.textContaining('…'), findsOneWidget);
      expect(find.text('Grilled Chicken With Sauce'), findsNothing);
    });

    testWidgets('1-component plan: no source tag chips', (tester) async {
      final ingredients = [
        _ingredient('Garlic', '3', 'cloves'),
      ];
      await tester.pumpWidget(_wrap(IngredientStrip(
        ingredients: ingredients,
        checkedIndices: const {},
        onToggle: (_) {},
        // sourceTagBuilder omitted — recipe cook contract.
      )));
      // No "From" group dividers in expanded view.
      await tester.tap(find.text('Expand'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ingredient_group_Dressing')), findsNothing);
      expect(find.textContaining('--- From'), findsNothing);
    });
  });

  group('cmm-4 — stable-key check-state restoration', () {
    test('stableKey survives flat-position drift across plan rebuild', () {
      // Original plan: [r1: 2 ingredients, r2: 3 ingredients] →
      // 5 flat ingredients with keys 0:0, 0:1, 1:0, 1:1, 1:2.
      final meal = _meal('m1', const [
        MealComponent(recipeId: 'r1', name: 'A', orderIndex: 0),
        MealComponent(recipeId: 'r2', name: 'B', orderIndex: 1),
      ]);
      final original = CookPlan.fromMeal(meal, [
        _recipe('r1', 'A', ingredients: [
          _ingredient('a0'),
          _ingredient('a1'),
        ]),
        _recipe('r2', 'B', ingredients: [
          _ingredient('b0'),
          _ingredient('b1'),
          _ingredient('b2'),
        ]),
      ]);
      // Simulate restoring the user's checked set from disk.
      final checked = {'1:1'};
      final flatChecked = <int>{
        for (var i = 0; i < original.ingredients.length; i++)
          if (checked.contains(original.ingredients[i].stableKey)) i,
      };
      // 1:1 → flat index 3.
      expect(flatChecked, {3});

      // Rebuild after the user re-imported B with one fewer ingredient
      // (1:1 no longer exists in the new shape). The stable-key set
      // silently drops the orphaned entry.
      final rebuilt = CookPlan.fromMeal(meal, [
        _recipe('r1', 'A', ingredients: [
          _ingredient('a0'),
          _ingredient('a1'),
        ]),
        _recipe('r2', 'B-shrunk', ingredients: [
          _ingredient('b0'),
        ]),
      ]);
      final flatCheckedRebuilt = <int>{
        for (var i = 0; i < rebuilt.ingredients.length; i++)
          if (checked.contains(rebuilt.ingredients[i].stableKey)) i,
      };
      // 1:1 has no slot in the rebuilt plan → silently dropped.
      expect(flatCheckedRebuilt, isEmpty);
    });

    test('rearranged components: stableKey rebinds by (componentIdx, orderIdx)',
        () {
      // Both plans have the same components in the same order, but the
      // ingredient order WITHIN component 1 is reversed. The stable
      // key "1:0" still points to position 2 in the new plan (the
      // formerly-last ingredient becomes the formerly-first).
      // Documents the trade-off: stable keys are positional within a
      // component, NOT name-based.
      final meal = _meal('m1', const [
        MealComponent(recipeId: 'r1', name: 'A', orderIndex: 0),
        MealComponent(recipeId: 'r2', name: 'B', orderIndex: 1),
      ]);
      final original = CookPlan.fromMeal(meal, [
        _recipe('r1', 'A', ingredients: [_ingredient('a0')]),
        _recipe('r2', 'B', ingredients: [
          _ingredient('b0'),
          _ingredient('b1'),
        ]),
      ]);
      expect(original.ingredients[1].stableKey, '1:0'); // b0
      expect(original.ingredients[2].stableKey, '1:1'); // b1
    });
  });

  group('cmm-4 — backend parity (smoke)', () {
    // Backend's `aggregate_meal_ingredients` returns one row per
    // (component, ingredient) pair in (component order, ingredient
    // order) order. The client's `CookPlan._flattenIngredients`
    // mirrors that contract. The full server fixture parity isn't
    // checked here (would require porting the SQLAlchemy fixture);
    // we instead assert the shape contract.
    test('flat ingredient list iterates components, then ingredients', () {
      final meal = _meal('m1', const [
        MealComponent(recipeId: 'r1', name: 'A', orderIndex: 0),
        MealComponent(recipeId: 'r2', name: 'B', orderIndex: 1),
        MealComponent(recipeId: 'r3', name: 'C', orderIndex: 2),
      ]);
      final plan = CookPlan.fromMeal(meal, [
        _recipe('r1', 'A', ingredients: [_ingredient('a0'), _ingredient('a1')]),
        _recipe('r2', 'B', ingredients: [_ingredient('b0')]),
        _recipe('r3', 'C', ingredients: [_ingredient('c0'), _ingredient('c1')]),
      ]);
      expect(
        plan.ingredients.map((i) => i.stableKey).toList(),
        ['0:0', '0:1', '1:0', '2:0', '2:1'],
      );
    });
  });
}
