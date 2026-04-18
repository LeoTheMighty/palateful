import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/providers/import_row_expansion_provider.dart';
import 'package:palateful/features/activity/widgets/import_row_caret.dart';

// irrd-4: ImportRowCaret owns the expand/collapse toggle, including
// the blue-row Stack-with-progress variant. These tests cover the
// toggle flow, per-row state isolation via `select`, semantic
// announce, and the progress-ring Stack composition for blue rows.

Widget _wrap(Widget child) =>
    ProviderScope(child: MaterialApp(home: Scaffold(body: child)));

void main() {
  testWidgets('starts collapsed, tap expands, tap again collapses',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const ImportRowCaret(
        rowId: 'row-a',
        recipeName: 'Mom\'s cake',
      ),
    ));

    // Initially the semantic label announces "Show details for…".
    expect(find.bySemanticsLabel('Show details for Mom\'s cake'),
        findsOneWidget);

    await tester.tap(find.byType(IconButton));
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel('Hide details for Mom\'s cake'),
        findsOneWidget);

    await tester.tap(find.byType(IconButton));
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel('Show details for Mom\'s cake'),
        findsOneWidget);
  });

  testWidgets('blue-row variant stacks a progress ring under the caret',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const ImportRowCaret(
        rowId: 'row-blue',
        recipeName: 'In Flight',
        showProgressRing: true,
        progressColor: Colors.blue,
      ),
    ));

    // Ring is read-only (tests for IgnorePointer wrapping); caret is
    // tappable. Both co-exist when showProgressRing is true.
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.byType(IconButton), findsOneWidget);
    // The ring's IgnorePointer is the one with ignoring: true — other
    // IgnorePointers exist in the Scaffold / Overlay chrome with
    // ignoring: false.
    final activeIgnorePointers = tester
        .widgetList<IgnorePointer>(find.byType(IgnorePointer))
        .where((w) => w.ignoring == true);
    expect(activeIgnorePointers, hasLength(1));
  });

  testWidgets('two carets with different rowIds keep independent state',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const Column(
        children: [
          ImportRowCaret(rowId: 'row-a', recipeName: 'A'),
          ImportRowCaret(rowId: 'row-b', recipeName: 'B'),
        ],
      ),
    ));

    // Tap row A.
    await tester.tap(find.bySemanticsLabel('Show details for A'));
    await tester.pumpAndSettle();

    // A is expanded, B still collapsed.
    expect(find.bySemanticsLabel('Hide details for A'), findsOneWidget);
    expect(find.bySemanticsLabel('Show details for B'), findsOneWidget);
  });

  test('ExpandedRowsNotifier — toggle / expand / collapse invariants', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    final notifier =
        container.read(importRowExpansionProvider.notifier);

    expect(notifier.isExpanded('x'), isFalse);

    notifier.toggle('x');
    expect(notifier.isExpanded('x'), isTrue);
    expect(container.read(importRowExpansionProvider), {'x'});

    notifier.toggle('x');
    expect(notifier.isExpanded('x'), isFalse);

    notifier.expand('x');
    notifier.expand('x'); // idempotent
    expect(container.read(importRowExpansionProvider), {'x'});

    notifier.collapse('y'); // idempotent on a missing id
    notifier.collapse('x');
    expect(container.read(importRowExpansionProvider), isEmpty);
  });
}
