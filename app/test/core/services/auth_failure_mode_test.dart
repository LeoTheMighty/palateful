import 'dart:async';
import 'dart:io' show SocketException;

import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:dio/dio.dart';
import 'package:flutter/services.dart' show PlatformException;
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/auth_failure_mode.dart';

/// authrep1 AC #1: an auth report has to carry enough context to tell the
/// failure modes apart. Crashlytics groups non-fatals by stack, so without
/// this key every `restoreCredentials` failure — revoked token, Auth0
/// outage, Keychain fault — lands in one group.
void main() {
  group('authFailureMode — credentials manager', () {
    test('no refresh token wins over the renewal wrapper', () {
      // The SDK can report both; "nothing to renew with" is the specific,
      // actionable one, and it is the branch that wipes the session.
      const e = CredentialsManagerException(
        'NO_REFRESH_TOKEN',
        'No refresh token found',
        {},
      );
      expect(e.isNoRefreshTokenFound, isTrue,
          reason: 'guards against an SDK code change silently reclassifying');
      expect(authFailureMode(e), AuthFailureMode.noRefreshToken);
    });

    test('no credentials found', () {
      const e = CredentialsManagerException(
        'NO_CREDENTIALS',
        'No credentials were found',
        {},
      );
      expect(authFailureMode(e), AuthFailureMode.noCredentials);
    });

    test('RENEW_FAILED — the cold-start blip, kept distinct from a revoke', () {
      const e = CredentialsManagerException(
        'RENEW_FAILED',
        'Failed to renew credentials',
        {},
      );
      expect(authFailureMode(e), AuthFailureMode.renewFailed);
    });

    test('any other credentials-manager failure is a storage failure', () {
      const e = CredentialsManagerException(
        'STORE_FAILED',
        'Failed to store credentials',
        {},
      );
      expect(authFailureMode(e), AuthFailureMode.storage);
    });
  });

  group('authFailureMode — web auth', () {
    test('user cancellation is its own mode, never reported as a failure', () {
      const e = WebAuthenticationException(
        'USER_CANCELLED',
        'The user cancelled the flow',
        {},
      );
      expect(authFailureMode(e), AuthFailureMode.userCancelled);
    });

    test('account-linking deny beats the generic access_denied', () {
      // Our Action's own text. The next sign-in succeeds, so this must not
      // read as a failure in the dashboard.
      const e = WebAuthenticationException(
        'access_denied',
        'Your accounts have been linked. Please sign in again.',
        {},
      );
      expect(authFailureMode(e), AuthFailureMode.accountLinked);
    });

    test('account-linking text carried in details, not message', () {
      // Which of the two fields Auth0 lands the Action text in has never
      // been observed on a device — check both, or the branch is
      // unreachable exactly when it matters.
      const e = WebAuthenticationException(
        'access_denied',
        'Access denied',
        {'error_description': 'This account has been linked to your other one'},
      );
      expect(authFailureMode(e), AuthFailureMode.accountLinked);
    });

    test('other access_denied — a rule, a blocked user', () {
      const e = WebAuthenticationException(
        'access_denied',
        'User is blocked',
        {},
      );
      expect(authFailureMode(e), AuthFailureMode.accessDenied);
    });

    test('anything else from the browser leg', () {
      const e = WebAuthenticationException('a0.invalid_state', 'Bad state', {});
      expect(authFailureMode(e), AuthFailureMode.webAuth);
    });
  });

  group('authFailureMode — transport and platform', () {
    test('socket failure', () {
      expect(authFailureMode(const SocketException('no route to host')),
          AuthFailureMode.network);
    });

    test('timeout', () {
      expect(authFailureMode(TimeoutException('renew', const Duration(seconds: 3))),
          AuthFailureMode.network);
    });

    test('keychain platform error is storage, not unknown', () {
      expect(
        authFailureMode(PlatformException(code: 'keychain_error')),
        AuthFailureMode.storage,
      );
    });

    test('an unmapped error is unknown, not silently mislabelled', () {
      expect(authFailureMode(StateError('boom')), AuthFailureMode.unknown);
      expect(authFailureMode(PlatformException(code: 'something_else')),
          AuthFailureMode.unknown);
    });
  });

  group('authFailureMode — the iOS shape (the reporting platform)', () {
    // iOS does NOT pass Auth0's OAuth code through. WebAuthExtensions.swift
    // maps every web-auth failure onto a closed set of SCREAMING_SNAKE
    // codes, so an Action deny arrives as OTHER with the real cause in
    // message/details. A code-only check made accessDenied dead on the one
    // platform these reports come from.
    test('an Action deny arrives as OTHER + cause, and still classifies', () {
      const e = WebAuthenticationException(
        'OTHER',
        'An unexpected error occurred.',
        {'cause': 'Access denied: user is blocked'},
      );
      expect(authFailureMode(e), AuthFailureMode.accessDenied);
    });

    test('the account-linking deny survives the same shape', () {
      const e = WebAuthenticationException(
        'OTHER',
        'An unexpected error occurred.',
        {'cause': 'Your accounts have been linked. Please sign in again.'},
      );
      expect(authFailureMode(e), AuthFailureMode.accountLinked);
    });

    test('an unrelated OTHER is not promoted to a denial', () {
      const e = WebAuthenticationException(
        'OTHER',
        'An unexpected error occurred.',
        {'cause': 'The operation could not be completed.'},
      );
      expect(authFailureMode(e), AuthFailureMode.webAuth);
    });
  });

  group('authFailureMode — DioException', () {
    // Every HTTP call on the auth path goes through Dio, which WRAPS
    // SocketException and timeouts. Without a Dio branch the network mode
    // never fired for the /me fetch or the post-login hand-off.
    DioException dio(DioExceptionType type, {int? status}) {
      final req = RequestOptions(path: '/v1/users/me');
      return DioException(
        requestOptions: req,
        type: type,
        response: status == null
            ? null
            : Response<dynamic>(requestOptions: req, statusCode: status),
      );
    }

    test('timeouts and connection errors are network, not unknown', () {
      for (final type in [
        DioExceptionType.connectionTimeout,
        DioExceptionType.sendTimeout,
        DioExceptionType.receiveTimeout,
        DioExceptionType.connectionError,
      ]) {
        expect(authFailureMode(dio(type)), AuthFailureMode.network,
            reason: '$type');
      }
    });

    test('401 and 403 are a denial', () {
      expect(authFailureMode(dio(DioExceptionType.badResponse, status: 401)),
          AuthFailureMode.accessDenied);
      expect(authFailureMode(dio(DioExceptionType.badResponse, status: 403)),
          AuthFailureMode.accessDenied);
    });

    test('a 500 is not a denial', () {
      expect(authFailureMode(dio(DioExceptionType.badResponse, status: 500)),
          AuthFailureMode.unknown);
    });
  });

  group('callbackFailureMode — the error REDIRECT, which throws nothing', () {
    test('silent-auth declines are benign and must not be reported', () {
      // The exception path already treats these as expected; reporting them
      // from the query-param path would make one page load look like a
      // failure and the next like a non-event.
      expect(callbackFailureMode('login_required', null), isNull);
      expect(callbackFailureMode('consent_required', 'Consent required'),
          isNull);
    });

    test('our Action deny classifies from error_description', () {
      expect(
        callbackFailureMode(
            'access_denied', 'Your accounts have been linked!'),
        AuthFailureMode.accountLinked,
      );
    });

    test('access_denied without the linking text is a plain denial', () {
      expect(callbackFailureMode('access_denied', 'user is blocked'),
          AuthFailureMode.accessDenied);
    });

    test('Auth0 failing is not Auth0 refusing', () {
      // Bucketing an outage as a denial would hide it inside the bucket we
      // watch for deliberate Action denies.
      for (final code in [
        'server_error',
        'temporarily_unavailable',
        'unauthorized_client',
        'invalid_request',
      ]) {
        expect(callbackFailureMode(code, null), AuthFailureMode.webAuth,
            reason: code);
      }
    });
  });

  group('isAccountLinkedError', () {
    test('matches both phrasings the Action has used', () {
      expect(isAccountLinkedError('Your accounts have been linked!'), isTrue);
      expect(isAccountLinkedError('This account has been linked'), isTrue);
    });

    test('does not match an unrelated denial', () {
      expect(isAccountLinkedError('User is blocked'), isFalse);
    });
  });
}
