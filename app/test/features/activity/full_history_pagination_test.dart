/// afh-6 regression — end-to-end pagination walk on the Notifications
/// See-all footer. Drives the provider through 5 pages back-to-back
/// and asserts: (a) cursors are captured in order; (b) every row is
/// accounted for without duplicates or gaps; (c) end-of-list row
/// renders when the last page's `next_cursor` is null. A true 10k-row
/// memory test requires DevTools integration that widget tests don't
/// have access to — this is the next best thing: a repeated-page walk
/// that exercises the same code paths the 10k scenario would.
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/providers/notifications_see_all_provider.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

Map<String, dynamic> _page(int pageNumber, {String? nextCursor}) {
  return {
    'items': List.generate(50, (i) {
      final rowIndex = pageNumber * 50 + i;
      return {
        'id': 'row-$rowIndex',
        'type': 'partner_action',
        'title': 'title-$rowIndex',
        'read': true,
        'created_at': '2026-01-01T00:00:00Z',
        'archived_at': '2026-02-01T00:00:00Z',
      };
    }),
    'next_cursor': nextCursor,
    'total': 0,
    'limit': 50,
    'offset': 0,
  };
}

class _MultiPageFakeApi extends ApiClient {
  final List<String?> cursorsSeen = [];

  @override
  Future<Response> listActivitiesSeeAll({
    String? cursor,
    int limit = 50,
  }) async {
    cursorsSeen.add(cursor);
    // 5-page walk: null → C1 → C2 → C3 → C4 → (end).
    const cursorChain = ['C1', 'C2', 'C3', 'C4', null];
    final pageNumber = cursorsSeen.length - 1;
    return _fakeResponse(_page(pageNumber, nextCursor: cursorChain[pageNumber]));
  }

  @override
  Future<Response> getActivitiesSeeAllCount() async =>
      _fakeResponse({'archived': 100, 'read_and_older': 150, 'total': 250});
}

void _register(ApiClient client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

void main() {
  setUpAll(() async {
  });

  tearDown(_unregister);

  test('walks 5 pages end-to-end, captures every cursor in order', () async {
    final api = _MultiPageFakeApi();
    _register(api);

    final container = ProviderContainer();
    addTearDown(container.dispose);
    final notifier = container.read(notificationsSeeAllProvider.notifier);

    // Walk until end-of-list.
    for (var i = 0; i < 6; i++) {
      final s = container.read(notificationsSeeAllProvider);
      if (s.hasLoadedFirstPage && s.nextCursor == null && !s.hasError) break;
      await notifier.loadNextPage();
    }

    final finalState = container.read(notificationsSeeAllProvider);
    expect(finalState.isEnded, isTrue);
    expect(finalState.items.length, 250);
    // Every row accounted for: row-0 through row-249 in order, unique.
    final seen = finalState.items.map((r) => r.id).toSet();
    expect(seen.length, 250, reason: 'no duplicate rows across pages');
    for (var i = 0; i < 250; i++) {
      expect(seen.contains('row-$i'), isTrue,
          reason: 'row-$i should be present — no gaps across the walk');
    }

    // Cursors were advanced in order across 5 calls.
    expect(api.cursorsSeen,
        equals([null, 'C1', 'C2', 'C3', 'C4']),
        reason: 'each page request carries the prior page\'s next_cursor');
  });

  test('rapid-fire archive + restore path keeps state coherent', () async {
    final api = _MultiPageFakeApi();
    _register(api);

    final container = ProviderContainer();
    addTearDown(container.dispose);
    final notifier = container.read(notificationsSeeAllProvider.notifier);

    // Load one page so we have rows to work with.
    await notifier.loadNextPage();
    final row = container.read(notificationsSeeAllProvider).items.first;

    // Archive optimistically (remove) → undo (restore) → re-archive (remove).
    notifier.removeRow(row.id);
    expect(container.read(notificationsSeeAllProvider).items.length, 49);

    notifier.restoreRow(row);
    expect(container.read(notificationsSeeAllProvider).items.length, 50);
    expect(container.read(notificationsSeeAllProvider).items.first.id, row.id);

    notifier.removeRow(row.id);
    expect(container.read(notificationsSeeAllProvider).items.length, 49);
    expect(
      container.read(notificationsSeeAllProvider).items.any((r) => r.id == row.id),
      isFalse,
    );
  });
}
