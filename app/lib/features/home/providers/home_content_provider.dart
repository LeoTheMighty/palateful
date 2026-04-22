import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/shared_state_service.dart';
import '../../../core/state/mutation_bus.dart';

/// Value object produced by [homeContentProvider]. Holds the pristine
/// (pre-filter, post-favorite-merge) data the Home grid renders from.
///
/// The screen keeps its filter/sort state local (pfc-4 guarantee:
/// filter flips do not refetch) and derives the visible list from this.
class HomeContent {
  const HomeContent({
    required this.recipes,
    required this.meals,
    required this.favorites,
    required this.favoriteIds,
    required this.favoriteMealIds,
    required this.todayMealEvent,
    required this.recentlyCooked,
  });

  /// All recipes across readable books. Each map has `is_favorite`
  /// merged in and `kind: 'recipe'`.
  final List<Map<String, dynamic>> recipes;

  /// Home-scope meals (`GET /v1/meals?scope=home`). Each has
  /// `kind: 'meal'` attached.
  final List<Map<String, dynamic>> meals;

  /// Union of favorited recipes + favorited meals for the carousel.
  final List<Map<String, dynamic>> favorites;
  final Set<String> favoriteIds;
  final Set<String> favoriteMealIds;

  /// `null` when nothing is scheduled for today.
  final Map<String, dynamic>? todayMealEvent;
  final List<Map<String, dynamic>> recentlyCooked;

  static const empty = HomeContent(
    recipes: <Map<String, dynamic>>[],
    meals: <Map<String, dynamic>>[],
    favorites: <Map<String, dynamic>>[],
    favoriteIds: <String>{},
    favoriteMealIds: <String>{},
    todayMealEvent: null,
    recentlyCooked: <Map<String, dynamic>>[],
  );
}

/// Fans out the same fetches the old imperative `_loadRecipes` /
/// `_loadHomeContext` made. `autoDispose` for cheap rebuilds between
/// tab switches; `ref.keepAlive()` gives a session-level cache so
/// hopping in and out of other tabs doesn't refetch.
///
/// Reacts to recipe + meal mutations via the MutationBus — a server
/// 200 on a mutation somewhere else in the app invalidates this
/// provider, which refetches and reconciles. Pull-to-refresh is a
/// separate path (`ref.refresh(...)` from the UI) — see epic Locked
/// Decision #2.
final homeContentProvider =
    FutureProvider.autoDispose<HomeContent>((ref) async {
  ref.keepAlive();

  // Subscribe directly to the broadcast stream. `ref.listen` on a
  // `Provider<Stream<T>>` only fires on *value change*, and the bus's
  // stream instance is stable for the app lifetime — so the canonical
  // shape is read-once + listen + cancel-on-dispose.
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (_shouldInvalidate(event)) ref.invalidateSelf();
  });
  ref.onDispose(sub.cancel);

  return _loadHomeContent();
});

bool _shouldInvalidate(MutationEvent event) => switch (event) {
      RecipeCreated() ||
      RecipeUpdated() ||
      RecipeArchived() ||
      RecipeUnarchived() ||
      RecipeFavorited() ||
      RecipeForked() ||
      RecipeMoved() ||
      RecipeBulkArchived() ||
      MealCreated() ||
      MealUpdated() ||
      MealArchived() ||
      MealFavorited() =>
        true,
      _ => false,
    };

