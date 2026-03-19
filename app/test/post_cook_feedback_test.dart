import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:palateful/core/services/recipe_cache_service.dart';
import 'package:palateful/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart';

void main() {
  // ------------------------------------------------------------------
  // RecipeCacheService.logCook / getCookLogs unit tests
  // ------------------------------------------------------------------

  group('RecipeCacheService cook logs', () {
    late RecipeCacheService service;

    setUp(() {
      SharedPreferences.setMockInitialValues({});
      service = RecipeCacheService();
    });

    test('logCook stores entry under correct key', () async {
      await service.logCook('r1', 4, DateTime(2026, 3, 19));

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.containsKey('palateful_cook_logs_r1'), isTrue);
    });

    test('getCookLogs returns empty list for unknown recipe', () async {
      final logs = await service.getCookLogs('unknown-recipe');
      expect(logs, isEmpty);
    });

    test('getCookLogs returns log after logCook', () async {
      final now = DateTime(2026, 3, 19, 18, 30);
      await service.logCook('r42', 5, now);

      final logs = await service.getCookLogs('r42');
      expect(logs.length, equals(1));
      expect(logs[0]['rating'], equals(5));
      expect(logs[0]['recipe_id'], equals('r42'));
      expect(logs[0]['cooked_at'], equals(now.toIso8601String()));
    });

    test('logCook appends multiple entries in order', () async {
      await service.logCook('r1', 3, DateTime(2026, 1, 1));
      await service.logCook('r1', 5, DateTime(2026, 2, 1));

      final logs = await service.getCookLogs('r1');
      expect(logs.length, equals(2));
      expect(logs[0]['rating'], equals(3));
      expect(logs[1]['rating'], equals(5));
    });
  });

  // ------------------------------------------------------------------
  // PostCookFeedbackSheet widget tests
  // ------------------------------------------------------------------

  group('PostCookFeedbackSheet', () {
    late RecipeCacheService cache;

    setUp(() {
      SharedPreferences.setMockInitialValues({});
      cache = RecipeCacheService();
    });

    // Helper to build the sheet in test harness.
    // Uses isOffline: true so no real API calls are made.
    Widget buildSheet({required VoidCallback onComplete}) {
      return MaterialApp(
        home: Scaffold(
          backgroundColor: const Color(0xFF3A2A1E),
          body: Builder(
            builder: (ctx) => PostCookFeedbackSheet(
              recipeId: 'r-test',
              recipeName: 'Test Pasta',
              // apiClient omitted — null by default, not called when isOffline: true
              recipeCache: cache,
              isOffline: true,
              onComplete: onComplete,
            ),
          ),
        ),
      );
    }

    testWidgets('renders 5 star icons, notes field, Save and Skip buttons',
        (tester) async {
      await tester.pumpWidget(buildSheet(onComplete: () {}));

      // 5 stars
      expect(find.byKey(const Key('star_1')), findsOneWidget);
      expect(find.byKey(const Key('star_3')), findsOneWidget);
      expect(find.byKey(const Key('star_5')), findsOneWidget);
      expect(find.byKey(const Key('star_rating_row')), findsOneWidget);

      // Notes field
      expect(find.byKey(const Key('notes_field')), findsOneWidget);

      // Buttons
      expect(find.byKey(const Key('save_button')), findsOneWidget);
      expect(find.byKey(const Key('skip_button')), findsOneWidget);
      expect(find.text('Save'), findsOneWidget);
      expect(find.text('Skip'), findsOneWidget);
    });

    testWidgets('Skip button fires onComplete without saving', (tester) async {
      bool completed = false;
      await tester.pumpWidget(buildSheet(onComplete: () => completed = true));

      await tester.tap(find.byKey(const Key('skip_button')));
      await tester.pump();

      expect(completed, isTrue);

      // No cook log should have been saved
      final logs = await cache.getCookLogs('r-test');
      expect(logs, isEmpty);
    });

    testWidgets('Save button fires onComplete after selecting a rating',
        (tester) async {
      bool completed = false;
      await tester.pumpWidget(buildSheet(onComplete: () => completed = true));

      // Tap the 4th star
      await tester.tap(find.byKey(const Key('star_4')));
      await tester.pump();

      // Tap Save
      await tester.tap(find.byKey(const Key('save_button')));
      await tester.pumpAndSettle();

      expect(completed, isTrue);

      // Cook log should be stored
      final logs = await cache.getCookLogs('r-test');
      expect(logs.length, equals(1));
      expect(logs[0]['rating'], equals(4));
    });

    testWidgets('Save without rating still fires onComplete (no log saved)',
        (tester) async {
      bool completed = false;
      await tester.pumpWidget(buildSheet(onComplete: () => completed = true));

      // Tap Save without selecting any star
      await tester.tap(find.byKey(const Key('save_button')));
      await tester.pumpAndSettle();

      expect(completed, isTrue);

      // No log saved (rating == 0)
      final logs = await cache.getCookLogs('r-test');
      expect(logs, isEmpty);
    });

    testWidgets('Save with note queues it offline via queueNoteAdd',
        (tester) async {
      await tester.pumpWidget(buildSheet(onComplete: () {}));

      // Enter a note
      await tester.enterText(find.byKey(const Key('notes_field')), 'Added more garlic');

      // Tap star 5 then Save
      await tester.tap(find.byKey(const Key('star_5')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('save_button')));
      await tester.pumpAndSettle();

      // Note should be in pending queue (offline path)
      final pending = await cache.getPendingNotes();
      expect(pending.length, equals(1));
      expect(pending[0]['body'], equals('Added more garlic'));
      expect(pending[0]['recipe_id'], equals('r-test'));
    });
  });
}
