/// E2E: Create a shopping list, add items, check one off.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:palateful/main.dart' as app;

import 'helpers.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('create shopping list, add and check off items', (tester) async {
    app.main();
    await waitFor(tester, find.text('Home'),
        timeout: const Duration(seconds: 20));

    // Navigate to Cart tab
    await tapText(tester, 'Cart');
    await waitFor(tester, find.text('Cart'));

    // Create a new shopping list via FAB ("New List" extended button)
    await tapFab(tester);
    await waitFor(tester, find.text('New Shopping List'));

    // Enter list name (hint: "List name (e.g. Weekly Groceries)")
    await enterIn(
        tester, 'List name (e.g. Weekly Groceries)', 'E2E Groceries');

    // Confirm creation
    await tapText(tester, 'Create');

    // Should navigate to the shopping list screen
    await waitFor(tester, find.text('E2E Groceries'),
        timeout: const Duration(seconds: 10));
    await waitFor(tester, find.text('Add item...'));

    // Add first item
    await enterIn(tester, 'Add item...', 'Milk');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await waitFor(tester, find.text('Milk'),
        timeout: const Duration(seconds: 5));

    // Add second item
    await enterIn(tester, 'Add item...', 'Eggs');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await waitFor(tester, find.text('Eggs'),
        timeout: const Duration(seconds: 5));

    // Check off Milk — tapping the tile toggles checked state
    await tapText(tester, 'Milk');
    await waitFor(tester, find.text('COMPLETED'),
        timeout: const Duration(seconds: 5));
  });
}
