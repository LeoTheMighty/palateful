/// Stub implementation for non-web platforms
/// These functions are never called on mobile - they exist only to satisfy the compiler
library;

dynamic createAuth0Web(String domain, String clientId) {
  throw UnsupportedError('Auth0Web is only supported on web');
}

Future<dynamic> onLoad(dynamic auth0Web, String audience) async {
  throw UnsupportedError('Auth0Web is only supported on web');
}

Future<void> loginWithRedirect(dynamic auth0Web, String audience, {String? connection}) async {
  throw UnsupportedError('Auth0Web is only supported on web');
}

Future<void> logout(dynamic auth0Web) async {
  throw UnsupportedError('Auth0Web is only supported on web');
}
