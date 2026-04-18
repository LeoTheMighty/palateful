import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../di/injection.dart';
import '../services/auth_service.dart';
import '../services/error_reporter.dart';
import '../../features/auth/login_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/onboarding/onboarding_welcome_screen.dart';
import '../../features/onboarding/onboarding_notification_permission_screen.dart';
import '../../features/onboarding/onboarding_start_screen.dart';
import '../../features/activity/activity_screen.dart';
import '../../features/activity/import_history_screen.dart';
import '../../features/recipe_books/archived_recipe_books_screen.dart';
import '../../features/recipe_books/recipe_book_members_screen.dart';
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
import '../../features/recipes/add_recipe/audio_import_screen.dart';
import '../../features/recipes/add_recipe/pdf_import_screen.dart';
import '../../features/recipes/add_recipe/spreadsheet_import_screen.dart';
import '../../features/recipes/add_recipe/text_paste_import_screen.dart';
import '../../features/recipes/add_recipe/url_import_screen.dart';
import '../../features/recipes/recipe_version_diff_screen.dart';
import '../../features/recipes/recipe_version_history_screen.dart';
import '../../features/search/search_screen.dart';
import '../../features/cart/cart_screen.dart';
import '../../features/shopping_cart/screens/shopping_list_screen.dart';
import '../../features/calendar/calendar_members_screen.dart';
import '../../features/calendar/calendar_screen.dart';
import '../../features/pantry/screens/pantry_editor_screen.dart';
import '../../features/pantry/screens/pantry_list_screen.dart';
import '../../features/invitations/invitations_screen.dart';
import '../../features/invitations/invite_link_preview_screen.dart';
import '../../features/recipes/public_recipe_screen.dart';
import '../../features/admin/admin_dashboard_screen.dart';
import '../../features/admin/admin_logs_screen.dart';
import '../../features/admin/admin_errors_screen.dart';
import '../../features/admin/admin_error_detail_screen.dart';
import '../../features/admin/admin_users_screen.dart';
import '../../features/chat/chat_screen.dart';
import '../../features/profile/notification_preferences_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/profile/recurring_plans/recurring_plans_screen.dart';
import '../../shared/widgets/scaffold_with_bottom_nav.dart';
import 'page_transitions.dart';

/// Navigation keys for each bottom nav branch
final _rootNavigatorKey = GlobalKey<NavigatorState>();

