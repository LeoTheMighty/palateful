/// Compile-time configuration. Values default to production; override for
/// local dev via `--dart-define=KEY=value` (see bin/dev).
///
/// None of these values are secrets — they all end up visible in the
/// compiled bundle in any SPA architecture. `AUTH0_CLIENT_ID` is an OAuth
/// public client ID (SPAs cannot hold secrets by design); security comes
/// from PKCE + Auth0's allowed-callback-URL list.
class Environment {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://api.palateful.app',
  );

  static const String auth0Domain = String.fromEnvironment(
    'AUTH0_DOMAIN',
    defaultValue: 'auth.palateful.app',
  );

  static const String auth0ClientId = String.fromEnvironment(
    'AUTH0_CLIENT_ID',
    defaultValue: 'Kge8bTdbfZ9rVQdCcTxDZLsF2YJ2I2Mc',
  );

  static const String auth0Audience = String.fromEnvironment(
    'AUTH0_AUDIENCE',
    defaultValue: 'https://api.palateful.app',
  );

  // Auth0 callback scheme (for mobile).
  // Must match CFBundleURLSchemes in ios/Runner/Info.plist
  // and android:scheme in AndroidManifest.xml.
  static const String auth0Scheme = 'com.palateful.app';
}

/// Set via --dart-define=E2E_MODE=true at build time to enable the E2E test bypass.
/// When true, Auth0 is skipped and a fixed test token is used instead.
const bool kE2EMode = bool.fromEnvironment('E2E_MODE');
