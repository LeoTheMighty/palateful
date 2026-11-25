/// Pure reconstruction of the redirect URL that `auth0_flutter`'s native
/// SDKs build for themselves when no explicit `redirectUrl` (login) or
/// `returnTo` (logout) is supplied.
///
/// Nothing in the app should ever *send* one of these strings — the SDK
/// already builds the right one, and hand-building it is how lgort1 shipped
/// a URL Auth0 rejected. The value of having it here is that it is the
/// string Auth0's **Allowed Callback URLs** / **Allowed Logout URLs** lists
/// must contain, so it is worth being able to print it on-device and pin it
/// in a test.
///
/// Derivations, from the vendored SDK sources rather than the README:
///
/// * **iOS** — `Auth0WebAuth.redirectURL` (Auth0.swift 2.10.0,
///   `app/ios/Pods/Auth0/Auth0/Auth0WebAuth.swift:41-62`) builds
///   `<scheme>://<domain>/<platform>/<bundleId>/callback` where `scheme` is
///   `Bundle.main.bundleIdentifier` (it is only `https` when `useHTTPS` is
///   set, which `auth0_flutter` leaves `false` by default). The *same*
///   property is used by both `start()` (login) and `clearSession()`
///   (logout), so the login callback URL and the logout `returnTo` are
///   byte-identical on iOS.
///
///   Note the custom scheme passed to `Auth0.webAuthentication(scheme:)` is
///   **ignored on iOS** — `darwin/Classes/WebAuth/*MethodHandler.swift`
///   never reads a `scheme` argument. It is an Android-only knob.
///
/// * **Android** — `LogoutWebAuthRequestHandler` /
///   `LoginWebAuthRequestHandler` forward the Dart `scheme` to
///   `WebAuthProvider.…Builder.withScheme`, and Auth0.android builds
///   `<scheme>://<domain>/android/<packageName>/callback`. This is also the
///   shape auth0_flutter's own `AndroidManifest.xml` registers for
///   `RedirectActivity` (`android:pathPrefix="/android/${applicationId}/callback"`).
///
/// [packageName] is the runtime bundle identifier / application id — read it
/// from `PackageInfo.fromPlatform().packageName`, never from a hand-copied
/// constant. On this app it is `com.palateful.palateful`, which is *not*
/// `Environment.auth0Scheme` (`com.palateful.app`); conflating the two was
/// the lgort1 defect.
String auth0DefaultRedirectUrl({
  required bool isIOS,
  required String domain,
  required String packageName,
  required String scheme,
}) {
  final platformSegment = isIOS ? 'ios' : 'android';
  final urlScheme = isIOS ? packageName : scheme;
  return '$urlScheme://$domain/$platformSegment/$packageName/callback';
}