/// Public accessor for the root navigator key (used by PushNotificationService).
GlobalKey<NavigatorState> get rootNavigatorKey => _rootNavigatorKey;
final _homeNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'home');
final _activityNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'activity');
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
    observers: [CrashlyticsNavObserver()],
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

      // Admin routes - require admin role
      final isAdminRoute = currentLocation.startsWith('/admin');
      if (isAdminRoute && !authService.isAdmin) {
        debugPrint('Redirecting to / (not admin)');
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
        path: '/onboarding/notifications',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final name = extra?['name'] as String? ?? '';
          return OnboardingNotificationPermissionScreen(name: name);
        },
      ),
      GoRoute(
        path: '/onboarding/start',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final name = extra?['name'] as String? ?? '';
          final notificationPermissionStatus =
              extra?['notification_permission_status'] as String?;
          return OnboardingStartScreen(
            name: name,
            notificationPermissionStatus: notificationPermissionStatus,
          );
        },
      ),
      // Archived recipes (must be before /recipes/:id to avoid path collision)
      GoRoute(
        path: '/recipes/archived',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const ArchivedRecipesScreen(),
      ),
      // Version history (must be before /recipes/:id to avoid path collision)
      GoRoute(
        path: '/recipes/:id/versions',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final id = state.pathParameters['id']!;
          final extra = state.extra as Map<String, dynamic>?;
          final recipeName = extra?['recipeName'] as String? ?? '';
          return RecipeVersionHistoryScreen(recipeId: id, recipeName: recipeName);
        },
      ),
      GoRoute(
        path: '/recipes/:id/versions/:versionId',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final id = state.pathParameters['id']!;
          final versionId = state.pathParameters['versionId']!;
          final extra = state.extra as Map<String, dynamic>?;
          final versionNumber = extra?['versionNumber'] as int? ?? 0;
          return RecipeVersionDiffScreen(
            recipeId: id,
            versionId: versionId,
            versionNumber: versionNumber,
          );
        },
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
          final extra = state.extra as Map<String, dynamic>?;
          final scaleFactor = (extra?['scaleFactor'] as num?)?.toDouble() ?? 1.0;
          return buildReduceMotionPage(
            context: context,
            state: state,
            child: CookModeScreen(recipeId: id, scaleFactor: scaleFactor),
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
        path: '/recipes/add/text',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final recipeBookId = extra?['recipeBookId'] as String?;
          return TextPasteImportScreen(recipeBookId: recipeBookId);
        },
      ),
      GoRoute(
        path: '/recipes/add/audio',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final recipeBookId = extra?['recipeBookId'] as String?;
          return AudioImportScreen(recipeBookId: recipeBookId);
        },
      ),
      GoRoute(
        path: '/recipes/add/pdf',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final recipeBookId = extra?['recipeBookId'] as String?;
          return PdfImportScreen(recipeBookId: recipeBookId);
        },
      ),
      GoRoute(
        path: '/recipes/add/spreadsheet',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>?;
          final recipeBookId = extra?['recipeBookId'] as String?;
          return SpreadsheetImportScreen(recipeBookId: recipeBookId);
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

      GoRoute(
        path: '/invitations',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const InvitationsScreen(),
      ),
      GoRoute(
        path: '/profile/recurring-plans',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const RecurringPlansScreen(),
      ),
      GoRoute(
        path: '/invite/:token',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final token = state.pathParameters['token']!;
          return InviteLinkPreviewScreen(token: token);
        },
      ),
      GoRoute(
        path: '/recipe-public/:token',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final token = state.pathParameters['token']!;
          return PublicRecipeScreen(token: token);
        },
      ),
      GoRoute(
        path: '/chat/:threadId',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final threadId = state.pathParameters['threadId']!;
          return ChatScreen(threadId: threadId);
        },
      ),

      // Admin routes (outside shell — web-only admin dashboard)
      GoRoute(
        path: '/admin',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const AdminDashboardScreen(),
      ),
      GoRoute(
        path: '/admin/logs',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const AdminLogsScreen(),
      ),
      GoRoute(
        path: '/admin/errors',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const AdminErrorsScreen(),
      ),
      GoRoute(
        path: '/admin/errors/:id',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final id = state.pathParameters['id']!;
          return AdminErrorDetailScreen(errorId: id);
        },
      ),
      GoRoute(
        path: '/admin/users',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const AdminUsersScreen(),
      ),

      // Recipe books routes (outside shell — navigated via push)
      GoRoute(
        path: '/recipe-books',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const RecipeBooksScreen(),
      ),
      GoRoute(
        path: '/recipe-books/archived',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const ArchivedRecipeBooksScreen(),
      ),
      GoRoute(
        path: '/recipe-books/:id',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final id = state.pathParameters['id']!;
          return RecipeBookDetailScreen(recipeBookId: id);
        },
      ),
      GoRoute(
        path: '/recipe-books/:id/members',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final id = state.pathParameters['id']!;
          final role = state.uri.queryParameters['role'] ?? 'viewer';
          return RecipeBookMembersScreen(
            recipeBookId: id,
            userRole: role,
          );
        },
      ),
      GoRoute(
        path: '/calendar/:id/members',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final id = state.pathParameters['id']!;
          final role = state.uri.queryParameters['role'] ?? 'editor';
          final name = state.uri.queryParameters['name'] ?? 'Calendar';
          return CalendarMembersScreen(
            calendarId: id,
            calendarName: name,
            userRole: role,
          );
        },
      ),

      // Shell route with bottom navigation
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return ScaffoldWithBottomNav(navigationShell: navigationShell);
        },
        branches: [
          // Home tab (index 0)
          StatefulShellBranch(
            navigatorKey: _homeNavigatorKey,
            routes: [
              GoRoute(
                path: '/',
                builder: (context, state) => const HomeScreen(),
              ),
              GoRoute(
                path: '/search',
                builder: (context, state) => SearchScreen(
                  initialQuery: state.uri.queryParameters['q'],
                ),
              ),
              GoRoute(
                path: '/pantry',
                builder: (context, state) => const PantryListScreen(),
                routes: [
                  GoRoute(
                    path: 'add',
                    builder: (context, state) =>
                        const PantryEditorScreen(ingredientId: 'new'),
                  ),
                  GoRoute(
                    path: 'edit/:ingredientId',
                    builder: (context, state) => PantryEditorScreen(
                      ingredientId: state.pathParameters['ingredientId']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          // Cart tab (index 1)
          StatefulShellBranch(
            navigatorKey: _cartNavigatorKey,
            routes: [
              GoRoute(
                path: '/cart',
                builder: (context, state) => const CartScreen(),
              ),
              GoRoute(
                path: '/shopping-lists/:id',
                builder: (context, state) {
                  final id = state.pathParameters['id']!;
                  return ShoppingListScreen(listId: id);
                },
              ),
            ],
          ),
          // Activity tab (index 2)
          StatefulShellBranch(
            navigatorKey: _activityNavigatorKey,
            routes: [
              GoRoute(
                path: '/activity',
                builder: (context, state) {
                  // Canonical deep-link schema: /activity?filter=<enum>
                  // enum: all | imports | partner | reminders (bugs-act-3)
                  final filter = state.uri.queryParameters['filter'];
                  return ActivityScreen(initialFilter: filter);
                },
                routes: [
                  GoRoute(
                    path: 'import-history',
                    builder: (context, state) => const ImportHistoryScreen(),
                  ),
                ],
              ),
            ],
          ),
          // Calendar tab (index 3)
          StatefulShellBranch(
            navigatorKey: _calendarNavigatorKey,
            routes: [
              GoRoute(
                path: '/calendar',
                builder: (context, state) => const CalendarScreen(),
              ),
            ],
          ),
          // Profile tab (index 4)
          StatefulShellBranch(
            navigatorKey: _profileNavigatorKey,
            routes: [
              GoRoute(
                path: '/profile',
                builder: (context, state) => const ProfileScreen(),
                routes: [
                  GoRoute(
                    path: 'notifications',
                    builder: (context, state) =>
                        const NotificationPreferencesScreen(),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    ],
  );
  return _router!;
}
