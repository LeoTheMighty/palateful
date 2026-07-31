import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/error_reporter.dart';
import '../../../core/state/mutation_bus.dart';
import '../models/shopping_list.dart';
import '../models/shopping_list_item.dart';

/// Service for managing shopping cart data and real-time sync.
class ShoppingCartService {
  final ApiClient _apiClient = getIt<ApiClient>();

  WebSocketChannel? _wsChannel;
  StreamSubscription? _wsSubscription;
  Timer? _reconnectTimer;
  Timer? _pingTimer;

  String? _currentListId;
  int _lastSequence = 0;

  // Event stream controllers
  final _itemAddedController =
      StreamController<ShoppingListItem>.broadcast();
  final _itemUpdatedController =
      StreamController<ShoppingListItem>.broadcast();
  final _itemRemovedController = StreamController<String>.broadcast();
  final _presenceController = StreamController<OnlineUser>.broadcast();
  final _syncController = StreamController<SyncResponse>.broadcast();
  final _connectionStateController =
      StreamController<WebSocketState>.broadcast();

  // Public streams
  Stream<ShoppingListItem> get onItemAdded => _itemAddedController.stream;
  Stream<ShoppingListItem> get onItemUpdated => _itemUpdatedController.stream;
  Stream<String> get onItemRemoved => _itemRemovedController.stream;
  Stream<OnlineUser> get onPresenceUpdate => _presenceController.stream;
  Stream<SyncResponse> get onSync => _syncController.stream;
  Stream<WebSocketState> get onWebSocketStateChange =>
      _connectionStateController.stream;

  WebSocketState _connectionState = WebSocketState.disconnected;
  WebSocketState get connectionState => _connectionState;

  // API Methods

  /// Get all shopping lists for the current user.
  Future<List<ShoppingList>> getShoppingLists() async {
    final response = await _apiClient.getShoppingLists();
    final items = response.data['items'] as List<dynamic>? ?? [];
    return items
        .map((i) => ShoppingList.fromJson(i as Map<String, dynamic>))
        .toList();
  }

  /// Get a single shopping list with items.
  Future<ShoppingList> getShoppingList(String listId) async {
    final response = await _apiClient.getShoppingList(listId);
    return ShoppingList.fromJson(response.data as Map<String, dynamic>);
  }

  /// Create a new shopping list.
  /// If the user has no default, the backend auto-sets it; refresh local state.
  Future<ShoppingList> createShoppingList(String name) async {
    final response = await _apiClient.createShoppingList({'name': name});
    final list = ShoppingList.fromJson(response.data as Map<String, dynamic>);

    // If user had no default, the backend just auto-set this list as default.
    // Refresh local auth state to stay in sync.
    final authService = getIt<AuthService>();
    if (authService.defaultShoppingListId == null) {
      authService.updateDefaultShoppingList(
        defaultShoppingListId: list.id,
      );
    }

    return list;
  }

  /// Add an item to a shopping list.
  Future<ShoppingListItem> addItem(
    String listId, {
    required String name,
    double? quantity,
    String? unit,
    String? category,
    String? notes,
  }) async {
    final response = await _apiClient.addShoppingListItem(listId, {
      'name': name,
      if (quantity != null) 'quantity': quantity,
      if (unit != null) 'unit': unit,
      if (category != null) 'category': category,
      if (notes != null) 'notes': notes,
    });
    final payload = response.data as Map<String, dynamic>;
    final item = ShoppingListItem.fromJson(payload);
    // rp-4: emit on the bus so Riverpod-based shopping-list surfaces
    // (landed in a follow-on epic) reconcile. Local mutation + WS
    // frame may both fire — subscribers are idempotent (Foundation's
    // WS/MutationBus duplication note).
    emitMutation(ShoppingListItemAdded(
      itemId: item.id,
      item: payload,
      listId: listId,
    ));
    return item;
  }

  /// Toggle item checked state.
  Future<ShoppingListItem> toggleItemChecked(
      String listId, ShoppingListItem item) async {
    final response = await _apiClient.updateShoppingListItem(listId, item.id, {
      'is_checked': !item.isChecked,
    });
    final payload = response.data as Map<String, dynamic>;
    final updated = ShoppingListItem.fromJson(payload);
    emitMutation(ShoppingListItemUpdated(
      itemId: updated.id,
      item: payload,
      listId: listId,
    ));
    return updated;
  }

