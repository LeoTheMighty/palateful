import 'package:dio/dio.dart';

import '../../../core/services/api_client.dart';
import '../models/meal.dart';

/// Typed exception for the 422 `COMPONENT_UNAVAILABLE` response — the
/// create path needs to show per-row Remove affordances when a component
/// was archived between selection and Save. mcv-5 reads this on the
/// sheet.
class MealComponentUnavailableException implements Exception {
  final List<String> recipeIds;
  MealComponentUnavailableException(this.recipeIds);
  @override
  String toString() =>
      'MealComponentUnavailableException(recipe_ids=$recipeIds)';
}

/// Typed exception for 409 `MEAL_COMPONENT_DUPLICATE` — surfaces as
/// "Already added" in the edit-mode picker.
class MealComponentDuplicateException implements Exception {
  MealComponentDuplicateException();
  @override
  String toString() => 'MealComponentDuplicateException()';
}

/// Typed exception for 422 `MEAL_MIN_COMPONENTS` — swipe-remove at 2.
class MealMinComponentsException implements Exception {
  MealMinComponentsException();
  @override
  String toString() => 'MealMinComponentsException()';
}

/// Typed exception for 422 `MEAL_REORDER_MISMATCH` — the drag-reorder
/// payload didn't match the current component set. The UI should rollback
/// the optimistic reorder and re-fetch.
class MealReorderMismatchException implements Exception {
  MealReorderMismatchException();
  @override
  String toString() => 'MealReorderMismatchException()';
}

/// Meal CRUD API client — wraps ApiClient + translates status codes into
/// typed exceptions so the UI layer doesn't switch on numeric codes.
class MealService {
  final ApiClient _apiClient;

  MealService(this._apiClient);

  // ---------------- reads ----------------

  Future<List<MealSummary>> listMealsInBook(
    String bookId, {
    int limit = 50,
    int offset = 0,
    bool includeArchived = false,
  }) async {
    final response = await _apiClient.listMealsInBook(
      bookId,
      limit: limit,
      offset: offset,
      includeArchived: includeArchived,
    );
    return _parseSummaryList(response);
  }

  Future<List<MealSummary>> listMeals({
    int? limit,
    int offset = 0,
    bool includeArchived = false,
    bool? archived,
    String? scope,
  }) async {
    final response = await _apiClient.listMeals(
      limit: limit,
      offset: offset,
      includeArchived: includeArchived,
      archived: archived,
      scope: scope,
    );
    return _parseSummaryList(response);
  }

  /// mcal-5: autocomplete for the plan-meal Meal picker. Returns meals
  /// matching the query across readable books (excludes archived), up to
  /// [limit] hits (server capped at 50; default 8 matches the call site).
  Future<List<MealSummary>> searchMeals(
    String query, {
    int limit = 8,
  }) async {
    final response = await _apiClient.listMeals(q: query, limit: limit);
    return _parseSummaryList(response);
  }