Future<HomeContent> _loadHomeContent() async {
  final api = getIt<ApiClient>();

  final booksResponse = await api.getRecipeBooks();
  final books =
      List<Map<String, dynamic>>.from(booksResponse.data['items'] ?? []);

  // Side-effect: mirror book list into the iOS App Group so the Share
  // Extension's book picker has something to show. Debounced inside
  // the service. Best-effort — a failure here must never tank the
  // home load (e.g. test harnesses that don't register the service).
  try {
    getIt<SharedStateService>().syncRecipeBooks(
      books
          .map((m) => SharedRecipeBook.fromMap(Map<String, dynamic>.from(m)))
          .toList(),
    );
  } catch (_) {}

  final recipesFuture = _loadAllRecipesFromBooks(api, books);
  final favFuture = api.getFavorites();
  // md-4: parallel Meal fetch. A failure must NOT block the grid — a
  // zero-Meal render is bit-identical to pre-epic.
  final mealsFuture = _loadMealsForHome(api);
  final todayFuture = _loadTodayMealEvent(api);
  final recentlyCookedFuture = _loadRecentlyCooked(api);

  final results = await Future.wait([
    recipesFuture,
    favFuture,
    mealsFuture,
    todayFuture,
    recentlyCookedFuture,
  ]);
  final allRecipes = results[0] as List<Map<String, dynamic>>;
  final favResponse = results[1];
  final meals = results[2] as List<Map<String, dynamic>>;
  final todayMealEvent = results[3] as Map<String, dynamic>?;
  final recentlyCooked = results[4] as List<Map<String, dynamic>>;

  final favData = (favResponse as dynamic).data as Map<String, dynamic>;
  final favItems = ((favData['items'] as List<dynamic>?) ?? [])
      .whereType<Map>()
      .map((m) => Map<String, dynamic>.from(m))
      .toList();
  final favIds = favItems
      .map((f) => f['id']?.toString())
      .whereType<String>()
      .toSet();

  // md-3: favorited meals render alongside favorited recipes.
  final favMealItems = ((favData['favorited_meals'] as List<dynamic>?) ?? [])
      .whereType<Map>()
      .map((m) => {...Map<String, dynamic>.from(m), 'kind': 'meal'})
      .toList();
  final favMealIds = favMealItems
      .map((m) => m['id']?.toString())
      .whereType<String>()
      .toSet();

  for (final recipe in allRecipes) {
    recipe['is_favorite'] = favIds.contains(recipe['id']?.toString());
    recipe['kind'] = 'recipe';
  }

  final favorites = <Map<String, dynamic>>[...favItems, ...favMealItems];

  return HomeContent(
    recipes: allRecipes,
    meals: meals,
    favorites: favorites,
    favoriteIds: favIds,
    favoriteMealIds: favMealIds,
    todayMealEvent: todayMealEvent,
    recentlyCooked: recentlyCooked,
  );
}

Future<List<Map<String, dynamic>>> _loadAllRecipesFromBooks(
  ApiClient api,
  List<Map<String, dynamic>> books,
) async {
  final results = await Future.wait(
    books.map((book) async {
      try {
        final bookDetail = await api.getRecipeBook(book['id']);
        final recipes = List<Map<String, dynamic>>.from(
          (bookDetail.data['recipes'] as List? ?? [])
              .whereType<Map>()
              .map((m) => Map<String, dynamic>.from(m)),
        );
        for (final recipe in recipes) {
          recipe['recipe_book_id'] = book['id'];
          recipe['recipe_book_name'] = book['name'];
        }
        return recipes;
      } catch (_) {
        return <Map<String, dynamic>>[];
      }
    }),
  );
  return results.expand((r) => r).toList();
}

Future<List<Map<String, dynamic>>> _loadMealsForHome(ApiClient api) async {
  try {
    final resp = await api.listMeals(scope: 'home');
    final items =
        ((resp.data as Map<String, dynamic>)['items'] as List? ?? [])
            .whereType<Map>()
            .map((m) => {...Map<String, dynamic>.from(m), 'kind': 'meal'})
            .toList();
    return items;
  } catch (_) {
    return <Map<String, dynamic>>[];
  }
}

Future<Map<String, dynamic>?> _loadTodayMealEvent(ApiClient api) async {
  try {
    final resp = await api.getMealEventsForToday();
    final items = resp.data['items'] as List?;
    if (items != null && items.isNotEmpty && items[0]['recipe'] != null) {
      return Map<String, dynamic>.from(items[0] as Map);
    }
    return null;
  } catch (_) {
    return null;
  }
}

Future<List<Map<String, dynamic>>> _loadRecentlyCooked(ApiClient api) async {
  try {
    final resp = await api.getRecentlyCookedRecipes();
    return ((resp.data['items'] as List?) ?? [])
        .whereType<Map>()
        .map((m) => Map<String, dynamic>.from(m))
        .toList();
  } catch (_) {
    return <Map<String, dynamic>>[];
  }
}