  /// Update an item.
  Future<ShoppingListItem> updateItem(
    String listId,
    String itemId,
    Map<String, dynamic> data,
  ) async {
    final response =
        await _apiClient.updateShoppingListItem(listId, itemId, data);
    final payload = response.data as Map<String, dynamic>;
    final updated = ShoppingListItem.fromJson(payload);
    emitMutation(ShoppingListItemUpdated(
      itemId: itemId,
      item: payload,
      listId: listId,
    ));
    return updated;
  }

  /// Delete an item.
  Future<void> deleteItem(String listId, String itemId) async {
    await _apiClient.deleteShoppingListItem(listId, itemId);
    emitMutation(ShoppingListItemRemoved(itemId: itemId, listId: listId));
  }

  /// Get items grouped by deadline urgency.
  Future<Map<String, List<ShoppingListItem>>> getDeadlines(
      String listId) async {
    final response = await _apiClient.getShoppingListDeadlines(listId);
    final data = response.data as Map<String, dynamic>;
    final result = <String, List<ShoppingListItem>>{};

    for (final key in ['overdue', 'urgent', 'today', 'soon', 'normal', 'none']) {
      final items = data[key] as List<dynamic>? ?? [];
      result[key] = items
          .map((i) => ShoppingListItem.fromJson(i as Map<String, dynamic>))
          .toList();
    }

    return result;
  }

  /// Add all ingredients from a recipe to a shopping list.
  Future<({int itemsAdded, int itemsSkipped})> populateFromRecipe(
    String listId,
    String recipeId, {
    double scaleFactor = 1.0,
  }) async {
    final response = await _apiClient.populateShoppingListFromRecipe(listId, {
      'recipe_id': recipeId,
      if (scaleFactor != 1.0) 'scale_factor': scaleFactor,
    });
    final data = response.data as Map<String, dynamic>;
    return (
      itemsAdded: data['items_added'] as int,
      itemsSkipped: data['items_skipped'] as int,
    );
  }

  /// Share a shopping list and get share code.
  Future<String> shareList(String listId) async {
    final response = await _apiClient.shareShoppingList(listId);
    return response.data['share_code'] as String;
  }

  /// Set the default shopping list.
  Future<void> setDefaultShoppingList(String? shoppingListId) async {
    final response = await _apiClient.setDefaultShoppingList(shoppingListId);
    final data = response.data as Map<String, dynamic>;
    final authService = getIt<AuthService>();
    authService.updateDefaultShoppingList(
      defaultShoppingListId: data['default_shopping_list_id'] as String?,
      previousShoppingListId: data['previous_shopping_list_id'] as String?,
    );
  }

  /// Restore the previous default shopping list.
  Future<void> restorePreviousDefault() async {
    final authService = getIt<AuthService>();
    final previousId = authService.previousShoppingListId;
    if (previousId == null) return;
    await setDefaultShoppingList(previousId);
  }

  /// Join a shopping list using share code.
  Future<ShoppingList> joinList(String shareCode) async {
    final response = await _apiClient.joinShoppingList(shareCode);
    return ShoppingList.fromJson(response.data as Map<String, dynamic>);
  }

  // WebSocket Methods

  /// Connect to WebSocket for real-time updates.
  void connectWebSocket(String listId) {
    if (_currentListId == listId && _wsChannel != null) {
      return; // Already connected
    }

    disconnectWebSocket();
    _currentListId = listId;
    _lastSequence = 0;

    _doConnect();
  }

