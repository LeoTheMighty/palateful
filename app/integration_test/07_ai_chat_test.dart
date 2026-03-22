/// E2E: Open AI assistant and send a message (mocked response).
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:palateful/main.dart' as app;

import 'helpers.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('AI assistant opens and responds to a message', (tester) async {
    app.main();
    await waitFor(tester, find.text('Home'),
        timeout: const Duration(seconds: 20));

    // Open AI assistant from home screen (tooltip: "AI Assistant")
    await tapTooltip(tester, 'AI Assistant');
    await waitFor(tester, find.text('AI Assistant'),
        timeout: const Duration(seconds: 10));

    // Chat screen should show the title
    assertVisible('AI Assistant');

    // Type a message — the hint uses the Unicode ellipsis character (…)
    await enterIn(tester, 'Ask about your recipes\u2026', 'What recipes do I have?');

    // Tap the send button — it's an IconButton.filled with Icons.send
    final sendIcon = find.byIcon(Icons.send);
    if (sendIcon.evaluate().isNotEmpty) {
      await tapFinder(tester, sendIcon);
    } else {
      // Fallback: submit via keyboard action
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pump(const Duration(milliseconds: 300));
    }

    // Wait for the mocked AI response to appear
    await waitFor(tester, find.textContaining('E2E test assistant'),
        timeout: const Duration(seconds: 15));

    assertNotVisible('Error');
  });
}
