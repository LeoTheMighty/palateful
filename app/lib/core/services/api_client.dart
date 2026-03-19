import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../config/environment.dart';
import 'auth_service.dart';

/// API client for communicating with the Palateful backend.
class ApiClient {
  late final Dio _dio;
  String? _authToken;
  AuthService? _authService;
  bool _isRefreshing = false;

  ApiClient() {
    _dio = Dio(BaseOptions(
      baseUrl: Environment.apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        // Required for ngrok free tier
        'ngrok-skip-browser-warning': 'true',
      },
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_authToken != null) {
          options.headers['Authorization'] = 'Bearer $_authToken';
        }
        return handler.next(options);
      },
      onError: (error, handler) async {
        debugPrint('API Error: ${error.response?.statusCode} - ${error.message}');

        // Auto-refresh on 401 and retry the request once
        if (error.response?.statusCode == 401 &&
            _authService != null &&
            !_isRefreshing) {
          _isRefreshing = true;
          try {
            final refreshed = await _authService!.refreshToken();
            if (refreshed && _authService!.accessToken != null) {
              _authToken = _authService!.accessToken;
              // Retry the original request with new token
              final opts = error.requestOptions;
              opts.headers['Authorization'] = 'Bearer $_authToken';
              final response = await _dio.fetch(opts);
              _isRefreshing = false;
              return handler.resolve(response);
            }
          } catch (e) {
            debugPrint('Token refresh during request failed: $e');
          }
          _isRefreshing = false;
        }

        return handler.next(error);
      },
    ));
  }

  /// Set the auth service for automatic token refresh on 401
  void setAuthService(AuthService authService) {
    _authService = authService;
  }

  void setAuthToken(String token) {
    _authToken = token;
  }

  void clearAuthToken() {
    _authToken = null;
  }

  bool get hasToken => _authToken != null;

  // Health check
  Future<Response> health() => _dio.get('/v1/health');

  // User endpoints
  Future<Response> getMe() => _dio.get('/v1/users/me');

  Future<Response> completeOnboarding({
    required String name,
    required String startMethod,
  }) =>
      _dio.post('/v1/users/me/complete-onboarding', data: {
        'name': name,
        'start_method': startMethod,
      });

  Future<Response> updateProfile({String? name}) =>
      _dio.put('/v1/users/me', data: {
        if (name != null) 'name': name,
      });

  Future<Response> setUsername(String username) =>
      _dio.put('/v1/users/me/username', data: {
        'username': username,
      });

  Future<Response> checkUsername(String username) =>
      _dio.get('/v1/users/check-username/$username');

  // Recipe Book endpoints
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) {
    return _dio.get('/v1/recipe-books', queryParameters: {
      'limit': limit,
      'offset': offset,
    });
  }

  Future<Response> createRecipeBook(Map<String, dynamic> data) {
    return _dio.post('/v1/recipe-books', data: data);
  }

  Future<Response> getRecipeBook(String id) {
    return _dio.get('/v1/recipe-books/$id');
  }

  Future<Response> updateRecipeBook(String id, Map<String, dynamic> data) {
    return _dio.put('/v1/recipe-books/$id', data: data);
  }

  Future<Response> deleteRecipeBook(String id) {
    return _dio.delete('/v1/recipe-books/$id');
  }

  Future<Response> archiveRecipeBook(String id) {
    return _dio.post('/v1/recipe-books/$id/archive');
  }

  Future<Response> restoreRecipeBook(String id) {
    return _dio.post('/v1/recipe-books/$id/restore');
  }

  Future<Response> getArchivedRecipeBooks() {
    return _dio.get('/v1/recipe-books/archived');
  }

  // Recipe endpoints
  Future<Response> getRecipes(String bookId,
      {int limit = 20, int offset = 0, String? search}) {
    return _dio.get('/v1/recipe-books/$bookId/recipes', queryParameters: {
      'limit': limit,
      'offset': offset,
      if (search != null) 'search': search,
    });
  }

  Future<Response> createRecipe(String bookId, Map<String, dynamic> data) {
    return _dio.post('/v1/recipe-books/$bookId/recipes', data: data);
  }

  Future<Response> getRecipe(String recipeId) {
    return _dio.get('/v1/recipes/$recipeId');
  }

  Future<Response> updateRecipe(String recipeId, Map<String, dynamic> data) {
    return _dio.put('/v1/recipes/$recipeId', data: data);
  }

  Future<Response> deleteRecipe(String recipeId) {
    return _dio.delete('/v1/recipes/$recipeId');
  }

  Future<Response> getRecipeVersions(String recipeId) {
    return _dio.get('/v1/recipes/$recipeId/versions');
  }

  Future<Response> getRecipeVersion(String recipeId, String versionId) {
    return _dio.get('/v1/recipes/$recipeId/versions/$versionId');
  }

  // Recipe photo upload
  Future<Response> getRecipePhotoUploadUrl(String recipeId, String filename) {
    return _dio.post('/v1/recipes/$recipeId/photo-upload-url', data: {
      'filename': filename,
    });
  }

  // Favorites
  Future<Response> toggleFavorite(String recipeId) {
    return _dio.post('/v1/recipes/$recipeId/favorite');
  }

  Future<Response> getFavorites() {
    return _dio.get('/v1/favorites');
  }

  // Archive
  Future<Response> getArchivedRecipes() {
    return _dio.get('/v1/recipes/archived');
  }

  Future<Response> restoreRecipe(String recipeId) {
    return _dio.post('/v1/recipes/$recipeId/restore');
  }

  // Move & Copy
  Future<Response> moveRecipe(String recipeId, String destinationBookId) {
    return _dio.post('/v1/recipes/$recipeId/move', data: {
      'destination_book_id': destinationBookId,
    });
  }

  Future<Response> copyRecipe(String recipeId, String destinationBookId) {
    return _dio.post('/v1/recipes/$recipeId/copy', data: {
      'destination_book_id': destinationBookId,
    });
  }

  // Bulk operations
  Future<Response> bulkMoveRecipes(List<String> recipeIds, String destinationBookId) {
    return _dio.post('/v1/recipes/bulk/move', data: {
      'recipe_ids': recipeIds,
      'destination_book_id': destinationBookId,
    });
  }

  Future<Response> bulkArchiveRecipes(List<String> recipeIds) {
    return _dio.post('/v1/recipes/bulk/archive', data: {
      'recipe_ids': recipeIds,
    });
  }

  Future<Response> bulkUpdateTags(List<String> recipeIds, {List<String>? addTags, List<String>? removeTags}) {
    return _dio.post('/v1/recipes/bulk/tags', data: {
      'recipe_ids': recipeIds,
      if (addTags != null) 'add_tags': addTags,
      if (removeTags != null) 'remove_tags': removeTags,
    });
  }

  // Search
  Future<Response> search(String query, {int limit = 20}) {
    return _dio.get('/v1/search', queryParameters: {
      'q': query,
      'limit': limit,
    });
  }

  // Ingredient endpoints
  Future<Response> searchIngredients(String query, {int limit = 10}) {
    return _dio.get('/v1/ingredients/search', queryParameters: {
      'q': query,
      'limit': limit,
    });
  }

  Future<Response> createIngredient(Map<String, dynamic> data) {
    return _dio.post('/v1/ingredients', data: data);
  }

  Future<Response> getIngredient(String id) {
    return _dio.get('/v1/ingredients/$id');
  }

  // Shopping List endpoints
  Future<Response> getShoppingLists({int limit = 20, int offset = 0}) {
    return _dio.get('/v1/shopping-lists', queryParameters: {
      'limit': limit,
      'offset': offset,
    });
  }

  Future<Response> createShoppingList(Map<String, dynamic> data) {
    return _dio.post('/v1/shopping-lists', data: data);
  }

  Future<Response> getShoppingList(String listId) {
    return _dio.get('/v1/shopping-lists/$listId');
  }

  Future<Response> updateShoppingList(String listId, Map<String, dynamic> data) {
    return _dio.put('/v1/shopping-lists/$listId', data: data);
  }

  Future<Response> deleteShoppingList(String listId) {
    return _dio.delete('/v1/shopping-lists/$listId');
  }

  Future<Response> addShoppingListItem(String listId, Map<String, dynamic> data) {
    return _dio.post('/v1/shopping-lists/$listId/items', data: data);
  }

  Future<Response> updateShoppingListItem(
      String listId, String itemId, Map<String, dynamic> data) {
    return _dio.put('/v1/shopping-lists/$listId/items/$itemId', data: data);
  }

  Future<Response> deleteShoppingListItem(String listId, String itemId) {
    return _dio.delete('/v1/shopping-lists/$listId/items/$itemId');
  }

  Future<Response> getShoppingListDeadlines(String listId) {
    return _dio.get('/v1/shopping-lists/$listId/deadlines');
  }

  Future<Response> getShoppingListEvents(String listId, {int sinceSequence = 0}) {
    return _dio.get('/v1/shopping-lists/$listId/events', queryParameters: {
      'since_sequence': sinceSequence,
    });
  }

  Future<Response> getShoppingListMembers(String listId) {
    return _dio.get('/v1/shopping-lists/$listId/members');
  }

  Future<Response> shareShoppingList(String listId) {
    return _dio.post('/v1/shopping-lists/$listId/share', data: {});
  }

  Future<Response> joinShoppingList(String shareCode) {
    return _dio.post('/v1/shopping-lists/join/$shareCode');
  }

  /// Get auth token for WebSocket connections
  String? get authToken => _authToken;

  /// Get base URL for WebSocket connections
  String get wsBaseUrl {
    final httpUrl = Environment.apiBaseUrl;
    return httpUrl.replaceFirst('http', 'ws');
  }

  // Push Notification Token endpoints
  Future<Response> registerPushToken({
    required String token,
    String? deviceType,
    String? deviceName,
  }) {
    return _dio.post('/v1/users/me/push-tokens', data: {
      'token': token,
      if (deviceType != null) 'device_type': deviceType,
      if (deviceName != null) 'device_name': deviceName,
    });
  }

  Future<Response> unregisterPushToken(String token) {
    return _dio.delete('/v1/users/me/push-tokens', data: {
      'token': token,
    });
  }

  Future<Response> getNotificationPreferences() {
    return _dio.get('/v1/users/me/notification-preferences');
  }

  Future<Response> updateNotificationPreferences({
    bool? pushEnabled,
    String? emailDigest,
    String? quietHoursStart,
    String? quietHoursEnd,
    String? timezone,
  }) {
    return _dio.put('/v1/users/me/notification-preferences', data: {
      if (pushEnabled != null) 'push_enabled': pushEnabled,
      if (emailDigest != null) 'email_digest': emailDigest,
      if (quietHoursStart != null) 'quiet_hours_start': quietHoursStart,
      if (quietHoursEnd != null) 'quiet_hours_end': quietHoursEnd,
      if (timezone != null) 'timezone': timezone,
    });
  }

  // Parser endpoints
  Future<Response> getParserUploadUrl(String filename) {
    return _dio.post('/v1/parser/upload-url', data: {
      'filename': filename,
    });
  }

  Future<Response> submitParserJob(String s3Key) {
    return _dio.post('/v1/parser/jobs', data: {
      's3_key': s3Key,
    });
  }

  Future<Response> submitBatchParserJob(List<String> s3Keys) {
    return _dio.post('/v1/parser/jobs/batch', data: {
      's3_keys': s3Keys,
    });
  }

  Future<Response> getParserJob(String jobId) {
    return _dio.get('/v1/parser/jobs/$jobId');
  }

  // Import endpoints
  Future<Response> startImport(String bookId, {required String sourceType, String? url, List<String>? urls, List<String>? ocrTexts}) {
    return _dio.post('/v1/recipe-books/$bookId/import', data: {
      'source_type': sourceType,
      if (url != null) 'url': url,
      if (urls != null) 'urls': urls,
      if (ocrTexts != null) 'ocr_texts': ocrTexts,
    });
  }

  Future<Response> getImportJob(String jobId) {
    return _dio.get('/v1/import-jobs/$jobId');
  }

  Future<Response> listImportItems(String jobId, {String? status}) {
    return _dio.get('/v1/import-jobs/$jobId/items', queryParameters: {
      if (status != null) 'status': status,
    });
  }

  Future<Response> getImportItem(String itemId) {
    return _dio.get('/v1/import-items/$itemId');
  }

  Future<Response> updateImportItem(String itemId, Map<String, dynamic> userEdits) {
    return _dio.put('/v1/import-items/$itemId', data: {
      'user_edits': userEdits,
    });
  }

  Future<Response> approveImportItem(String itemId) {
    return _dio.post('/v1/import-items/$itemId/approve');
  }

  Future<Response> skipImportItem(String itemId) {
    return _dio.post('/v1/import-items/$itemId/skip');
  }

  Future<Response> cancelImportJob(String jobId) {
    return _dio.delete('/v1/import-jobs/$jobId');
  }
}
