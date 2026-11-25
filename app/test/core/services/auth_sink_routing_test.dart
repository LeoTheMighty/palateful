import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/auth_failure_mode.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/error_reporter.dart';

/// authrep1 AC #2, asserted AT THE CALL SITES.
///
/// `error_reporter_pre_auth_test.dart` proves the library routes correctly;
/// these prove the auth path uses it. The distinction matters: an earlier
/// draft of this work had `testMirrorHook` firing *after* the
/// `testReportHook` early return, so every call-site test passed
/// identically whether the site called `report` or `reportPreAuth` — the
/// AC could have regressed with a green suite.
///
/// `mirrored` in the extras is the sink decision the code made, recorded so
/// the same fact is visible in Crashlytics during triage.
void main() {
  late _FakeCredentialsManager cm;
  late List<String> mirrored;
  late List<Map<String, Object?>?> reportExtras;

  setUp(() {
    cm = _FakeCredentialsManager();
    mirrored = [];
    reportExtras = [];
    ErrorReporter.testMirrorHook = (area, operation) {
      mirrored.add('$area/$operation');
    };
    ErrorReporter.testReportHook = (error, stack,
        {area, operation, extras, fatal = false}) {
      reportExtras.add(extras);
    };
  });

  tearDown(() {
    ErrorReporter.testMirrorHook = null;
    ErrorReporter.testReportHook = null;
  });

  test('a failed restore never reaches the mirror', () async {
    // No token by construction — the mirror endpoint would 401 and
    // `_postMirror` would swallow it, losing the event entirely.
    cm.hasValid = true;
    cm.credentialsError = _cmError('RENEW_FAILED');

    await AuthService(credentialsManager: cm).tryRestoreCredentials();

    expect(mirrored, isEmpty);
  });

  test('a reactive refresh failure (no live token) skips the mirror',
      () async {
    // The ApiClient 401 path: the token on hand was already rejected.
    cm.renewError = _cmError('RENEW_FAILED');
    final auth = AuthService(credentialsManager: cm);

    expect(await auth.refreshToken(), isFalse);
    expect(mirrored, isEmpty);
    expect(reportExtras.single?['mirrored'], isFalse);
    expect(reportExtras.single?['failureMode'], AuthFailureMode.renewFailed);
  });

  test('a proactive refresh failure (token still live) DOES mirror',
      () async {
    // main.dart refreshes inside the 5-minute buffer while the current
    // token is still valid, so the mirror POST can authenticate and the
    // row is queryable by audit_errors.py. Routing by call site instead of
    // by token state threw this away.
    cm.hasValid = true;
    cm.credentialsResult = _creds(refreshToken: 'rt');
    final auth = AuthService(credentialsManager: cm);
    expect(await auth.tryRestoreCredentials(), isTrue,
        reason: 'seeds a live access token');

    cm.renewError = _cmError('RENEW_FAILED');
    mirrored.clear();
    reportExtras.clear();

    expect(await auth.refreshToken(), isFalse);
    expect(mirrored, ['auth/refreshToken']);
    expect(reportExtras.single?['mirrored'], isTrue);
  });

  test('an expired token is not a live token', () async {
    cm.hasValid = true;
    cm.credentialsResult = _creds(
      refreshToken: 'rt',
      expiresAt: DateTime.now().subtract(const Duration(minutes: 1)),
    );
    final auth = AuthService(credentialsManager: cm);
    await auth.tryRestoreCredentials();

    cm.renewError = _cmError('RENEW_FAILED');
    mirrored.clear();

    await auth.refreshToken();
    expect(mirrored, isEmpty);
  });

  test('a logout failure after the session is gone skips the mirror',
      () async {
    // logout() is also called from ApiClient after a refresh failure, when
    // nothing can authenticate a mirror POST.
    cm.clearError = _cmError('STORE_FAILED');
    final auth = AuthService(credentialsManager: cm);

    await auth.logout();

    expect(mirrored, isEmpty);
    expect(
      reportExtras.map((e) => e?['failureMode']),
      contains(AuthFailureMode.storage),
    );
  });
}

// ---------------------------------------------------------------------------

Credentials _creds({String? refreshToken, DateTime? expiresAt}) => Credentials(
      idToken: 'id',
      accessToken: 'at',
      refreshToken: refreshToken,
      expiresAt: expiresAt ?? DateTime.now().add(const Duration(hours: 24)),
      user: const UserProfile(sub: 'auth0|leo'),
      tokenType: 'Bearer',
    );

CredentialsManagerException _cmError(String code) =>
    CredentialsManagerException(code, 'fake $code', const {});

class _FakeCredentialsManager extends CredentialsManager {
  bool hasValid = false;
  Credentials? credentialsResult;
  Object? credentialsError;
  Credentials? renewResult;
  Object? renewError;
  Object? clearError;

  @override
  Future<Credentials> credentials({
    int minTtl = 0,
    Set<String> scopes = const {},
    Map<String, String> parameters = const {},
  }) async {
    if (credentialsError != null) throw credentialsError!;
    return credentialsResult ?? _creds();
  }

  @override
  Future<Credentials> renewCredentials({
    Map<String, String> parameters = const {},
  }) async {
    if (renewError != null) throw renewError!;
    return renewResult ?? _creds();
  }

  @override
  Future<bool> storeCredentials(Credentials credentials) async => true;

  @override
  Future<bool> hasValidCredentials({int minTtl = 0}) async => hasValid;

  @override
  Future<bool> clearCredentials() async {
    if (clearError != null) throw clearError!;
    return true;
  }
}