  void _doConnect() {
    final listId = _currentListId;
    if (listId == null) {
      ErrorReporter.report(
        StateError('shopping WS connect with null list id'),
        StackTrace.current,
        area: 'shopping.websocket',
        operation: 'connect',
        extras: {'reason': 'null_list_id'},
      );
      return;
    }

    final token = _apiClient.authToken;
    if (token == null) {
      _updateWebSocketState(WebSocketState.error);
      return;
    }

    _updateWebSocketState(WebSocketState.connecting);

    try {
      final wsUrl =
          '${_apiClient.wsBaseUrl}/v1/ws/shopping-lists/$listId?token=$token';
      _wsChannel = WebSocketChannel.connect(Uri.parse(wsUrl));

      _wsSubscription = _wsChannel!.stream.listen(
        _handleMessage,
        onError: _handleError,
        onDone: _handleDisconnect,
      );

      _updateWebSocketState(WebSocketState.connected);
      _startPingTimer();
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'shopping.websocket',
        operation: 'connect',
        extras: {'list_id': listId},
      );
      _updateWebSocketState(WebSocketState.error);
      _scheduleReconnect();
    }
  }

  @visibleForTesting
  void handleMessageForTest(dynamic data) => _handleMessage(data);

  @visibleForTesting
  void setCurrentListIdForTest(String listId) {
    _currentListId = listId;
  }

  /// Drives the 4xxx-close-code branch of [_handleDisconnect] without a
  /// live socket. Exposed because the real path needs a channel whose
  /// `closeCode` the test cannot set.
  @visibleForTesting
  Future<void> refreshTokenThenReconnectForTest(int closeCode) =>
      _refreshTokenThenReconnect(closeCode);

  void _handleMessage(dynamic data) {
    try {
      final message = jsonDecode(data as String) as Map<String, dynamic>;
      final type = message['type'] as String?;
      final listId = _currentListId;

      switch (type) {
        case 'sync_response':
          // Not a mutation — transport-level state only; no emit.
          _handleSyncResponse(message);
          break;
        case 'item_added':
          final payload = message['data'] as Map<String, dynamic>;
          final item = ShoppingListItem.fromJson(payload);
          _itemAddedController.add(item);
          if (listId != null) {
            emitMutation(ShoppingListItemAdded(
              itemId: item.id,
              item: payload,
              listId: listId,
            ));
          }
          break;
        case 'item_updated':
        case 'item_checked':
          final payload = message['data'] as Map<String, dynamic>;
          final item = ShoppingListItem.fromJson(payload);
          _itemUpdatedController.add(item);
          if (listId != null) {
            emitMutation(ShoppingListItemUpdated(
              itemId: item.id,
              item: payload,
              listId: listId,
            ));
          }
          break;
        case 'item_removed':
          final itemId = message['data']['item_id'] as String;
          _itemRemovedController.add(itemId);
          if (listId != null) {
            emitMutation(ShoppingListItemRemoved(
              itemId: itemId,
              listId: listId,
            ));
          }
          break;
        case 'presence_update':
          // Transient session state — not a mutation; no emit.
          final user = OnlineUser.fromJson(message);
          _presenceController.add(user);
          break;
        case 'pong':
          // Keepalive response, ignore
          break;
      }

      // Update sequence number
      final sequence = message['sequence'] as int?;
      if (sequence != null && sequence > _lastSequence) {
        _lastSequence = sequence;
      }
    } catch (e) {
      debugPrint('Error handling WebSocket message: $e');
    }
  }

  void _handleSyncResponse(Map<String, dynamic> message) {
    final sequence = message['current_sequence'] as int? ?? 0;
    final onlineUsers = (message['online_users'] as List<dynamic>?)
            ?.map((u) => u.toString())
            .toList() ??
        [];

    final events = message['events'] as List<dynamic>?;
    List<SyncEvent>? syncEvents;
    if (events != null) {
      syncEvents = events
          .map((e) => SyncEvent.fromJson(e as Map<String, dynamic>))
          .toList();
    }

    _lastSequence = sequence;
    _syncController.add(SyncResponse(
      currentSequence: sequence,
      onlineUsers: onlineUsers,
      events: syncEvents,
    ));
  }

  void _handleError(Object error) {
    debugPrint('WebSocket error: $error');
    ErrorReporter.report(
      error,
      null,
      area: 'shopping.websocket',
      operation: 'stream',
      extras: {'list_id': _currentListId},
    );
    _updateWebSocketState(WebSocketState.error);
    _scheduleReconnect();
  }

  void _handleDisconnect() {
    // When the backend closes with an app-defined code (4xxx), treat it
    // as an auth/access issue and try a single refresh before the next
    // reconnect attempt. Known close codes: 4003 access denied, 4004
    // shopping list not found (see services/api/src/api/v1/shopping_list/websocket.py).
    final closeCode = _wsChannel?.closeCode;
    _updateWebSocketState(WebSocketState.disconnected);
    if (closeCode != null && closeCode >= 4000 && closeCode < 5000) {
      unawaited(_refreshTokenThenReconnect(closeCode));
      return;
    }
    _scheduleReconnect();
  }

  Future<void> _refreshTokenThenReconnect(int closeCode) async {
    ErrorReporter.report(
      StateError('shopping WS closed with code $closeCode'),
      null,
      area: 'shopping.websocket',
      operation: 'disconnect',
      extras: {'list_id': _currentListId, 'close_code': closeCode},
    );
    try {
      final authService = getIt<AuthService>();
      final refreshed = await authService.refreshToken();
      final token = authService.accessToken;
      if (refreshed && token != null) {
        // AuthService.refreshToken() only rotates its own credentials.
        // Nothing else pushes the new access token into ApiClient at
        // runtime — the Dio 401 interceptor (bas-4) is the only other
        // writer and it needs an HTTP 401 to fire. Without this line
        // the _scheduleReconnect below re-reads the same rejected token
        // from _apiClient.authToken, the backend closes 4003 again, and
        // the 5s reconnect + ErrorReporter.report pair repeats forever.
        _apiClient.setAuthToken(token);
      }
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'shopping.websocket',
        operation: 'refresh_on_disconnect',
        extras: {'list_id': _currentListId, 'close_code': closeCode},
      );
    }
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), _doConnect);
  }

  void _startPingTimer() {
    _pingTimer?.cancel();
    _pingTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      sendPing();
    });
  }

  void _updateWebSocketState(WebSocketState state) {
    if (_connectionState != state) {
      _connectionState = state;
      _connectionStateController.add(state);
    }
  }

  /// Send ping to keep connection alive.
  void sendPing() {
    _wsChannel?.sink.add(jsonEncode({'type': 'ping'}));
  }

  /// Update presence status.
  void updatePresence(String status) {
    _wsChannel?.sink.add(jsonEncode({
      'type': 'presence',
      'status': status,
    }));
  }

  /// Request sync from a sequence number.
  void requestSync({int? sinceSequence}) {
    _wsChannel?.sink.add(jsonEncode({
      'type': 'sync_request',
      'since_sequence': sinceSequence ?? _lastSequence,
    }));
  }

  /// Disconnect WebSocket.
  void disconnectWebSocket() {
    _pingTimer?.cancel();
    _reconnectTimer?.cancel();
    _wsSubscription?.cancel();
    _wsChannel?.sink.close();
    _wsChannel = null;
    _currentListId = null;
    _updateWebSocketState(WebSocketState.disconnected);
  }

  /// Dispose resources.
  void dispose() {
    disconnectWebSocket();
    _itemAddedController.close();
    _itemUpdatedController.close();
    _itemRemovedController.close();
    _presenceController.close();
    _syncController.close();
    _connectionStateController.close();
  }
}

/// WebSocket connection state.
enum WebSocketState {
  disconnected,
  connecting,
  connected,
  error,
}

/// Sync response from WebSocket.
class SyncResponse {
  final int currentSequence;
  final List<String> onlineUsers;
  final List<SyncEvent>? events;

  SyncResponse({
    required this.currentSequence,
    required this.onlineUsers,
    this.events,
  });
}

/// Sync event from WebSocket.
class SyncEvent {
  final String id;
  final String eventType;
  final Map<String, dynamic> eventData;
  final String? userId;
  final String? userName;
  final int sequence;
  final DateTime createdAt;

  SyncEvent({
    required this.id,
    required this.eventType,
    required this.eventData,
    this.userId,
    this.userName,
    required this.sequence,
    required this.createdAt,
  });

  factory SyncEvent.fromJson(Map<String, dynamic> json) {
    return SyncEvent(
      id: json['id'] as String,
      eventType: json['event_type'] as String,
      eventData: json['event_data'] as Map<String, dynamic>,
      userId: json['user_id'] as String?,
      userName: json['user_name'] as String?,
      sequence: json['sequence'] as int,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}
