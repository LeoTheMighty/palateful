import 'dart:async';
import 'dart:io' show SocketException;

import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:dio/dio.dart';
import 'package:flutter/services.dart' show PlatformException;

/// Coarse classification of an auth-path failure, attached to every auth
/// report as the `failureMode` custom key.
///
/// Crashlytics groups non-fatals by stack, which for the auth path means one
/// group per call site — `restoreCredentials` covers a revoked refresh token,
/// an Auth0 outage and a Keychain failure alike. These are different
/// incidents with different fixes, so the key exists to tell them apart in
/// the dashboard without opening individual reports.
///
/// Values are stable strings: they are filter terms in Crashlytics, so
/// renaming one orphans the saved filters that use it.
class AuthFailureMode {
  AuthFailureMode._();

  /// The user dismissed the sign-in or logout sheet. Normal, not a defect —
  /// the auth path returns early instead of reporting these.
  static const userCancelled = 'user_cancelled';

  /// Our own Auth0 Action's `api.access.deny()` after it links a second
  /// provider to an existing email. The next sign-in succeeds; the login
  /// screen says so rather than showing a generic failure.
  static const accountLinked = 'account_linked';

  /// Auth0 refused the authorization itself (`access_denied`) for a reason
  /// other than account linking — a rule, an Action, or a blocked user.
  static const accessDenied = 'access_denied';

  /// The SDK wrapped a failed renewal request. Note this is NOT evidence the
  /// refresh token is dead: Auth0.swift reports a timeout, an offline device
  /// and a 5xx under the same code (see the comment in
  /// `AuthService.tryRestoreCredentials`).
  static const renewFailed = 'renew_failed';

  /// Nothing to renew with — the stored credentials carry no refresh token.
  static const noRefreshToken = 'no_refresh_token';

  /// Nothing stored at all. Expected on a first launch; a signal when it
  /// follows a successful login.
  static const noCredentials = 'no_credentials';

  /// The credentials store itself failed — Keychain / EncryptedSharedPrefs
  /// read, write or clear. Distinct from "the token was rejected": the
  /// device could not keep the session, so a re-login will not stick either.
  static const storage = 'storage';

  /// The browser/web-auth leg failed for a transport-shaped reason.
  static const webAuth = 'web_auth';

  /// No connectivity / timed out before any Auth0 verdict.
  static const network = 'network';

  /// Unclassified. A rising count here means this classifier needs a new
  /// branch — check the grouped stacks in Crashlytics.
  static const unknown = 'unknown';
}

/// True when [e] is the denial our Auth0 Action raises after linking a
/// second provider to an existing account.
///
/// Checks the exception's message AND its details: on an `access_denied`
/// redirect Auth0 carries the Action's text as `error_description`, and which
/// of the two fields the SDK lands it in has not been observed on a device —
/// this branch was unreachable until #35 stopped `login()` swallowing.
bool isAccountLinkedError(Object e) {
  final text =
      (e is WebAuthenticationException ? '${e.message} ${e.details}' : '$e')
          .toLowerCase();
  return text.contains('account has been linked') ||
      text.contains('accounts have been linked');
}

/// True when [e] carries an OAuth `access_denied` anywhere the SDK might
/// have put it.
///
/// **Not** a `code` check. The two platforms disagree: Android passes
/// Auth0's literal `access_denied` through as the code
/// (`LoginWebAuthRequestHandler.kt`), while iOS maps every web-auth failure
/// onto a closed set of SCREAMING_SNAKE codes — an Action deny arrives as
/// `OTHER` with the real cause in `message`/`details`
/// (`WebAuthExtensions.swift`, verified against auth0_flutter 1.14.0). A
/// code-only check therefore made this mode dead on iOS, which is the
/// platform the reports we are chasing come from.
bool _isAccessDenied(WebAuthenticationException e) {
  final text = '${e.code} ${e.message} ${e.details}'.toLowerCase();
  return text.contains('access_denied') || text.contains('access denied');
}

/// Classify [e] into an [AuthFailureMode] value.
///
/// Order matters where two tests can both be true: a cancellation is
/// checked first (it is the one non-defect), and the account-linking deny
/// is checked before the general denial it is a kind of.
String authFailureMode(Object e) {
  if (e is WebAuthenticationException) {
    if (e.isUserCancelledException) return AuthFailureMode.userCancelled;
    if (isAccountLinkedError(e)) return AuthFailureMode.accountLinked;
    if (_isAccessDenied(e)) return AuthFailureMode.accessDenied;
    return AuthFailureMode.webAuth;
  }

  if (e is CredentialsManagerException) {
    // These four predicates are exact `code ==` comparisons against
    // disjoint strings in the SDK, so no instance satisfies two and the
    // order here is presentational, not load-bearing.
    if (e.isNoRefreshTokenFound) return AuthFailureMode.noRefreshToken;
    if (e.isNoCredentialsFound) return AuthFailureMode.noCredentials;
    if (e.isTokenRenewFailed) return AuthFailureMode.renewFailed;
    return AuthFailureMode.storage;
  }

  if (e is DioException) {
    // Every HTTP call on the auth path goes through Dio, which wraps
    // SocketException and timeouts rather than letting them through — so
    // without this branch the network mode never fired for the /me fetch
    // or the post-login hand-off.
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.connectionError:
        return AuthFailureMode.network;
      case DioExceptionType.badResponse:
        final status = e.response?.statusCode;
        if (status == 401 || status == 403) return AuthFailureMode.accessDenied;
        return AuthFailureMode.unknown;
      default:
        return AuthFailureMode.unknown;
    }
  }

  if (e is SocketException || e is TimeoutException) {
    return AuthFailureMode.network;
  }

  if (e is PlatformException) {
    // Plugin-channel failures from the credentials store reach us unwrapped
    // when the SDK's own mapping misses. Keychain / KeyStore codes are the
    // ones worth separating from a generic platform error.
    final code = e.code.toLowerCase();
    if (code.contains('keychain') ||
        code.contains('keystore') ||
        code.contains('secure_storage')) {
      return AuthFailureMode.storage;
    }
  }

  return AuthFailureMode.unknown;
}

/// Errors Auth0 returns on a redirect that mean "no session yet", not
/// "something broke".
///
/// `login_required` and `consent_required` are the expected outcomes of a
/// silent-auth attempt in a fresh browser — the same two the web `onLoad`
/// catch already treats as normal. Reporting them from the query-param path
/// while the exception path calls them expected would make one page load
/// look like a failure and the next like a non-event.
const benignCallbackErrors = {'login_required', 'consent_required'};

/// Classify an Auth0 error *redirect* (`?error=&error_description=`).
///
/// Returns null when the redirect is a benign "not signed in yet" outcome
/// that should not be reported at all.
String? callbackFailureMode(String? error, String? errorDescription) {
  final code = error?.toLowerCase();
  if (code != null && benignCallbackErrors.contains(code)) return null;
  if (errorDescription != null && isAccountLinkedError(errorDescription)) {
    return AuthFailureMode.accountLinked;
  }
  if (code == 'access_denied') return AuthFailureMode.accessDenied;
  // server_error, temporarily_unavailable, unauthorized_client,
  // invalid_request, interaction_required — Auth0 failing, not refusing.
  // Calling all of them a denial would hide an outage inside the bucket we
  // watch for deliberate Action denies.
  return AuthFailureMode.webAuth;
}
