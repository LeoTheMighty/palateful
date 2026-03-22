import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:flutter/foundation.dart';
import '../config/environment.dart';

// Conditional import for web
import 'auth_service_stub.dart'
    if (dart.library.html) 'auth_service_web.dart' as platform;

/// Authentication service using Auth0.
class AuthService extends ChangeNotifier {
  Auth0? _auth0;
  Credentials? _credentials;
  UserProfile? _userProfile;
  bool _isLoading = false;
  String? _manualToken;
  bool _hasCompletedOnboarding = false;
  String? _defaultRecipeBookId;
  String? _previousRecipeBookId;
  String? _defaultShoppingListId;
  String? _previousShoppingListId;

  // Web-specific auth instance
  dynamic _auth0Web;

  AuthService() {
    if (kIsWeb) {
      _auth0Web = platform.createAuth0Web(
        Environment.auth0Domain,
        Environment.auth0ClientId,
      );
    } else {
      _auth0 = Auth0(Environment.auth0Domain, Environment.auth0ClientId);
    }
  }

  /// Check for and restore persisted credentials on app startup
  Future<bool> tryRestoreCredentials() async {
    if (kIsWeb) return false;
    if (_auth0 == null) return false;

    try {
      final hasValid = await _auth0!.credentialsManager.hasValidCredentials();
      debugPrint('AuthService.tryRestoreCredentials: hasValidCredentials=$hasValid');

      if (hasValid) {
        _credentials = await _auth0!.credentialsManager.credentials();
        _userProfile = _credentials?.user;
        debugPrint('AuthService: Restored credentials from secure storage');
        notifyListeners();
        return true;
      }
    } catch (e) {
      debugPrint('AuthService.tryRestoreCredentials error: $e');
    }
    return false;
  }

  bool get isAuthenticated {
    final hasCredentials = _credentials != null;
    final hasToken = _manualToken != null && _manualToken!.isNotEmpty;
    debugPrint('AuthService.isAuthenticated: hasCredentials=$hasCredentials, hasToken=$hasToken');
    return hasCredentials || hasToken;
  }

  bool get isLoading => _isLoading;
  String? get accessToken => _credentials?.accessToken ?? _manualToken;
  UserProfile? get userProfile => _userProfile;
  bool get hasCompletedOnboarding => _hasCompletedOnboarding;
  String? get defaultRecipeBookId => _defaultRecipeBookId;
  String? get previousRecipeBookId => _previousRecipeBookId;
  String? get defaultShoppingListId => _defaultShoppingListId;
  String? get previousShoppingListId => _previousShoppingListId;

  /// Update onboarding state from API response
  void updateOnboardingState({
    required bool hasCompletedOnboarding,
    String? defaultRecipeBookId,
    String? previousRecipeBookId,
    String? defaultShoppingListId,
    String? previousShoppingListId,
  }) {
    _hasCompletedOnboarding = hasCompletedOnboarding;
    _defaultRecipeBookId = defaultRecipeBookId;
    _previousRecipeBookId = previousRecipeBookId;
    _defaultShoppingListId = defaultShoppingListId;
    _previousShoppingListId = previousShoppingListId;
    notifyListeners();
  }

  /// Update the default recipe book from API response
  void updateDefaultRecipeBook({
    String? defaultRecipeBookId,
    String? previousRecipeBookId,
  }) {
    _defaultRecipeBookId = defaultRecipeBookId;
    _previousRecipeBookId = previousRecipeBookId;
    notifyListeners();
  }

  /// Set the default shopping list (calls API, updates local state)
  void updateDefaultShoppingList({
    String? defaultShoppingListId,
    String? previousShoppingListId,
  }) {
    _defaultShoppingListId = defaultShoppingListId;
    _previousShoppingListId = previousShoppingListId;
    notifyListeners();
  }

  /// Mark onboarding as complete (called after successful API call)
  void markOnboardingComplete() {
    _hasCompletedOnboarding = true;
    notifyListeners();
  }

