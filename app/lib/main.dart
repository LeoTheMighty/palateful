import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'firebase_options.dart';
import 'core/di/injection.dart';
import 'core/router/app_router.dart';
import 'core/services/auth_service.dart';
import 'core/services/api_client.dart';
import 'core/services/push_notification_service.dart';
import 'core/theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Load environment variables from .env file
  await dotenv.load(fileName: '.env');

  // Initialize Firebase
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  setupDependencies();

  // Initialize auth service (handles web redirect callback and credential restoration)
  final authService = getIt<AuthService>();
  await authService.initialize();

  // If already authenticated (from restored credentials or redirect), set up the session
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

  runApp(const ProviderScope(child: PalatefulApp()));
}

class PalatefulApp extends StatelessWidget {
  const PalatefulApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Palateful',
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: appRouter,
      debugShowCheckedModeBanner: false,
    );
  }
}
