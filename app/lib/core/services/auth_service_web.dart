import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:auth0_flutter/auth0_flutter_web.dart';
import 'package:flutter/foundation.dart';
import 'auth_failure_mode.dart';
import 'error_reporter.dart';
import 'web_session_marker.dart';

/// Web implementation using Auth0Web

/// Distinguishes a first visit from a lost session. See
/// [WebSessionMarker] — the decision lives there so it is testable on the
/// VM; this file is behind a conditional import and cannot be.
final WebSessionMarker _sessionMarker = WebSessionMarker();

/// Persist the session cache in `localStorage`, not in memory.
///
/// **This is the session-loss bug.** The SDK default is `memory`
/// (`auth0_flutter 1.14.0`, `client_options.dart:13`), whose own doc says
/// "the cache is lost on page reload". With it, every reload and every new
/// tab starts with an empty cache and the app depends entirely on silent
/// auth — a hidden-iframe `/authorize?prompt=none` against the Auth0
/// session cookie, which is third-party and increasingly blocked by
/// browsers. When that is blocked the SDK reports `login_required`, which
/// `onLoad` below treats as expected, and the user is silently logged out.
/// `Auth0Web`'s own constructor doc says `localStorage` "is often required
/// for seamless silent authentication on page reloads".
Auth0Web createAuth0Web(String domain, String clientId) {
  debugPrint('Creating Auth0Web with domain=$domain, clientId=$clientId');
  return Auth0Web(
    domain,
    clientId,
    cacheLocation: CacheLocation.localStorage,
  );
}

Future<Credentials?> onLoad(dynamic auth0Web, String audience) async {
  final web = auth0Web as Auth0Web;

  // Check if this is a callback from Auth0 (has code in URL)
  final uri = Uri.base;
  final hasCode = uri.queryParameters.containsKey('code');
  final hasError = uri.queryParameters.containsKey('error');
  // `state` is what makes this OUR redirect rather than any URL that
  // happens to carry `?error=` — a deep link, a shared link, a third-party
  // redirect. Auth0 always round-trips it.
  final hasState = uri.queryParameters.containsKey('state');

  debugPrint('onLoad: hasCode=$hasCode, hasError=$hasError, uri=$uri');
  debugPrint('onLoad: audience=$audience');

  if (hasError) {
    final error = uri.queryParameters['error'];
    final errorDesc = uri.queryParameters['error_description'];
    debugPrint('Auth callback error: $error - $errorDesc');
    // Auth0 redirected back with an error instead of a code — an Action
    // deny (including the account-linking one), a rejected callback URL, a
    // blocked user. Not an exception, so no catch ever saw it; it returned
    // null and the app simply stayed logged out.
    if (hasState) {
      // `state` is what makes this OUR redirect. Without the check, any URL
      // carrying `?error=` reported — and re-reported on every reload,
      // since the parameter stays in the address bar.
      final mode = callbackFailureMode(error, errorDesc);
      if (mode == null) {
        debugPrint('Silent auth declined ($error) — expected, not reported');
      } else {
        ErrorReporter.reportPreAuth(
          Exception('Auth0 callback error: $error'),
          StackTrace.current,
          area: 'auth',
          operation: 'web.onLoad.callbackError',
          extras: {
            'failureMode': mode,
            'error': error,
            'errorDescription': errorDesc,
          },
        );
      }
    }
    return null;
  }

  try {
    // onLoad will handle the callback if code is present,
    // or try silent auth if not
    // Pass audience to ensure we get an access token for the API
    // `useRefreshTokens` is what survives a blocked third-party cookie:
    // renewal then goes through a refresh token held in the (now
    // persistent) cache rather than through an iframe. `Fallback` keeps
    // the iframe as a second attempt where cookies still work.
    // `offline_access` must be in scope for a refresh token to be issued
    // — it already is on `loginWithRedirect` below, and these two have to
    // agree or the refresh token is never granted in the first place.
    final credentials = await web.onLoad(
      audience: audience,
      useRefreshTokens: true,
      useRefreshTokensFallback: true,
      scopes: const {'openid', 'profile', 'email', 'offline_access'},
    );
    debugPrint('onLoad credentials: ${credentials != null}');
    if (credentials != null) {
      // No token prefix — debugPrint ships in release and prints to the
      // browser console.
      debugPrint('Got access token');
      await _sessionMarker.record();
      return credentials;
    }

    // No exception, no credentials: silent auth declined. Expected on a
    // first visit; a **session loss** for anyone who has signed in here
    // before, and reported as such — previously this returned null either
    // way and nothing distinguished them.
    await _reportSessionLossIfAny(
      operation: 'web.onLoad.silentAuthReturnedNull',
      detail: 'no credentials and no error',
    );
    return credentials;
  } catch (e) {
    debugPrint('onLoad threw error: $e');

    // If we had a code in the URL, the SDK might have stored credentials
    // before throwing. Try to retrieve them.
    if (hasCode) {
      try {
        debugPrint('Had code in URL, trying to get stored credentials...');
        final storedCredentials = await web.credentials(audience: audience);
        debugPrint('Got stored credentials');
        return storedCredentials;
      } catch (credError, credSt) {
        debugPrint('Failed to get stored credentials: $credError');
        // Last resort in the callback path: the URL carried a code, so the
        // user did authenticate, and we still ended with no session. Silent
        // until now, which is one of the shapes "login failed" takes.
        ErrorReporter.reportPreAuth(credError, credSt,
            area: 'auth',
            operation: 'web.onLoad.storedCredentials',
            extras: {'failureMode': authFailureMode(credError)});
      }
    }

    // Ignore consent_required errors on silent auth - user just needs to login
    if (e.toString().contains('consent_required') ||
        e.toString().contains('login_required')) {
      // "Expected" only for someone who was never signed in on this
      // browser. For anyone who was, this IS the silent logout — the
      // failure mode Leo reports as "sessions not holding" — so it is
      // reported rather than swallowed.
      debugPrint('Silent auth declined: $e');
      await _reportSessionLossIfAny(
        operation: 'web.onLoad.silentAuthDeclined',
        detail: e.toString().contains('login_required')
            ? 'login_required'
            : 'consent_required',
      );
      return null;
    }
    debugPrint('onLoad error: $e');
    rethrow;
  }
}

