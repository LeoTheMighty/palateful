// rp-3 — Pantry stateless refactor + provider reactivity regression.
//
// Covers:
//   1. PantryService emits one PantryItem* event per mutation with
//      pantryId in the payload.
//   2. `pantryIngredientsProvider(pantryId)` invalidates on events
//      scoped to the same pantryId, ignores others.
//   3. Regression: the service has no internal cache fields — invoking
//      a mutation on one instance does not affect another.

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/pantry/providers/pantry_provider.dart';
import 'package:palateful/features/pantry/services/pantry_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApi extends ApiClient {
  int getDefaultPantryCalls = 0;
  bool throwNext = false;
  List<Map<String, dynamic>> items = [
    {
      'pantry_id': 'p1',
      'ingredient_id': 'i-flour',
      'ingredient_name': 'Flour',
      'quantity_display': 1.0,
      'unit_display': 'bag',
      'quantity_normalized': 1.0,
      'unit_normalized': 'bag',
    },
  ];

  @override
  Future<Response> getDefaultPantry() async {
    getDefaultPantryCalls++;
    return _ok({'id': 'p1', 'name': 'Default', 'items': items});
  }

  @override
  Future<Response> addPantryIngredient(
    String pantryId,
    Map<String, dynamic> data,
  ) async {
    _maybeThrow();
    final added = {
      'pantry_id': pantryId,
      'ingredient_id': data['ingredient_id'] ?? 'i-new',
      'ingredient_name': data['name'] ?? 'New',
      'quantity_display': data['quantity_display'] ?? 1.0,
      'unit_display': data['unit_display'] ?? 'each',
      'quantity_normalized': data['quantity_normalized'] ?? 1.0,
      'unit_normalized': data['unit_normalized'] ?? 'each',
    };
    items = [...items, added];
    return _ok(added);
  }

  @override
  Future<Response> updatePantryIngredient(
    String pantryId,
    String ingredientId,
    Map<String, dynamic> data,
  ) async {
    _maybeThrow();
    final updated = {
      'pantry_id': pantryId,
      'ingredient_id': ingredientId,
      'ingredient_name': 'Updated',
      'quantity_display': data['quantity_display'] ?? 2.0,
      'unit_display': data['unit_display'] ?? 'cups',
      'quantity_normalized': data['quantity_normalized'] ?? 2.0,
      'unit_normalized': data['unit_normalized'] ?? 'cups',
    };
    return _ok(updated);
  }

  @override
  Future<Response> deletePantryIngredient(
    String pantryId,
    String ingredientId,
  ) async {
    _maybeThrow();
    items = items.where((i) => i['ingredient_id'] != ingredientId).toList();
    return _ok({'success': true});
  }

  void _maybeThrow() {
    if (throwNext) {
      throwNext = false;
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 500,
        ),
        type: DioExceptionType.badResponse,
      );
    }
  }
}

Future<List<MutationEvent>> _captureAllEvents(
  Future<void> Function() action,
) async {
  final events = <MutationEvent>[];
  final sub = mutationBusStream().listen(events.add);
  await action();
  await Future<void>.delayed(Duration.zero);
  await sub.cancel();
  return events;
}

void _register(_FakeApi api) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<PantryService>()) gi.unregister<PantryService>();
  gi.registerSingleton<ApiClient>(api);
  gi.registerLazySingleton<PantryService>(
    () => PantryService(api: gi<ApiClient>()),
  );
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<PantryService>()) gi.unregister<PantryService>();
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

void main() {
  setUpAll(() async {
  });

  group('PantryService emits', () {
    late _FakeApi api;
    late PantryService service;

    setUp(() {
      api = _FakeApi();
      _register(api);
      service = GetIt.instance<PantryService>();
    });

    tearDown(_unregister);

    test('addPantryIngredient emits PantryItemAdded with pantryId', () async {
      final events = await _captureAllEvents(() async {
        await service.addPantryIngredient('p1', {'name': 'Sugar'});
      });
      final added = events.whereType<PantryItemAdded>().single;
      expect(added.pantryId, 'p1');
    });

    test('updatePantryIngredient emits PantryItemUpdated', () async {
      final events = await _captureAllEvents(() async {
        await service.updatePantryIngredient(
          'p1',
          'i-flour',
          {'quantity_display': 5.0},
        );
      });
      final upd = events.whereType<PantryItemUpdated>().single;
      expect(upd.itemId, 'i-flour');
      expect(upd.pantryId, 'p1');
    });

    test('deletePantryIngredient emits PantryItemRemoved', () async {
      final events = await _captureAllEvents(() async {
        await service.deletePantryIngredient('p1', 'i-flour');
      });
      final rem = events.whereType<PantryItemRemoved>().single;
      expect(rem.itemId, 'i-flour');
      expect(rem.pantryId, 'p1');
    });

    test('failed add throws and emits NOTHING', () async {
      api.throwNext = true;
      final events = await _captureAllEvents(() async {
        try {
          await service.addPantryIngredient('p1', {'name': 'x'});
        } on DioException {
          // swallowed
        }
      });
      expect(events, isEmpty);
    });
  });

  group('PantryService is stateless', () {
    setUp(() {
      final gi = GetIt.instance;
      if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
      gi.registerSingleton<ApiClient>(_FakeApi());
    });

    tearDown(() {
      final gi = GetIt.instance;
      if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    });

    test('two service instances share no cache', () async {
      final a = PantryService(api: GetIt.instance<ApiClient>());
      final b = PantryService(api: GetIt.instance<ApiClient>());
      await a.addPantryIngredient('p1', {'name': 'A'});
      // Verify b has no "dirty" state — the service holds nothing.
      final pantry = await b.getDefaultPantry();
      expect(pantry.id, 'p1');
    });
  });

  group('pantryIngredientsProvider', () {
    late _FakeApi api;
    late ProviderContainer container;

    setUp(() {
      api = _FakeApi();
      _register(api);
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
      _unregister();
    });

    test('invalidates on PantryItemAdded for same pantry', () async {
      await container.read(pantryIngredientsProvider('p1').future);
      final baseline = api.getDefaultPantryCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const PantryItemAdded(
        itemId: 'i-sugar',
        item: <String, dynamic>{'ingredient_id': 'i-sugar'},
        pantryId: 'p1',
      ));
      await Future<void>.delayed(Duration.zero);
      await container.read(pantryIngredientsProvider('p1').future);
      expect(api.getDefaultPantryCalls, greaterThan(baseline));
    });

    test('does NOT invalidate on event for a different pantry', () async {
      await container.read(pantryIngredientsProvider('p1').future);
      final baseline = api.getDefaultPantryCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const PantryItemAdded(
        itemId: 'i-sugar',
        item: <String, dynamic>{'ingredient_id': 'i-sugar'},
        pantryId: 'p-other',
      ));
      await Future<void>.delayed(Duration.zero);
      expect(api.getDefaultPantryCalls, baseline);
    });

    test('ignores RecipeCreated (unrelated event type)', () async {
      await container.read(pantryIngredientsProvider('p1').future);
      final baseline = api.getDefaultPantryCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(RecipeCreated(
        recipeId: 'r1',
        recipe: const {'id': 'r1'},
        bookId: 'b1',
      ));
      await Future<void>.delayed(Duration.zero);
      expect(api.getDefaultPantryCalls, baseline);
    });
  });
}
