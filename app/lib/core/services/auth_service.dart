import 'dart:io' show Platform;

import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';
import '../config/auth0_urls.dart';
import '../config/environment.dart';
import 'auth_failure_mode.dart';
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

  /// Report an auth-path failure to the sink that can actually receive it.
  ///
  /// The `error_logs` mirror POSTs `/v1/users/me/client-errors`, which is
  /// behind `get_current_user_async`. Whether that can succeed is a property
  /// of the moment, not of the call site: `refreshToken()` runs both
  /// proactively (token still valid for up to [_refreshBufferSeconds], so the
  /// mirror works and an `audit_errors.py`-queryable row is worth having) and
  /// reactively from `ApiClient`'s 401 interceptor (token already rejected,
  /// so the mirror 401s and `_postMirror` drops the event). Deciding per call
  /// site meant guessing; this asks the token.
  ///
  /// Sites that are pre-auth by construction — restore, login, the web
  /// callback — call [ErrorReporter.reportPreAuth] directly instead, because
  /// there the answer can never be "a token exists".
  /// True when the token on hand could still authenticate the `error_logs`
  /// mirror POST (`/v1/users/me/client-errors`, behind
  /// `get_current_user_async`).
  ///
  /// The catches below pass this as `mirror:` rather than calling a
  /// reporting wrapper: the silent-catch guard looks for a literal
  /// `ErrorReporter.report(` inside the catch block, and a helper that
  /// reports on the catch's behalf is exactly the indirection that makes a
  /// swallow look handled. Keeping the call visible keeps the guard honest
  /// about this file.
  bool get _canMirrorReport {
    final expiresAt = _credentials?.expiresAt;
    return accessToken != null &&
        (expiresAt == null || expiresAt.isAfter(DateTime.now()));
  }

  /// Standard extras for an auth report: the failure mode, plus the sink
  /// decision itself so triage sees the routing rather than inferring it
  /// from a row's presence or absence in `error_logs`.
  Map<String, Object?> _authExtras(Object e, [Map<String, Object?>? more]) => {
        'failureMode': authFailureMode(e),
        'mirrored': _canMirrorReport,
        ...?more,
      };

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
      // user, which by definition there isn't here — `reportPreAuth` is what
      // enforces that (plain `report` would POST the mirror, collect a 401
      // and drop the event). The `code` and `details` carry the renewal's
      // underlying cause, which is what tells a transient failure apart from
      // a revoked token.
      ErrorReporter.reportPreAuth(e, st, area: 'auth', operation: 'restoreCredentials', extras: {
        'failureMode': authFailureMode(e),
        'code': e.code,
        'renewFailed': e.isTokenRenewFailed,
        'noRefreshToken': e.isNoRefreshTokenFound,
        'noCredentials': e.isNoCredentialsFound,
        'cleared': unusable,
        'details': e.details.toString(),
      });
    } catch (e, st) {
      debugPrint('AuthService.tryRestoreCredentials error: $e');
      // Pre-auth by construction: restore is what would have produced the
      // token the mirror needs. Anything reaching here is a non-Auth0
      // failure — a plugin channel error, a Keychain fault — which
      // `authFailureMode` separates from the SDK's own error codes.
      ErrorReporter.reportPreAuth(e, st, area: 'auth', operation: 'restoreCredentials', extras: {
        'failureMode': authFailureMode(e),
      });
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
      } catch (e, st) {
        debugPrint('Auth init error: $e');
        // The web redirect callback failing leaves the user on a blank
        // post-login screen with no session and no trace. Pre-auth: onLoad
        // IS the step that produces the token.
        //
        // Crashlytics is disabled on web (no platform implementation), so
        // today this call only debugPrints under the suppression branch —
        // it is still the right call site, and it is what a web sink would
        // pick up the day one exists. Leo's reports are iOS, where it does
        // reach Crashlytics via the native path below.
        ErrorReporter.reportPreAuth(e, st, area: 'auth', operation: 'initializeWeb', extras: {
          'failureMode': authFailureMode(e),
        });
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
      // Pre-auth: a failed login is precisely the state where no token
      // exists to authenticate the error_logs mirror with.
      ErrorReporter.reportPreAuth(
        e,
        st,
        area: 'auth',
        operation: 'login',
        extras: {
          'failureMode': authFailureMode(e),
          'connection': connection ?? 'universal',
        },
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
        ErrorReporter.report(e, st,
            area: 'auth',
            operation: 'logout',
            extras: _authExtras(e),
            mirror: _canMirrorReport);
      }
      try {
        // Still clear persisted credentials on error — unless the failure
        // we are handling IS that clear, in which case retrying it just
        // produces a second identical report for one incident.
        final clearAlreadyFailed = e is CredentialsManagerException;
        if (!kIsWeb && _auth0 != null && !clearAlreadyFailed) {
          try {
            await _auth0!.credentialsManager.clearCredentials();
          } catch (e2, st2) {
            // A clear that fails here leaves credentials on the device
            // after the app has told the user they are logged out — a real
            // defect (next launch silently restores the session), and one
            // that was invisible while this catch was empty. Reported, not
            // rethrown: the logout must still finish clearing in-memory
            // state.
            ErrorReporter.report(e2, st2,
                area: 'auth',
                operation: 'logout.clearCredentials',
                extras: _authExtras(e2),
                mirror: _canMirrorReport);
          }
        }
      } finally {
        // In a finally because this is the part that must happen. Reporting
        // stringifies the error and touches the mirror; if any of that
        // threw, the old shape skipped these two lines and left the app
        // with _isLoading true and a live session — the exact outcome the
        // catch exists to prevent.
        _clearSessionState();
        notifyListeners();
      }
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
    } catch (e, st) {
      debugPrint('AuthService: could not derive expected returnTo: $e');
      // Diagnostics-only, so this never blocks logout — but a silent failure
      // here is why lgort1 had to re-derive the URL from vendored SDK
      // sources instead of reading it off a device.
      ErrorReporter.report(e, st,
          area: 'auth',
          operation: 'expectedReturnTo',
          extras: _authExtras(e),
          mirror: _canMirrorReport);
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
      // Sink chosen by whether the token on hand is still usable, not by
      // call site: main.dart refreshes proactively inside the 5-minute
      // buffer (mirror works), ApiClient refreshes after a 401 (mirror
      // 401s). This is the failure that logs a user out mid-session — the
      // exact shape behind "the login doesn't hold".
      ErrorReporter.report(e, st,
          area: 'auth',
          operation: 'refreshToken',
          extras: _authExtras(e),
          mirror: _canMirrorReport);
      return false;
    }
  }
}
