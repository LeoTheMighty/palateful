import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:auth0_flutter_platform_interface/auth0_flutter_platform_interface.dart'
    show Auth0FlutterWebAuthPlatform, WebAuthRequest, WebAuthLoginOptions;
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/error_reporter.dart';
import 'package:palateful/features/auth/login_screen.dart' show isAccountLinkedError;

/// "Sometimes I get a random 'login failed'" — regression guard.
///
/// login() used to catch every exception and return false, so a dismissed
/// sheet, a network error and our Auth0 Action's deliberate account-linking
/// denial all showed the same "Login failed", none left a trace, and the
/// login screen's handler for the account-linked message was unreachable.
void main() {
  late _FakeWebAuth webAuth;
  late List<String?> reportedOps;
  late Auth0FlutterWebAuthPlatform original;

  setUp(() {
    original = Auth0FlutterWebAuthPlatform.instance;
    webAuth = _FakeWebAuth();
    Auth0FlutterWebAuthPlatform.instance = webAuth;
    reportedOps = [];
    ErrorReporter.testReportHook = (error, stack,
        {area, operation, extras, fatal = false}) {
      reportedOps.add(operation);
    };
  });

  tearDown(() {
    Auth0FlutterWebAuthPlatform.instance = original;
    ErrorReporter.testReportHook = null;
  });

  test('a dismissed sign-in sheet returns false and reports nothing', () async {
    webAuth.error = const WebAuthenticationException('USER_CANCELLED', 'cancelled', {});
    final auth = AuthService(credentialsManager: _NoopCredentialsManager());

    expect(await auth.login(), isFalse);
    expect(reportedOps, isEmpty);
    expect(auth.isLoading, isFalse);
  });

  test('any other failure is reported and RETHROWN, not swallowed into false', () async {
    webAuth.error = const WebAuthenticationException(
      'a0.response.invalid',
      'access_denied',
      {'error_description': 'Your accounts have been linked. Please sign in again.'},
    );
    final auth = AuthService(credentialsManager: _NoopCredentialsManager());

    await expectLater(auth.login(), throwsA(isA<WebAuthenticationException>()));
    expect(reportedOps, ['login']);
    expect(auth.isLoading, isFalse);
  });

  test('success returns true and does not store a second time', () async {
    // webAuthentication() defaults to useCredentialsManager: true, so the
    // SDK's login() stores once; AuthService used to store again.
    final cm = _NoopCredentialsManager();
    webAuth.result = Credentials(
      idToken: 'id',
      accessToken: 'at',
      refreshToken: 'rt',
      expiresAt: DateTime.now().add(const Duration(hours: 24)),
      user: const UserProfile(sub: 'auth0|leo'),
      tokenType: 'Bearer',
    );
    final auth = AuthService(credentialsManager: cm);

    expect(await auth.login(), isTrue);
    expect(cm.stores, 1, reason: 'the SDK stores once; AuthService must not add a second');
  });

  group('isAccountLinkedError', () {
    // The Action's text arrives as Auth0's `error_description`; whether the
    // SDK puts it in the message or the details map hasn't been observed on
    // a device, so both must match.
    test('matches the text in the details map', () {
      expect(
        isAccountLinkedError(const WebAuthenticationException(
            'x', 'access_denied', {'error_description': 'Your accounts have been linked'})),
        isTrue,
      );
    });

    test('matches the text in the message', () {
      expect(
        isAccountLinkedError(const WebAuthenticationException(
            'x', 'Your account has been linked, sign in again', {})),
        isTrue,
      );
    });

    test("matches the Action's exact production string, wherever it lands", () {
      // Verbatim from the "Palateful Account Linking" Action's
      // `api.access.deny(...)`, read back from the Auth0 dashboard 2026-09-22.
      // Pinned so a rewording on either side is caught here, not by a user.
      const actionText = 'Your account has been linked. Please sign in again.';
      expect(
        isAccountLinkedError(const WebAuthenticationException('x', actionText, {})),
        isTrue,
      );
      expect(
        isAccountLinkedError(const WebAuthenticationException(
            'x', 'access_denied', {'error_description': actionText})),
        isTrue,
      );
    });

    test('does not match an unrelated failure', () {
      expect(
        isAccountLinkedError(const WebAuthenticationException('x', 'network error', {})),
        isFalse,
      );
    });
  });
}

class _FakeWebAuth extends Auth0FlutterWebAuthPlatform {
  Object? error;
  Credentials? result;

  @override
  Future<Credentials> login(WebAuthRequest<WebAuthLoginOptions> request) async {
    if (error != null) throw error!;
    return result!;
  }
}

/// Counts stores. The SDK's own login() calls storeCredentials on this
/// manager because webAuthentication() defaults to useCredentialsManager.
class _NoopCredentialsManager extends CredentialsManager {
  int stores = 0;

  @override
  Future<Credentials> credentials({
    int minTtl = 0,
    Set<String> scopes = const {},
    Map<String, String> parameters = const {},
  }) async =>
      throw UnimplementedError();

  @override
  Future<Credentials> renewCredentials({Map<String, String> parameters = const {}}) async =>
      throw UnimplementedError();

  @override
  Future<bool> storeCredentials(Credentials credentials) async {
    stores++;
    return true;
  }

  @override
  Future<bool> hasValidCredentials({int minTtl = 0}) async => false;

  @override
  Future<bool> clearCredentials() async => true;
}
