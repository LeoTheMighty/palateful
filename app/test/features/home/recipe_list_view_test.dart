import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/recipe_list_view.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  group('recipeListViewProvider', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('default-constructs to grid', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(container.read(recipeListViewProvider), RecipeListView.grid);
    });

    test('respects override at construction time', () {
      final container = ProviderContainer(
        overrides: [
          recipeListViewProvider.overrideWith(
            () => RecipeListViewNotifier(RecipeListView.table),
          ),
        ],
      );
      addTearDown(container.dispose);
      expect(container.read(recipeListViewProvider), RecipeListView.table);
    });

    test('toggle flips state and persists', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      await container.read(recipeListViewProvider.notifier).toggle();
      expect(container.read(recipeListViewProvider), RecipeListView.table);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('recipe_list_view'), 'table');

      await container.read(recipeListViewProvider.notifier).toggle();
      expect(container.read(recipeListViewProvider), RecipeListView.grid);
      expect(prefs.getString('recipe_list_view'), 'grid');
    });

    test('set is no-op when already in target state', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      var notifyCount = 0;
      container.listen<RecipeListView>(
        recipeListViewProvider,
        (_, _) => notifyCount++,
      );

      await container.read(recipeListViewProvider.notifier).set(
            RecipeListView.grid,
          );
      expect(notifyCount, 0);

      await container.read(recipeListViewProvider.notifier).set(
            RecipeListView.table,
          );
      expect(notifyCount, 1);
    });
  });

  group('loadSavedRecipeListView', () {
    test('returns grid when nothing persisted', () async {
      SharedPreferences.setMockInitialValues({});
      expect(await loadSavedRecipeListView(), RecipeListView.grid);
    });

    test('returns persisted table value', () async {
      SharedPreferences.setMockInitialValues({'recipe_list_view': 'table'});
      expect(await loadSavedRecipeListView(), RecipeListView.table);
    });

    test('falls back to grid on unrecognized value', () async {
      SharedPreferences.setMockInitialValues({'recipe_list_view': 'gibberish'});
      expect(await loadSavedRecipeListView(), RecipeListView.grid);
    });
  });
}