  /// mcal-5: append a Meal's aggregated ingredients to a shopping list
  /// without scheduling the Meal on the calendar. Returns the raw
  /// response payload so callers can surface `items_added` /
  /// `items_skipped` counts and the `meal_summary` block.
  Future<MealAddToShoppingListResult> addToShoppingList(
    String mealId,
    String shoppingListId,
  ) async {
    final response = await _apiClient.addMealToShoppingList(
      mealId,
      {'shopping_list_id': shoppingListId},
    );
    return MealAddToShoppingListResult.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  /// md-2: reverse lookup — Meals that reference a given recipe.
  /// Returns an empty list if the user cannot read any meal (or none exist).
  Future<List<MealSummary>> listMealsUsingRecipe(String recipeId) async {
    final response = await _apiClient.listMealsUsingRecipe(recipeId);
    final data = response.data as Map<String, dynamic>;
    final items = (data['items'] as List? ?? [])
        .cast<Map<String, dynamic>>();
    return items.map(MealSummary.fromJson).toList();
  }

  Future<Meal> getMeal(String mealId) async {
    final response = await _apiClient.getMeal(mealId);
    return Meal.fromJson(response.data as Map<String, dynamic>);
  }

  // ---------------- writes ----------------

  Future<Meal> createMeal({
    required String bookId,
    required String name,
    String? description,
    required List<String> componentRecipeIds,
  }) async {
    try {
      final response = await _apiClient.createMealInBook(bookId, {
        'name': name,
        if (description != null && description.isNotEmpty)
          'description': description,
        'component_recipe_ids': componentRecipeIds,
      });
      return Meal.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      _rethrowTyped(e);
    }
  }

  Future<Meal> updateMeal(
    String mealId, {
    String? name,
    String? description,
  }) async {
    final data = <String, dynamic>{};
    if (name != null) data['name'] = name;
    if (description != null) data['description'] = description;
    final response = await _apiClient.updateMeal(mealId, data);
    return Meal.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Meal> addRecipeToMeal(
    String mealId, {
    required String recipeId,
    int? orderIndex,
  }) async {
    try {
      final response = await _apiClient.addRecipeToMeal(mealId, {
        'recipe_id': recipeId,
        if (orderIndex != null) 'order_index': orderIndex,
      });
      return Meal.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      _rethrowTyped(e);
    }
  }

  Future<Meal> removeRecipeFromMeal(
    String mealId,
    String recipeId,
  ) async {
    try {
      final response =
          await _apiClient.removeRecipeFromMeal(mealId, recipeId);
      return Meal.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      _rethrowTyped(e);
    }
  }

  Future<Meal> reorderMealComponents(
    String mealId,
    List<String> recipeIds,
  ) async {
    try {
      final response = await _apiClient.reorderMealComponents(mealId, {
        'recipe_ids': recipeIds,
      });
      return Meal.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      _rethrowTyped(e);
    }
  }

  Future<void> archiveMeal(String mealId) async {
    await _apiClient.archiveMeal(mealId);
  }

  Future<void> restoreMeal(String mealId) async {
    await _apiClient.restoreMeal(mealId);
  }

  Future<bool> favoriteMeal(String mealId) async {
    final response = await _apiClient.favoriteMeal(mealId);
    final data = response.data as Map<String, dynamic>;
    return data['is_favorite'] as bool? ?? true;
  }

  Future<bool> unfavoriteMeal(String mealId) async {
    final response = await _apiClient.unfavoriteMeal(mealId);
    final data = response.data as Map<String, dynamic>;
    return data['is_favorite'] as bool? ?? false;
  }

  /// msa-1 / msa-2: generate (or re-fetch) the public share link for a
  /// Meal. Idempotent — the first call returns 201 + token, subsequent
  /// calls return 200 + the same token.
  Future<ShareMealResult> share(String mealId) async {
    final response = await _apiClient.shareMeal(mealId);
    final data = response.data as Map<String, dynamic>;
    return ShareMealResult(
      token: data['token'] as String,
      deepLink: data['deep_link'] as String,
    );
  }

  /// msa-1 / msa-2: unauthenticated read of a Meal by its share token.
  Future<PublicMealDto> getPublicMealByToken(String token) async {
    final response = await _apiClient.getPublicMealByToken(token);
    return PublicMealDto.fromJson(response.data as Map<String, dynamic>);
  }

  // ---------------- helpers ----------------

  List<MealSummary> _parseSummaryList(Response response) {
    final data = response.data as Map<String, dynamic>;
    final items = (data['items'] as List? ?? [])
        .cast<Map<String, dynamic>>();
    return items.map(MealSummary.fromJson).toList();
  }

  /// Translate Dio error → typed exception. Falls through to the original
  /// DioException when the response isn't a Meal-specific error code.
  Never _rethrowTyped(DioException e) {
    final status = e.response?.statusCode;
    final body = e.response?.data;
    final errorCode = (body is Map<String, dynamic>)
        ? body['error_code']
        : null;
    if (status == 422 && errorCode == 306) {
      // MEAL_COMPONENT_UNAVAILABLE (306) — carries recipe_ids in data
      final data = (body as Map<String, dynamic>)['data'];
      final rawIds = (data is Map<String, dynamic>)
          ? data['recipe_ids']
          : null;
      final recipeIds = (rawIds is List)
          ? rawIds.map((e) => e.toString()).toList()
          : <String>[];
      throw MealComponentUnavailableException(recipeIds);
    }
    if (status == 409 && errorCode == 303) {
      throw MealComponentDuplicateException();
    }
    if (status == 422 && errorCode == 304) {
      throw MealMinComponentsException();
    }
    if (status == 422 && errorCode == 305) {
      throw MealReorderMismatchException();
    }
    throw e;
  }
}
