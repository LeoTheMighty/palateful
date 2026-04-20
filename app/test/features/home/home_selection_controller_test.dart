import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/home_selection_controller.dart';

void main() {
  group('HomeSelectionState.shape', () {
    const base = HomeSelectionState.empty;

    test('empty ↦ SelectionShape.empty', () {
      expect(base.shape, SelectionShape.empty);
    });

    test('1 recipe ↦ singleRecipe', () {
      final s = base.copyWith(
        isActive: true,
        selectedRecipeIds: {'r1'},
      );
      expect(s.shape, SelectionShape.singleRecipe);
    });

    test('2+ recipes ↦ multipleRecipesOnly', () {
      final s = base.copyWith(
        isActive: true,
        selectedRecipeIds: {'r1', 'r2'},
      );
      expect(s.shape, SelectionShape.multipleRecipesOnly);
    });

    test('1 meal only ↦ singleMealNoRecipes', () {
      final s = base.copyWith(isActive: true, selectedMealIds: {'m1'});
      expect(s.shape, SelectionShape.singleMealNoRecipes);
    });

    test('1 meal + 1+ recipes ↦ singleMealWithRecipes', () {
      final s = base.copyWith(
        isActive: true,
        selectedMealIds: {'m1'},
        selectedRecipeIds: {'r1'},
      );
      expect(s.shape, SelectionShape.singleMealWithRecipes);
    });

    test('2+ meals ↦ multipleMeals', () {
      final s = base.copyWith(
        isActive: true,
        selectedMealIds: {'m1', 'm2'},
      );
      expect(s.shape, SelectionShape.multipleMeals);
    });
  });

  group('resolvePrimaryAction', () {
    test('empty ↦ EmptyAction', () {
      expect(resolvePrimaryAction(SelectionShape.empty),
          isA<EmptyAction>());
    });

    test('singleRecipe ↦ DisabledAction with teaching tooltip', () {
      final action = resolvePrimaryAction(SelectionShape.singleRecipe);
      expect(action, isA<DisabledAction>());
      expect((action as DisabledAction).reason,
          contains('Select 1 more recipe'));
    });

    test('multipleRecipesOnly ↦ CreateMealAction', () {
      expect(
        resolvePrimaryAction(SelectionShape.multipleRecipesOnly),
        isA<CreateMealAction>(),
      );
    });

    test('singleMealNoRecipes ↦ DisabledAction', () {
      final action =
          resolvePrimaryAction(SelectionShape.singleMealNoRecipes);
      expect(action, isA<DisabledAction>());
      expect((action as DisabledAction).reason,
          contains('Select recipes to add'));
    });

    test('singleMealWithRecipes ↦ AddToMealAction', () {
      expect(
        resolvePrimaryAction(SelectionShape.singleMealWithRecipes),
        isA<AddToMealAction>(),
      );
    });

    test('multipleMeals ↦ DisabledAction', () {
      final action =
          resolvePrimaryAction(SelectionShape.multipleMeals);
      expect(action, isA<DisabledAction>());
      expect((action as DisabledAction).reason,
          contains('only one Meal'));
    });
  });

  group('HomeSelectionController transitions', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer();
      addTearDown(container.dispose);
    });

    test('enterWith(recipe) seeds selection and flips isActive', () {
      final c = container.read(homeSelectionProvider.notifier);
      c.enterWith(kind: 'recipe', id: 'r1');
      final s = container.read(homeSelectionProvider);
      expect(s.isActive, true);
      expect(s.selectedRecipeIds, {'r1'});
    });

    test('enterWith(meal) goes into meals set', () {
      final c = container.read(homeSelectionProvider.notifier);
      c.enterWith(kind: 'meal', id: 'm1');
      final s = container.read(homeSelectionProvider);
      expect(s.selectedMealIds, {'m1'});
    });

    test('toggleRecipe adds then removes and exits when empty', () {
      final c = container.read(homeSelectionProvider.notifier);
      c.enterWith(kind: 'recipe', id: 'r1');
      c.toggleRecipe('r1');
      expect(container.read(homeSelectionProvider).isActive, false);
    });

    test('exit clears both sets', () {
      final c = container.read(homeSelectionProvider.notifier);
      c.enterWith(kind: 'recipe', id: 'r1');
      c.toggleMeal('m1');
      c.exit();
      final s = container.read(homeSelectionProvider);
      expect(s.isActive, false);
      expect(s.totalSelected, 0);
    });

    test('reconcile drops vanished ids; returns true when all gone', () {
      final c = container.read(homeSelectionProvider.notifier);
      c.enterWith(kind: 'recipe', id: 'r1');
      c.toggleMeal('m1');
      final emptied = c.reconcile(
        knownRecipeIds: {},
        knownMealIds: {},
      );
      expect(emptied, true);
      expect(container.read(homeSelectionProvider).isActive, false);
    });

    test('reconcile keeps still-present ids', () {
      final c = container.read(homeSelectionProvider.notifier);
      c.enterWith(kind: 'recipe', id: 'r1');
      c.toggleRecipe('r2');
      final emptied = c.reconcile(
        knownRecipeIds: {'r1'},
        knownMealIds: {},
      );
      expect(emptied, false);
      expect(container.read(homeSelectionProvider).selectedRecipeIds,
          {'r1'});
    });
  });
}
