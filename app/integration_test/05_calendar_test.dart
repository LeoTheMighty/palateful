/// E2E: Calendar screen loads and shows the current week.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:palateful/main.dart' as app;

import 'helpers.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('calendar loads and displays current week', (tester) async {
    app.main();
    await waitFor(tester, find.text('Home'),
        timeout: const Duration(seconds: 20));

    // Navigate to Calendar tab
    await tapText(tester, 'Calendar');
    await waitFor(tester, find.text('Mon'),
        timeout: const Duration(seconds: 10));

    // Day labels should be visible — confirms the week view rendered
    assertVisible('Mon');
    assertVisible('Sun');

    // No error state
    assertNotVisible('Failed');
  });
}
