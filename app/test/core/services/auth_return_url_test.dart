import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/auth_return_url.dart';

/// Auth0 rejected every non-Home route after path URLs shipped.
///
/// `_currentOrigin()` was documented as "the current page origin" and
/// appended `uri.path`. That was invisible while the app used hash URLs —
/// the route lived in the fragment, so `Uri.base.path` was always `/` and
/// the function returned the right answer **for a reason nobody knew it
/// depended on**. #115 made the path real; logging out from `/login` then
/// asked Auth0 to return to `https://palateful.app/login`, which is not a
/// registered URL, and the user got "Oops!, something went wrong".
///
/// Observed by 0e on the deployed site:
///   auth.palateful.app/v2/logout?…&returnTo=https%3A%2F%2Fpalateful.app%2Flogin
void main() {
  group('the path is dropped — this is the regression', () {
    test('a route path does not reach Auth0', () {
      expect(
        authReturnUrl(Uri.parse('https://palateful.app/pantry')),
        'https://palateful.app/',
      );
      expect(
        authReturnUrl(Uri.parse('https://palateful.app/login')),
        'https://palateful.app/',
        reason: 'the exact URL 0e saw rejected',
      );
    });

    test('a nested path does not reach Auth0 either', () {
      expect(
        authReturnUrl(Uri.parse('https://palateful.app/recipes/abc/edit')),
        'https://palateful.app/',
      );
    });

    test('query and fragment are dropped', () {
      expect(
        authReturnUrl(
            Uri.parse('https://palateful.app/activity?tab=imports#frag')),
        'https://palateful.app/',
      );
    });

    test('a hash-form URL gives the same answer', () {
      // The old behaviour, preserved: this is what made the bug dormant.
      expect(
        authReturnUrl(Uri.parse('https://palateful.app/#/pantry')),
        'https://palateful.app/',
      );
    });
  });

  group('the parts that must not change', () {
    test('default ports are omitted, so it matches the registration', () {
      expect(authReturnUrl(Uri.parse('https://palateful.app:443/x')),
          'https://palateful.app/');
      expect(authReturnUrl(Uri.parse('http://example.test:80/x')),
          'http://example.test/');
    });

    test('a non-default port is kept — local dev is a real callback URL', () {
      expect(authReturnUrl(Uri.parse('http://localhost:8080/pantry')),
          'http://localhost:8080/');
    });

    test('the trailing slash is present', () {
      // Auth0 registrations are exact strings; `https://palateful.app` and
      // `https://palateful.app/` are not interchangeable.
      expect(authReturnUrl(Uri.parse('https://palateful.app')),
          endsWith('/'));
    });

    test('the scheme is preserved', () {
      expect(authReturnUrl(Uri.parse('http://localhost:3000/')),
          startsWith('http://'));
    });
  });
}
