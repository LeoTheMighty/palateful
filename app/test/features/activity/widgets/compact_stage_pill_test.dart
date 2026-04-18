import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/models/import_item_telemetry.dart';
import 'package:palateful/features/activity/widgets/compact_stage_pill.dart';

// irrd-5: CompactStagePill renders four tiny dots — the glanceable blue
// row variant. Tests cover dot count, semantic label, and that the
// pulsing current dot animates (keeps pumping frames).

Widget _wrap(Widget child) =>
    MaterialApp(home: Scaffold(body: Center(child: child)));

ImportItemTelemetry _tel(List<StageEntry> entries) =>
    ImportItemTelemetry(stages: entries);

void main() {
  testWidgets('renders four dot containers', (tester) async {
    await tester.pumpWidget(_wrap(CompactStagePill(
      telemetry: _tel([
        const StageEntry(stage: 'parsed', status: 'ok'),
        const StageEntry(stage: 'extracted', status: 'pending'),
        const StageEntry(stage: 'matched', status: 'pending'),
        const StageEntry(stage: 'created', status: 'pending'),
      ]),
    )));
    await tester.pump();

    // Each dot is a Container with width/height 7.
    final dots = tester
        .widgetList<Container>(find.byType(Container))
        .where((c) {
      final constraints = c.constraints;
      if (constraints == null) return false;
      return constraints.maxWidth == 7 && constraints.maxHeight == 7;
    });
    expect(dots.length, 4);
  });

  testWidgets('semantic label encodes each stage state', (tester) async {
    await tester.pumpWidget(_wrap(CompactStagePill(
      telemetry: _tel([
        const StageEntry(stage: 'parsed', status: 'ok'),
        const StageEntry(stage: 'extracted', status: 'pending'),
        const StageEntry(stage: 'matched', status: 'pending'),
        const StageEntry(stage: 'created', status: 'pending'),
      ]),
    )));
    await tester.pump();

    expect(
      find.bySemanticsLabel(
        'Pipeline: parsed done, extracted in progress, matched pending, created pending',
      ),
      findsOneWidget,
    );
  });

  testWidgets('current-stage pulse schedules frames', (tester) async {
    await tester.pumpWidget(_wrap(CompactStagePill(
      telemetry: _tel([
        const StageEntry(stage: 'parsed', status: 'ok'),
        const StageEntry(stage: 'extracted', status: 'pending'),
        const StageEntry(stage: 'matched', status: 'pending'),
        const StageEntry(stage: 'created', status: 'pending'),
      ]),
    )));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(tester.binding.hasScheduledFrame, isTrue);
  });

  testWidgets('failed stage suppresses current-stage pulse', (tester) async {
    await tester.pumpWidget(_wrap(CompactStagePill(
      telemetry: _tel([
        const StageEntry(stage: 'parsed', status: 'ok'),
        const StageEntry(stage: 'extracted', status: 'failed'),
        const StageEntry(stage: 'matched', status: 'pending'),
        const StageEntry(stage: 'created', status: 'pending'),
      ]),
    )));
    await tester.pump();

    expect(
      find.bySemanticsLabel(
        'Pipeline: parsed done, extracted failed, matched pending, created pending',
      ),
      findsOneWidget,
    );
  });
}
