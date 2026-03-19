import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_sync_service.dart';

/// Minimal stub — only provides the wsBaseUrl and authToken needed by the service.
class _StubApiClient extends Fake implements ApiClient {
  @override
  String get wsBaseUrl => 'ws://localhost:8000';

  @override
  String? get authToken => 'test-token';
}

void main() {
  group('RecipeBookWebSocketState', () {
    test('enum has 4 values', () {
      expect(RecipeBookWebSocketState.values, hasLength(4));
    });

    test('disconnected value name is correct', () {
      expect(RecipeBookWebSocketState.disconnected.name, 'disconnected');
    });

    test('connected value name is correct', () {
      expect(RecipeBookWebSocketState.connected.name, 'connected');
    });

    test('connecting value name is correct', () {
      expect(RecipeBookWebSocketState.connecting.name, 'connecting');
    });

    test('error value name is correct', () {
      expect(RecipeBookWebSocketState.error.name, 'error');
    });
  });

  group('RecipeBookSyncService', () {
    late RecipeBookSyncService service;

    setUp(() {
      service = RecipeBookSyncService(apiClient: _StubApiClient());
    });

    tearDown(() {
      service.dispose();
    });

    test('initial state is disconnected', () {
      expect(service.connectionState, RecipeBookWebSocketState.disconnected);
    });

    test('disconnectWebSocket resets state to disconnected', () {
      service.disconnectWebSocket();
      expect(service.connectionState, RecipeBookWebSocketState.disconnected);
    });

    test('onRecipeAdded is a broadcast stream (multiple listeners allowed)', () {
      final s1 = service.onRecipeAdded.listen((_) {});
      final s2 = service.onRecipeAdded.listen((_) {});
      s1.cancel();
      s2.cancel();
    });

    test('onRecipeUpdated is a broadcast stream', () {
      final s1 = service.onRecipeUpdated.listen((_) {});
      final s2 = service.onRecipeUpdated.listen((_) {});
      s1.cancel();
      s2.cancel();
    });

    test('onRecipeRemoved is a broadcast stream', () {
      final s1 = service.onRecipeRemoved.listen((_) {});
      final s2 = service.onRecipeRemoved.listen((_) {});
      s1.cancel();
      s2.cancel();
    });

    test('onConnectionStateChange is a broadcast stream', () {
      final s1 = service.onConnectionStateChange.listen((_) {});
      final s2 = service.onConnectionStateChange.listen((_) {});
      s1.cancel();
      s2.cancel();
    });

    test('dispose completes without error', () {
      expect(() => service.dispose(), returnsNormally);
    });
  });
}
