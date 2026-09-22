import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/pantry/widgets/fuzzy_expiry_text.dart';

void main() {
  // Every DateTime below is tagged `no-time-travel`, and for a stronger
  // reason than usual: this group injects its own `now`, so it never reads
  // the wall clock and cannot rot. Shifting both sides is not a no-op
  // though — a 406-day shift lands the 2026-04-16 → 2026-04-21 interval
  // across the 2025 spring-forward, which shortens the delta by an hour
  // and drops `inDays` from 5 to 4, failing three assertions that are
  // perfectly correct. That is a harness false positive, not a fuse.
  group('fuzzyExpiry', () {
    final now = DateTime(2026, 4, 16, 12, 0);  // no-time-travel

    test('null → No expiry set', () {
      final r = fuzzyExpiry(null, now: now);
      expect(r.label, 'No expiry set');
      expect(r.urgency, ExpiryUrgency.none);
    });

    test('same day → Expires today', () {
      final r = fuzzyExpiry(DateTime(2026, 4, 16, 20, 0), now: now);  // no-time-travel
      expect(r.label, 'Expires today');
      expect(r.urgency, ExpiryUrgency.today);
    });

    test('1 day → Expires tomorrow', () {
      final r = fuzzyExpiry(DateTime(2026, 4, 17, 9, 0), now: now);  // no-time-travel
      expect(r.label, 'Expires tomorrow');
      expect(r.urgency, ExpiryUrgency.tomorrow);
    });

    test('2 days → Expires in 2 days (soon)', () {
      final r = fuzzyExpiry(DateTime(2026, 4, 18), now: now);  // no-time-travel
      expect(r.label, 'Expires in 2 days');
      expect(r.urgency, ExpiryUrgency.soon);
    });

    test('5 days → Good for ~5 days (fresh)', () {
      final r = fuzzyExpiry(DateTime(2026, 4, 21), now: now);  // no-time-travel
      expect(r.label, 'Good for ~5 days');
      expect(r.urgency, ExpiryUrgency.fresh);
    });

    test('30 days → Good for ~30 days (plenty)', () {
      final r = fuzzyExpiry(DateTime(2026, 5, 16), now: now);  // no-time-travel
      expect(r.label, 'Good for ~30 days');
      expect(r.urgency, ExpiryUrgency.plenty);
    });

    test('past → Expired', () {
      final r = fuzzyExpiry(DateTime(2026, 4, 14), now: now);  // no-time-travel
      expect(r.label, 'Expired');
      expect(r.urgency, ExpiryUrgency.expired);
    });

    test('boundary: 7 days → fresh (not plenty)', () {
      final r = fuzzyExpiry(DateTime(2026, 4, 23), now: now);  // no-time-travel
      expect(r.urgency, ExpiryUrgency.fresh);
    });

    test('boundary: 8 days → plenty', () {
      final r = fuzzyExpiry(DateTime(2026, 4, 24), now: now);  // no-time-travel
      expect(r.urgency, ExpiryUrgency.plenty);
    });
  });
}