  /// Initialize - call this on app start to handle web redirects and restore credentials
  Future<void> initialize() async {
    debugPrint('AuthService.initialize() called, kIsWeb=$kIsWeb');

    if (kIsWeb && _auth0Web != null) {
      // Web: handle redirect callback
      try {
        debugPrint('Calling onLoad()...');
        final credentials = await platform.onLoad(_auth0Web, Environment.auth0Audience);
        debugPrint('onLoad() returned: ${credentials != null ? "credentials" : "null"}');
        if (credentials != null) {
          _credentials = credentials;
          _manualToken = credentials.accessToken;
          _userProfile = credentials.user;
          debugPrint('Stored token: ${_manualToken?.substring(0, 20)}...');
          notifyListeners();
        }
      } catch (e) {
        debugPrint('Auth init error: $e');
      }
    } else {
      // Native: try to restore persisted credentials
      await tryRestoreCredentials();
    }
  }

  /// Log in with Auth0.
  /// Optionally pass [connection] to skip Universal Login and go directly
  /// to a social provider (e.g. 'google-oauth2', 'apple').
  Future<bool> login({String? connection}) async {
    try {
      _isLoading = true;
      notifyListeners();

      if (kIsWeb) {
        await platform.loginWithRedirect(
          _auth0Web,
          Environment.auth0Audience,
          connection: connection,
        );
        // Won't reach here - page redirects
        return false;
      } else {
        _credentials = await _auth0!.webAuthentication(scheme: Environment.auth0Scheme).login(
          audience: Environment.auth0Audience,
          scopes: {'openid', 'profile', 'email', 'offline_access'},
          parameters: {
            if (connection != null) 'connection': connection,
          },
        );
        _userProfile = _credentials?.user;

        // Store credentials for persistence across app restarts
        if (_credentials != null) {
          await _auth0!.credentialsManager.storeCredentials(_credentials!);
          debugPrint('AuthService: Stored credentials to secure storage');
        }

        _isLoading = false;
        notifyListeners();
        return true;
      }
    } catch (e) {
      debugPrint('Login error: $e');
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Log out
  Future<void> logout() async {
    try {
      _isLoading = true;
      notifyListeners();

      if (kIsWeb) {
        await platform.logout(_auth0Web);
      } else {
        // Clear persisted credentials first
        await _auth0!.credentialsManager.clearCredentials();
        debugPrint('AuthService: Cleared credentials from secure storage');

        await _auth0!.webAuthentication(scheme: Environment.auth0Scheme).logout();
      }

      _credentials = null;
      _userProfile = null;
      _manualToken = null;
      _hasCompletedOnboarding = false;
      _defaultRecipeBookId = null;
      _previousRecipeBookId = null;
      _defaultShoppingListId = null;
      _previousShoppingListId = null;

      _isLoading = false;
      notifyListeners();
    } catch (e) {
      debugPrint('Logout error: $e');
      // Still clear persisted credentials on error
      if (!kIsWeb && _auth0 != null) {
        try {
          await _auth0!.credentialsManager.clearCredentials();
        } catch (_) {}
      }
      _credentials = null;
      _userProfile = null;
      _manualToken = null;
      _hasCompletedOnboarding = false;
      _defaultRecipeBookId = null;
      _previousRecipeBookId = null;
      _defaultShoppingListId = null;
      _previousShoppingListId = null;
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Set access token manually (useful for testing)
  void setAccessToken(String token) {
    _manualToken = token;
    notifyListeners();
  }

  /// Check if credentials need refresh
  bool get needsRefresh {
    if (_manualToken != null) return false;
    if (_credentials == null) return true;
    final expiresAt = _credentials!.expiresAt;
    return expiresAt.isBefore(DateTime.now().add(const Duration(minutes: 5)));
  }

  /// Refresh the access token
  Future<bool> refreshToken() async {
    if (kIsWeb) return false;
    if (_credentials?.refreshToken == null) return false;

    try {
      _credentials = await _auth0!.api.renewCredentials(
        refreshToken: _credentials!.refreshToken!,
      );

      // Store the refreshed credentials
      if (_credentials != null) {
        await _auth0!.credentialsManager.storeCredentials(_credentials!);
        debugPrint('AuthService: Stored refreshed credentials');
      }

      notifyListeners();
      return true;
    } catch (e) {
      debugPrint('Token refresh error: $e');
      return false;
    }
  }
}
