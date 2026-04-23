import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/debug/perf_overlay.dart';
import 'package:palateful/core/debug/perf_request_log.dart';

Widget _harness(Widget child) => MaterialApp(
      home: PerfOverlay(child: child),
    );

void main() {
  setUp(() => PerfRequestLog.instance.clear());

  testWidgets('kDebugMode ON — panel hidden by default', (tester) async {
    // Running tests always sets kDebugMode=true.
    await tester.pumpWidget(_harness(
      Scaffold(body: const Text('underlying-ui')),
    ));
    expect(find.text('underlying-ui'), findsOneWidget);
    expect(find.text('Perf — recent requests'), findsNothing);
  });

  testWidgets('long-press on top-right hit-zone toggles panel on/off',
      (tester) async {
    await tester.pumpWidget(_harness(
      Scaffold(body: const Text('underlying-ui')),
    ));

    final hitZone = find.byKey(const ValueKey('perf_overlay_hit_zone'));
    expect(hitZone, findsOneWidget);

    await tester.longPress(hitZone);
    await tester.pumpAndSettle();
    expect(find.text('Perf — recent requests'), findsOneWidget);
    expect(find.text('No requests yet'), findsOneWidget);

    // Close button toggles off.
    await tester
        .tap(find.byKey(const ValueKey('perf_overlay_close')));
    await tester.pumpAndSettle();
    expect(find.text('Perf — recent requests'), findsNothing);
  });

  testWidgets('panel renders entries and color-codes status',
      (tester) async {
    PerfRequestLog.instance.add(PerfRequestEntry(
      timestamp: DateTime(2026, 4, 23, 12),
      method: 'GET',
      path: '/v1/recipe-books',
      statusCode: 200,
      duration: const Duration(milliseconds: 42),
    ));
    PerfRequestLog.instance.add(PerfRequestEntry(
      timestamp: DateTime(2026, 4, 23, 12, 0, 1),
      method: 'POST',
      path: '/v1/recipes/abc/share',
      statusCode: 500,
      duration: const Duration(milliseconds: 789),
    ));

    await tester.pumpWidget(_harness(
      Scaffold(body: const SizedBox.expand()),
    ));
    await tester.longPress(
      find.byKey(const ValueKey('perf_overlay_hit_zone')),
    );
    await tester.pumpAndSettle();

    expect(find.text('/v1/recipe-books'), findsOneWidget);
    expect(find.text('/v1/recipes/abc/share'), findsOneWidget);
    expect(find.text('200'), findsOneWidget);
    expect(find.text('500'), findsOneWidget);
    expect(find.text('42ms'), findsOneWidget);
    expect(find.text('789ms'), findsOneWidget);
  });

  testWidgets('taps pass through to underlying UI when panel is closed',
      (tester) async {
    var tapped = 0;
    await tester.pumpWidget(_harness(
      Scaffold(
        appBar: AppBar(
          actions: [
            IconButton(
              key: const ValueKey('app-button'),
              icon: const Icon(Icons.add),
              onPressed: () => tapped++,
            ),
          ],
        ),
        body: const SizedBox.expand(),
      ),
    ));

    // The IconButton lives in the top-right — confirm it still receives
    // taps despite the hit-zone sitting on top of it.
    await tester.tap(find.byKey(const ValueKey('app-button')));
    await tester.pump();
    expect(tapped, 1);
  });

  test('kDebugMode is true inside tests (sanity)', () {
    // Dart's kDebugMode is compiled out in release via tree-shake; in
    // `flutter test` runs it always evaluates true.
    expect(kDebugMode, isTrue);
  });
}
