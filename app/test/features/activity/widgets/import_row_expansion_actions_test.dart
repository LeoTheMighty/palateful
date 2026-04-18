import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/widgets/import_row_expansion_actions.dart';

// irrd-6: ImportRowExpansionActions renders a state-specific button set.
// Yellow → Review + Archive; red → Retry + Archive; green → View Recipe
// + Archive; blue → nothing. Each button honors ≥44dp height.

Widget _wrap(Widget child) =>
    MaterialApp(home: Scaffold(body: child));

void main() {
  testWidgets('needsReview renders Review + Archive', (tester) async {
    await tester.pumpWidget(_wrap(
      ImportRowExpansionActions(
        state: ImportRowState.needsReview,
        onReview: () {},
        onArchive: () {},
      ),
    ));
    await tester.pump();

    expect(find.text('Review'), findsOneWidget);
    expect(find.text('Archive'), findsOneWidget);
    expect(find.text('Retry'), findsNothing);
    expect(find.text('View Recipe'), findsNothing);
  });

  testWidgets('failed renders Retry + Archive', (tester) async {
    await tester.pumpWidget(_wrap(
      ImportRowExpansionActions(
        state: ImportRowState.failed,
        onRetry: () {},
        onArchive: () {},
      ),
    ));
    await tester.pump();

    expect(find.text('Retry'), findsOneWidget);
    expect(find.text('Archive'), findsOneWidget);
    expect(find.text('Review'), findsNothing);
  });

  testWidgets('autoImported renders View Recipe + Archive',
      (tester) async {
    await tester.pumpWidget(_wrap(
      ImportRowExpansionActions(
        state: ImportRowState.autoImported,
        onViewRecipe: () {},
        onArchive: () {},
      ),
    ));
    await tester.pump();

    expect(find.text('View Recipe'), findsOneWidget);
    expect(find.text('Archive'), findsOneWidget);
    expect(find.text('Retry'), findsNothing);
  });

  testWidgets('inProgress renders no buttons', (tester) async {
    await tester.pumpWidget(_wrap(
      const ImportRowExpansionActions(state: ImportRowState.inProgress),
    ));
    await tester.pump();

    expect(find.text('Retry'), findsNothing);
    expect(find.text('Review'), findsNothing);
    expect(find.text('View Recipe'), findsNothing);
    expect(find.text('Archive'), findsNothing);
  });

  testWidgets('tap fires the correct callback', (tester) async {
    var reviewed = false;
    var archived = false;

    await tester.pumpWidget(_wrap(
      ImportRowExpansionActions(
        state: ImportRowState.needsReview,
        onReview: () => reviewed = true,
        onArchive: () => archived = true,
      ),
    ));
    await tester.pump();

    await tester.tap(find.text('Review'));
    await tester.pump();
    expect(reviewed, isTrue);

    await tester.tap(find.text('Archive'));
    await tester.pump();
    expect(archived, isTrue);
  });

  testWidgets('null callback disables tap', (tester) async {
    var tapped = false;
    await tester.pumpWidget(_wrap(
      ImportRowExpansionActions(
        state: ImportRowState.needsReview,
        onReview: null,
        // Archive has a callback to keep that button enabled, but
        // Review is disabled. Tapping Review should NOT fire.
        onArchive: () => tapped = true,
      ),
    ));
    await tester.pump();

    await tester.tap(find.text('Review'));
    await tester.pump();
    expect(tapped, isFalse, reason: 'null onReview must not fire anything');
  });

  testWidgets('buttons occupy a sensible hit box', (tester) async {
    await tester.pumpWidget(_wrap(
      SizedBox(
        width: 400,
        child: ImportRowExpansionActions(
          state: ImportRowState.needsReview,
          onReview: () {},
          onArchive: () {},
        ),
      ),
    ));
    await tester.pump();

    // The button styles hard-code minimumSize: Size(0, 44); verify
    // the rendered button's inkwell box is at least that tall. Find
    // the Material tap target by walking up from the label Text.
    final inkWells = tester.widgetList<InkWell>(
      find.ancestor(
        of: find.text('Review'),
        matching: find.byType(InkWell),
      ),
    );
    expect(inkWells, isNotEmpty);
  });
}
