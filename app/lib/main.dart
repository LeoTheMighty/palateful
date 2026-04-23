import 'dart:async';

import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';
import 'firebase_options.dart';
import 'core/debug/perf_dio_interceptor.dart';
import 'core/debug/perf_overlay.dart';
import 'core/di/injection.dart';
import 'core/router/app_router.dart';
import 'core/services/auth_service.dart';
import 'core/services/api_client.dart';
import 'core/services/cook_timer_notification_service.dart';
import 'core/services/error_reporter.dart';
import 'core/services/live_activity_service.dart';
import 'core/services/push_notification_service.dart';
import 'core/services/share_intent_handler.dart';
import 'core/services/shared_state_service.dart';
import 'core/services/pending_imports_reconciler.dart';
import 'core/services/perf_flags_service.dart';
import 'core/config/environment.dart';
import 'core/theme/app_theme.dart';
import 'features/recipes/cook_mode/services/cook_session_persister.dart';
import 'providers/theme_mode_provider.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Load environment variables from .env file (or .env.prod with --dart-define=ENV=prod)
  await dotenv.load(fileName: envFileName);

  // Initialize Firebase (skip in E2E mode — no push notifications needed,
  // and waiting on Firebase delays test startup significantly)
  if (!kE2EMode) {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );

    // Crashlytics: enables collection and wires fatal handlers. No-ops in
    // debug and on web (firebase_crashlytics has no web implementation).
    await ErrorReporter.initialize();
  }

  setupDependencies();

  // Bind the API client into ErrorReporter so every report()/log() call
  // mirrors into backend error_logs as service="client". Fire-and-forget
  // from the reporter side — a failing mirror POST is swallowed.
  ErrorReporter.bindApiClient(getIt<ApiClient>());

  // cla-1c: warm the client-latency kill-switch flag. Fire-and-forget —
  // fail-open if the endpoint errors/times out so boot is never blocked
  // on it. Telemetry emitters re-read the cached flag on every enqueue.
  unawaited(getIt<PerfFlagsService>().initialize());

  // ptd-1: attach the debug-only perf interceptor so the [PerfOverlay]
  // (installed as the MaterialApp builder below) shows live HTTP
  // request timings. Release builds skip this entirely.
  if (kDebugMode) {
    getIt<ApiClient>().dio.interceptors.add(PerfDioInterceptor());
  }

  // Prune cook sessions older than 30 days on startup (epic-cook-mode-resume).
  unawaited(CookSessionPersister().pruneStaleOlderThan(const Duration(days: 30)));

  final authService = getIt<AuthService>();

  // Wire the iOS Share Extension bridge. Initialize the App Group handle
  // now (no-op on Android / non-iOS) and register a listener that re-syncs
  // auth state on every notifyListeners call. Debounced 250 ms inside the
  // service, so the listener firing on every profile/book field tick is
  // cheap. See app/ios/PalatefulShare/SharedState.swift for the reader.
  final sharedState = getIt<SharedStateService>();
  await sharedState.initialize();
  authService.addListener(() {
    if (!authService.isAuthenticated) {
      sharedState.clear();
      return;
    }
    sharedState.syncAuth(
      authJwt: authService.accessToken,
      authJwtExpiresAt: authService.accessTokenExpiresAt,
      userId: authService.userProfile?.sub,
      apiBaseUrl: Environment.apiBaseUrl,
      lastUsedBookId:
          authService.defaultRecipeBookId ?? authService.previousRecipeBookId,
    );
  });

  // Initialize local timer notifications unconditionally (no auth required — purely local OS APIs).
  // Web skipped: both services call dart:io Platform APIs which throw on web.
  if (!kE2EMode && !kIsWeb) {
    final timerService = getIt<CookTimerNotificationService>();
    await timerService.initialize();
    // Live Activities (iOS-only; the service no-ops on other platforms).
    await getIt<LiveActivityService>().initialize();
  }

  if (kE2EMode) {
    // E2E mode: bypass Auth0, inject a fixed test token that the API accepts
    // when E2E_TEST_MODE=true is set server-side.
    const testToken = 'e2e-test-token';
    authService.setAccessToken(testToken);
    final apiClient = getIt<ApiClient>();
    apiClient.setAuthToken(testToken);
    try {
      final response = await apiClient.getMe();
      if (response.statusCode == 200) {
        authService.updateOnboardingState(
          hasCompletedOnboarding: response.data['has_completed_onboarding'] ?? false,
          defaultRecipeBookId: response.data['default_recipe_book_id'],
          previousRecipeBookId: response.data['previous_recipe_book_id'],
          defaultShoppingListId: response.data['default_shopping_list_id'],
          previousShoppingListId: response.data['previous_shopping_list_id'],
        );
        authService.updateAdminState(response.data['is_admin'] ?? false);
      }
    } catch (e) {
      debugPrint('E2E: getMe failed: $e');
    }
  } else {
    // Normal flow: restore credentials from Auth0 / handle web redirect
    await authService.initialize();

    if (authService.isAuthenticated && authService.accessToken != null) {
      // Refresh token if expired/expiring before making API calls
      if (authService.needsRefresh) {
        debugPrint('Access token needs refresh, attempting...');
        final refreshed = await authService.refreshToken();
        debugPrint('Token refresh result: $refreshed');
      }

      final apiClient = getIt<ApiClient>();
      apiClient.setAuthService(authService);
      apiClient.setAuthToken(authService.accessToken!);

      // BOOT SMOKE TEST (push-diag debugging): direct client-error POST
      // bypassing ErrorReporter. If this row lands in error_logs
      // (service='client', error_type='BootSmokeTest') we know the
      // mirror endpoint + auth + network are all fine, and any missing
      // ErrorReporter rows are due to a wiring bug in error_reporter.dart.
      // If this row is also missing, the binary doesn't have the new
      // Dart code (stale TestFlight / caching issue).
      unawaited(() async {
        try {
          await apiClient
              .recordClientError(
                errorType: 'BootSmokeTest',
                errorMessage: 'main.dart boot smoke test 1.0.36+49',
                area: 'diag',
                operation: 'boot_smoke_test',
              )
              .timeout(const Duration(seconds: 5));
        } catch (_) {
          // Swallow — diagnostic only.
        }
      }());

      // Fetch user data to get onboarding state
      try {
        final response = await apiClient.getMe();
        if (response.statusCode == 200) {
          final userData = response.data;
          authService.updateOnboardingState(
            hasCompletedOnboarding: userData['has_completed_onboarding'] ?? false,
            defaultRecipeBookId: userData['default_recipe_book_id'],
          );
          authService.updateAdminState(userData['is_admin'] ?? false);

          // Tag crash reports with user ID
          if (!kE2EMode && userData['id'] != null) {
            ErrorReporter.setUserIdentifier(userData['id'].toString());
          }
        }
      } catch (e) {
        debugPrint('Failed to fetch user data on startup: $e');
        if (_isAuthError(e)) {
          // Auth error (401/403): try refreshing token once, then logout
          final refreshed = await authService.refreshToken();
          if (refreshed) {
            apiClient.setAuthToken(authService.accessToken!);
            try {
              final retryResponse = await apiClient.getMe();
              if (retryResponse.statusCode == 200) {
                final userData = retryResponse.data;
                authService.updateOnboardingState(
                  hasCompletedOnboarding: userData['has_completed_onboarding'] ?? false,
                  defaultRecipeBookId: userData['default_recipe_book_id'],
                );
                authService.updateAdminState(userData['is_admin'] ?? false);
              }
            } catch (retryError) {
              debugPrint('Retry after refresh also failed: $retryError');
              await authService.logout();
            }
          } else {
            await authService.logout();
          }
        }
        // Network/server errors: skip silently — user keeps auth state and
        // the app will retry on next launch or navigation
      }

      // Initialize push notifications after auth. autoPrompt is gated on
      // hasCompletedOnboarding so brand-new users on their first launch
      // hit notif-4's onboarding prompt (not the boot-path prompt); the
      // boot-path only auto-prompts past-onboarding users whose status is
      // notDetermined (Leo's case). See push-diag-2.
      final pushService = getIt<PushNotificationService>();
      await pushService.ensureRegistered(
        autoPrompt: authService.hasCompletedOnboarding,
      );

      // Cold-start reconciliation: the Share Extension may have queued
      // pending imports while the main app was dead. Fire-and-forget
      // from this point — the reconciler is server-idempotent.
      unawaited(getIt<PendingImportsReconciler>().reconcile());
    }
  }

  final appearance = await loadSavedAppearance();
  runApp(
    ProviderScope(
      overrides: [
        themeModeProvider
            .overrideWith(() => ThemeModeNotifier(appearance.themeMode)),
        fontStyleProvider
            .overrideWith(() => FontStyleNotifier(appearance.fontStyle)),
      ],
      child: const PalatefulApp(),
    ),
  );
}

