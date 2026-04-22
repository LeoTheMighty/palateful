import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/features/recipes/cook_mode/cook_mode_screen.dart';
import 'package:palateful/features/recipes/cook_mode/services/cook_session_persister.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'helpers/cook_mode_test_harness.dart';

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    await setUpCookModeHarness();
  });

  tearDown(() {
    tearDownCookModeHarness();
  });

  Future<void> _pumpCookMode(
    WidgetTester tester, {
    String recipeId = 'r1',
  }) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light(),
      home: CookModeScreen(recipeId: recipeId),
    ));
    // Allow the async _initCookSession + _loadRecipe chain to resolve.
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
  }

  group('cmr-2 — persistence writes', () {
    testWidgets('advancing a step + checking ingredient + starting timer '
        'produces a persisted snapshot on AppLifecycleState.paused',
        (tester) async {
      await _pumpCookMode(tester);
      // Recipe should have rendered with 3 steps.
      expect(find.text('Do step 1'), findsOneWidget);

      // Advance to step 2 (index 1) via Next button.
      await tester.tap(find.text('Next'));
      await tester.pump();
      // Advance to step 3 (index 2).
      await tester.tap(find.text('Next'));
      await tester.pump();

      // Check the first ingredient. The ingredient chip has a pre-existing
      // ~7px overflow when the check icon appears; drain it so it doesn't
      // fail the test.
      await tester.tap(find.text('Ingredient 1'));
      await tester.pump();
      tester.takeException();

      // Push the app to paused — flushes the debounce window.
      final handler =
          WidgetsBinding.instance.handleAppLifecycleStateChanged;
      handler(AppLifecycleState.paused);
      // Let the async flushNow + save complete.
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      final prefs = await SharedPreferences.getInstance();
      final key = CookSessionKey.forRecipe('r1');
      final raw = prefs.getString(key);
      expect(raw, isNotNull, reason: 'state should persist on paused');
      final decoded = jsonDecode(raw!) as Map<String, dynamic>;
      expect(decoded['current_step'], 2);
      expect(decoded['checked_ingredients'], contains('0'));
      expect(decoded['target_kind'], 'recipe');
      expect(decoded['target_id'], 'r1');
    });

    testWidgets('no prior state mounts fresh at step 0 (regression guard)',
        (tester) async {
      await _pumpCookMode(tester);
      expect(find.text('Do step 1'), findsOneWidget);
      // No gate sheet visible (cmr-3 introduces it).
      expect(find.text('Resume'), findsNothing);
      expect(find.text('Start Over'), findsNothing);
    });
  });
}
