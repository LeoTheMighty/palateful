import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/auth_failure_mode.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/error_reporter.dart';

/// Auth hardening regression guard — the two failure modes behind "the login
/// credentials don't hold as long as possible".
///
/// 1. Renewal went through the RAW `api.renewCredentials` plus a manual
///    store. It must go through the MANAGED credentials manager, which
///    serializes renewals (with rotation on and 0 s overlap, two renewals
///    presenting one token revokes the family), persists the result itself,
///    and backfills the refresh token if rotation is ever turned off.
/// 2. Startup restore wiped the saved credentials on RENEW_FAILED — which the
///    SDK raises for any failed renewal request, including a dropped
///    connection. A flaky network at launch therefore destroyed a good
///    refresh token. Only provably-unusable credentials may be cleared.
void main() {
  late _FakeCredentialsManager cm;
  late List<_Report> reports;

  setUp(() {
    cm = _FakeCredentialsManager();
    reports = [];
    ErrorReporter.testReportHook = (error, stack,
        {area, operation, extras, fatal = false}) {
      reports.add(_Report(error, area, operation, extras));
    };
  });

  tearDown(() => ErrorReporter.testReportHook = null);

  group('refreshToken', () {
    test('renews through the MANAGED credentials manager', () async {
      cm.renewResult = _creds(refreshToken: 'rt-kept');
      final auth = AuthService(credentialsManager: cm);

      expect(await auth.refreshToken(), isTrue);
      expect(cm.calls, contains('renewCredentials'));
      expect(auth.accessToken, 'at-new');
    });

    test('does not store after renewing — the managed renew already did', () async {
      // The SDK documents store as not thread-safe against its own managed
      // renewals; a manual store after renewing is exactly what it warns
      // against.
      cm.renewResult = _creds(refreshToken: 'rt-kept');
      final auth = AuthService(credentialsManager: cm);

      await auth.refreshToken();
      expect(cm.calls, isNot(contains('storeCredentials')));
    });

    test('a failed renewal returns false and is reported, not swallowed', () async {
      cm.renewError = _cmError('RENEW_FAILED');
      final auth = AuthService(credentialsManager: cm);

      expect(await auth.refreshToken(), isFalse);
      expect(reports.single.operation, 'refreshToken');
      expect(reports.single.area, 'auth');
    });
  });

  group('tryRestoreCredentials', () {
    test('asks the managed manager to renew anything inside the 5-minute buffer', () async {
      // Restore used to renew only once the token had already expired while
      // `needsRefresh` fired at 5 min, so every cold start in between took
      // a second, raw renewal path. One shared buffer closes that window.
      cm.hasValid = true;
      cm.credentialsResult = _creds(refreshToken: 'rt');
      final auth = AuthService(credentialsManager: cm);

      expect(await auth.tryRestoreCredentials(), isTrue);
      expect(cm.lastMinTtl, 300);
    });

    test('a RENEW_FAILED at launch KEEPS the saved credentials', () async {
      // THE regression. RENEW_FAILED wraps every failed renewal request —
      // no connectivity and timeouts included — so it is not evidence the
      // refresh token is bad.
      cm.hasValid = true;
      cm.credentialsError = _cmError('RENEW_FAILED');
      final auth = AuthService(credentialsManager: cm);

      expect(await auth.tryRestoreCredentials(), isFalse);
      expect(cm.calls, isNot(contains('clearCredentials')));
    });

    test('a RENEW_FAILED at launch is reported with its cause', () async {
      cm.hasValid = true;
      cm.credentialsError = _cmError('RENEW_FAILED', details: {'cause': 'network'});
      final auth = AuthService(credentialsManager: cm);

      await auth.tryRestoreCredentials();
      final r = reports.single;
      expect(r.operation, 'restoreCredentials');
      expect(r.extras?['renewFailed'], isTrue);
      expect(r.extras?['cleared'], isFalse);
      expect(r.extras?['details'], contains('network'));
    });

    test('no refresh token → credentials are unusable and are cleared', () async {
      cm.hasValid = true;
      cm.credentialsError = _cmError('NO_REFRESH_TOKEN');
      final auth = AuthService(credentialsManager: cm);

      expect(await auth.tryRestoreCredentials(), isFalse);
      expect(cm.calls, contains('clearCredentials'));
      expect(reports.single.extras?['cleared'], isTrue);
    });

    test('every restore failure carries a failureMode (authrep1)', () async {
      // Crashlytics groups by stack, so all three land in one group without
      // this key — a transient network blip is then indistinguishable from
      // a revoked token in the dashboard.
      final cases = <String, String>{
        'RENEW_FAILED': AuthFailureMode.renewFailed,
        'NO_REFRESH_TOKEN': AuthFailureMode.noRefreshToken,
        'NO_CREDENTIALS': AuthFailureMode.noCredentials,
      };
      for (final entry in cases.entries) {
        reports.clear();
        final localCm = _FakeCredentialsManager()
          ..hasValid = true
          ..credentialsError = _cmError(entry.key);
        final auth = AuthService(credentialsManager: localCm);

        await auth.tryRestoreCredentials();

        expect(reports.single.extras?['failureMode'], entry.value,
            reason: 'restore failure ${entry.key}');
      }
    });

    test('a non-Auth0 restore failure is still reported (authrep1)', () async {
      // The generic catch used to be the one that reported nothing useful.
      cm.hasValid = true;
      cm.credentialsError = StateError('platform channel died');
      final auth = AuthService(credentialsManager: cm);

      expect(await auth.tryRestoreCredentials(), isFalse);
      expect(reports.single.operation, 'restoreCredentials');
      expect(reports.single.extras?['failureMode'], AuthFailureMode.unknown);
    });

    test('no stored credentials → cleared, and nothing else is disturbed', () async {
      cm.hasValid = true;
      cm.credentialsError = _cmError('NO_CREDENTIALS');
      final auth = AuthService(credentialsManager: cm);

      expect(await auth.tryRestoreCredentials(), isFalse);
      expect(cm.calls, contains('clearCredentials'));
    });
  });
}

