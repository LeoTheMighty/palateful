/// hmp-5 E2E: meals-home-promotion flow against a real backend.
///
/// Spins up the app, navigates home, enters selection mode, creates a
/// Meal via the home long-press flow, then verifies the Meal appears
/// in the grid. Guards against contract drift in `CreateMealSheet`'s
/// submission payload — widget tests alone can't catch that.
///
/// Skipped when the E2E backend isn't reachable (same posture as the
/// other 0X_*.dart tests in this directory).

library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:palateful/features/home/widgets/recipe_card.dart';
import 'package:palateful/features/meals/widgets/meal_tile.dart';
import 'package:palateful/main.dart' as app;

import 'helpers.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('home long-press → Create Meal → Meal appears in grid',
      (tester) async {
    app.main();

    // Wait for app shell + home.
    await waitFor(tester, find.text('Home'),
        timeout: const Duration(seconds: 20));
    await settle(tester);

    // Require at least 2 recipes on home to seed the Create Meal flow.
    // A fixture backend is responsible for pre-seeding these.
    if (find.byType(RecipeCard).evaluate().length < 2) {
      markTestSkipped(
        'Fewer than 2 recipes on home — fixture backend must pre-seed.',
      );
      return;
    }

    // Long-press the first recipe, tap the second.
    await tester.longPress(find.byType(RecipeCard).first);
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.byType(RecipeCard).at(1));
    await tester.pump(const Duration(milliseconds: 300));

    // Primary bulk-bar action should be "Create Meal" for 2R/0M.
    await waitFor(tester, find.text('Create Meal'),
        timeout: const Duration(seconds: 5));
    await tester.tap(find.text('Create Meal'));
    await settle(tester);

    // CreateMealSheet opens pre-filled. Type a unique name, hit Create.
    final uniqueName =
        'hmp5-e2e-${DateTime.now().millisecondsSinceEpoch}';
    final nameField = find.widgetWithText(TextField, 'Name');
    expect(nameField, findsOneWidget);
    await tester.enterText(nameField, uniqueName);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(find.widgetWithText(FilledButton, 'Create'));
    await settle(tester);

    // The new Meal should appear in the grid.
    await waitFor(tester, find.text(uniqueName),
        timeout: const Duration(seconds: 10));
    expect(find.byType(MealTile), findsWidgets);
    expect(find.text(uniqueName), findsOneWidget);
  });
}
