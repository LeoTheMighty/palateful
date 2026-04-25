import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/widgets/recipe_book_pill_row.dart';

void main() {
  final books = <Map<String, dynamic>>[
    {
      'id': 'a',
      'name': 'Apple Crisps',
      'is_system': false,
      'user_role': 'owner',
    },
    {
      'id': 'sys',
      'name': 'Trying Out',
      'is_system': true,
      'user_role': 'owner',
    },
    {
      'id': 'b',
      'name': "Mom's Recipes",
      'is_system': false,
      'user_role': 'editor',
    },
  ];

  group('sortBooksForPillRow', () {
    test('system books come before user books', () {
      final sorted = sortBooksForPillRow(books);
      expect(sorted.map((b) => b['id']).toList(), ['sys', 'a', 'b']);
    });

    test('preserves user-book relative order', () {
      final sorted = sortBooksForPillRow(books);
      // 'a' came before 'b' in input → still does in output.
      expect(sorted.indexWhere((b) => b['id'] == 'a'),
          lessThan(sorted.indexWhere((b) => b['id'] == 'b')));
    });
  });

  testWidgets('collapsed state shows current book name only', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RecipeBookPillRow(
          books: books,
          currentBookId: 'a',
          onSelect: (_) {},
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Apple Crisps'), findsOneWidget);
    // Other books should not appear when collapsed.
    expect(find.text('Trying Out'), findsNothing);
    expect(find.text("Mom's Recipes"), findsNothing);
    expect(find.text('New book'), findsNothing);
  });

  testWidgets('tapping the collapsed pill expands the row', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RecipeBookPillRow(
          books: books,
          currentBookId: 'a',
          onSelect: (_) {},
        ),
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Apple Crisps'));
    await tester.pumpAndSettle();

    // System book first, then user books, then "New book".
    expect(find.text('Trying Out'), findsOneWidget);
    expect(find.text("Mom's Recipes"), findsOneWidget);
    expect(find.text('Apple Crisps'), findsOneWidget);
    expect(find.text('New book'), findsOneWidget);
  });

  testWidgets('tapping a non-current pill fires onSelect with book id',
      (tester) async {
    String? selected;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RecipeBookPillRow(
          books: books,
          currentBookId: 'a',
          onSelect: (id) => selected = id,
        ),
      ),
    ));
    await tester.pumpAndSettle();
    // Expand.
    await tester.tap(find.text('Apple Crisps'));
    await tester.pumpAndSettle();
    // Tap Trying Out.
    await tester.tap(find.text('Trying Out'));
    await tester.pumpAndSettle();
    expect(selected, 'sys');
  });

  testWidgets('tapping the "+ New book" pill fires onSelect with null',
      (tester) async {
    String? capturedId = 'sentinel';
    bool captured = false;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RecipeBookPillRow(
          books: books,
          currentBookId: 'a',
          onSelect: (id) {
            captured = true;
            capturedId = id;
          },
        ),
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Apple Crisps'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('New book'));
    await tester.pumpAndSettle();
    expect(captured, true);
    expect(capturedId, isNull);
  });

  testWidgets(
      'tapping the current pill in expanded state collapses without firing',
      (tester) async {
    int taps = 0;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RecipeBookPillRow(
          books: books,
          currentBookId: 'a',
          onSelect: (_) => taps++,
        ),
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Apple Crisps'));
    await tester.pumpAndSettle();
    // Expanded — tap the current book pill (still labeled "Apple Crisps").
    await tester.tap(find.text('Apple Crisps'));
    await tester.pumpAndSettle();
    expect(taps, 0);
    // Back in collapsed mode → other names hidden again.
    expect(find.text("Mom's Recipes"), findsNothing);
  });

  testWidgets('isWorking disables the collapsed and expanded affordances',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RecipeBookPillRow(
          books: books,
          currentBookId: 'a',
          isWorking: true,
          onSelect: (_) {},
        ),
      ),
    ));
    await tester.pumpAndSettle();
    final chip = tester.widget<ActionChip>(find.byType(ActionChip).first);
    expect(chip.onPressed, isNull);
  });
}
