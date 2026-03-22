/// E2E: App launches in E2E mode and shows the main navigation.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:palateful/main.dart' as app;

import 'helpers.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('app launches and shows bottom navigation', (tester) async {
    app.main();

    // Wait for the bottom nav to appear — proves auth bypass and getMe() worked
    await waitFor(tester, find.text('Home'),
        timeout: const Duration(seconds: 20));

    // All five navigation tabs should be visible
    assertVisible('Home');
    assertVisible('Books');
    assertVisible('Cart');
    assertVisible('Calendar');
    assertVisible('Profile');
  });
}
