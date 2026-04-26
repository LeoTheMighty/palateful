import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/services/share_service.dart';

// pos-6a: every share payload appends the canonical tagline. We don't
// invoke the share sheet (`Share.share` opens a native plugin which
// doesn't work in unit tests); we test the pure-string composer that
// the three share methods funnel through.

void main() {
  group('ShareService.appendTagline', () {
    test('appends the canonical tagline to recipe-share text', () {
      final body = 'Check out "Roasted carrots" on Palateful!\n'
          'https://palateful.app/recipes/shared/abc';
      final out = ShareService.appendTagline(body);
      expect(out, contains(body));
      expect(out, endsWith(
        'Get Palateful — free forever: https://palateful.app',
      ));
    });

    test('separates body from tagline with a blank line', () {
      final out = ShareService.appendTagline('hello');
      expect(out, equals(
        'hello\n\nGet Palateful — free forever: https://palateful.app',
      ));
    });

    test('handles empty bodies (degenerate case)', () {
      final out = ShareService.appendTagline('');
      expect(out, equals(
        '\n\nGet Palateful — free forever: https://palateful.app',
      ));
    });
  });
}