// ---------------------------------------------------------------------------

class _Report {
  _Report(this.error, this.area, this.operation, this.extras);
  final Object error;
  final String? area;
  final String? operation;
  final Map<String, Object?>? extras;
}

Credentials _creds({String? refreshToken}) => Credentials(
      idToken: 'id',
      accessToken: 'at-new',
      refreshToken: refreshToken,
      expiresAt: DateTime.now().add(const Duration(hours: 24)),
      user: const UserProfile(sub: 'auth0|leo'),
      tokenType: 'Bearer',
    );

CredentialsManagerException _cmError(String code, {Map<String, dynamic> details = const {}}) =>
    CredentialsManagerException(code, 'fake $code', details);

class _FakeCredentialsManager extends CredentialsManager {
  final calls = <String>[];
  bool hasValid = false;
  Credentials? credentialsResult;
  Object? credentialsError;
  Credentials? renewResult;
  Object? renewError;
  int? lastMinTtl;

  @override
  Future<Credentials> credentials({
    int minTtl = 0,
    Set<String> scopes = const {},
    Map<String, String> parameters = const {},
  }) async {
    calls.add('credentials');
    lastMinTtl = minTtl;
    if (credentialsError != null) throw credentialsError!;
    return credentialsResult!;
  }

  @override
  Future<Credentials> renewCredentials({Map<String, String> parameters = const {}}) async {
    calls.add('renewCredentials');
    if (renewError != null) throw renewError!;
    return renewResult!;
  }

  @override
  Future<bool> storeCredentials(Credentials credentials) async {
    calls.add('storeCredentials');
    return true;
  }

  @override
  Future<bool> hasValidCredentials({int minTtl = 0}) async {
    calls.add('hasValidCredentials');
    return hasValid;
  }

  @override
  Future<bool> clearCredentials() async {
    calls.add('clearCredentials');
    return true;
  }
}
