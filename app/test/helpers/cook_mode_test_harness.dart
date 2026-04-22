import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/cook_timer_notification_service.dart';
import 'package:palateful/core/services/live_activity_service.dart';
import 'package:palateful/core/services/recipe_cache_service.dart';

/// Minimal stub of the production FastAPI recipe payload — enough for
/// `CookModeScreen._populateFromData` to succeed.
Map<String, dynamic> fakeRecipe({
  String id = 'r1',
  String name = 'Test Recipe',
  int stepCount = 3,
  int ingredientCount = 4,
}) {
  final steps = List.generate(
    stepCount,
    (i) => {
      'step_number': i + 1,
      'instruction': 'Do step ${i + 1}',
      'timers': const [],
    },
  );
  final ingredients = List.generate(
    ingredientCount,
    (i) => {
      'ingredient': {'canonical_name': 'Ingredient ${i + 1}'},
      'quantity_display': '1',
      'unit_display': 'cup',
      'notes': null,
    },
  );
  return {
    'id': id,
    'name': name,
    'servings': 4,
    'steps': steps,
    'ingredients': ingredients,
  };
}

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

/// ApiClient fake scoped to the calls `CookModeScreen` makes:
/// `getRecipe`, `getNotificationPreferences`, `recordClientError`.
class FakeCookModeApiClient extends ApiClient {
  final Map<String, dynamic> recipe;
  final Map<String, dynamic> notificationPrefs;

  FakeCookModeApiClient({
    Map<String, dynamic>? recipe,
    Map<String, dynamic>? notificationPrefs,
  })  : recipe = recipe ?? fakeRecipe(),
        notificationPrefs = notificationPrefs ??
            const {
              'categories': {'timers': true},
            };

  @override
  Future<Response> getRecipe(String recipeId, {bool debug = false}) async =>
      _fakeResponse(recipe);

  @override
  Future<Response> getNotificationPreferences() async =>
      _fakeResponse(notificationPrefs);

  @override
  Future<Response> recordClientError({
    required String errorType,
    required String errorMessage,
    String? area,
    String? operation,
    Map<String, Object?>? extras,
    int? statusCode,
  }) async =>
      _fakeResponse({'ok': true});
}

/// Registers fakes for every getIt lookup `CookModeScreen` performs.
/// Call from `setUp`; pair with [tearDownCookModeHarness].
Future<void> setUpCookModeHarness({
  Map<String, dynamic>? recipe,
  Map<String, dynamic>? notificationPrefs,
}) async {
  TestWidgetsFlutterBinding.ensureInitialized();
  // ApiClient reads API_BASE_URL during construction, so stub dotenv.
  if (!dotenv.isInitialized) {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  }
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(
    FakeCookModeApiClient(recipe: recipe, notificationPrefs: notificationPrefs),
  );
  if (gi.isRegistered<CookTimerNotificationService>()) {
    gi.unregister<CookTimerNotificationService>();
  }
  // The production service no-ops every public call when `_initialized`
  // is false, so an unstarted instance is safe in tests.
  gi.registerSingleton<CookTimerNotificationService>(
    CookTimerNotificationService(),
  );
  if (gi.isRegistered<LiveActivityService>()) {
    gi.unregister<LiveActivityService>();
  }
  gi.registerSingleton<LiveActivityService>(LiveActivityService());
  if (gi.isRegistered<RecipeCacheService>()) {
    gi.unregister<RecipeCacheService>();
  }
  gi.registerSingleton<RecipeCacheService>(RecipeCacheService());
}

void tearDownCookModeHarness() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<CookTimerNotificationService>()) {
    gi.unregister<CookTimerNotificationService>();
  }
  if (gi.isRegistered<LiveActivityService>()) {
    gi.unregister<LiveActivityService>();
  }
  if (gi.isRegistered<RecipeCacheService>()) {
    gi.unregister<RecipeCacheService>();
  }
}
