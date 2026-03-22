/// E2E: Create a recipe inside the E2E test book via the wizard.
/// Prerequisite: run 02_recipe_books_test first to create "E2E Test Book".
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:palateful/main.dart' as app;

import 'helpers.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('create a recipe via the wizard', (tester) async {
    app.main();
    await waitFor(tester, find.text('Home'),
        timeout: const Duration(seconds: 20));

    // Navigate to Books → E2E Test Book
    await tapText(tester, 'Books');
    await waitFor(tester, find.text('Recipe Books'));
    await tapText(tester, 'E2E Test Book');
    await waitFor(tester, find.text('E2E Test Book'),
        timeout: const Duration(seconds: 10));

    // Tap FAB — goes directly to RecipeWizardScreen (no bottom sheet)
    await tapFab(tester);
    await waitFor(tester, find.text('New Recipe'),
        timeout: const Duration(seconds: 10));

    // Step 1: Name & Photo — enter recipe name
    await waitFor(tester, find.text('Recipe Name'));
    await enterIn(tester, 'Recipe Name', 'E2E Pasta Test');

    // Tap "Next" to advance to Step 2 (Ingredients)
    await tapText(tester, 'Next');
    await waitFor(tester, find.text('Add ingredients'),
        timeout: const Duration(seconds: 5));

    // Step 2: skip ingredients — tap "Next"
    await tapText(tester, 'Next');
    await waitFor(tester, find.text('How do you make it?'),
        timeout: const Duration(seconds: 5));

    // Step 3: skip instructions — tap "Next"
    await tapText(tester, 'Next');
    await waitFor(tester, find.text('Final details'),
        timeout: const Duration(seconds: 5));

    // Step 4: tap "Save Recipe"
    await tapText(tester, 'Save Recipe');

    // Should navigate back to recipe book detail with new recipe
    await waitFor(tester, find.textContaining('E2E Pasta Test'),
        timeout: const Duration(seconds: 10));
  });
}
