import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/widgets/awaiting_review_reason_chip.dart';

// irrd-6: AwaitingReviewReasonChip renders the 1-word yellow-row hint.
// Unknown / null reasons collapse to SizedBox.shrink so parent layouts
// don't reserve empty space.

Widget _wrap(Widget child) =>
    MaterialApp(home: Scaffold(body: Center(child: child)));

void main() {
  testWidgets('renders the label for each known reason', (tester) async {
    const cases = {
      'low_confidence': 'low confidence',
      'unmatched_ingredients': 'unmatched ingredients',
      'missing_title': 'missing title',
      'manual': 'manual review',
    };

    for (final entry in cases.entries) {
      await tester.pumpWidget(_wrap(
        AwaitingReviewReasonChip(reason: entry.key),
      ));
      await tester.pump();
      expect(find.text(entry.value), findsOneWidget,
          reason: 'reason=${entry.key} should render "${entry.value}"');
    }
  });

  testWidgets('null renders an empty shrink (no Container)',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const AwaitingReviewReasonChip(reason: null),
    ));
    await tester.pump();

    expect(find.byType(Container), findsNothing);
    expect(find.byType(Text), findsNothing);
  });

  testWidgets('unknown reason renders an empty shrink', (tester) async {
    await tester.pumpWidget(_wrap(
      const AwaitingReviewReasonChip(reason: 'unrecognized'),
    ));
    await tester.pump();

    expect(find.textContaining('unrecognized'), findsNothing);
  });

  testWidgets('semantic label prefixes with "Reason:"', (tester) async {
    await tester.pumpWidget(_wrap(
      const AwaitingReviewReasonChip(reason: 'low_confidence'),
    ));
    await tester.pump();

    expect(
      find.byWidgetPredicate(
        (w) =>
            w is Semantics &&
            w.properties.label == 'Reason: low confidence',
      ),
      findsOneWidget,
    );
  });
}
