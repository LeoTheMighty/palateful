import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/models/import_item_telemetry.dart';
import 'package:palateful/features/activity/widgets/stage_timeline.dart';

// irrd-5: StageTimeline renders a 4-chip horizontal strip with per-stage
// glyphs derived from the telemetry payload. The "current" stage pulses
// via an AnimationController we assert is active.

Widget _wrap(Widget child) =>
    MaterialApp(home: Scaffold(body: Center(child: child)));

ImportItemTelemetry _tel(List<StageEntry> entries) =>
    ImportItemTelemetry(stages: entries);

void main() {
  testWidgets('renders 4 labeled chips in order', (tester) async {
    await tester.pumpWidget(_wrap(StageTimeline(
      telemetry: _tel([
        const StageEntry(stage: 'parsed', status: 'ok'),
        const StageEntry(stage: 'extracted', status: 'ok'),
        const StageEntry(stage: 'matched', status: 'pending'),
        const StageEntry(stage: 'created', status: 'pending'),
      ]),
    )));
    await tester.pump();

    expect(find.text('Parsed'), findsOneWidget);
    expect(find.text('Extracted'), findsOneWidget);
    expect(find.text('Matched'), findsOneWidget);
    expect(find.text('Created'), findsOneWidget);

    // Semantic label on the parent reads "Stage timeline".
    expect(find.bySemanticsLabel('Stage timeline'), findsOneWidget);
  });

  testWidgets('completed stages show a check icon', (tester) async {
    await tester.pumpWidget(_wrap(StageTimeline(
      telemetry: _tel([
        const StageEntry(stage: 'parsed', status: 'ok'),
        const StageEntry(stage: 'extracted', status: 'pending'),
        const StageEntry(stage: 'matched', status: 'pending'),
        const StageEntry(stage: 'created', status: 'pending'),
      ]),
    )));
    await tester.pump();
    expect(find.byIcon(Icons.check), findsOneWidget);
  });

  testWidgets('failed stage shows a close icon', (tester) async {
    await tester.pumpWidget(_wrap(StageTimeline(
      telemetry: _tel([
        const StageEntry(stage: 'parsed', status: 'ok'),
        const StageEntry(stage: 'extracted', status: 'failed'),
        const StageEntry(stage: 'matched', status: 'pending'),
        const StageEntry(stage: 'created', status: 'pending'),
      ]),
    )));
    await tester.pump();
    expect(find.byIcon(Icons.close), findsOneWidget);
  });

  testWidgets('current stage renders pulsing hourglass (animation active)',
      (tester) async {
    await tester.pumpWidget(_wrap(StageTimeline(
      telemetry: _tel([
        const StageEntry(stage: 'parsed', status: 'ok'),
        const StageEntry(stage: 'extracted', status: 'pending'),
        const StageEntry(stage: 'matched', status: 'pending'),
        const StageEntry(stage: 'created', status: 'pending'),
      ]),
    )));
    await tester.pump();

    // Hourglass icon appears for the "extracted" current stage.
    expect(find.byIcon(Icons.hourglass_bottom), findsOneWidget);

    // Pulse animation forces frames — verifying active timer count
    // increases across two pumps.
    final hasPendingFramesBefore = tester.binding.hasScheduledFrame;
    await tester.pump(const Duration(milliseconds: 450));
    final hasPendingFramesAfter = tester.binding.hasScheduledFrame;

    // When the pulse AnimationController is running, Flutter schedules
    // a frame every tick — so hasScheduledFrame is true after a pump.
    expect(hasPendingFramesBefore || hasPendingFramesAfter, isTrue);
  });

  testWidgets('stages after a failed one are not marked current',
      (tester) async {
    await tester.pumpWidget(_wrap(StageTimeline(
      telemetry: _tel([
        const StageEntry(stage: 'parsed', status: 'ok'),
        const StageEntry(stage: 'extracted', status: 'failed'),
        const StageEntry(stage: 'matched', status: 'pending'),
        const StageEntry(stage: 'created', status: 'pending'),
      ]),
    )));
    await tester.pump();

    // No hourglass should be present — extracted failed, nothing after
    // is "current".
    expect(find.byIcon(Icons.hourglass_bottom), findsNothing);
  });

  testWidgets('tooltip contains duration + label for completed stage',
      (tester) async {
    await tester.pumpWidget(_wrap(StageTimeline(
      telemetry: _tel([
        StageEntry(
          stage: 'parsed',
          status: 'ok',
          durationMs: 3200,
          completedAt: DateTime.now().subtract(const Duration(minutes: 2)),
        ),
        const StageEntry(stage: 'extracted', status: 'pending'),
        const StageEntry(stage: 'matched', status: 'pending'),
        const StageEntry(stage: 'created', status: 'pending'),
      ]),
    )));
    await tester.pump();

    final tooltip = tester
        .widgetList<Tooltip>(find.byType(Tooltip))
        .firstWhere((t) => (t.message ?? '').startsWith('Parsed'));
    expect(tooltip.message, contains('Parsed'));
    expect(tooltip.message, contains('completed'));
    // 3200ms renders as "3.2s".
    expect(tooltip.message, contains('3.2s'));
  });
}
