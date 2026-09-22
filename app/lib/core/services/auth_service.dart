import 'dart:io' show Platform;

import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';
import '../config/auth0_urls.dart';
import '../config/environment.dart';
import 'error_reporter.dart';

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
  bool _isAdmin = false;
  String? _defaultRecipeBookId;
  String? _previousRecipeBookId;
  String? _defaultShoppingListId;
  String? _previousShoppingListId;

  // Web-specific auth instance
  dynamic _auth0Web;

  /// [credentialsManager] is a test seam, passed straight through to the
  /// SDK's own `Auth0(..., credentialsManager:)` parameter. Production leaves
  /// it null and gets the SDK default.
  AuthService({CredentialsManager? credentialsManager}) {
    if (kIsWeb) {
      _auth0Web = platform.createAuth0Web(
        Environment.auth0Domain,
        Environment.auth0ClientId,
      );
    } else {
      _auth0 = Auth0(
        Environment.auth0Domain,
        Environment.auth0ClientId,
        credentialsManager: credentialsManager,
      );
    }
  }

  /// Renew any access token with less than this left. Shared by startup
  /// restore and [needsRefresh] so the two can never disagree about when a
  /// token is "due" — they used to (restore renewed only once already
  /// expired, `needsRefresh` fired at 5 min), and the gap between them sent
  /// every cold start in that window down the raw renewal path.
  static const int _refreshBufferSeconds = 300;

  /// Check for and restore persisted credentials on app startup
  Future<bool> tryRestoreCredentials() async {
    if (kIsWeb) return false;
    if (_auth0 == null) return false;

    try {
      final hasValid = await _auth0!.credentialsManager.hasValidCredentials();
      debugPrint('AuthService.tryRestoreCredentials: hasValidCredentials=$hasValid');

      if (hasValid) {
        // minTtl makes the MANAGED manager renew anything inside the buffer
        // here, at restore — instead of handing back a nearly-expired token
        // for `needsRefresh` to renew moments later through a second path.
        _credentials = await _auth0!.credentialsManager.credentials(
          minTtl: _refreshBufferSeconds,
        );
        _userProfile = _credentials?.user;
        debugPrint('AuthService: Restored credentials from secure storage');
        notifyListeners();
        return true;
      }
    } on CredentialsManagerException catch (e, st) {
      debugPrint('AuthService.tryRestoreCredentials error: $e');
      // Wipe the saved credentials ONLY when they are provably unusable:
      // nothing stored, or no refresh token to renew with.
      //
      // Deliberately NOT on `isTokenRenewFailed`. The SDK wraps *every*
      // failure of the renewal request as RENEW_FAILED — a revoked token,
      // but equally no connectivity, a timeout, or an Auth0 5xx
      // (Auth0.swift CredentialsManager: `.failure(let error)` →
      // `CredentialsManagerError(code: .renewFailed, cause: error)`). Clearing
      // on it meant a flaky connection at launch, with an expired access
      // token, permanently deleted a perfectly good refresh token and forced
      // a fresh login — "credentials don't hold", and random because it
      // depends on the network at the moment the app opens. Prod agrees: 30
      // days of API logs show zero 401s, so this fails on-device before any
      // request is made. Keeping the credentials costs at most one more
      // failed renewal next launch if the token really was revoked; a new
      // login overwrites them anyway.
      final unusable = e.isNoRefreshTokenFound || e.isNoCredentialsFound;
      if (unusable) {
        await _auth0!.credentialsManager.clearCredentials();
        debugPrint('AuthService: Cleared unusable credentials');
      }
      // Crashlytics, not error_logs: the error_logs mirror needs a signed-in
      // user, which by definition there isn't here. The `code` and
      // `details` carry the renewal's underlying cause, which is what tells
      // a transient failure apart from a revoked token.
      ErrorReporter.report(e, st, area: 'auth', operation: 'restoreCredentials', extras: {
        'code': e.code,
        'renewFailed': e.isTokenRenewFailed,
        'noRefreshToken': e.isNoRefreshTokenFound,
        'noCredentials': e.isNoCredentialsFound,
        'cleared': unusable,
        'details': e.details.toString(),
      });
    } catch (e, st) {
      debugPrint('AuthService.tryRestoreCredentials error: $e');
      ErrorReporter.report(e, st, area: 'auth', operation: 'restoreCredentials');
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
  DateTime? get accessTokenExpiresAt => _credentials?.expiresAt;
  UserProfile? get userProfile => _userProfile;
  bool get hasCompletedOnboarding => _hasCompletedOnboarding;
  bool get isAdmin => _isAdmin;
  String? get defaultRecipeBookId => _defaultRecipeBookId;
  String? get previousRecipeBookId => _previousRecipeBookId;
  String? get defaultShoppingListId => _defaultShoppingListId;
  String? get previousShoppingListId => _previousShoppingListId;

  /// Update the admin state from API response
  void updateAdminState(bool isAdmin) {
    _isAdmin = isAdmin;
    notifyListeners();
  }

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
          // No token prefix: debugPrint is not stripped from release
          // builds, and on web it lands in the browser console.
          debugPrint('Stored token from onLoad');
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
  ///
  /// Returns true on success and false when the user cancelled. Any other
  /// failure is reported and **rethrown**, so the caller can tell the user
  /// what actually happened instead of a generic "Login failed".
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
        // No explicit storeCredentials: webAuthentication() defaults to
        // useCredentialsManager: true, so the SDK's login() has already
        // persisted these. A second store here was redundant, and the SDK
        // documents store as not thread-safe against its managed renewals.

        _isLoading = false;
        notifyListeners();
        return true;
      }
    } catch (e, st) {
      _isLoading = false;
      notifyListeners();
      // Dismissing the sign-in sheet is a normal choice, not a failure: no
      // error message, nothing reported.
      if (e is WebAuthenticationException && e.isUserCancelledException) {
        debugPrint('Login cancelled by user');
        return false;
      }
      // Everything else used to be swallowed into `false`, so every failure —
      // an Auth0 Action's deliberate `api.access.deny()` on account linking,
      // a network error, ID-token validation — showed the same "Login
      // failed", left no trace, and made the real condition unobservable
      // ("random"). It also made the login screen's own handler for the
      // account-linked message unreachable from the day it was written
      // (a2aa52cb). Report it, then let the caller show the right message.
      debugPrint('Login error: $e');
      ErrorReporter.report(
        e,
        st,
        area: 'auth',
        operation: 'login',
        extras: {'connection': connection ?? 'universal'},
      );
      rethrow;
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

        // Breadcrumb the URL the SDK is about to use, so the on-device
        // check in lgort1's ACs (and any later Allowed Logout URLs audit)
        // can read it off the device log instead of re-deriving it from
        // the vendored SDK sources. Logging only — never passed in.
        final expectedReturnTo = await _expectedNativeRedirectUrl();
        if (expectedReturnTo != null) {
          debugPrint('AuthService: logout returnTo (SDK default) = '
              '$expectedReturnTo');
          ErrorReporter.log('auth.logout returnTo=$expectedReturnTo');
        }

        // Deliberately NO returnTo. auth0_flutter's native SDKs already
        // default it to exactly the redirect URL they use for the login
        // callback — on iOS it is literally the same
        // `Auth0WebAuth.redirectURL` property shared by `start()` and
        // `clearSession()`, and on Android it is the same CallbackHelper
        // URL that `RedirectActivity` is registered for. bas-1 (f839f67)
        // hand-built the string instead and put Environment.auth0Scheme
        // ('com.palateful.app') where the SDK puts the bundle id /
        // application id ('com.palateful.palateful'). Auth0 rejects a
        // returnTo that is absent from Allowed Logout URLs and parks the
        // browser on its own hosted error page — the original "logging
        // out shows a weird auth0 page" report. See
        // debug/debug-lgort1-2026-07-27T17:41-auth0-logout-returnto-malformed.md
        // and app/lib/core/config/auth0_urls.dart.
        await _auth0!
            .webAuthentication(scheme: Environment.auth0Scheme)
            .logout();
      }

      _clearSessionState();
      notifyListeners();
    } catch (e, st) {
      debugPrint('Logout error: $e');
      // lgort1: this catch used to swallow silently, which is why a logout
      // that ended on Auth0's hosted error page left no trace anywhere —
      // local state was cleared and the app looked logged out. Report
      // before _clearSessionState(), which resets the Crashlytics user id.
      //
      // A user dismissing the browser sheet surfaces here as a
      // user-cancelled WebAuthenticationException. That is a normal
      // interaction, not a defect, and reporting it would bury the signal
      // we actually want under one row per dismissed sheet.
      final isUserCancelled =
          e is WebAuthenticationException && e.isUserCancelledException;
      if (isUserCancelled) {
        debugPrint('AuthService: logout dismissed by user');
      } else {
        ErrorReporter.report(e, st, area: 'auth', operation: 'logout');
      }
      // Still clear persisted credentials on error
      if (!kIsWeb && _auth0 != null) {
        try {
          await _auth0!.credentialsManager.clearCredentials();
        } catch (_) {}
      }
      _clearSessionState();
      notifyListeners();
    }
  }

  /// Best-effort reconstruction of the redirect URL the native Auth0 SDK
  /// will build for itself. Logging / diagnostics only — the value is
  /// never handed back to the SDK (see the comment in [logout]).
  Future<String?> _expectedNativeRedirectUrl() async {
    try {
      final info = await PackageInfo.fromPlatform();
      return auth0DefaultRedirectUrl(
        isIOS: Platform.isIOS,
        domain: Environment.auth0Domain,
        packageName: info.packageName,
        scheme: Environment.auth0Scheme,
      );
    } catch (e) {
      debugPrint('AuthService: could not derive expected returnTo: $e');
      return null;
    }
  }

  /// Reset in-memory session state. Also clears the Crashlytics user id
  /// so post-logout crash reports aren't tagged with the previous user.
  void _clearSessionState() {
    _credentials = null;
    _userProfile = null;
    _manualToken = null;
    _hasCompletedOnboarding = false;
    _isAdmin = false;
    _defaultRecipeBookId = null;
    _previousRecipeBookId = null;
    _defaultShoppingListId = null;
    _previousShoppingListId = null;
    _isLoading = false;
    ErrorReporter.setUserIdentifier('');
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
    return expiresAt.isBefore(
      DateTime.now().add(const Duration(seconds: _refreshBufferSeconds)),
    );
  }

  /// Refresh the access token
  Future<bool> refreshToken() async {
    if (kIsWeb) return false;
    if (_auth0 == null) return false;

    try {
      // Renew through the MANAGED credentials manager — never the raw
      // `_auth0.api.renewCredentials`, which this used to call before
      // storing the result by hand. Three reasons, in order of relevance to
      // this tenant (Refresh Token Rotation ON, 0 s overlap):
      //  1. Serialization. The managed manager queues concurrent renewals.
      //     With rotation on and no overlap, two renewals presenting the same
      //     refresh token is breach detection: Auth0 revokes the whole token
      //     family and the user is logged out. The raw path could race the
      //     manager's own renewal at startup.
      //  2. Persistence. It stores the result itself; the SDK documents a
      //     manual store afterwards as not thread-safe against it.
      //  3. Latent, not live here: the raw call decodes `/oauth/token` as-is,
      //     so if rotation were ever turned OFF the response would carry no
      //     refresh token and storing it would wipe the saved one. The
      //     managed renew backfills (Auth0.swift CredentialsManager:
      //     `credentials.refreshToken ?? refreshToken`).
      // What this does NOT fix: a renewal whose response is lost after Auth0
      // has already rotated. The app keeps the old token, and presenting it
      // with 0 s overlap revokes the family. Only a non-zero Rotation Overlap
      // Period in the Auth0 dashboard covers that.
      _credentials = await _auth0!.credentialsManager.renewCredentials();
      _userProfile = _credentials?.user ?? _userProfile;
      notifyListeners();
      return true;
    } catch (e, st) {
      debugPrint('Token refresh error: $e');
      // Reported: a failed renewal is what logs a user out early, and until
      // now it left no trace anywhere.
      ErrorReporter.report(e, st, area: 'auth', operation: 'refreshToken');
      return false;
    }
  }
}
