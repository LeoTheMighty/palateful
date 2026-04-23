// cmt-6 — end-to-end regression sweep for the cook-mode timer flows.
//
// We can't easily mount the full CookModeScreen without DI, so these
// integration tests compose the public pieces (StepTimer, extractTimers,
// StepTimersRow, disambiguateTimerLabel) to verify the rendering and
// decision rules end to end without duplicating implementation.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/cook_mode/shared/util/timer_regex.dart';
import 'package:palateful/features/recipes/cook_mode/shared/widgets/manual_timer_sheet.dart';
import 'package:palateful/features/recipes/cook_mode/shared/widgets/step_timers_row.dart';

Widget _wrap(Widget child) => MaterialApp(
      home: Scaffold(body: Center(child: child)),
    );

/// Mirrors the branch in cook_mode_screen._buildStepContent: prefer
/// structured timers, fall back to regex. Hybrid is fallback, NOT merge.
List<StepTimer> _resolveStepTimers(List<StepTimer> structured, String text) {
  if (structured.isNotEmpty) return structured;
  return extractTimers(text);
}

void main() {
  group('Path A — extracted timers only', () {
    testWidgets('one structured timer renders one button, ignores regex',
        (tester) async {
      final structured = [
        const StepTimer(durationMinutes: 3, label: 'simmer'),
      ];
      // Instruction ALSO mentions 25 min; hybrid is fallback, the regex
      // must NOT fire when structured is non-empty.
      final resolved = _resolveStepTimers(
        structured,
        'Simmer 3 min then bake 25 min',
      );
      expect(resolved.length, 1);
      expect(resolved.first.durationMinutes, 3);

      await tester.pumpWidget(
        _wrap(StepTimersRow(timers: resolved, onStart: (_, __) {})),
      );
      expect(find.byType(OutlinedButton), findsOneWidget);
      expect(find.text('3 min simmer'), findsOneWidget);
      expect(find.textContaining('25'), findsNothing);
    });
  });

  group('Path B — legacy: no structured timers, regex fires', () {
    testWidgets('Bake 25 min, rotate at 12 -> two buttons', (tester) async {
      final resolved = _resolveStepTimers(
        const [],
        'Bake 25 min, rotate at 12 minutes',
      );
      expect(resolved.length, 2);
      expect(resolved[0].durationMinutes, 25);
      expect(resolved[1].durationMinutes, 12);

      await tester.pumpWidget(
        _wrap(StepTimersRow(timers: resolved, onStart: (_, __) {})),
      );
      expect(find.byType(OutlinedButton), findsNWidgets(2));
    });

    testWidgets('wrong-type JSON timer falls back to regex without crash',
        (tester) async {
      // `{"duration_minutes": "25"}` — string, not int. StepTimer.fromJson
      // returns null so _StepData.timers ends up empty, then regex kicks
      // in and finds "25 minutes" in the instruction.
      final structured = <StepTimer>[];
      final raw = <dynamic>[
        {'duration_minutes': '25', 'label': 'bake'},
      ];
      for (final r in raw) {
        final parsed = StepTimer.fromJson(r);
        if (parsed != null) structured.add(parsed);
      }
      expect(structured, isEmpty);

      final resolved = _resolveStepTimers(structured, 'Bake 25 minutes');
      expect(resolved.length, 1);
      expect(resolved.first.durationMinutes, 25);
    });
  });

  group('Path C — no timers anywhere', () {
    testWidgets('empty structured + no regex match -> no inline buttons',
        (tester) async {
      final resolved = _resolveStepTimers(
        const [],
        'Let the dough rise until doubled',
      );
      expect(resolved, isEmpty);

      await tester.pumpWidget(
        _wrap(StepTimersRow(timers: resolved, onStart: (_, __) {})),
      );
      expect(find.byType(OutlinedButton), findsNothing);
    });
  });

  group('Manual-timer disambiguation end-to-end', () {
    test('two default "Timer" entries become "Timer" + "Timer 2"', () {
      final activeLabels = <String>[];
      // First manual add → "Timer".
      activeLabels.add(
        disambiguateTimerLabel('Timer', activeLabels),
      );
      expect(activeLabels, ['Timer']);
      // Second manual add while first still running → "Timer 2".
      activeLabels.add(
        disambiguateTimerLabel('Timer', activeLabels),
      );
      expect(activeLabels, ['Timer', 'Timer 2']);
      // Third → "Timer 3".
      activeLabels.add(
        disambiguateTimerLabel('Timer', activeLabels),
      );
      expect(activeLabels, ['Timer', 'Timer 2', 'Timer 3']);
    });

    test('distinct manual labels are never disambiguated', () {
      final active = <String>['simmer'];
      expect(disambiguateTimerLabel('bake', active), 'bake');
      expect(disambiguateTimerLabel('rise', active), 'rise');
    });
  });

  group('Defensive parsing end-to-end', () {
    test('_StepData-equivalent parsing strips malformed timers', () {
      // Mirrors cook_mode_screen._StepData.fromJson + StepTimer.fromJson.
      final rawTimers = <dynamic>[
        {'duration_minutes': 10, 'label': 'simmer'}, // ok
        {'duration_minutes': '25', 'label': 'bake'}, // wrong type
        {'duration_minutes': 400, 'label': 'oops'}, // out of range
        {'duration_minutes': 5}, // missing label -> defaults
        'not a dict',
        null,
      ];
      final parsed = <StepTimer>[];
      for (final r in rawTimers) {
        final p = StepTimer.fromJson(r);
        if (p != null) parsed.add(p);
      }
      expect(parsed.length, 2);
      expect(parsed[0].durationMinutes, 10);
      expect(parsed[0].label, 'simmer');
      expect(parsed[1].durationMinutes, 5);
      expect(parsed[1].label, 'timer'); // defaulted
    });
  });
}
