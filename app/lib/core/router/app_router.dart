import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../di/injection.dart';
import '../services/auth_service.dart';
import '../../features/auth/login_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/onboarding/onboarding_welcome_screen.dart';
import '../../features/onboarding/onboarding_start_screen.dart';
import '../../features/recipe_books/archived_recipe_books_screen.dart';
import '../../features/recipe_books/recipe_books_screen.dart';
import '../../features/recipe_books/recipe_book_detail_screen.dart';
import '../../features/recipes/recipe_detail_screen.dart';
import '../../features/recipes/archived_recipes_screen.dart';
import '../../features/recipes/cook_mode/cook_mode_screen.dart';
import '../../features/recipes/edit_recipe_screen.dart';
import '../../features/recipes/add_recipe/recipe_wizard_screen.dart';
import '../../features/recipes/add_recipe/photo_capture_screen.dart';
import '../../features/recipes/add_recipe/bulk_url_import_screen.dart';
import '../../features/recipes/add_recipe/file_import_screen.dart';
import '../../features/recipes/add_recipe/import_item_review_screen.dart';
import '../../features/recipes/add_recipe/import_review_list_screen.dart';
import '../../features/recipes/add_recipe/share_import_screen.dart';
import '../../features/recipes/add_recipe/url_import_screen.dart';
import '../../features/search/search_screen.dart';
import '../../features/cart/cart_screen.dart';
import '../../features/calendar/calendar_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../shared/widgets/scaffold_with_bottom_nav.dart';
import 'page_transitions.dart';

/// Navigation keys for each bottom nav branch
final _rootNavigatorKey = GlobalKey<NavigatorState>();
final _homeNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'home');
final _booksNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'books');
final _cartNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'cart');
final _calendarNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'calendar');
final _profileNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'profile');

/// App router configuration - lazily initialized
GoRouter? _router;

/// Reset the router singleton (useful for hot restart in debug mode).
void resetRouter() {
  _router?.dispose();
  _router = null;
}

