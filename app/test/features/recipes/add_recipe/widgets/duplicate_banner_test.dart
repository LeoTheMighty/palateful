import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/add_recipe/widgets/duplicate_banner.dart';

/// import-dup-3 — widget tests for DuplicateBanner.
///
/// The banner is purely presentational; tests verify both rendering
/// (correct copy + correct buttons per state) and that user taps fire
/// the expected callbacks. Parent-side mutation logic (skip endpoint
/// call, deep-link routing) is exercised in the screen-level test.

Future<void> _pumpBanner(
  WidgetTester tester, {
  required Map<String, dynamic> match,
  required VoidCallback onSkip,
  required VoidCallback onAddAnyway,
  required VoidCallback onTapMatch,
  VoidCallback? onRestore,
  VoidCallback? onShowAll,
  int otherMatchCount = 0,
  bool isProcessing = false,
}) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: DuplicateBanner(
          match: match,
          onSkip: onSkip,
          onAddAnyway: onAddAnyway,
          onTapMatch: onTapMatch,
          onRestore: onRestore,
          onShowAll: onShowAll,
          otherMatchCount: otherMatchCount,
          isProcessing: isProcessing,
        ),
      ),
    ),
  ));
}

void main() {
  group('DuplicateBanner', () {
    testWidgets('renders active match in blue with Skip + Add anyway only',
        (tester) async {
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': "Mom's Brisket",
          'current_book_name': "Mom's Recipes",
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        },
        onSkip: () {},
        onAddAnyway: () {},
        onTapMatch: () {},
      );

      expect(find.byKey(const Key('duplicate_banner')), findsOneWidget);
      expect(find.textContaining('You already have'), findsOneWidget);
      expect(find.textContaining("Mom's Brisket"), findsOneWidget);
      expect(find.textContaining("Mom's Recipes"), findsOneWidget);
      // Active state: Skip + Add anyway. No Restore.
      expect(find.byKey(const Key('duplicate_banner_skip')), findsOneWidget);
      expect(find.byKey(const Key('duplicate_banner_add_anyway')),
          findsOneWidget);
      expect(find.byKey(const Key('duplicate_banner_restore')), findsNothing);
    });

    testWidgets('renders archived match in amber with Restore + Skip + Add anyway',
        (tester) async {
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': "Mom's Brisket",
          'current_book_name': "Mom's Recipes",
          'archived_at': '2024-03-12T09:30:00+00:00',
          'last_cooked': null,
          'match_kind': 'title',
        },
        onSkip: () {},
        onRestore: () {},
        onAddAnyway: () {},
        onTapMatch: () {},
      );

      expect(find.textContaining('You archived'), findsOneWidget);
      expect(find.textContaining("Mom's Brisket"), findsOneWidget);
      expect(find.textContaining('2024-03-12'), findsOneWidget);
      // Archived state: Restore + Skip + Add anyway.
      expect(
        find.byKey(const Key('duplicate_banner_restore')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('duplicate_banner_skip')), findsOneWidget);
      expect(
        find.byKey(const Key('duplicate_banner_add_anyway')),
        findsOneWidget,
      );
    });

    testWidgets('renders multi-match "Show all" button when otherMatchCount > 0',
        (tester) async {
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': "Mom's Brisket",
          'current_book_name': "Mom's Recipes",
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        },
        otherMatchCount: 2,
        onSkip: () {},
        onAddAnyway: () {},
        onTapMatch: () {},
        onShowAll: () {},
      );

      expect(
        find.byKey(const Key('duplicate_banner_show_all')),
        findsOneWidget,
      );
      expect(
        find.textContaining('+ 2 more matches — show all'),
        findsOneWidget,
      );
    });

    testWidgets('singular "match" copy when otherMatchCount == 1',
        (tester) async {
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': 'X',
          'current_book_name': 'Y',
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        },
        otherMatchCount: 1,
        onSkip: () {},
        onAddAnyway: () {},
        onTapMatch: () {},
        onShowAll: () {},
      );

      expect(
        find.textContaining('+ 1 more match — show all'),
        findsOneWidget,
      );
    });

    testWidgets('Skip button fires onSkip', (tester) async {
      var skipCount = 0;
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': 'X',
          'current_book_name': 'Y',
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        },
        onSkip: () => skipCount++,
        onAddAnyway: () {},
        onTapMatch: () {},
      );

      await tester.tap(find.byKey(const Key('duplicate_banner_skip')));
      await tester.pump();
      expect(skipCount, 1);
    });

    testWidgets('Restore button fires onRestore on archived match',
        (tester) async {
      var restoreCount = 0;
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': 'X',
          'current_book_name': 'Y',
          'archived_at': '2024-03-12T09:30:00+00:00',
          'last_cooked': null,
          'match_kind': 'title',
        },
        onSkip: () {},
        onRestore: () => restoreCount++,
        onAddAnyway: () {},
        onTapMatch: () {},
      );

      await tester.tap(find.byKey(const Key('duplicate_banner_restore')));
      await tester.pump();
      expect(restoreCount, 1);
    });

    testWidgets('Add anyway button fires onAddAnyway', (tester) async {
      var addCount = 0;
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': 'X',
          'current_book_name': 'Y',
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        },
        onSkip: () {},
        onAddAnyway: () => addCount++,
        onTapMatch: () {},
      );

      await tester.tap(find.byKey(const Key('duplicate_banner_add_anyway')));
      await tester.pump();
      expect(addCount, 1);
    });

    testWidgets('Show all button fires onShowAll', (tester) async {
      var showAllCount = 0;
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': 'X',
          'current_book_name': 'Y',
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        },
        otherMatchCount: 3,
        onSkip: () {},
        onAddAnyway: () {},
        onTapMatch: () {},
        onShowAll: () => showAllCount++,
      );

      await tester.tap(find.byKey(const Key('duplicate_banner_show_all')));
      await tester.pump();
      expect(showAllCount, 1);
    });

    testWidgets('all action buttons disabled when isProcessing', (tester) async {
      var skipCount = 0;
      var restoreCount = 0;
      var addCount = 0;
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': 'X',
          'current_book_name': 'Y',
          'archived_at': '2024-03-12T09:30:00+00:00',
          'last_cooked': null,
          'match_kind': 'title',
        },
        isProcessing: true,
        onSkip: () => skipCount++,
        onRestore: () => restoreCount++,
        onAddAnyway: () => addCount++,
        onTapMatch: () {},
      );

      // Verify buttons are disabled (taps no-op, callbacks not fired)
      await tester.tap(find.byKey(const Key('duplicate_banner_skip')));
      await tester.tap(find.byKey(const Key('duplicate_banner_restore')));
      await tester.tap(find.byKey(const Key('duplicate_banner_add_anyway')));
      await tester.pump();
      expect(skipCount, 0);
      expect(restoreCount, 0);
      expect(addCount, 0);
    });

    testWidgets('renders last_cooked when present', (tester) async {
      // Use a fixed "1 day ago" timestamp so the relative format is
      // deterministic. Subtract 26 hours to land safely in the day bucket.
      final oneDayAgo =
          DateTime.now().subtract(const Duration(hours: 26)).toIso8601String();
      await _pumpBanner(
        tester,
        match: {
          'recipe_id': 'r-1',
          'title': 'X',
          'current_book_name': 'Y',
          'archived_at': null,
          'last_cooked': oneDayAgo,
          'match_kind': 'title',
        },
        onSkip: () {},
        onAddAnyway: () {},
        onTapMatch: () {},
      );

      expect(find.textContaining('last cooked'), findsOneWidget);
      expect(find.textContaining('day'), findsOneWidget);
    });

    testWidgets('omits last_cooked fragment when null', (tester) async {
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': 'X',
          'current_book_name': 'Y',
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        },
        onSkip: () {},
        onAddAnyway: () {},
        onTapMatch: () {},
      );

      expect(find.textContaining('last cooked'), findsNothing);
    });

    testWidgets('falls back to "an earlier date" on malformed archived_at',
        (tester) async {
      await _pumpBanner(
        tester,
        match: const {
          'recipe_id': 'r-1',
          'title': 'X',
          'current_book_name': 'Y',
          'archived_at': 'not-a-date',
          'last_cooked': null,
          'match_kind': 'title',
        },
        onSkip: () {},
        onRestore: () {},
        onAddAnyway: () {},
        onTapMatch: () {},
      );

      expect(find.textContaining('an earlier date'), findsOneWidget);
    });
  });
}
