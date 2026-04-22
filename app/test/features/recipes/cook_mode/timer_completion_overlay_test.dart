import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/theme/theme.dart';
import 'package:palateful/features/recipes/cook_mode/widgets/timer_completion_overlay.dart';

/// Pumps a host that exposes a button which invokes the overlay. We need
/// a real navigator around the host so `showModalBottomSheet` can push
/// the sheet route.
Future<void> _pumpHostAndOpen(
  WidgetTester tester, {
  required String label,
  String? recipeName,
  int? stepNumber,
  VoidCallback? onAdd2,
  VoidCallback? onAdd5,
  VoidCallback? onReset,
  VoidCallback? onStop,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(
        extensions: const <ThemeExtension<dynamic>>[CookModeTheme.light],
      ),
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () => showTimerCompletionOverlay(
                context: context,
                label: label,
                recipeName: recipeName,
                stepNumber: stepNumber,
                onAdd2: onAdd2 ?? () {},
                onAdd5: onAdd5 ?? () {},
                onReset: onReset ?? () {},
                onStop: onStop ?? () {},
              ),
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

void main() {
  group('showTimerCompletionOverlay', () {
    testWidgets('renders title, four buttons, subtitle when recipe given',
        (tester) async {
      await _pumpHostAndOpen(
        tester,
        label: 'Simmer',
        recipeName: 'Sweet Potato Quiche',
        stepNumber: 2, // displayed as Step 3
      );

      expect(find.byKey(const Key('timer_overlay_title')), findsOneWidget);
      expect(find.text("Time's up — Simmer"), findsOneWidget);

      expect(find.byKey(const Key('timer_overlay_subtitle')), findsOneWidget);
      expect(find.text('Sweet Potato Quiche · Step 3'), findsOneWidget);

      expect(find.byKey(const Key('timer_overlay_add_2')), findsOneWidget);
      expect(find.byKey(const Key('timer_overlay_add_5')), findsOneWidget);
      expect(find.byKey(const Key('timer_overlay_reset')), findsOneWidget);
      expect(find.byKey(const Key('timer_overlay_stop')), findsOneWidget);

      expect(find.text('+ 2 min'), findsOneWidget);
      expect(find.text('+ 5 min'), findsOneWidget);
      expect(find.text('Reset'), findsOneWidget);
      expect(find.text('Stop'), findsOneWidget);
    });

    testWidgets('omits subtitle when recipeName is null', (tester) async {
      await _pumpHostAndOpen(
        tester,
        label: 'Rest dough',
      );

      expect(find.byKey(const Key('timer_overlay_title')), findsOneWidget);
      expect(find.byKey(const Key('timer_overlay_subtitle')), findsNothing);
    });

    testWidgets('omits subtitle when recipeName is empty', (tester) async {
      await _pumpHostAndOpen(
        tester,
        label: 'Rest dough',
        recipeName: '',
        stepNumber: 0,
      );

      expect(find.byKey(const Key('timer_overlay_subtitle')), findsNothing);
    });

    testWidgets('shows recipe-only subtitle when stepNumber omitted',
        (tester) async {
      await _pumpHostAndOpen(
        tester,
        label: 'Rest dough',
        recipeName: 'Focaccia',
      );

      expect(find.text('Focaccia'), findsOneWidget);
      expect(find.textContaining('Step'), findsNothing);
    });

    testWidgets('+ 2 min button invokes onAdd2 and closes the sheet',
        (tester) async {
      bool add2 = false;
      await _pumpHostAndOpen(
        tester,
        label: 'Bake',
        onAdd2: () => add2 = true,
      );

      await tester.tap(find.byKey(const Key('timer_overlay_add_2')));
      await tester.pumpAndSettle();

      expect(add2, isTrue);
      expect(find.byKey(const Key('timer_overlay_title')), findsNothing);
    });

    testWidgets('+ 5 min button invokes onAdd5 and closes the sheet',
        (tester) async {
      bool add5 = false;
      await _pumpHostAndOpen(
        tester,
        label: 'Bake',
        onAdd5: () => add5 = true,
      );

      await tester.tap(find.byKey(const Key('timer_overlay_add_5')));
      await tester.pumpAndSettle();

      expect(add5, isTrue);
      expect(find.byKey(const Key('timer_overlay_title')), findsNothing);
    });

    testWidgets('Reset button invokes onReset and closes the sheet',
        (tester) async {
      bool reset = false;
      await _pumpHostAndOpen(
        tester,
        label: 'Bake',
        onReset: () => reset = true,
      );

      await tester.tap(find.byKey(const Key('timer_overlay_reset')));
      await tester.pumpAndSettle();

      expect(reset, isTrue);
      expect(find.byKey(const Key('timer_overlay_title')), findsNothing);
    });

    testWidgets('Stop button invokes onStop and closes the sheet',
        (tester) async {
      bool stopped = false;
      await _pumpHostAndOpen(
        tester,
        label: 'Bake',
        onStop: () => stopped = true,
      );

      await tester.tap(find.byKey(const Key('timer_overlay_stop')));
      await tester.pumpAndSettle();

      expect(stopped, isTrue);
      expect(find.byKey(const Key('timer_overlay_title')), findsNothing);
    });

    testWidgets('action buttons have at least 56dp tap height',
        (tester) async {
      await _pumpHostAndOpen(
        tester,
        label: 'Bake',
      );

      for (final key in const [
        Key('timer_overlay_add_2'),
        Key('timer_overlay_add_5'),
        Key('timer_overlay_reset'),
        Key('timer_overlay_stop'),
      ]) {
        final size = tester.getSize(find.byKey(key));
        expect(size.height, greaterThanOrEqualTo(56.0),
            reason: 'Button $key should be >= 56dp tall');
      }
    });
  });
}
