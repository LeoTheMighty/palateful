import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/config/auth0_urls.dart';
import 'package:palateful/core/config/environment.dart';

/// lgort1 regression guard.
///
/// `AuthService.logout()` must never hand a hand-built `returnTo` to
/// `auth0_flutter`; these expectations pin what the SDK builds for itself
/// so that (a) the exact strings that belong in Auth0's **Allowed Callback
/// URLs** / **Allowed Logout URLs** lists are written down somewhere
/// executable, and (b) anyone tempted to reconstruct the URL by hand trips
/// the "scheme is not the bundle id" case below.
void main() {
  // Real values: iOS PRODUCT_BUNDLE_IDENTIFIER
  // (app/ios/Runner.xcodeproj/project.pbxproj) and Android applicationId
  // (app/android/app/build.gradle.kts) are both com.palateful.palateful.
  const packageName = 'com.palateful.palateful';

  group('auth0DefaultRedirectUrl', () {
    test('iOS uses the bundle id as BOTH scheme and path segment', () {
      expect(
        auth0DefaultRedirectUrl(
          isIOS: true,
          domain: 'auth.palateful.app',
          packageName: packageName,
          scheme: 'com.palateful.app',
        ),
        'com.palateful.palateful://auth.palateful.app/ios/com.palateful.palateful/callback',
      );
    });

    test('Android uses the custom scheme and the applicationId path', () {
      expect(
        auth0DefaultRedirectUrl(
          isIOS: false,
          domain: 'auth.palateful.app',
          packageName: packageName,
          scheme: 'com.palateful.app',
        ),
        'com.palateful.app://auth.palateful.app/android/com.palateful.palateful/callback',
      );
    });

    test('the custom scheme never reaches the path segment on either platform',
        () {
      // This is the exact shape bas-1 (f839f67) shipped and lgort1 reverts:
      // com.palateful.app://auth.palateful.app/ios/com.palateful.app/callback
      const malformed =
          'com.palateful.app://auth.palateful.app/ios/com.palateful.app/callback';
      for (final isIOS in [true, false]) {
        final url = auth0DefaultRedirectUrl(
          isIOS: isIOS,
          domain: Environment.auth0Domain,
          packageName: packageName,
          scheme: Environment.auth0Scheme,
        );
        expect(url, isNot(malformed));
        expect(
          url,
          endsWith('/$packageName/callback'),
          reason: 'the path segment is the bundle id / applicationId, '
              'never Environment.auth0Scheme',
        );
      }
    });

    test('scheme and packageName really are different strings in this app', () {
      // If these ever converge the lgort1 defect becomes invisible, so the
      // guard above would silently stop guarding anything.
      expect(Environment.auth0Scheme, isNot(packageName));
    });
  });
}
