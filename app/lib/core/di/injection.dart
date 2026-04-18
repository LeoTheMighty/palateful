import 'package:get_it/get_it.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/cook_timer_notification_service.dart';
import '../services/push_notification_service.dart';
import '../services/recipe_cache_service.dart';
import '../services/shared_state_service.dart';
import '../services/pending_imports_reconciler.dart';
import '../../features/pantry/services/pantry_service.dart';
import '../../features/shopping_cart/services/shopping_cart_service.dart';
import '../../features/recipe_books/services/recipe_book_sync_service.dart';
import '../../features/recipes/add_recipe/batch_parser_service.dart';
import '../../features/calendar/services/calendar_service.dart';
import '../../features/calendar/services/meal_calendar_service.dart';
import '../../features/meals/services/meal_service.dart';
import '../../features/activity/providers/activity_read_provider.dart';
import '../../features/recipes/services/session_alias_map.dart';

final getIt = GetIt.instance;

/// Initialize dependency injection
void setupDependencies() {
  // Services (singletons)
  getIt.registerSingleton<AuthService>(AuthService());
  getIt.registerSingleton<ApiClient>(ApiClient());
  getIt.registerLazySingleton<ShoppingCartService>(() => ShoppingCartService());
  getIt.registerLazySingleton<PantryService>(() => PantryService());
  getIt.registerLazySingleton<RecipeBookSyncService>(() => RecipeBookSyncService());
  getIt.registerLazySingleton<PushNotificationService>(
    () => PushNotificationService(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<BatchParserService>(() => BatchParserService());
  getIt.registerLazySingleton<CookTimerNotificationService>(
    () => CookTimerNotificationService(),
  );
  getIt.registerLazySingleton<RecipeCacheService>(() => RecipeCacheService());
  getIt.registerLazySingleton<SharedStateService>(() => SharedStateService());
  getIt.registerLazySingleton<PendingImportsReconciler>(
    () => PendingImportsReconciler.forApi(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<MealCalendarService>(
    () => MealCalendarService(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<CalendarService>(
    () => CalendarService(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<MealService>(
    () => MealService(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<ActivityReadProvider>(
    () => ActivityReadProvider(getIt<ApiClient>()),
  );
  // Session-scoped alias map for the UnitInput coerce-on-blur path
  // (riip-5). Seeded synchronously with the hardcoded fallback; the
  // live fetch is fired-and-forgotten at startup.
  getIt.registerLazySingleton<SessionAliasMap>(
    () => SessionAliasMap(getIt<ApiClient>())..init(),
  );
}