/// Returns true for auth-related errors (401/403) where we should reset auth.
/// Returns false for network/server errors where the user should just retry.
bool _isAuthError(Object e) {
  if (e is DioException) {
    final statusCode = e.response?.statusCode;
    return statusCode == 401 || statusCode == 403;
  }
  return false;
}

class PalatefulApp extends ConsumerStatefulWidget {
  const PalatefulApp({super.key});

  @override
  ConsumerState<PalatefulApp> createState() => _PalatefulAppState();
}

class _PalatefulAppState extends ConsumerState<PalatefulApp>
    with WidgetsBindingObserver {
  StreamSubscription? _shareSubscription;
  ShareIntentHandler? _shareHandler;
  VoidCallback? _authListener;

  @override
  void initState() {
    super.initState();
    // Pass navigator key to push notification service for in-app banners
    // (requires Firebase — skip in E2E mode where Firebase is not initialized)
    if (!kE2EMode) {
      final pushService = getIt<PushNotificationService>();
      pushService.setNavigatorKey(rootNavigatorKey);
      WidgetsBinding.instance.addObserver(this);
    }

    if (!kIsWeb) {
      _shareHandler = ShareIntentHandler(authService: getIt<AuthService>());
      _initShareListener();
      _initAuthReplayListener();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // When the app returns to foreground, verify OS permission + token state.
    // Covers: user flipped iOS Settings while backgrounded, token rotated, etc.
    // autoPrompt mirrors the boot-path rule: only past-onboarding users may
    // trigger the OS prompt from here. See push-diag-2.
    if (state == AppLifecycleState.resumed && !kE2EMode) {
      final authService = getIt<AuthService>();
      if (authService.isAuthenticated) {
        getIt<PushNotificationService>().ensureRegistered(
          autoPrompt: authService.hasCompletedOnboarding,
        );
        // Reconcile anything the iOS Share Extension persisted while the
        // main app was backgrounded. Server is idempotent by
        // idempotency_key, so a double-fire is harmless.
        unawaited(getIt<PendingImportsReconciler>().reconcile());
      }
    }
  }

  void _initShareListener() {
    // Cold start: app was launched from share
    ReceiveSharingIntent.instance.getInitialMedia().then((files) {
      _handleSharedFiles(files);
      ReceiveSharingIntent.instance.reset();
    });

    // Hot share: app was already running
    _shareSubscription = ReceiveSharingIntent.instance
        .getMediaStream()
        .listen(_handleSharedFiles, onError: (_) {});
  }

  /// getInitialMedia() can resolve before AuthService rehydrates on cold
  /// start. We persist the route to SharedPreferences in that window
  /// and replay it on the first successful auth + onboarding tick.
  /// Gating on both prevents the replay from firing mid-redirect to
  /// /onboarding/welcome (which would consume + drop the payload).
  void _initAuthReplayListener() {
    final authService = getIt<AuthService>();
    void onAuthChange() {
      if (!authService.isAuthenticated) return;
      if (!authService.hasCompletedOnboarding) return;
      unawaited(_replayPendingShare());
    }
    _authListener = onAuthChange;
    authService.addListener(onAuthChange);
    // If auth rehydrated before initState ran, try now.
    if (authService.isAuthenticated && authService.hasCompletedOnboarding) {
      unawaited(_replayPendingShare());
    }
  }

  Future<void> _replayPendingShare() async {
    final handler = _shareHandler;
    if (handler == null) return;
    final route = await handler.consumePending();
    if (route == null) return;
    _navigateAfterFrame(route);
  }

  void _handleSharedFiles(List<SharedMediaFile> files) {
    final handler = _shareHandler;
    if (handler == null) return;
    unawaited(() async {
      final resolved = await handler.resolve(files);
      if (resolved == null) return;
      if (!handler.isAuthenticated) {
        await handler.persistPending(resolved.route);
        return;
      }
      _navigateAfterFrame(resolved.route, skippedCount: resolved.skippedCount);
    }());
  }

  void _navigateAfterFrame(String route, {int skippedCount = 0}) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final authService = getIt<AuthService>();
      if (!authService.isAuthenticated) return;
      appRouter.go(route);
      if (skippedCount > 0) {
        final ctx = rootNavigatorKey.currentContext;
        if (ctx != null) {
          final messenger = ScaffoldMessenger.maybeOf(ctx);
          messenger?.showSnackBar(
            SnackBar(
              content: Text(
                skippedCount == 1
                    ? 'Only the first item was imported (1 skipped).'
                    : 'Only the first item was imported ($skippedCount skipped).',
              ),
            ),
          );
        }
      }
    });
  }

  @override
  void dispose() {
    _shareSubscription?.cancel();
    final listener = _authListener;
    if (listener != null) {
      getIt<AuthService>().removeListener(listener);
    }
    if (!kE2EMode) {
      WidgetsBinding.instance.removeObserver(this);
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final themeMode = ref.watch(themeModeProvider);
    final fontStyle = ref.watch(fontStyleProvider);
    return MaterialApp.router(
      title: 'Palateful',
      theme: AppTheme.light(fontStyle),
      darkTheme: AppTheme.dark(fontStyle),
      themeMode: themeMode,
      routerConfig: appRouter,
      debugShowCheckedModeBanner: false,
      // ptd-1: debug-only overlay listing recent HTTP requests.
      // Returns child unwrapped in release — zero cost off-debug.
      builder: (context, child) =>
          PerfOverlay(child: child ?? const SizedBox.shrink()),
    );
  }
}
