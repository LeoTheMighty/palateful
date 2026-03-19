import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';

/// WebSocket connection state.
enum RecipeBookWebSocketState {
  disconnected,
  connecting,
  connected,
  error,
}

/// Service for real-time recipe book sync via WebSocket.
///
/// Subscribes to a single recipe book at a time. When another member adds,
/// updates, or removes a recipe in the book, the corresponding stream emits
/// an event so the UI can refresh.
class RecipeBookSyncService {
  late final ApiClient _apiClient;

  WebSocketChannel? _wsChannel;
  StreamSubscription? _wsSubscription;
  Timer? _reconnectTimer;
  Timer? _pingTimer;

  String? _currentBookId;
  int _reconnectAttempts = 0;

  RecipeBookSyncService({ApiClient? apiClient}) {
    _apiClient = apiClient ?? getIt<ApiClient>();
  }

  // Event stream controllers
  final _recipeAddedController =
      StreamController<Map<String, dynamic>>.broadcast();
  final _recipeUpdatedController =
      StreamController<Map<String, dynamic>>.broadcast();
  final _recipeRemovedController = StreamController<String>.broadcast();
  final _connectionStateController =
      StreamController<RecipeBookWebSocketState>.broadcast();

  // Public streams
  Stream<Map<String, dynamic>> get onRecipeAdded =>
      _recipeAddedController.stream;
  Stream<Map<String, dynamic>> get onRecipeUpdated =>
      _recipeUpdatedController.stream;
  Stream<String> get onRecipeRemoved => _recipeRemovedController.stream;
  Stream<RecipeBookWebSocketState> get onConnectionStateChange =>
      _connectionStateController.stream;

  RecipeBookWebSocketState _connectionState =
      RecipeBookWebSocketState.disconnected;
  RecipeBookWebSocketState get connectionState => _connectionState;

  /// Connect to WebSocket for real-time updates on [bookId].
  /// No-op if already connected to the same book.
  void connectWebSocket(String bookId) {
    if (_currentBookId == bookId && _wsChannel != null) {
      return;
    }
    disconnectWebSocket();
    _currentBookId = bookId;
    _doConnect();
  }

  void _doConnect() {
    if (_currentBookId == null) return;

    final token = _apiClient.authToken;
    if (token == null) {
      _updateState(RecipeBookWebSocketState.error);
      return;
    }

    _updateState(RecipeBookWebSocketState.connecting);

    try {
      final wsUrl =
          '${_apiClient.wsBaseUrl}/v1/recipe-books/ws/$_currentBookId?token=$token';
      _wsChannel = WebSocketChannel.connect(Uri.parse(wsUrl));

      _wsSubscription = _wsChannel!.stream.listen(
        _handleMessage,
        onError: _handleError,
        onDone: _handleDisconnect,
      );

      _updateState(RecipeBookWebSocketState.connected);
      _startPingTimer();
    } catch (e) {
      _updateState(RecipeBookWebSocketState.error);
      _scheduleReconnect();
    }
  }

  @visibleForTesting
  void handleMessageForTest(dynamic data) => _handleMessage(data);

  void _handleMessage(dynamic data) {
    try {
      final message = jsonDecode(data as String) as Map<String, dynamic>;
      final type = message['type'] as String?;

      switch (type) {
        case 'recipe_added':
          final payload = (message['data'] as Map<String, dynamic>?) ?? {};
          _recipeAddedController.add(payload);
          break;
        case 'recipe_updated':
          final payload = (message['data'] as Map<String, dynamic>?) ?? {};
          _recipeUpdatedController.add(payload);
          break;
        case 'recipe_removed':
          final recipeId =
              ((message['data'] as Map<String, dynamic>?))?['recipe_id']
                  as String? ??
              '';
          _recipeRemovedController.add(recipeId);
          break;
        case 'connected':
          _reconnectAttempts = 0;
          _updateState(RecipeBookWebSocketState.connected);
          break;
        case 'pong':
          // Keepalive response — no-op
          break;
      }
    } catch (e) {
      // Ignore malformed messages
    }
  }

  void _handleError(Object error) {
    _updateState(RecipeBookWebSocketState.error);
    _scheduleReconnect();
  }

  void _handleDisconnect() {
    _updateState(RecipeBookWebSocketState.disconnected);
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    // Exponential back-off: 5s, 10s, 20s, 40s, capped at 60s
    final delaySecs = (5 * (1 << _reconnectAttempts)).clamp(5, 60);
    _reconnectAttempts++;
    _reconnectTimer = Timer(Duration(seconds: delaySecs), _doConnect);
  }

  void _startPingTimer() {
    _pingTimer?.cancel();
    _pingTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _sendPing();
    });
  }

  void _sendPing() {
    _wsChannel?.sink.add(jsonEncode({'type': 'ping'}));
  }

  void _updateState(RecipeBookWebSocketState state) {
    if (_connectionState != state) {
      _connectionState = state;
      _connectionStateController.add(state);
    }
  }

  /// Disconnect from the current WebSocket.
  void disconnectWebSocket() {
    _pingTimer?.cancel();
    _reconnectTimer?.cancel();
    _wsSubscription?.cancel();
    _wsChannel?.sink.close();
    _wsChannel = null;
    _currentBookId = null;
    _reconnectAttempts = 0;
    _updateState(RecipeBookWebSocketState.disconnected);
  }

  /// Dispose all resources.
  void dispose() {
    disconnectWebSocket();
    _recipeAddedController.close();
    _recipeUpdatedController.close();
    _recipeRemovedController.close();
    _connectionStateController.close();
  }
}
