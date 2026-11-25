/// The URL Auth0 is told to come back to.
///
/// **A true origin — scheme, host, port. No path.** Auth0 matches
/// `returnTo` / `redirect_uri` against a registered allowlist, so every
/// distinct value has to be registered by hand. An origin is one entry;
/// origin-plus-path is one entry per route, which is an open-ended set.
///
/// This lived inside `auth_service_web.dart` as `_currentOrigin()`, was
/// documented as "the current page origin", and **appended `uri.path`**.
/// It returned the right answer anyway for as long as the app used hash
/// URLs: the route lived in the fragment, `Uri.base.path` was always `/`,
/// and the bug could not fire. Switching to path URLs (#115) made the
/// path real, so logging in or out from `/pantry` asked Auth0 to return to
/// `https://palateful.app/pantry` — unregistered, rejected, "Oops!,
/// something went wrong".
///
/// **The function was correct for a reason nobody knew it depended on.**
/// Extracted here so it is unit-testable: as a private function in a file
/// behind a `dart.library.html` conditional import, nothing could assert
/// on it, which is why a mismatch between its name, its doc and its body
/// survived.
String authReturnUrl(Uri base) {
  final isDefaultPort = (base.scheme == 'https' && base.port == 443) ||
      (base.scheme == 'http' && base.port == 80) ||
      base.port == 0;
  final host = isDefaultPort ? base.host : '${base.host}:${base.port}';
  // Trailing slash, not a bare origin: Auth0 registrations are exact
  // strings, and `https://palateful.app/` is the form already registered.
  return '${base.scheme}://$host/';
}
