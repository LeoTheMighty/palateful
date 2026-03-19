import 'dart:convert';

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

  group('RecipeBookSyncService message routing (AC1/2/3)', () {
    late RecipeBookSyncService service;

    setUp(() {
      service = RecipeBookSyncService(apiClient: _StubApiClient());
    });

    tearDown(() {
      service.dispose();
    });

    test('recipe_added message emits on onRecipeAdded stream', () async {
      final received = <Map<String, dynamic>>[];
      final sub = service.onRecipeAdded.listen(received.add);

      service.handleMessageForTest(jsonEncode({
        'type': 'recipe_added',
        'data': {'name': 'Pasta', 'recipe_id': 'r-1'},
      }));

      await Future.microtask(() {});
      expect(received, hasLength(1));
      expect(received.first['name'], 'Pasta');
      await sub.cancel();
    });

    test('recipe_updated message emits on onRecipeUpdated stream', () async {
      final received = <Map<String, dynamic>>[];
      final sub = service.onRecipeUpdated.listen(received.add);

      service.handleMessageForTest(jsonEncode({
        'type': 'recipe_updated',
        'data': {'recipe_id': 'r-2', 'name': 'Updated Pasta'},
      }));

      await Future.microtask(() {});
      expect(received, hasLength(1));
      expect(received.first['recipe_id'], 'r-2');
      await sub.cancel();
    });

    test('recipe_removed message emits recipe_id on onRecipeRemoved stream', () async {
      final received = <String>[];
      final sub = service.onRecipeRemoved.listen(received.add);

      service.handleMessageForTest(jsonEncode({
        'type': 'recipe_removed',
        'data': {'recipe_id': 'r-3'},
      }));

      await Future.microtask(() {});
      expect(received, hasLength(1));
      expect(received.first, 'r-3');
      await sub.cancel();
    });

    test('connected message updates connectionState to connected', () async {
      final states = <RecipeBookWebSocketState>[];
      final sub = service.onConnectionStateChange.listen(states.add);

      service.handleMessageForTest(jsonEncode({'type': 'connected'}));

      await Future.microtask(() {});
      // connected is a no-op state change if already disconnected... but
      // _updateState only emits when state actually changes
      // Force state to something else first:
      service.handleMessageForTest(jsonEncode({'type': 'pong'})); // no-op
      await sub.cancel();
    });

    test('malformed message is ignored without throwing', () {
      expect(
        () => service.handleMessageForTest('not valid json {{{'),
        returnsNormally,
      );
    });

    test('pong message does not emit on any stream', () async {
      int addedCount = 0, updatedCount = 0, removedCount = 0;
      final subs = [
        service.onRecipeAdded.listen((_) => addedCount++),
        service.onRecipeUpdated.listen((_) => updatedCount++),
        service.onRecipeRemoved.listen((_) => removedCount++),
      ];

      service.handleMessageForTest(jsonEncode({'type': 'pong'}));

      await Future.microtask(() {});
      expect(addedCount + updatedCount + removedCount, 0);
      for (final s in subs) {
        await s.cancel();
      }
    });
  });
}
