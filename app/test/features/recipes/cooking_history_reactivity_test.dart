// rp-3 AC #6 — CookingLogService + recipeCookingHistoryProvider
// handoff from the meals/calendar epic.
//
// Covers:
//   1. CookingLogService.create emits `CookingLogCreated(recipeId)`.
//   2. `recipeCookingHistoryProvider(recipeId)` invalidates on
//      `CookingLogCreated` filtered by recipeId.
//   3. Unrelated event types don't invalidate.

import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/recipes/providers/cooking_history_provider.dart';
import 'package:palateful/features/recipes/services/cooking_log_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApi extends ApiClient {
  int getRecipeCookingLogsCalls = 0;
  List<Map<String, dynamic>> logs = const [];

  @override
  Future<Response> createCookingLog(Map<String, dynamic> data) async =>
      _ok({'id': 'log-new', ...data});

  @override
  Future<Response> getRecipeCookingLogs(String recipeId) async {
    getRecipeCookingLogsCalls++;
    return _ok({'items': logs});
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
  if (gi.isRegistered<CookingLogService>()) {
    gi.unregister<CookingLogService>();
  }
  gi.registerSingleton<ApiClient>(api);
  gi.registerLazySingleton<CookingLogService>(
    () => CookingLogService(gi<ApiClient>()),
  );
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<CookingLogService>()) {
    gi.unregister<CookingLogService>();
  }
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  group('CookingLogService emits', () {
    late _FakeApi api;
    late CookingLogService service;

    setUp(() {
      api = _FakeApi();
      _register(api);
      service = GetIt.instance<CookingLogService>();
    });

    tearDown(_unregister);

    test('create emits CookingLogCreated with recipeId', () async {
      final events = await _captureAllEvents(() async {
        await service.create('r-42', {'rating': 5});
      });
      final ev = events.whereType<CookingLogCreated>().single;
      expect(ev.recipeId, 'r-42');
      expect(ev.logId, 'log-new');
    });
  });

  group('recipeCookingHistoryProvider', () {
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

    test('invalidates on CookingLogCreated for same recipe', () async {
      await container.read(recipeCookingHistoryProvider('r-42').future);
      final baseline = api.getRecipeCookingLogsCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const CookingLogCreated(
        logId: 'log-new',
        log: <String, dynamic>{'id': 'log-new'},
        recipeId: 'r-42',
      ));
      await Future<void>.delayed(Duration.zero);
      await container.read(recipeCookingHistoryProvider('r-42').future);
      expect(api.getRecipeCookingLogsCalls, greaterThan(baseline));
    });

    test('does NOT invalidate on CookingLogCreated for a different recipe',
        () async {
      await container.read(recipeCookingHistoryProvider('r-42').future);
      final baseline = api.getRecipeCookingLogsCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const CookingLogCreated(
        logId: 'log-new',
        log: <String, dynamic>{'id': 'log-new'},
        recipeId: 'r-other',
      ));
      await Future<void>.delayed(Duration.zero);
      expect(api.getRecipeCookingLogsCalls, baseline);
    });
  });
}
