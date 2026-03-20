import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:auth0_flutter/auth0_flutter_web.dart';
import 'package:flutter/foundation.dart';

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

  debugPrint('onLoad: hasCode=$hasCode, hasError=$hasError, uri=$uri');
  debugPrint('onLoad: audience=$audience');

  if (hasError) {
    final error = uri.queryParameters['error'];
    final errorDesc = uri.queryParameters['error_description'];
    debugPrint('Auth callback error: $error - $errorDesc');
    return null;
  }

  try {
    // onLoad will handle the callback if code is present,
    // or try silent auth if not
    // Pass audience to ensure we get an access token for the API
    final credentials = await web.onLoad(audience: audience);
    debugPrint('onLoad credentials: ${credentials != null}');
    if (credentials != null) {
      debugPrint('Got access token: ${credentials.accessToken.substring(0, 20)}...');
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
        debugPrint('Got stored credentials: ${storedCredentials.accessToken.substring(0, 20)}...');
        return storedCredentials;
      } catch (credError) {
        debugPrint('Failed to get stored credentials: $credError');
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