/// Report a lost session, and only a lost one.
///
/// Silent auth declining is unremarkable for a browser that has never
/// signed in — reporting it there would bury the real signal in first
/// visits. It is only notable when this browser *had* a session, which is
/// what [WebSessionMarker] records. The marker is consumed so a single loss
/// reports once rather than on every subsequent reload.
Future<void> _reportSessionLossIfAny({
  required String operation,
  required String detail,
}) async {
  if (!await _sessionMarker.consumeIfLost()) {
    debugPrint('Silent auth declined and no prior session here — expected');
    return;
  }
  ErrorReporter.reportPreAuth(
    Exception('Web session lost: $detail'),
    StackTrace.current,
    area: 'auth',
    operation: operation,
    extras: {
      'failureMode': 'sessionLost',
      'detail': detail,
    },
  );
}

/// Returns the current page origin without query params or fragments.
/// Omits default ports (80 for http, 443 for https) so the URL matches
/// what is registered as a callback URL in Auth0 exactly.
String _currentOrigin() {
  final uri = Uri.base;
  final isDefaultPort = (uri.scheme == 'https' && uri.port == 443) ||
      (uri.scheme == 'http' && uri.port == 80) ||
      uri.port == 0;
  final host = isDefaultPort ? uri.host : '${uri.host}:${uri.port}';
  final path = uri.path.isEmpty ? '/' : uri.path;
  return '${uri.scheme}://$host$path';
}

Future<void> loginWithRedirect(dynamic auth0Web, String audience, {String? connection}) async {
  final web = auth0Web as Auth0Web;
  final redirectUrl = _currentOrigin();
  debugPrint('loginWithRedirect: redirectUrl=$redirectUrl, audience=$audience, connection=$connection');

  await web.loginWithRedirect(
    redirectUrl: redirectUrl,
    audience: audience,
    scopes: {'openid', 'profile', 'email', 'offline_access'},
    parameters: {
      'prompt': 'consent',
      if (connection != null) 'connection': connection,
    },
  );
}

Future<void> logout(dynamic auth0Web) async {
  final web = auth0Web as Auth0Web;
  // Cleared before the redirect: a deliberate logout must not leave a
  // marker that makes the next visit's declined silent auth look like a
  // lost session.
  await _sessionMarker.clear();
  await web.logout(returnToUrl: _currentOrigin());
}
