import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Environment configuration for the app.
/// Reads from .env file (loaded via flutter_dotenv).
class Environment {
  // API Base URL
  static String get apiBaseUrl => dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';

  // Auth0 Configuration
  static String get auth0Domain {
    final v = dotenv.env['AUTH0_DOMAIN'] ?? '';
    assert(v.isNotEmpty, 'AUTH0_DOMAIN is required in app/.env');
    return v;
  }

  static String get auth0ClientId {
    final v = dotenv.env['AUTH0_CLIENT_ID'] ?? '';
    assert(v.isNotEmpty, 'AUTH0_CLIENT_ID is required in app/.env');
    return v;
  }

  static String get auth0Audience =>
      dotenv.env['AUTH0_AUDIENCE'] ?? 'https://api.palateful.app';

  // Auth0 callback scheme (for mobile).
  // Must match CFBundleURLSchemes in ios/Runner/Info.plist
  // and android:scheme in AndroidManifest.xml.
  static const String auth0Scheme = 'com.palateful.app';
}
