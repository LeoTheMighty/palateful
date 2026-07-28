import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/add_recipe/state/receive_import_notifier.dart';
import 'package:palateful/features/recipes/add_recipe/widgets/receive_progress_card.dart';

// sru-4 — the progress card has to carry the user across the whole
// copy-to-sandbox → uploading → sending sequence without ever going
// blank. These tests pin each stage's copy and indicator type.

Future<void> _pump(WidgetTester tester, ReceiveImportState state) async {
  await tester.pumpWidget(
    MaterialApp(home: ReceiveProgressCard(state: state)),
  );
  await tester.pump();
}

void main() {
  testWidgets('detecting shows the branch copy and an indeterminate spinner',
      (tester) async {
    await _pump(
      tester,
      const ReceiveImportState(
        phase: ReceivePhase.detecting,
        branch: ReceiveBranch.pdf,
      ),
    );

    expect(find.text('Reading your PDF'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsNothing);
  });

  testWidgets('uploading shows percent copy, a byte bar, and a byte readout',
      (tester) async {
    await _pump(
      tester,
      const ReceiveImportState(
        phase: ReceivePhase.uploading,
        branch: ReceiveBranch.video,
        uploadedBytes: 5 * 1024 * 1024,
        totalBytes: 20 * 1024 * 1024,
      ),
    );

    expect(find.text('Uploading… 25%'), findsOneWidget);
    expect(find.text('5.0 MB / 20 MB'), findsOneWidget);
    final bar = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator),
    );
    expect(bar.value, closeTo(0.25, 0.0001));
  });

  testWidgets('a zero total falls back to branch copy, not "Uploading… 0%"',
      (tester) async {
    await _pump(
      tester,
      const ReceiveImportState(
        phase: ReceivePhase.uploading,
        branch: ReceiveBranch.audio,
      ),
    );

    expect(find.text('Transcribing audio…'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('sending swaps the byte bar for the claim stage',
      (tester) async {
    await _pump(
      tester,
      const ReceiveImportState(
        phase: ReceivePhase.sending,
        branch: ReceiveBranch.pdf,
        uploadedBytes: 2048,
        totalBytes: 2048,
      ),
    );

    expect(find.text('Sending to Palateful…'), findsOneWidget);
    // Determinate bar parked at 100% for the whole 409-retry handshake
    // reads as a hang — the spinner is the honest signal here.
    expect(find.byType(LinearProgressIndicator), findsNothing);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });
}
