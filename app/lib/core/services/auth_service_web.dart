import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:auth0_flutter/auth0_flutter_web.dart';
import 'package:flutter/foundation.dart';

import 'auth_failure_mode.dart';
import 'error_reporter.dart';

/// Web implementation using Auth0Web

Auth0Web createAuth0Web(String domain, String clientId) {
  debugPrint('Creating Auth0Web with domain=$domain, clientId=$clientId');
  return Auth0Web(domain, clientId);
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
    final credentials = await web.onLoad(audience: audience);
    debugPrint('onLoad credentials: ${credentials != null}');
    if (credentials != null) {
      // No token prefix — debugPrint ships in release and prints to the
      // browser console.
      debugPrint('Got access token');
    }
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
      debugPrint('Silent auth failed (expected): $e');
      return null;
    }
    debugPrint('onLoad error: $e');
    rethrow;
  }
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
  await web.logout(returnToUrl: _currentOrigin());
}
