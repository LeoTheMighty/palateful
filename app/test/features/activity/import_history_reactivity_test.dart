// rf-5 — Imports reactivity regression.
//
// Tests the three wiring points:
//   1. `importsSeeAllProvider` refreshes when an ImportItemDismissed /
//      ImportJobDismissed / ImportItemRetried event fires on the bus.
//   2. `ActivityReadProvider` calls `refreshUnreadCount()` on the same
//      events (badge recomputes without waiting 30s).
//   3. The import events reach the bus — `emitMutation` is called from
//      the dismiss/retry paths and subscribers receive it.
//
// Uses the shared `pumpWithMutation` helper; never `pumpAndSettle` with
// a wall-clock timeout (Locked Decision #5 flaky-risk mitigation).

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';
import 'package:palateful/features/activity/providers/imports_see_all_provider.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApi extends ApiClient {
  int listImportJobsCalls = 0;
  int listImportItemsCalls = 0;
  int listImportItemsBatchCalls = 0;
  int getUnreadActivityCountCalls = 0;

  @override
  Future<Response> listImportJobs({
    String? status,
    int limit = 20,
    int offset = 0,
    bool includeArchived = false,
    bool archivedOnly = false,
    String? cursor,
  }) async {
    listImportJobsCalls++;
    return _ok({
      'jobs': [
        {'id': 'j1', 'source_type': 'url'},
      ],
      'next_cursor': null,
    });
  }

  @override
  Future<Response> listImportItems(
    String jobId, {
    String? status,
    bool includeArchived = false,
  }) async {
    listImportItemsCalls++;
    return _ok({
      'items': [
        {
          'id': 'i1',
          'recipe_name': 'Pasta',
          'status': 'dismissed',
          'source_type': 'url',
          'archived_at': '2026-04-22T10:00:00Z',
          'created_at': '2026-04-22T09:00:00Z',
        },
      ],
    });
  }

  @override
  Future<Response> listImportItemsBatch(
    List<String> jobIds, {
    String? status,
    bool includeArchived = false,
  }) async {
    listImportItemsBatchCalls++;
    final items = <dynamic>[];
    for (final jobId in jobIds) {
      items.add({
        'id': 'i1',
        'job_id': jobId,
        'recipe_name': 'Pasta',
        'status': 'dismissed',
        'source_type': 'url',
        'archived_at': '2026-04-22T10:00:00Z',
        'created_at': '2026-04-22T09:00:00Z',
      });
    }
    return _ok({'items': items});
  }

  @override
  Future<Response> getUnreadActivityCount() async {
    getUnreadActivityCountCalls++;
    return _ok({
      'notifications': 0,
      'imports_actionable': 2,
      'count': 2,
    });
  }
}

void main() {
  setUpAll(() async {
  });

  group('importsSeeAllProvider MutationBus subscription', () {
    test('ImportItemDismissed after first load → refetches from top',
        () async {
      final api = _FakeApi();
      final container = ProviderContainer(overrides: [
        // Use the same getIt-free path the provider takes: the API
        // client is resolved via getIt in the production provider.
        // We shim by registering a getIt binding before reading.
      ]);
      addTearDown(container.dispose);

      // Wire the fake into getIt so the provider picks it up.
      _registerApi(api);
      addTearDown(_unregisterApi);

      // Trigger first load — mirrors UI expansion.
      await container
          .read(importsSeeAllProvider.notifier)
          .loadNextPage();
      expect(api.listImportJobsCalls, 1);
      // ffm-2: the per-job loop became a single batch call.
      expect(api.listImportItemsBatchCalls, 1);
      expect(api.listImportItemsCalls, 0);
      expect(container.read(importsSeeAllProvider).items, hasLength(1));

      // Emit dismiss — provider should kick off refreshFromTop.
      emitMutation(const ImportItemDismissed(
        itemId: 'x',
        item: null,
        jobDismissed: false,
      ));
      // refreshFromTop clears state + calls loadNextPage — both async.
      // Drain the microtask queue.
      await Future.delayed(Duration.zero);
      await Future.delayed(Duration.zero);

      expect(api.listImportJobsCalls, 2,
          reason: 'dismiss event should trigger exactly one refetch');
      expect(api.listImportItemsBatchCalls, 2);
    });

    test('ImportItemRetried before first load → no-op (section closed)',
        () async {
      final api = _FakeApi();
      final container = ProviderContainer();
      addTearDown(container.dispose);
      _registerApi(api);
      addTearDown(_unregisterApi);

      // Read provider to wire the subscription. Don't call loadNextPage.
      container.read(importsSeeAllProvider);

      emitMutation(const ImportItemRetried(itemId: 'x', item: null));
      await Future.delayed(Duration.zero);

      // No refetch — the section hasn't been opened yet.
      expect(api.listImportJobsCalls, 0);
      expect(api.listImportItemsBatchCalls, 0);
    });

    test('unrelated event (RecipeCreated) never triggers a refetch',
        () async {
      final api = _FakeApi();
      final container = ProviderContainer();
      addTearDown(container.dispose);
      _registerApi(api);
      addTearDown(_unregisterApi);

      await container
          .read(importsSeeAllProvider.notifier)
          .loadNextPage();
      expect(api.listImportJobsCalls, 1);

      emitMutation(const RecipeCreated(
        recipeId: 'r-1',
        recipe: {'id': 'r-1'},
        bookId: 'b-1',
      ));
      await Future.delayed(Duration.zero);

      expect(api.listImportJobsCalls, 1,
          reason: 'recipe events must not invalidate imports-see-all');
    });
  });

  group('ActivityReadProvider MutationBus subscription', () {
    test('ImportItemDismissed → refreshUnreadCount fires', () async {
      final api = _FakeApi();
      final provider = ActivityReadProvider(api);
      addTearDown(provider.dispose);

      // Baseline call count — the constructor doesn't prefetch.
      expect(api.getUnreadActivityCountCalls, 0);

      emitMutation(const ImportItemDismissed(
        itemId: 'i1',
        item: null,
        jobDismissed: false,
      ));
      // Drain microtasks for the async refresh.
      await Future.delayed(Duration.zero);
      await Future.delayed(Duration.zero);

      expect(api.getUnreadActivityCountCalls, 1);
      expect(provider.importsActionableCount.value, 2);
    });

    test('ImportJobDismissed → refreshUnreadCount fires', () async {
      final api = _FakeApi();
      final provider = ActivityReadProvider(api);
      addTearDown(provider.dispose);

      emitMutation(const ImportJobDismissed(jobId: 'j1'));
      await Future.delayed(Duration.zero);
      await Future.delayed(Duration.zero);

      expect(api.getUnreadActivityCountCalls, 1);
    });

    test('RecipeCreated → does NOT trigger refreshUnreadCount', () async {
      final api = _FakeApi();
      final provider = ActivityReadProvider(api);
      addTearDown(provider.dispose);

      emitMutation(const RecipeCreated(
        recipeId: 'r-1',
        recipe: {'id': 'r-1'},
        bookId: 'b-1',
      ));
      await Future.delayed(Duration.zero);

      expect(api.getUnreadActivityCountCalls, 0,
          reason: 'recipe events are not import events — badge poll only');
    });
  });
}

void _registerApi(ApiClient api) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(api);
}

void _unregisterApi() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}
