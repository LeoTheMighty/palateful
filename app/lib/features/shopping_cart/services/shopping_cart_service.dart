import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';
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
    return ShoppingListItem.fromJson(response.data as Map<String, dynamic>);
  }

  /// Toggle item checked state.
  Future<ShoppingListItem> toggleItemChecked(
      String listId, ShoppingListItem item) async {
    final response = await _apiClient.updateShoppingListItem(listId, item.id, {
      'is_checked': !item.isChecked,
    });
    return ShoppingListItem.fromJson(response.data as Map<String, dynamic>);
  }

  /// Update an item.
  Future<ShoppingListItem> updateItem(
    String listId,
    String itemId,
    Map<String, dynamic> data,
  ) async {
    final response =
        await _apiClient.updateShoppingListItem(listId, itemId, data);
    return ShoppingListItem.fromJson(response.data as Map<String, dynamic>);
  }

  /// Delete an item.
  Future<void> deleteItem(String listId, String itemId) async {
    await _apiClient.deleteShoppingListItem(listId, itemId);
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
    String recipeId,
  ) async {
    final response = await _apiClient.populateShoppingListFromRecipe(
        listId, {'recipe_id': recipeId});
    final data = response.data as Map<String, dynamic>;
    return (
      itemsAdded: data['items_added'] as int,
      itemsSkipped: data['items_skipped'] as int,
    );
  }

  /// Add all ingredients from a date range of meal events to a shopping list.
  Future<({int itemsAdded, int itemsSkipped, int mealEventsIncluded})>
      populateFromCalendarRange(
          String listId, DateTime start, DateTime end) async {
    String isoDate(DateTime d) =>
        '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
    final response = await _apiClient.populateShoppingListFromCalendar(listId, {
      'start_date': isoDate(start),
      'end_date': isoDate(end),
    });
    final data = response.data as Map<String, dynamic>;
    return (
      itemsAdded: data['items_added'] as int,
      itemsSkipped: data['items_skipped'] as int,
      mealEventsIncluded: data['meal_events_included'] as int,
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
    if (_currentListId == null) return;

    final token = _apiClient.authToken;
    if (token == null) {
      _updateWebSocketState(WebSocketState.error);
      return;
    }

    _updateWebSocketState(WebSocketState.connecting);

    try {
      final wsUrl =
          '${_apiClient.wsBaseUrl}/v1/ws/shopping-lists/$_currentListId?token=$token';
      _wsChannel = WebSocketChannel.connect(Uri.parse(wsUrl));

      _wsSubscription = _wsChannel!.stream.listen(
        _handleMessage,
        onError: _handleError,
        onDone: _handleDisconnect,
      );

      _updateWebSocketState(WebSocketState.connected);
      _startPingTimer();
    } catch (e) {
      _updateWebSocketState(WebSocketState.error);
      _scheduleReconnect();
    }
  }

  void _handleMessage(dynamic data) {
    try {
      final message = jsonDecode(data as String) as Map<String, dynamic>;
      final type = message['type'] as String?;

      switch (type) {
        case 'sync_response':
          _handleSyncResponse(message);
          break;
        case 'item_added':
          final item = ShoppingListItem.fromJson(
              message['data'] as Map<String, dynamic>);
          _itemAddedController.add(item);
          break;
        case 'item_updated':
        case 'item_checked':
          final item = ShoppingListItem.fromJson(
              message['data'] as Map<String, dynamic>);
          _itemUpdatedController.add(item);
          break;
        case 'item_removed':
          final itemId = message['data']['item_id'] as String;
          _itemRemovedController.add(itemId);
          break;
        case 'presence_update':
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
    _updateWebSocketState(WebSocketState.error);
    _scheduleReconnect();
  }

  void _handleDisconnect() {
    _updateWebSocketState(WebSocketState.disconnected);
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
