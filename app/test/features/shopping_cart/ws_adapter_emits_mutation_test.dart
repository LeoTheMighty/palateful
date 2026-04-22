// rp-4 — ShoppingCartService WS adapter consolidation.
//
// Asserts that:
//   1. Each inbound WS frame (item_added / item_updated / item_checked /
//      item_removed) lowers into a MutationBus event, keyed by the
//      currently-connected list id.
//   2. Transport-level frames (presence_update, sync_response) do NOT
//      emit — they are not mutations.
//   3. External ShoppingCartService API (onItemAdded etc.) still fires
//      alongside the new emits (additive, not replacing).
//   4. Local mutation methods (addItem/updateItem/toggleItemChecked/
//      deleteItem) emit on success.
//   5. Dual-path idempotence — local + WS frame for the same id both
//      emit.

import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list_item.dart';
import 'package:palateful/features/shopping_cart/services/shopping_cart_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApi extends ApiClient {
  @override
  Future<Response> addShoppingListItem(
    String listId,
    Map<String, dynamic> data,
  ) async =>
      _ok({
        'id': 'item-local-1',
        'list_id': listId,
        'name': data['name'],
        'quantity': data['quantity'] ?? 1.0,
        'is_checked': false,
        'added_at': '2026-04-01T00:00:00Z',
      });

  @override
  Future<Response> updateShoppingListItem(
    String listId,
    String itemId,
    Map<String, dynamic> data,
  ) async =>
      _ok({
        'id': itemId,
        'list_id': listId,
        'name': 'Something',
        'quantity': 1.0,
        'is_checked': data['is_checked'] ?? false,
        'added_at': '2026-04-01T00:00:00Z',
      });

  @override
  Future<Response> deleteShoppingListItem(String listId, String itemId) async =>
      _ok({'success': true});
}

Future<List<MutationEvent>> _capture(
  Future<void> Function() action,
) async {
  final events = <MutationEvent>[];
  final sub = mutationBusStream().listen(events.add);
  await action();
  await Future<void>.delayed(Duration.zero);
  await sub.cancel();
  return events;
}

Map<String, dynamic> _wsItem(String id, {bool checked = false}) => {
      'id': id,
      'list_id': 'list-1',
      'name': 'Milk',
      'quantity': 1.0,
      'is_checked': checked,
      'added_at': '2026-04-01T00:00:00Z',
    };

String _wsFrame(String type, Map<String, dynamic> data) =>
    jsonEncode({'type': type, 'data': data});

String _wsPresenceFrame() => jsonEncode({
      'type': 'presence_update',
      'user_id': 'u1',
      'name': 'Alice',
      'status': 'online',
    });

void _register(_FakeApi api) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<ShoppingCartService>()) {
    gi.unregister<ShoppingCartService>();
  }
  gi.registerSingleton<ApiClient>(api);
  gi.registerLazySingleton<ShoppingCartService>(() => ShoppingCartService());
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ShoppingCartService>()) {
    gi.unregister<ShoppingCartService>();
  }
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  group('Local mutation methods emit', () {
    late _FakeApi api;
    late ShoppingCartService service;

    setUp(() {
      api = _FakeApi();
      _register(api);
      service = GetIt.instance<ShoppingCartService>();
    });

    tearDown(_unregister);

    test('addItem emits ShoppingListItemAdded', () async {
      final events = await _capture(() async {
        await service.addItem('list-1', name: 'Milk');
      });
      final added = events.whereType<ShoppingListItemAdded>().single;
      expect(added.listId, 'list-1');
      expect(added.itemId, 'item-local-1');
    });

    test('updateItem emits ShoppingListItemUpdated', () async {
      final events = await _capture(() async {
        await service.updateItem(
          'list-1',
          'item-x',
          const {'is_checked': true},
        );
      });
      final upd = events.whereType<ShoppingListItemUpdated>().single;
      expect(upd.listId, 'list-1');
      expect(upd.itemId, 'item-x');
    });

    test('toggleItemChecked emits ShoppingListItemUpdated', () async {
      final item = ShoppingListItem.fromJson(_wsItem('item-y'));
      final events = await _capture(() async {
        await service.toggleItemChecked('list-1', item);
      });
      expect(events.whereType<ShoppingListItemUpdated>(), hasLength(1));
    });

    test('deleteItem emits ShoppingListItemRemoved', () async {
      final events = await _capture(() async {
        await service.deleteItem('list-1', 'item-z');
      });
      final rem = events.whereType<ShoppingListItemRemoved>().single;
      expect(rem.itemId, 'item-z');
    });
  });

  group('WS frames lower to MutationBus', () {
    late _FakeApi api;
    late ShoppingCartService service;

    setUp(() {
      api = _FakeApi();
      _register(api);
      service = GetIt.instance<ShoppingCartService>();
      service.setCurrentListIdForTest('list-1');
    });

    tearDown(_unregister);

    test('item_added frame emits ShoppingListItemAdded', () async {
      final events = await _capture(() async {
        service.handleMessageForTest(_wsFrame('item_added', _wsItem('i-1')));
      });
      final added = events.whereType<ShoppingListItemAdded>().single;
      expect(added.itemId, 'i-1');
      expect(added.listId, 'list-1');
    });

    test('item_updated frame emits ShoppingListItemUpdated', () async {
      final events = await _capture(() async {
        service.handleMessageForTest(_wsFrame('item_updated', _wsItem('i-2')));
      });
      expect(events.whereType<ShoppingListItemUpdated>(), hasLength(1));
    });

    test('item_checked frame also emits ShoppingListItemUpdated', () async {
      final events = await _capture(() async {
        service.handleMessageForTest(
          _wsFrame('item_checked', _wsItem('i-3', checked: true)),
        );
      });
      expect(events.whereType<ShoppingListItemUpdated>(), hasLength(1));
    });

    test('item_removed frame emits ShoppingListItemRemoved', () async {
      final events = await _capture(() async {
        service.handleMessageForTest(
          jsonEncode({'type': 'item_removed', 'data': {'item_id': 'i-4'}}),
        );
      });
      final rem = events.whereType<ShoppingListItemRemoved>().single;
      expect(rem.itemId, 'i-4');
    });

    test('presence_update frame does NOT emit (not a mutation)', () async {
      final events = await _capture(() async {
        service.handleMessageForTest(_wsPresenceFrame());
      });
      expect(events, isEmpty);
    });

    test('pong frame does NOT emit', () async {
      final events = await _capture(() async {
        service.handleMessageForTest(jsonEncode({'type': 'pong'}));
      });
      expect(events, isEmpty);
    });

    test('malformed frame does NOT throw and does NOT emit', () async {
      final events = await _capture(() async {
        service.handleMessageForTest('not valid json');
      });
      expect(events, isEmpty);
    });

    test('StreamController sinks still fire alongside new emits', () async {
      final addedItems = <ShoppingListItem>[];
      final sub = service.onItemAdded.listen(addedItems.add);
      service.handleMessageForTest(_wsFrame('item_added', _wsItem('i-5')));
      await Future<void>.delayed(Duration.zero);
      await sub.cancel();
      expect(addedItems, hasLength(1));
      expect(addedItems.single.id, 'i-5');
    });

    test('dual-path: local + WS frame for the same id both emit', () async {
      final events = await _capture(() async {
        await service.addItem('list-1', name: 'Milk');
        service.handleMessageForTest(
          _wsFrame('item_added', _wsItem('item-local-1')),
        );
      });
      // Two add events (subscribers are expected to be idempotent).
      expect(events.whereType<ShoppingListItemAdded>(), hasLength(2));
    });
  });
}
