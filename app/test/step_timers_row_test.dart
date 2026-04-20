// cmt-4 — widget tests for the step timers row.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/cook_mode/util/timer_regex.dart';
import 'package:palateful/features/recipes/cook_mode/widgets/step_timers_row.dart';

Widget _wrap(Widget child) => MaterialApp(
      home: Scaffold(body: Center(child: child)),
    );

void main() {
  testWidgets('empty timers renders nothing', (tester) async {
    await tester.pumpWidget(
      _wrap(StepTimersRow(timers: const [], onStart: (_, __) {})),
    );
    // No OutlinedButton present.
    expect(find.byType(OutlinedButton), findsNothing);
  });

  testWidgets('renders one button per timer with "N min label" form',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        StepTimersRow(
          timers: const [
            StepTimer(durationMinutes: 3, label: 'simmer'),
            StepTimer(durationMinutes: 10, label: 'bake'),
          ],
          onStart: (_, __) {},
        ),
      ),
    );
    expect(find.text('3 min simmer'), findsOneWidget);
    expect(find.text('10 min bake'), findsOneWidget);
  });

  testWidgets('default label "timer" renders concise "N min" form',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        StepTimersRow(
          timers: const [StepTimer(durationMinutes: 5, label: 'timer')],
          onStart: (_, __) {},
        ),
      ),
    );
    expect(find.text('5 min'), findsOneWidget);
  });

  testWidgets('tap invokes onStart with Duration + label', (tester) async {
    Duration? capturedDuration;
    String? capturedLabel;
    await tester.pumpWidget(
      _wrap(
        StepTimersRow(
          timers: const [StepTimer(durationMinutes: 7, label: 'simmer')],
          onStart: (d, l) {
            capturedDuration = d;
            capturedLabel = l;
          },
        ),
      ),
    );
    await tester.tap(find.byType(OutlinedButton));
    await tester.pump();
    expect(capturedDuration, const Duration(minutes: 7));
    expect(capturedLabel, 'simmer');
  });

  testWidgets('rangeUpperLabel wraps in a Tooltip', (tester) async {
    await tester.pumpWidget(
      _wrap(
        StepTimersRow(
          timers: const [
            StepTimer(
              durationMinutes: 3,
              label: 'simmer',
              rangeUpperLabel: '3–5 min in recipe',
            ),
          ],
          onStart: (_, __) {},
        ),
      ),
    );
    expect(find.byTooltip('3–5 min in recipe'), findsOneWidget);
  });

  testWidgets('no tooltip when rangeUpperLabel is null', (tester) async {
    await tester.pumpWidget(
      _wrap(
        StepTimersRow(
          timers: const [StepTimer(durationMinutes: 3, label: 'simmer')],
          onStart: (_, __) {},
        ),
      ),
    );
    expect(find.byType(Tooltip), findsNothing);
  });

  testWidgets('renders horizontally-scrollable row', (tester) async {
    await tester.pumpWidget(
      _wrap(
        StepTimersRow(
          timers: List.generate(
            10,
            (i) => StepTimer(durationMinutes: i + 1, label: 'timer'),
          ),
          onStart: (_, __) {},
        ),
      ),
    );
    final scroll = tester.widget<SingleChildScrollView>(
      find.byType(SingleChildScrollView),
    );
    expect(scroll.scrollDirection, Axis.horizontal);
  });
}
