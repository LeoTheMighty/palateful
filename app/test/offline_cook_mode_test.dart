import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:palateful/core/services/recipe_cache_service.dart';
import 'package:palateful/core/theme/app_colors.dart';

/// Tests for RecipeCacheService and the offline indicator widget.
///
/// RecipeCacheService tests use the shared_preferences in-memory stub
/// (SharedPreferences.setMockInitialValues) so no platform channel is needed.
void main() {
  // ------------------------------------------------------------------
  // RecipeCacheService unit tests
  // ------------------------------------------------------------------

  group('RecipeCacheService', () {
    late RecipeCacheService service;

    setUp(() {
      SharedPreferences.setMockInitialValues({});
      service = RecipeCacheService();
    });

    test('cacheRecipe stores data under correct key', () async {
      const id = 'abc123';
      final data = {'name': 'Pasta', 'ingredients': []};

      await service.cacheRecipe(id, data);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.containsKey('palateful_recipe_$id'), isTrue);
    });

    test('loadCachedRecipe returns null for unknown recipe', () async {
      final result = await service.loadCachedRecipe('does-not-exist');
      expect(result, isNull);
    });

    test('loadCachedRecipe returns data after cacheRecipe', () async {
      const id = 'recipe-42';
      final data = {'name': 'Pizza', 'steps': [], 'ingredients': []};

      await service.cacheRecipe(id, data);
      final result = await service.loadCachedRecipe(id);

      expect(result, isNotNull);
      expect(result!['name'], equals('Pizza'));
    });

    test('queueNoteAdd appends entry to pending notes list', () async {
      await service.queueNoteAdd('r1', 'First note');
      await service.queueNoteAdd('r1', 'Second note');

      final notes = await service.getPendingNotes();
      expect(notes.length, equals(2));
      expect(notes[0]['body'], equals('First note'));
      expect(notes[1]['body'], equals('Second note'));
      expect(notes[0]['recipe_id'], equals('r1'));
    });

    test('clearPendingNotes removes all pending notes', () async {
      await service.queueNoteAdd('r1', 'note');
      await service.clearPendingNotes();

      final notes = await service.getPendingNotes();
      expect(notes, isEmpty);
    });

    test('hasCachedRecipe returns false when recipe not cached', () async {
      final result = await service.hasCachedRecipe('not-cached');
      expect(result, isFalse);
    });

    test('hasCachedRecipe returns true after caching', () async {
      await service.cacheRecipe('r99', {'name': 'Test'});
      expect(await service.hasCachedRecipe('r99'), isTrue);
    });
  });

  // ------------------------------------------------------------------
  // Offline indicator widget test
  // ------------------------------------------------------------------

  group('Offline indicator widget', () {
    // ignore: no_leading_underscores_for_local_identifiers
    Widget _buildOfflineIndicator({required bool isOffline}) {
      return MaterialApp(
        home: Scaffold(
          body: Row(
            children: [
              if (isOffline) ...[
                const Icon(Icons.wifi_off,
                    key: Key('offline_icon'),
                    size: 14,
                    color: AppColors.terracotta),
                const SizedBox(width: 2),
                const Text(
                  'Offline',
                  key: Key('offline_text'),
                  style: TextStyle(
                      fontSize: 11, color: AppColors.terracotta),
                ),
              ],
            ],
          ),
        ),
      );
    }

    testWidgets('offline indicator renders when _isOffline is true',
        (tester) async {
      await tester.pumpWidget(_buildOfflineIndicator(isOffline: true));

      expect(find.byKey(const Key('offline_icon')), findsOneWidget);
      expect(find.byKey(const Key('offline_text')), findsOneWidget);
      expect(find.text('Offline'), findsOneWidget);
    });

    testWidgets('offline indicator is absent when _isOffline is false',
        (tester) async {
      await tester.pumpWidget(_buildOfflineIndicator(isOffline: false));

      expect(find.byKey(const Key('offline_icon')), findsNothing);
      expect(find.text('Offline'), findsNothing);
    });
  });
}
