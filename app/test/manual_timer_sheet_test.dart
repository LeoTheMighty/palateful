// cmt-5 — widget tests for the manual timer sheet.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/cook_mode/shared/widgets/manual_timer_sheet.dart';

Widget _harness({required Function(dynamic) onResult}) {
  return MaterialApp(
    home: Scaffold(
      body: Builder(
        builder: (ctx) => Center(
          child: ElevatedButton(
            onPressed: () async {
              final result = await showModalBottomSheet<(int, String)>(
                context: ctx,
                isScrollControlled: true,
                builder: (_) => const ManualTimerSheet(),
              );
              onResult(result);
            },
            child: const Text('open'),
          ),
        ),
      ),
    ),
  );
}

void main() {
  group('ManualTimerSheet', () {
    testWidgets('Start disabled until minutes entered', (tester) async {
      dynamic captured;
      await tester.pumpWidget(_harness(onResult: (r) => captured = r));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      final start = find.byKey(const Key('manual_timer_start'));
      expect(
        (tester.widget<FilledButton>(start)).onPressed,
        isNull,
      );
      expect(captured, null);
    });

    testWidgets('valid 15-min entry returns (15, "Timer")', (tester) async {
      dynamic captured;
      await tester.pumpWidget(_harness(onResult: (r) => captured = r));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('manual_timer_minutes')),
        '15',
      );
      await tester.pump();

      final start = find.byKey(const Key('manual_timer_start'));
      expect(
        (tester.widget<FilledButton>(start)).onPressed,
        isNotNull,
      );
      await tester.tap(start);
      await tester.pumpAndSettle();
      expect(captured, (15, 'Timer'));
    });

    testWidgets('0 min blocks Start', (tester) async {
      await tester.pumpWidget(_harness(onResult: (_) {}));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('manual_timer_minutes')),
        '0',
      );
      await tester.pump();

      final start = find.byKey(const Key('manual_timer_start'));
      expect(
        (tester.widget<FilledButton>(start)).onPressed,
        isNull,
      );
    });

    testWidgets('400 min blocks Start', (tester) async {
      await tester.pumpWidget(_harness(onResult: (_) {}));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('manual_timer_minutes')),
        '400',
      );
      await tester.pump();

      final start = find.byKey(const Key('manual_timer_start'));
      expect(
        (tester.widget<FilledButton>(start)).onPressed,
        isNull,
      );
    });

    testWidgets('non-digit input is filtered on paste', (tester) async {
      dynamic captured;
      await tester.pumpWidget(_harness(onResult: (r) => captured = r));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      // Simulate a paste of "40abc" — digitsOnly formatter drops the alpha.
      await tester.enterText(
        find.byKey(const Key('manual_timer_minutes')),
        '40abc',
      );
      await tester.pump();

      final start = find.byKey(const Key('manual_timer_start'));
      expect(
        (tester.widget<FilledButton>(start)).onPressed,
        isNotNull,
      );
      await tester.tap(start);
      await tester.pumpAndSettle();
      // The filter left "40" in the field; label defaulted to "Timer".
      expect(captured, (40, 'Timer'));
    });

    testWidgets('empty label falls back to "Timer"', (tester) async {
      dynamic captured;
      await tester.pumpWidget(_harness(onResult: (r) => captured = r));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('manual_timer_minutes')),
        '5',
      );
      await tester.enterText(
        find.byKey(const Key('manual_timer_label')),
        '   ',
      );
      await tester.pump();
      await tester.tap(find.byKey(const Key('manual_timer_start')));
      await tester.pumpAndSettle();
      expect(captured, (5, 'Timer'));
    });

    testWidgets('label trimmed on submit', (tester) async {
      dynamic captured;
      await tester.pumpWidget(_harness(onResult: (r) => captured = r));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('manual_timer_minutes')),
        '5',
      );
      await tester.enterText(
        find.byKey(const Key('manual_timer_label')),
        '  rise  ',
      );
      await tester.pump();
      await tester.tap(find.byKey(const Key('manual_timer_start')));
      await tester.pumpAndSettle();
      expect(captured, (5, 'rise'));
    });
  });

  group('disambiguateTimerLabel', () {
    test('no collision returns requested label verbatim', () {
      expect(
        disambiguateTimerLabel('rise', {'bake'}),
        'rise',
      );
    });

    test('one collision appends " 2"', () {
      expect(
        disambiguateTimerLabel('Timer', {'Timer'}),
        'Timer 2',
      );
    });

    test('two collisions appends " 3"', () {
      expect(
        disambiguateTimerLabel('Timer', {'Timer', 'Timer 2'}),
        'Timer 3',
      );
    });

    test('skips gaps gracefully', () {
      // Even with non-contiguous existing variants, the first unused
      // integer suffix wins. Here "Timer 2" is taken but "Timer" itself
      // is not — so the requested "Timer" is returned as-is.
      expect(
        disambiguateTimerLabel('Timer', {'Timer 2'}),
        'Timer',
      );
    });
  });
}
