import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/move_source_disambiguation_sheet.dart';

/// Render the sheet body directly inside a Scaffold. We don't go through
/// `showModalBottomSheet` here — the `Navigator.pop` interaction lives
/// in the framework and isn't worth re-testing. Result return values
/// for Continue / Cancel are exercised by the e2e in story 5.
Future<void> _pumpDirect(
  WidgetTester tester,
  List<SourceBookGroup> groups,
) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: MoveSourceDisambiguationSheet(groups: groups),
    ),
  ));
  await tester.pump();
}

void main() {
  testWidgets('renders title, body copy, and per-source counts',
      (tester) async {
    final groups = const [
      SourceBookGroup(
        bookId: 'b1',
        bookName: "Mom's Recipes",
        recipeIds: ['r1', 'r2', 'r3'],
      ),
      SourceBookGroup(
        bookId: 'b2',
        bookName: 'Trying Out',
        recipeIds: ['r4', 'r5'],
      ),
    ];
    await _pumpDirect(tester, groups);
    expect(find.text('Move from which book?'), findsOneWidget);
    expect(
      find.textContaining('Uncheck a book to leave its recipes'),
      findsOneWidget,
    );
    expect(find.text("Mom's Recipes"), findsOneWidget);
    expect(find.text('Trying Out'), findsOneWidget);
    expect(find.text('3 recipes'), findsOneWidget);
    expect(find.text('2 recipes'), findsOneWidget);
  });

  testWidgets('every source is checked by default; Continue is enabled',
      (tester) async {
    final groups = const [
      SourceBookGroup(
        bookId: 'b1',
        bookName: "Mom's",
        recipeIds: ['r1', 'r2'],
      ),
      SourceBookGroup(
        bookId: 'b2',
        bookName: 'Trying Out',
        recipeIds: ['r3'],
      ),
    ];
    await _pumpDirect(tester, groups);
    final checkboxes = find.byType(Checkbox);
    expect(checkboxes, findsNWidgets(2));
    for (var i = 0; i < 2; i++) {
      final cb = tester.widget<Checkbox>(checkboxes.at(i));
      expect(cb.value, true);
    }
    final btn = tester.widget<FilledButton>(
      find.ancestor(
        of: find.text('Continue'),
        matching: find.byType(FilledButton),
      ),
    );
    expect(btn.onPressed, isNotNull);
  });

  testWidgets('unchecking the only source disables Continue',
      (tester) async {
    final groups = const [
      SourceBookGroup(
        bookId: 'b1',
        bookName: "Mom's",
        recipeIds: ['r1'],
      ),
    ];
    await _pumpDirect(tester, groups);

    await tester.tap(find.byType(Checkbox).first);
    await tester.pump();

    final btn = tester.widget<FilledButton>(
      find.ancestor(
        of: find.text('Continue'),
        matching: find.byType(FilledButton),
      ),
    );
    expect(btn.onPressed, isNull);
  });

  testWidgets('unchecking one of two sources keeps Continue enabled',
      (tester) async {
    final groups = const [
      SourceBookGroup(
        bookId: 'b1',
        bookName: "Mom's",
        recipeIds: ['r1', 'r2'],
      ),
      SourceBookGroup(
        bookId: 'b2',
        bookName: 'Trying Out',
        recipeIds: ['r3'],
      ),
    ];
    await _pumpDirect(tester, groups);
    await tester.tap(find.byType(Checkbox).first);
    await tester.pump();

    final btn = tester.widget<FilledButton>(
      find.ancestor(
        of: find.text('Continue'),
        matching: find.byType(FilledButton),
      ),
    );
    expect(btn.onPressed, isNotNull);

    final cb0 = tester.widget<Checkbox>(find.byType(Checkbox).at(0));
    final cb1 = tester.widget<Checkbox>(find.byType(Checkbox).at(1));
    expect(cb0.value, false);
    expect(cb1.value, true);
  });

  testWidgets('count subtitle singularizes for 1 recipe', (tester) async {
    final groups = const [
      SourceBookGroup(
        bookId: 'b1',
        bookName: 'Single',
        recipeIds: ['r1'],
      ),
      SourceBookGroup(
        bookId: 'b2',
        bookName: 'Multi',
        recipeIds: ['r2', 'r3'],
      ),
    ];
    await _pumpDirect(tester, groups);
    expect(find.text('1 recipe'), findsOneWidget);
    expect(find.text('2 recipes'), findsOneWidget);
  });
}