GoRouter get appRouter {
  _router ??= GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/login',
    refreshListenable: getIt<AuthService>(),
    redirect: (context, state) {
      final authService = getIt<AuthService>();
      final isAuthenticated = authService.isAuthenticated;
      final hasCompletedOnboarding = authService.hasCompletedOnboarding;
      final currentLocation = state.matchedLocation;
      final isOnLoginPage = currentLocation == '/login';
      final isOnOnboardingPage = currentLocation.startsWith('/onboarding');

      debugPrint('Router redirect: location=$currentLocation, isAuthenticated=$isAuthenticated, hasCompletedOnboarding=$hasCompletedOnboarding');

      // Not authenticated - go to login (unless already there)
      if (!isAuthenticated && !isOnLoginPage) {
        debugPrint('Redirecting to /login (not authenticated)');
        return '/login';
      }

      // Authenticated but not onboarded - go to onboarding (unless already there)
      if (isAuthenticated && !hasCompletedOnboarding && !isOnOnboardingPage) {
        debugPrint('Redirecting to /onboarding/welcome (not onboarded)');
        return '/onboarding/welcome';
      }

      // Authenticated and onboarded, but on login or onboarding page - go home
      if (isAuthenticated && hasCompletedOnboarding && (isOnLoginPage || isOnOnboardingPage)) {
        debugPrint('Redirecting to / (already onboarded)');
        return '/';
      }

      debugPrint('No redirect needed');
      return null;
    },
    routes: [
      // Non-shell routes (outside bottom nav)
      GoRoute(
        path: '/login',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/onboarding/welcome',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const OnboardingWelcomeScreen(),
      ),
      GoRoute(
        path: '/onboarding/start',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final name = extra?['name'] as String? ?? '';
          return OnboardingStartScreen(name: name);
        },
      ),
      // Archived recipes (must be before /recipes/:id to avoid path collision)
      GoRoute(
        path: '/recipes/archived',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const ArchivedRecipesScreen(),
      ),
      // Recipe detail and cook mode are outside shell (full-screen)
      GoRoute(
        path: '/recipes/:id',
        parentNavigatorKey: _rootNavigatorKey,
        pageBuilder: (context, state) {
          final id = state.pathParameters['id']!;
          return buildReduceMotionPage(
            context: context,
            state: state,
            child: RecipeDetailScreen(recipeId: id),
          );
        },
      ),
      GoRoute(
        path: '/recipes/:id/edit',
        parentNavigatorKey: _rootNavigatorKey,
        pageBuilder: (context, state) {
          final id = state.pathParameters['id']!;
          return buildReduceMotionPage(
            context: context,
            state: state,
            child: EditRecipeScreen(recipeId: id),
          );
        },
      ),
      GoRoute(
        path: '/recipes/:id/cook',
        parentNavigatorKey: _rootNavigatorKey,
        pageBuilder: (context, state) {
          final id = state.pathParameters['id']!;
          return buildReduceMotionPage(
            context: context,
            state: state,
            child: CookModeScreen(recipeId: id),
          );
        },
      ),
      GoRoute(
        path: '/recipes/add/wizard',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final recipeBookId = extra?['recipeBookId'] as String?;
          return RecipeWizardScreen(recipeBookId: recipeBookId);
        },
      ),
      GoRoute(
        path: '/recipes/add/photo',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final recipeBookId = extra?['recipeBookId'] as String?;
          return PhotoCaptureScreen(recipeBookId: recipeBookId);
        },
      ),
      GoRoute(
        path: '/recipes/add/files',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const FileImportScreen(),
      ),
      GoRoute(
        path: '/recipes/add/bulk-urls',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final recipeBookId = extra?['recipeBookId'] as String?;
          return BulkUrlImportScreen(recipeBookId: recipeBookId);
        },
      ),
      GoRoute(
        path: '/recipes/add/url',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final recipeBookId = extra?['recipeBookId'] as String?;
          return UrlImportScreen(recipeBookId: recipeBookId);
        },
      ),

      GoRoute(
        path: '/recipes/add/share',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final url = state.uri.queryParameters['url'] ?? '';
          return ShareImportScreen(initialUrl: url);
        },
      ),
      GoRoute(
        path: '/recipes/import/review-list/:jobId',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final jobId = state.pathParameters['jobId']!;
          return ImportReviewListScreen(jobId: jobId);
        },
      ),
      GoRoute(
        path: '/recipes/import/review/:itemId',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final itemId = state.pathParameters['itemId']!;
          return ImportItemReviewScreen(itemId: itemId);
        },
      ),

      // Shell route with bottom navigation
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return ScaffoldWithBottomNav(navigationShell: navigationShell);
        },
        branches: [
          // Home tab
          StatefulShellBranch(
            navigatorKey: _homeNavigatorKey,
            routes: [
              GoRoute(
                path: '/',
                builder: (context, state) => const HomeScreen(),
              ),
              GoRoute(
                path: '/search',
                builder: (context, state) => const SearchScreen(),
              ),
            ],
          ),
          // Books tab
          StatefulShellBranch(
            navigatorKey: _booksNavigatorKey,
            routes: [
              GoRoute(
                path: '/recipe-books',
                builder: (context, state) => const RecipeBooksScreen(),
                routes: [
                  // Archived books (must be before :id to avoid path collision)
                  GoRoute(
                    path: 'archived',
                    builder: (context, state) =>
                        const ArchivedRecipeBooksScreen(),
                  ),
                  GoRoute(
                    path: ':id',
                    builder: (context, state) {
                      final id = state.pathParameters['id']!;
                      return RecipeBookDetailScreen(recipeBookId: id);
                    },
                  ),
                ],
              ),
            ],
          ),
          // Cart tab
          StatefulShellBranch(
            navigatorKey: _cartNavigatorKey,
            routes: [
              GoRoute(
                path: '/cart',
                builder: (context, state) => const CartScreen(),
              ),
            ],
          ),
          // Calendar tab
          StatefulShellBranch(
            navigatorKey: _calendarNavigatorKey,
            routes: [
              GoRoute(
                path: '/calendar',
                builder: (context, state) => const CalendarScreen(),
              ),
            ],
          ),
          // Profile tab
          StatefulShellBranch(
            navigatorKey: _profileNavigatorKey,
            routes: [
              GoRoute(
                path: '/profile',
                builder: (context, state) => const ProfileScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
  );
  return _router!;
}
