import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/core/utils/fraction_parser.dart';

void main() {
  group('parseFraction', () {
    test('null and empty → null', () {
      expect(parseFraction(null), isNull);
      expect(parseFraction(''), isNull);
      expect(parseFraction('   '), isNull);
    });

    test('integer strings', () {
      expect(parseFraction('0'), 0);
      expect(parseFraction('1'), 1);
      expect(parseFraction('42'), 42);
    });

    test('decimal strings', () {
      expect(parseFraction('0.5'), 0.5);
      expect(parseFraction('1.25'), 1.25);
      expect(parseFraction('0.333'), closeTo(0.333, 1e-9));
    });

    test('simple fractions', () {
      expect(parseFraction('1/2'), 0.5);
      expect(parseFraction('3/4'), 0.75);
      expect(parseFraction('1/3'), closeTo(1 / 3, 1e-9));
    });

    test('mixed numbers', () {
      expect(parseFraction('1 1/2'), 1.5);
      expect(parseFraction('2 1/4'), 2.25);
      expect(parseFraction('3 3/8'), 3.375);
    });

    test('malformed strings → null', () {
      expect(parseFraction('1//2'), isNull);
      expect(parseFraction('abc'), isNull);
      expect(parseFraction('1/a'), isNull);
      expect(parseFraction('1 1'), isNull);
    });

    test('divide-by-zero → null', () {
      expect(parseFraction('1/0'), isNull);
    });
  });

  group('formatFraction (limit_denominator=8)', () {
    test('integers format as plain integers', () {
      expect(formatFraction(0), '0');
      expect(formatFraction(1), '1');
      expect(formatFraction(42), '42');
    });

    test('common kitchen fractions', () {
      expect(formatFraction(0.5), '1/2');
      expect(formatFraction(0.25), '1/4');
      expect(formatFraction(0.75), '3/4');
      expect(formatFraction(0.125), '1/8');
      expect(formatFraction(0.375), '3/8');
    });

    test('thirds survive because 3 ≤ 8', () {
      expect(formatFraction(1 / 3), '1/3');
      expect(formatFraction(2 / 3), '2/3');
    });

    test('mixed numbers', () {
      expect(formatFraction(1.25), '1 1/4');
      expect(formatFraction(1.5), '1 1/2');
      expect(formatFraction(2.5), '2 1/2');
      expect(formatFraction(2.25), '2 1/4');
    });

    test('approximate thirds (0.333) round to 1/3', () {
      expect(formatFraction(0.333), '1/3');
    });

    test('0.1 snaps to 1/8 since 10 > 8 (closest denom ≤ 8)', () {
      // 1/10 with max denom 8 → nearest is 1/8 (0.125) or 1/9…but
      // limit_denominator(8) on Python Fraction(0.1) returns 1/8? Let's
      // verify the behavior: minimal |0.1 - n/d| for d=1..8 is n=1,d=8
      // (err 0.025) vs d=7,n=1 (err ≈ 0.043). So 1/8 wins.
      expect(formatFraction(0.1), '1/8');
    });

    test('round-trip: format then parse', () {
      for (final v in [0.5, 0.25, 0.75, 1 / 3, 2 / 3, 1.25, 2.5]) {
        final formatted = formatFraction(v);
        final reparsed = parseFraction(formatted);
        expect(reparsed, closeTo(v, 0.01),
            reason: 'round-trip for $v → "$formatted" → $reparsed');
      }
    });

    test('rounding edge case: 0.999 → 1', () {
      expect(formatFraction(0.999), '1');
    });

    test('NaN and Infinity are safe', () {
      expect(formatFraction(double.nan), '');
      expect(formatFraction(double.infinity), '');
    });
  });
}
