import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';
import 'firebase_options.dart';
import 'core/di/injection.dart';
import 'core/router/app_router.dart';
import 'core/services/auth_service.dart';
import 'core/services/api_client.dart';
import 'core/services/cook_timer_notification_service.dart';
import 'core/services/push_notification_service.dart';
import 'core/config/environment.dart';
import 'core/theme/app_theme.dart';
import 'providers/theme_mode_provider.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Load environment variables from .env file
  await dotenv.load(fileName: '.env');

  // Initialize Firebase (skip in E2E mode — no push notifications needed,
  // and waiting on Firebase delays test startup significantly)
  if (!kE2EMode) {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
  }

  setupDependencies();

  final authService = getIt<AuthService>();

  // Initialize local timer notifications unconditionally (no auth required — purely local OS APIs)
  if (!kE2EMode) {
    final timerService = getIt<CookTimerNotificationService>();
    await timerService.initialize();
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

      // Fetch user data to get onboarding state
      try {
        final response = await apiClient.getMe();
        if (response.statusCode == 200) {
          final userData = response.data;
          authService.updateOnboardingState(
            hasCompletedOnboarding: userData['has_completed_onboarding'] ?? false,
            defaultRecipeBookId: userData['default_recipe_book_id'],
          );
        }
      } catch (e) {
        debugPrint('Failed to fetch user data on startup: $e');
        // If getMe fails with auth error, try refreshing token and retrying
        if (authService.needsRefresh || e.toString().contains('401')) {
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
              }
            } catch (retryError) {
              debugPrint('Retry after refresh also failed: $retryError');
            }
          }
        }
      }

      // Initialize push notifications after auth
      final pushService = getIt<PushNotificationService>();
      await pushService.initialize();
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

class PalatefulApp extends ConsumerStatefulWidget {
  const PalatefulApp({super.key});

  @override
  ConsumerState<PalatefulApp> createState() => _PalatefulAppState();
}

class _PalatefulAppState extends ConsumerState<PalatefulApp> {
  StreamSubscription? _shareSubscription;

  @override
  void initState() {
    super.initState();
    // Pass navigator key to push notification service for in-app banners
    // (requires Firebase — skip in E2E mode where Firebase is not initialized)
    if (!kE2EMode) {
      final pushService = getIt<PushNotificationService>();
      pushService.setNavigatorKey(rootNavigatorKey);
    }

    if (!kIsWeb) {
      _initShareListener();
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

  void _handleSharedFiles(List<SharedMediaFile> files) {
    for (final file in files) {
      final path = file.path.trim();
      if (path.startsWith('http://') || path.startsWith('https://')) {
        // Navigate after first frame (router may not be ready on cold start)
        WidgetsBinding.instance.addPostFrameCallback((_) {
          final authService = getIt<AuthService>();
          if (authService.isAuthenticated) {
            appRouter.go('/recipes/add/share?url=${Uri.encodeComponent(path)}');
          }
        });
        return;
      }
      // Try to extract URL from text
      final urlMatch = RegExp(r'https?://\S+').firstMatch(path);
      if (urlMatch != null) {
        final url = urlMatch.group(0)!;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          final authService = getIt<AuthService>();
          if (authService.isAuthenticated) {
            appRouter.go('/recipes/add/share?url=${Uri.encodeComponent(url)}');
          }
        });
        return;
      }
    }
  }

  @override
  void dispose() {
    _shareSubscription?.cancel();
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
    );
  }
}
