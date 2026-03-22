/// E2E: Create a recipe book.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:palateful/main.dart' as app;

import 'helpers.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('create a new recipe book and verify it appears', (tester) async {
    app.main();
    await waitFor(tester, find.text('Home'),
        timeout: const Duration(seconds: 20));

    // Navigate to Books tab
    await tapText(tester, 'Books');
    await waitFor(tester, find.text('Recipe Books'));

    // Open create dialog via FAB
    await tapFab(tester);
    await waitFor(tester, find.text('New Recipe Book'));

    // Enter book name (hint: "My Recipe Book")
    await enterIn(tester, 'My Recipe Book', 'E2E Test Book');

    // Confirm creation
    await tapText(tester, 'Create');

    // Verify book appears in the list
    await waitFor(tester, find.textContaining('E2E Test Book'));
  });
}
