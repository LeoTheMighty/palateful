import 'package:get_it/get_it.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/cook_timer_notification_service.dart';
import '../services/push_notification_service.dart';
import '../services/recipe_cache_service.dart';
import '../../features/shopping_cart/services/shopping_cart_service.dart';
import '../../features/recipe_books/services/recipe_book_sync_service.dart';
import '../../features/recipes/add_recipe/batch_parser_service.dart';

final getIt = GetIt.instance;

/// Initialize dependency injection
void setupDependencies() {
  // Services (singletons)
  getIt.registerSingleton<AuthService>(AuthService());
  getIt.registerSingleton<ApiClient>(ApiClient());
  getIt.registerLazySingleton<ShoppingCartService>(() => ShoppingCartService());
  getIt.registerLazySingleton<RecipeBookSyncService>(() => RecipeBookSyncService());
  getIt.registerLazySingleton<PushNotificationService>(
    () => PushNotificationService(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<BatchParserService>(() => BatchParserService());
  getIt.registerLazySingleton<CookTimerNotificationService>(
    () => CookTimerNotificationService(),
  );
  getIt.registerLazySingleton<RecipeCacheService>(() => RecipeCacheService());
}
