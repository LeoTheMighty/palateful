import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../config/environment.dart';
import 'auth_service.dart';
import 'error_reporter.dart';

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

        // Report server-side failures (5xx) to Crashlytics as non-fatal
        // events. Resolved 401 retries above don't reach here. Client
        // errors (4xx) and connectivity failures are intentionally
        // skipped for now — see Phase 1 scope.
        final status = error.response?.statusCode;
        if (status != null && status >= 500 && status < 600) {
          ErrorReporter.report(
            error,
            error.stackTrace,
            area: 'api',
          );
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

  /// Expose the underlying Dio instance (e.g. for SSE streaming in ChatService).
  Dio get dio => _dio;

  // Health check
  Future<Response> health() => _dio.get('/v1/health');

  /// Fetch the alias → canonical-unit map (riip-4). Cached server-side
  /// for 24 h; the Dio client honors the Cache-Control header, so the
  /// SessionAliasMap doesn't need an in-process TTL of its own.
  Future<Response> getUnitAliases() => _dio.get('/v1/units/aliases');

  // User endpoints
  Future<Response> getMe() => _dio.get('/v1/users/me');

  Future<Response> completeOnboarding({
    required String name,
    required String startMethod,
    String? notificationPermissionStatus,
  }) =>
      _dio.post('/v1/users/me/complete-onboarding', data: {
        'name': name,
        'start_method': startMethod,
        if (notificationPermissionStatus != null)
          'notification_permission_status': notificationPermissionStatus,
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

  Future<Response> setDefaultRecipeBook(String? recipeBookId) =>
      _dio.put('/v1/users/me/default-recipe-book', data: {
        'recipe_book_id': recipeBookId,
      });

  Future<Response> setDefaultShoppingList(String? shoppingListId) =>
      _dio.put('/v1/users/me/default-shopping-list', data: {
        'shopping_list_id': shoppingListId,
      });

  Future<Response> exportRecipes() => _dio.get('/v1/users/me/export');

  // Activity endpoints
  Future<Response> getActivities({int limit = 50, int offset = 0}) {
    return _dio.get('/v1/activities', queryParameters: {
      'limit': limit,
      'offset': offset,
    });
  }

  /// afh-3 — See-all history fetch. Sends `since_days=` as the empty-
  /// string null sentinel (afh-1a AC3) so the backend disables the 30d
  /// retention window; client-side we cannot just omit the key because
  /// "absent" means "use default = 30".
  Future<Response> listActivitiesSeeAll({
    String? cursor,
    int limit = 50,
  }) {
    return _dio.get('/v1/activities', queryParameters: {
      'include_archived': true,
      'include_read': true,
      'since_days': '',
      'limit': limit,
      if (cursor != null) 'cursor': cursor,
    });
  }

  /// afh-3 — See-all triple for the Notifications tab.
  Future<Response> getActivitiesSeeAllCount() =>
      _dio.get('/v1/activities/see-all-count');

  /// afh-4 — See-all triple for the Imports tab.
  Future<Response> getImportItemsSeeAllCount() =>
      _dio.get('/v1/import-items/see-all-count');

  /// afh-4 — cursor-paginated import-items list (See-all mode).
  /// `jobId` scopes to a single import job; the Imports See-all uses
  /// the job-level endpoint to walk archived + old-completed items.
  Future<Response> listImportItemsSeeAll(
    String jobId, {
    String? cursor,
    int limit = 50,
  }) {
    return _dio.get('/v1/import-jobs/$jobId/items', queryParameters: {
      'include_archived': true,
      'limit': limit,
      if (cursor != null) 'cursor': cursor,
    });
  }

  Future<Response> getUnreadActivityCount() =>
      _dio.get('/v1/activities/unread-count');

  Future<Response> markActivityRead(String id) =>
      _dio.put('/v1/activities/$id/read');

  Future<Response> markAllActivitiesRead() =>
      _dio.put('/v1/activities/read-all');

  Future<Response> archiveActivity(String id) =>
      _dio.post('/v1/activities/$id/archive');

  Future<Response> unarchiveActivity(String id) =>
      _dio.post('/v1/activities/$id/unarchive');

  Future<Response> archiveImportItem(String id) =>
      _dio.post('/v1/import-items/$id/archive');

  Future<Response> unarchiveImportItem(String id) =>
      _dio.post('/v1/import-items/$id/unarchive');

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

  Future<Response> addRecipeBookMember(String bookId, Map<String, dynamic> data) {
    return _dio.post('/v1/recipe-books/$bookId/members', data: data);
  }

  Future<Response> removeRecipeBookMember(String bookId, String userId) {
    return _dio.delete('/v1/recipe-books/$bookId/members/$userId');
  }

  Future<Response> updateRecipeBookMemberRole(String bookId, String userId, Map<String, dynamic> data) {
    return _dio.patch('/v1/recipe-books/$bookId/members/$userId', data: data);
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

  Future<Response> getRecipe(String recipeId, {bool debug = false}) {
    return _dio.get(
      '/v1/recipes/$recipeId',
      queryParameters: debug ? {'debug': 'true'} : null,
    );
  }

  Future<Response> shareRecipe(String recipeId) =>
      _dio.post('/v1/recipes/$recipeId/share');

  Future<Response> revokeRecipeShare(String recipeId) =>
      _dio.delete('/v1/recipes/$recipeId/share');

  Future<Response> getPublicRecipeByToken(String token) =>
      _dio.get('/v1/recipes/public/$token');

  Future<Response> getVibeOptions() {
    return _dio.get('/v1/recipes/vibes/options');
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

  Future<Response> restoreRecipeVersion(String recipeId, String versionId) {
    return _dio.post('/v1/recipes/$recipeId/versions/$versionId/restore');
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

  Future<Response> forkRecipe(String recipeId, String destinationBookId) {
    return _dio.post('/v1/recipes/$recipeId/fork', data: {
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
  Future<Response> search(
    String query, {
    int limit = 20,
    String? bookId,
    List<String>? tags,
    int? maxPrepTime,
    int? maxCookTime,
    String? scope,
  }) {
    final params = <String, dynamic>{
      'q': query,
      'limit': limit,
    };
    if (bookId != null) params['book_id'] = bookId;
    if (tags != null && tags.isNotEmpty) params['tags'] = tags.join(',');
    if (maxPrepTime != null) params['max_prep_time'] = maxPrepTime;
    if (maxCookTime != null) params['max_cook_time'] = maxCookTime;
    if (scope != null) params['scope'] = scope;
    return _dio.get('/v1/search', queryParameters: params);
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

  // ── Pantry ───────────────────────────────────────────────────────────────

  Future<Response> getDefaultPantry() {
    return _dio.get('/v1/pantries/default');
  }

  Future<Response> addPantryIngredient(String pantryId, Map<String, dynamic> data) {
    return _dio.post('/v1/pantries/$pantryId/ingredients', data: data);
  }

  Future<Response> updatePantryIngredient(
      String pantryId, String ingredientId, Map<String, dynamic> data) {
    return _dio.patch('/v1/pantries/$pantryId/ingredients/$ingredientId', data: data);
  }

  Future<Response> deletePantryIngredient(String pantryId, String ingredientId) {
    return _dio.delete('/v1/pantries/$pantryId/ingredients/$ingredientId');
  }

  Future<Response> estimatePantryExpiry(
      String pantryId, Map<String, dynamic> data) {
    return _dio.post('/v1/pantries/$pantryId/estimate-expiry', data: data);
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

  Future<Response> populateShoppingListFromRecipe(
      String listId, Map<String, dynamic> data) {
    return _dio.post('/v1/shopping-lists/$listId/populate-from-recipe',
        data: data);
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
    bool? partnerActivity,
    bool? autoApproveImports,
  }) {
    return _dio.put('/v1/users/me/notification-preferences', data: {
      if (pushEnabled != null) 'push_enabled': pushEnabled,
      if (emailDigest != null) 'email_digest': emailDigest,
      if (quietHoursStart != null) 'quiet_hours_start': quietHoursStart,
      if (quietHoursEnd != null) 'quiet_hours_end': quietHoursEnd,
      if (timezone != null) 'timezone': timezone,
      if (partnerActivity != null) 'partner_activity': partnerActivity,
      if (autoApproveImports != null) 'auto_approve_imports': autoApproveImports,
    });
  }

  // Parser endpoints
  Future<Response> getParserUploadUrl(String filename) {
    return _dio.post('/v1/parser/upload-url', data: {
      'filename': filename,
    });
  }

  Future<Response> submitParserJob(String s3Key, {String? recipeBookId}) {
    return _dio.post('/v1/parser/jobs', data: {
      's3_key': s3Key,
      if (recipeBookId != null) 'recipe_book_id': recipeBookId,
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

  // Parser batch endpoints (story 13.12+)
  Future<Response> createParserBatch({
    required String recipeBookId,
    required List<Map<String, dynamic>> items,
  }) {
    return _dio.post('/v1/parser/batches', data: {
      'recipe_book_id': recipeBookId,
      'items': items,
    });
  }

  Future<Response> getParserBatch(String batchId) {
    return _dio.get('/v1/parser/batches/$batchId');
  }

  Future<Response> listParserBatches({bool activeOnly = true, int limit = 20}) {
    return _dio.get('/v1/parser/batches', queryParameters: {
      if (activeOnly) 'active': true,
      'limit': limit,
    });
  }

  // Import endpoints
  Future<Response> startImport(String bookId, {required String sourceType, String? url, List<String>? urls, List<String>? ocrTexts, String? rawText, String? fileBase64, String? fileName}) {
    return _dio.post('/v1/recipe-books/$bookId/import', data: {
      'source_type': sourceType,
      if (url != null) 'url': url,
      if (urls != null) 'urls': urls,
      if (ocrTexts != null) 'ocr_texts': ocrTexts,
      if (rawText != null) 'raw_text': rawText,
      if (fileBase64 != null) 'file_base64': fileBase64,
      if (fileName != null) 'file_name': fileName,
    });
  }

  Future<Response> getImportJob(String jobId) {
    return _dio.get('/v1/import-jobs/$jobId');
  }

  /// Low-level import POST used by PendingImportsReconciler — the Share
  /// Extension builds the exact payload (including `idempotency_key`,
  /// `s3_key`, `etag`) and the reconciler forwards it verbatim.
  Future<Response> postImportForBook(String bookId, Map<String, dynamic> body) {
    return _dio.post('/v1/recipe-books/$bookId/import', data: body);
  }

  Future<Response> listImportItems(String jobId, {String? status}) {
    return _dio.get('/v1/import-jobs/$jobId/items', queryParameters: {
      if (status != null) 'status': status,
    });
  }

  Future<Response> getImportItem(String itemId) {
    return _dio.get('/v1/import-items/$itemId');
  }

  /// irrd-2 telemetry endpoint — returns a 4-stage array plus raw-text
  /// previews for parsed/extracted. Cheap enough to call on every
  /// caret expansion per NFR55.
  Future<Response> getImportItemTelemetry(String itemId) {
    return _dio.get('/v1/import-items/$itemId/telemetry');
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

  Future<Response> retryImportItem(String itemId) {
    return _dio.post('/v1/import-items/$itemId/retry');
  }

  Future<Response> dismissImportItem(String itemId) {
    return _dio.post('/v1/import-items/$itemId/dismiss');
  }

  /// efi-5 — audit one user correction of an inferred field. Dispatched
  /// from Review Import on focus-loss after a 1500ms debounce. Best-
  /// effort: callers swallow network errors and never block save.
  /// `corrected` is dynamic because inferable fields vary in type —
  /// int for times/servings, string for description / cuisine /
  /// category / vibes.
  Future<Response> submitImportCorrection({
    required String itemId,
    required String field,
    required Object? corrected,
  }) {
    return _dio.post(
      '/v1/import-items/$itemId/corrections',
      data: {'field': field, 'corrected': corrected},
    );
  }

  Future<Response> dismissAllFailedImports() {
    return _dio.post('/v1/import-jobs/dismiss-all-failed');
  }

  Future<Response> cancelImportJob(String jobId) {
    return _dio.delete('/v1/import-jobs/$jobId');
  }

  Future<Response> listImportJobs({
    String? status,
    int limit = 20,
    int offset = 0,
    bool includeArchived = false,
    bool archivedOnly = false,
  }) {
    return _dio.get('/v1/import-jobs', queryParameters: {
      'limit': limit,
      'offset': offset,
      if (status != null) 'status': status,
      if (includeArchived) 'include_archived': true,
      if (archivedOnly) 'archived_only': true,
    });
  }

  // Recipe notes
  Future<Response> addRecipeNote(String recipeId, String body) {
    return _dio.post('/v1/recipes/$recipeId/notes', data: {'body': body});
  }

  // User feedback — admin inbox channel. `body` is 1..4000 chars,
  // `category` is one of bug/idea/praise/other (or null), `context` is a
  // small envelope of {app_version, platform, route, recipe_id} — any
  // unknown key triggers a 422 on the server.
  Future<Response> submitFeedback({
    required String body,
    String? category,
    Map<String, dynamic>? context,
  }) {
    return _dio.post(
      '/v1/users/me/feedback',
      data: {
        'body': body,
        if (category != null) 'category': category,
        if (context != null) 'context': context,
      },
    );
  }

  Future<Response> deleteRecipeNote(String recipeId, String noteId) {
    return _dio.delete('/v1/recipes/$recipeId/notes/$noteId');
  }

  // Meal events
  Future<Response> getMealEventsForToday() {
    final today = DateTime.now().toIso8601String().substring(0, 10);
    return _dio.get('/v1/meal-events', queryParameters: {
      'start_date': today,
      'end_date': today,
      'status': 'planned',
      'limit': 1,
    });
  }

  Future<Response> listMealEventsForRange(
    DateTime start,
    DateTime end, {
    String? calendarId,
  }) {
    return _dio.get('/v1/meal-events', queryParameters: {
      'start_date': start.toIso8601String().substring(0, 10),
      'end_date': end.toIso8601String().substring(0, 10),
      'limit': 50,
      if (calendarId != null) 'calendar_id': calendarId,
    });
  }

  // Calendars (cal-found-1 onward)
  Future<Response> listCalendars() => _dio.get('/v1/calendars');

  Future<Response> createCalendar(Map<String, dynamic> data) =>
      _dio.post('/v1/calendars', data: data);

  Future<Response> getCalendar(String id) =>
      _dio.get('/v1/calendars/$id');

  Future<Response> updateCalendar(String id, Map<String, dynamic> data) =>
      _dio.patch('/v1/calendars/$id', data: data);

  Future<Response> deleteCalendar(String id) =>
      _dio.delete('/v1/calendars/$id');

  // Calendar member management (cal-share-2)
  Future<Response> listCalendarMembers(String calendarId) =>
      _dio.get('/v1/calendars/$calendarId/members');

  Future<Response> updateCalendarMember(
    String calendarId,
    String userId,
    Map<String, dynamic> data,
  ) =>
      _dio.patch('/v1/calendars/$calendarId/members/$userId', data: data);

  Future<Response> removeCalendarMember(String calendarId, String userId) =>
      _dio.delete('/v1/calendars/$calendarId/members/$userId');

  Future<Response> leaveCalendar(String calendarId) =>
      _dio.post('/v1/calendars/$calendarId/leave');

  Future<Response> createMealEvent(Map<String, dynamic> data) {
    return _dio.post('/v1/meal-events', data: data);
  }

  Future<Response> updateMealEvent(String eventId, Map<String, dynamic> data) {
    return _dio.put('/v1/meal-events/$eventId', data: data);
  }

  Future<Response> deleteMealEvent(String eventId) {
    return _dio.delete('/v1/meal-events/$eventId');
  }

  // Recurrence rules
  Future<Response> listRecurrenceRules() =>
      _dio.get('/v1/recurrence-rules');

  Future<Response> createRecurrenceRule(Map<String, dynamic> data) =>
      _dio.post('/v1/recurrence-rules', data: data);

  Future<Response> getRecurrenceRule(String ruleId) =>
      _dio.get('/v1/recurrence-rules/$ruleId');

  Future<Response> updateRecurrenceRule(
    String ruleId,
    Map<String, dynamic> data,
  ) =>
      _dio.put('/v1/recurrence-rules/$ruleId', data: data);

  Future<Response> deleteRecurrenceRule(
    String ruleId, {
    String scope = 'series',
    String? occurrenceDate,
  }) {
    final params = <String, dynamic>{'scope': scope};
    if (occurrenceDate != null) {
      params['occurrence_date'] = occurrenceDate;
    }
    return _dio.delete(
      '/v1/recurrence-rules/$ruleId',
      queryParameters: params,
    );
  }

  // Cooking logs
  Future<Response> getRecentlyCookedRecipes({int limit = 5}) {
    return _dio.get('/v1/cooking-logs', queryParameters: {'limit': limit});
  }

  // Invitations
  Future<Response> listReceivedInvitations() =>
      _dio.get('/v1/invitations');

  Future<Response> listSentInvitations() =>
      _dio.get('/v1/invitations/sent');

  Future<Response> sendInvitation(Map<String, dynamic> data) =>
      _dio.post('/v1/invitations', data: data);

  Future<Response> acceptInvitation(String invitationId) =>
      _dio.post('/v1/invitations/$invitationId/accept');

  Future<Response> declineInvitation(String invitationId) =>
      _dio.post('/v1/invitations/$invitationId/decline');

  Future<Response> revokeInvitation(String invitationId) =>
      _dio.delete('/v1/invitations/$invitationId');

  Future<Response> claimInvitations() =>
      _dio.post('/v1/invitations/claim');

  // Invite Links
  Future<Response> createInviteLink(Map<String, dynamic> data) =>
      _dio.post('/v1/invite-links', data: data);

  Future<Response> previewInviteLink(String token) =>
      _dio.get('/v1/invite-links/$token');

  Future<Response> joinViaLink(String token) =>
      _dio.post('/v1/invite-links/$token/join');

  Future<Response> deactivateInviteLink(String inviteLinkId) =>
      _dio.delete('/v1/invite-links/$inviteLinkId');

  // Admin endpoints
  Future<Response> getAdminLogs({
    String service = 'api',
    String? level,
    String? search,
    int limit = 100,
  }) {
    return _dio.get('/v1/admin/logs', queryParameters: {
      'service': service,
      'limit': limit,
      if (level != null) 'level': level,
      if (search != null) 'search': search,
    });
  }

  Future<Response> getAdminErrors({
    String? service,
    int limit = 50,
    int offset = 0,
  }) {
    return _dio.get('/v1/admin/errors', queryParameters: {
      'limit': limit,
      'offset': offset,
      if (service != null) 'service': service,
    });
  }

  Future<Response> getAdminErrorDetail(String errorId) {
    return _dio.get('/v1/admin/errors/$errorId');
  }

  Future<Response> getAdminUsers({int limit = 50, int offset = 0}) {
    return _dio.get('/v1/admin/users', queryParameters: {
      'limit': limit,
      'offset': offset,
    });
  }

  Future<Response> updateUserAdmin(String userId, bool isAdmin) {
    return _dio.put('/v1/admin/users/$userId/admin', data: {
      'is_admin': isAdmin,
    });
  }

  // Admin feedback inbox
  Future<Response> getAdminFeedback({
    String status = 'unread',
    int offset = 0,
    int limit = 25,
  }) {
    return _dio.get('/v1/admin/feedback', queryParameters: {
      'status': status,
      'offset': offset,
      'limit': limit,
    });
  }

  Future<Response> updateFeedbackStatus(String feedbackId, String status) {
    return _dio.put(
      '/v1/admin/feedback/$feedbackId/status',
      data: {'status': status},
    );
  }

  Future<Response> getAdminStats() {
    return _dio.get('/v1/admin/stats');
  }

  // Admin latency metrics (obs-latency-2)
  Future<Response> getEndpointMetrics({String window = '24h'}) {
    return _dio.get(
      '/v1/admin/metrics/endpoints',
      queryParameters: {'window': window},
    );
  }

  Future<Response> getTaskMetrics({String window = '24h'}) {
    return _dio.get(
      '/v1/admin/metrics/tasks',
      queryParameters: {'window': window},
    );
  }

  Future<Response> sendAdminTestPush({
    String? title,
    String? body,
    String? targetUserId,
    bool force = true,
  }) {
    return _dio.post(
      '/v1/admin/notifications/test-push',
      queryParameters: {'force': force},
      data: {
        if (title != null) 'title': title,
        if (body != null) 'body': body,
        if (targetUserId != null) 'target_user_id': targetUserId,
      },
    );
  }

  /// push-diag-3: per-user push-health lookup (admin-only). Path parameter
  /// is either a UUID or an email; backend picks the right lookup strategy.
  Future<Response> getAdminPushHealth(String idOrEmail, {int errorLimit = 10}) {
    return _dio.get(
      '/v1/admin/notifications/health/${Uri.encodeComponent(idOrEmail)}',
      queryParameters: {'error_limit': errorLimit},
    );
  }

  // ---------------------------------------------------------------------
  // Meals (mcv-2, mcv-3)
  // ---------------------------------------------------------------------

  Future<Response> listMeals({
    int? limit,
    int offset = 0,
    bool includeArchived = false,
    bool? archived,
    String? scope,
    String? q,
  }) {
    final params = <String, dynamic>{'offset': offset};
    if (limit != null) params['limit'] = limit;
    if (includeArchived) params['include_archived'] = 'true';
    if (archived != null) params['archived'] = archived.toString();
    if (scope != null) params['scope'] = scope;
    if (q != null && q.isNotEmpty) params['q'] = q;
    return _dio.get('/v1/meals', queryParameters: params);
  }

  /// mcal-5: append a Meal's aggregated ingredients to a shopping list
  /// without scheduling it on the calendar.
  Future<Response> addMealToShoppingList(
    String mealId,
    Map<String, dynamic> data,
  ) =>
      _dio.post('/v1/meals/$mealId/add-to-shopping-list', data: data);

  /// mcal-5: per-event "Add to Shopping List" — handles both recipe-only
  /// and Meal events (Meal events fan-out + dedupe server-side).
  Future<Response> addMealEventToShoppingList(
    String eventId,
    Map<String, dynamic> data,
  ) =>
      _dio.post(
        '/v1/meal-events/$eventId/add-to-shopping-list',
        data: data,
      );

  /// md-2: reverse lookup — Meals referencing this recipe.
  Future<Response> listMealsUsingRecipe(String recipeId) =>
      _dio.get('/v1/recipes/$recipeId/meals');

  Future<Response> getMeal(String mealId) => _dio.get('/v1/meals/$mealId');

  Future<Response> updateMeal(String mealId, Map<String, dynamic> data) =>
      _dio.patch('/v1/meals/$mealId', data: data);

  Future<Response> archiveMeal(String mealId) =>
      _dio.post('/v1/meals/$mealId/archive');

  Future<Response> restoreMeal(String mealId) =>
      _dio.post('/v1/meals/$mealId/restore');

  Future<Response> addRecipeToMeal(String mealId, Map<String, dynamic> data) =>
      _dio.post('/v1/meals/$mealId/recipes', data: data);

  Future<Response> removeRecipeFromMeal(String mealId, String recipeId) =>
      _dio.delete('/v1/meals/$mealId/recipes/$recipeId');

  Future<Response> reorderMealComponents(
          String mealId, Map<String, dynamic> data) =>
      _dio.post('/v1/meals/$mealId/reorder', data: data);

  Future<Response> favoriteMeal(String mealId) =>
      _dio.post('/v1/meals/$mealId/favorite');

  Future<Response> unfavoriteMeal(String mealId) =>
      _dio.delete('/v1/meals/$mealId/favorite');

  Future<Response> listMealsInBook(
    String bookId, {
    int limit = 20,
    int offset = 0,
    bool includeArchived = false,
  }) =>
      _dio.get('/v1/recipe-books/$bookId/meals', queryParameters: {
        'limit': limit,
        'offset': offset,
        if (includeArchived) 'include_archived': 'true',
      });

  Future<Response> createMealInBook(
          String bookId, Map<String, dynamic> data) =>
      _dio.post('/v1/recipe-books/$bookId/meals', data: data);

  /// msa-1: generate / return the Meal's public share token.
  /// Idempotent — re-POSTing returns the same token (200) as the first call (201).
  Future<Response> shareMeal(String mealId) =>
      _dio.post('/v1/meals/$mealId/share');

  /// msa-1: unauthenticated read of a Meal by its share token.
  Future<Response> getPublicMealByToken(String token) =>
      _dio.get('/v1/meals/public/$token');
}
