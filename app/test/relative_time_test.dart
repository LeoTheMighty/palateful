import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/cook_mode/util/relative_time.dart';

void main() {
  final now = DateTime(2026, 4, 22, 12);

  test('< 1 minute returns "just now"', () {
    expect(relativeTime(now.subtract(const Duration(seconds: 30)), now: now),
        'just now');
    expect(relativeTime(now, now: now), 'just now');
  });

  test('future timestamps clamp to "just now"', () {
    expect(relativeTime(now.add(const Duration(minutes: 5)), now: now),
        'just now');
  });

  test('1 min ago uses singular', () {
    expect(relativeTime(now.subtract(const Duration(minutes: 1)), now: now),
        '1 min ago');
  });

  test('N min ago uses plural', () {
    expect(relativeTime(now.subtract(const Duration(minutes: 5)), now: now),
        '5 min ago');
    expect(relativeTime(now.subtract(const Duration(minutes: 59)), now: now),
        '59 min ago');
  });

  test('1 h ago and N h ago', () {
    expect(relativeTime(now.subtract(const Duration(hours: 1)), now: now),
        '1 h ago');
    expect(relativeTime(now.subtract(const Duration(hours: 5)), now: now),
        '5 h ago');
    expect(relativeTime(now.subtract(const Duration(hours: 23)), now: now),
        '23 h ago');
  });

  test('yesterday at the 24–48h window', () {
    expect(relativeTime(now.subtract(const Duration(hours: 24)), now: now),
        'yesterday');
    expect(
        relativeTime(now.subtract(const Duration(hours: 47, minutes: 59)),
            now: now),
        'yesterday');
  });

  test('N days ago at the 2–7 day window', () {
    expect(relativeTime(now.subtract(const Duration(days: 2)), now: now),
        '2 days ago');
    expect(relativeTime(now.subtract(const Duration(days: 6)), now: now),
        '6 days ago');
  });

  test('1 week ago and N weeks ago beyond 7 days', () {
    expect(relativeTime(now.subtract(const Duration(days: 7)), now: now),
        '1 week ago');
    expect(relativeTime(now.subtract(const Duration(days: 14)), now: now),
        '2 weeks ago');
    expect(relativeTime(now.subtract(const Duration(days: 30)), now: now),
        '4 weeks ago');
  });
}
