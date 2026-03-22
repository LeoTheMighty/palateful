/// E2E: Search accepts input from the search screen and returns results or
/// empty state.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:palateful/main.dart' as app;

import 'helpers.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('search accepts input and does not crash', (tester) async {
    app.main();
    await waitFor(tester, find.text('Home'),
        timeout: const Duration(seconds: 20));

    // Home screen has a tappable search area (not a TextField) that navigates
    // to the SearchScreen.
    await tapText(tester, 'Search recipes...');
    await waitFor(tester, find.byType(TextField),
        timeout: const Duration(seconds: 5));

    // SearchScreen has an autofocused TextField with hint "Search recipes, people..."
    await enterIn(tester, 'Search recipes, people...', 'pasta');
    await settle(tester, timeout: const Duration(seconds: 5));

    // No crash / error
    assertNotVisible('Error');
  });
}
