// cmt-4 — unit tests for the pure-Dart timer extraction regex.
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/cook_mode/shared/util/timer_regex.dart';

void main() {
  group('extractTimers single-value', () {
    test('simple N minutes', () {
      final timers = extractTimers('Simmer 10 minutes.');
      expect(timers.length, 1);
      expect(timers.first.durationMinutes, 10);
    });

    test('single N min', () {
      final timers = extractTimers('Bake 25 min.');
      expect(timers.length, 1);
      expect(timers.first.durationMinutes, 25);
    });

    test('single N hour converts to minutes', () {
      final timers = extractTimers('Roast 1 hour.');
      expect(timers.length, 1);
      expect(timers.first.durationMinutes, 60);
    });

    test('single N sec converts and rounds to at least 1 min', () {
      final timers = extractTimers('Whisk 30 sec.');
      expect(timers.length, 1);
      expect(timers.first.durationMinutes, 1); // clamp floor at 1 min
    });

    test('multi-match in one step', () {
      final timers = extractTimers(
        'Bake 25 min, rotate at 12 minutes, broil 2 min.',
      );
      expect(timers.length, 3);
      expect(timers.map((t) => t.durationMinutes), [25, 12, 2]);
    });

    test('alias: hr/hrs', () {
      final timers = extractTimers('Rest 2 hrs.');
      expect(timers.first.durationMinutes, 120);
    });
  });

  group('extractTimers range', () {
    test('N-M minutes takes lower and sets rangeUpperLabel', () {
      final timers = extractTimers('Simmer 3-5 minutes.');
      expect(timers.length, 1);
      expect(timers.first.durationMinutes, 3);
      expect(timers.first.rangeUpperLabel, '3–5 min in recipe');
    });

    test('N–M with en-dash', () {
      final timers = extractTimers('Bake 10–12 minutes.');
      expect(timers.first.durationMinutes, 10);
      expect(timers.first.rangeUpperLabel, '10–12 min in recipe');
    });

    test('N to M minutes', () {
      final timers = extractTimers('Cook for 1 to 2 minutes.');
      expect(timers.first.durationMinutes, 1);
      expect(timers.first.rangeUpperLabel, '1–2 min in recipe');
    });

    test('ranges suppress overlapping single matches', () {
      // Without suppression, this would emit 3, 5, 3, 5 ...
      final timers = extractTimers('Simmer 3-5 min.');
      expect(timers.length, 1);
      expect(timers.first.durationMinutes, 3);
    });
  });

  group('extractTimers decimals', () {
    test('0.5 hour -> 30 min', () {
      final timers = extractTimers('Rest 0.5 hour.');
      expect(timers.first.durationMinutes, 30);
    });

    test('1.5 hr -> 90 min', () {
      final timers = extractTimers('Simmer 1.5 hr.');
      expect(timers.first.durationMinutes, 90);
    });
  });

  group('extractTimers edge cases', () {
    test('empty string returns empty list', () {
      expect(extractTimers(''), isEmpty);
    });

    test('whitespace-only returns empty list', () {
      expect(extractTimers('   \n\t  '), isEmpty);
    });

    test('no duration mentioned returns empty', () {
      expect(extractTimers('Let rise until doubled.'), isEmpty);
    });

    test('malformed "two minutes" returns empty', () {
      expect(extractTimers('Bake for two minutes.'), isEmpty);
    });

    test('2000-char cap does not hang', () {
      final big = 'Bake 10 min. ' * 2000;
      final timers = extractTimers(big);
      expect(timers.length, lessThanOrEqualTo(10));
    });

    test('max 10 matches returned even if more present', () {
      final many = List.generate(20, (i) => '${i + 1} min').join(' then ');
      final timers = extractTimers(many);
      expect(timers.length, 10);
    });

    test('durations > 360 min clamp to 360', () {
      final timers = extractTimers('Rest 10 hours.');
      expect(timers.first.durationMinutes, 360);
    });
  });

  group('StepTimer.fromJson', () {
    test('valid dict', () {
      final t = StepTimer.fromJson({
        'duration_minutes': 10,
        'label': 'simmer',
      });
      expect(t, isNotNull);
      expect(t!.durationMinutes, 10);
      expect(t.label, 'simmer');
    });

    test('string duration returns null', () {
      expect(
        StepTimer.fromJson({'duration_minutes': '10', 'label': 'x'}),
        isNull,
      );
    });

    test('out of range returns null', () {
      expect(
        StepTimer.fromJson({'duration_minutes': 0, 'label': 'x'}),
        isNull,
      );
      expect(
        StepTimer.fromJson({'duration_minutes': 400, 'label': 'x'}),
        isNull,
      );
    });

    test('empty label defaults to "timer"', () {
      final t = StepTimer.fromJson({'duration_minutes': 5, 'label': ''});
      expect(t?.label, 'timer');
    });

    test('overlong label truncated to 40 chars', () {
      final t = StepTimer.fromJson({
        'duration_minutes': 5,
        'label': 'a' * 80,
      });
      expect(t?.label.length, 40);
    });

    test('non-map input returns null', () {
      expect(StepTimer.fromJson(null), isNull);
      expect(StepTimer.fromJson('bogus'), isNull);
      expect(StepTimer.fromJson(42), isNull);
    });
  });
}
