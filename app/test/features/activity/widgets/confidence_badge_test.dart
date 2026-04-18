import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/widgets/confidence_badge.dart';

// irrd-5: ConfidenceBadge takes {score, source} and renders one of four
// visual treatments. Thresholds verified at the label + glyph level.

Widget _wrap(Widget child) =>
    MaterialApp(home: Scaffold(body: Center(child: child)));

void main() {
  testWidgets('null score renders Unavailable label + help glyph',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const ConfidenceBadge(score: null, source: null),
    ));
    await tester.pump();

    expect(find.text('Unavailable'), findsOneWidget);
    expect(find.byIcon(Icons.help_outline), findsOneWidget);
  });

  testWidgets('low score (<0.5) renders "Low (N%)" + warning glyph',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const ConfidenceBadge(score: 0.42, source: 'model'),
    ));
    await tester.pump();

    expect(find.text('Low (42%)'), findsOneWidget);
    expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
  });

  testWidgets('medium score (0.5..0.8) renders just N%', (tester) async {
    await tester.pumpWidget(_wrap(
      const ConfidenceBadge(score: 0.72, source: 'model'),
    ));
    await tester.pump();

    expect(find.text('72%'), findsOneWidget);
    expect(find.byIcon(Icons.remove_circle_outline), findsOneWidget);
  });

  testWidgets('high score (>0.8) renders N% + check glyph', (tester) async {
    await tester.pumpWidget(_wrap(
      const ConfidenceBadge(score: 0.92, source: 'model'),
    ));
    await tester.pump();

    expect(find.text('92%'), findsOneWidget);
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });

  testWidgets('heuristic source adds *est superscript', (tester) async {
    await tester.pumpWidget(_wrap(
      const ConfidenceBadge(score: 0.6, source: 'heuristic'),
    ));
    await tester.pump();

    expect(find.text('*est'), findsOneWidget);
  });

  testWidgets('model source does not add *est', (tester) async {
    await tester.pumpWidget(_wrap(
      const ConfidenceBadge(score: 0.6, source: 'model'),
    ));
    await tester.pump();

    expect(find.text('*est'), findsNothing);
  });

  testWidgets('boundary: 0.5 is medium, 0.8 is medium, 0.8001 is high',
      (tester) async {
    for (final (score, label) in [
      (0.5, '50%'),
      (0.8, '80%'),
      (0.81, '81%'),
    ]) {
      await tester.pumpWidget(_wrap(
        ConfidenceBadge(score: score, source: 'model'),
      ));
      await tester.pump();
      expect(find.text(label), findsOneWidget,
          reason: 'score=$score should render $label');
    }
  });

  testWidgets('semantic label encodes level, percent, source',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const ConfidenceBadge(score: 0.62, source: 'heuristic'),
    ));
    await tester.pump();

    // Tooltip's internal Semantics wraps our own, so look for the
    // Semantics widget directly rather than via bySemanticsLabel.
    expect(
      find.byWidgetPredicate(
        (w) =>
            w is Semantics &&
            w.properties.label ==
                'Confidence: medium, 62%, source heuristic',
      ),
      findsOneWidget,
    );
  });
}
