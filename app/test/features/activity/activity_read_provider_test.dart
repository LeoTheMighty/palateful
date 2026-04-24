import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';

Response<dynamic> _fakeResponse(dynamic data, {int status = 200}) {
  return Response(
    data: data,
    requestOptions: RequestOptions(path: ''),
    statusCode: status,
  );
}

class _FakeApiClient extends ApiClient {
  final List<String> markedIds = [];
  final Map<String, int> attemptsPerId = {};
  final Set<String> failOnceIds;
  final Set<String> always404Ids;
  int unreadCountCalls = 0;
  int unreadCountValue;
  // abi-3: structured payload fields. When both are non-null, the fake
  // returns the new `{notifications, imports_actionable, count}` shape
  // (mirroring the abi-1 server). When either is null, it falls back to
  // the legacy `{count: unreadCountValue}` shape so old-client tests can
  // exercise the fallback branch.
  int? notificationsValue;
  int? importsActionableValue;
  List<Map<String, dynamic>> activities;

  _FakeApiClient({
    this.failOnceIds = const {},
    this.always404Ids = const {},
    this.unreadCountValue = 0,
    this.notificationsValue,
    this.importsActionableValue,
    this.activities = const [],
  });

  @override
  Future<Response> markActivityRead(String id) async {
    final prev = attemptsPerId[id] ?? 0;
    final attempt = prev + 1;
    attemptsPerId[id] = attempt;

    if (always404Ids.contains(id)) {
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 404,
        ),
      );
    }
    if (failOnceIds.contains(id) && attempt == 1) {
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        type: DioExceptionType.connectionError,
      );
    }
    markedIds.add(id);
    return _fakeResponse({'success': true});
  }

  @override
  Future<Response> getUnreadActivityCount() async {
    unreadCountCalls++;
    if (notificationsValue != null && importsActionableValue != null) {
      final n = notificationsValue!;
      final i = importsActionableValue!;
      return _fakeResponse({
        'notifications': n,
        'imports_actionable': i,
        'count': n + i,
      });
    }
    return _fakeResponse({'count': unreadCountValue});
  }

  @override
  Future<Response> getActivities({int limit = 50, int offset = 0}) async {
    return _fakeResponse({'items': activities, 'total': activities.length});
  }
}

void main() {
  setUpAll(() async {
  });

  group('ActivityReadProvider', () {
    test('markIdsRead fires one request per id', () async {
      final api = _FakeApiClient();
      final provider = ActivityReadProvider(api);

      await provider.markIdsRead(['a', 'b', 'c']);

      expect(api.markedIds..sort(), equals(['a', 'b', 'c']));
      expect(api.attemptsPerId['a'], 1);
      expect(api.attemptsPerId['b'], 1);
      expect(api.attemptsPerId['c'], 1);
    });

    test('markIdsRead retries on transient failure (connection error)',
        () async {
      final api = _FakeApiClient(failOnceIds: {'flaky'});
      final provider = ActivityReadProvider(api);

      await provider.markIdsRead(['flaky']);

      expect(api.markedIds, contains('flaky'));
      expect(api.attemptsPerId['flaky'], 2,
          reason: 'should retry once after first failure');
    });

    test('markIdsRead does NOT retry on 4xx (activity gone)', () async {
      final api = _FakeApiClient(always404Ids: {'gone'});
      final provider = ActivityReadProvider(api);

      await provider.markIdsRead(['gone']);

      expect(api.attemptsPerId['gone'], 1,
          reason: '404 is terminal — do not spin on a deleted activity');
      expect(api.markedIds, isEmpty);
    });

    test('markIdsRead is a no-op on empty iterable', () async {
      final api = _FakeApiClient();
      final provider = ActivityReadProvider(api);

      await provider.markIdsRead(const []);

      expect(api.attemptsPerId, isEmpty);
    });

    test('refreshUnreadCount updates ValueNotifier', () async {
      final api = _FakeApiClient(unreadCountValue: 7);
      final provider = ActivityReadProvider(api);

      expect(provider.unreadCount.value, 0);
      await provider.refreshUnreadCount();
      expect(provider.unreadCount.value, 7);
      expect(api.unreadCountCalls, 1);
    });

    test('markLoadedImportActivitiesRead only touches import-typed unread',
        () async {
      final api = _FakeApiClient(
        activities: [
          {'id': '1', 'type': 'partner_action', 'read': false},
          {'id': '2', 'type': 'import_failed', 'read': false},
          {'id': '3', 'type': 'import_complete', 'read': true},
          {'id': '4', 'type': 'import_needs_review', 'read': false},
        ],
      );
      final provider = ActivityReadProvider(api);

      await provider.markLoadedImportActivitiesRead();

      expect(api.markedIds..sort(), equals(['2', '4']),
          reason: 'non-import and already-read activities are skipped');
    });

    test('setUnreadCount notifies listeners only on change', () async {
      final api = _FakeApiClient();
      final provider = ActivityReadProvider(api);
      var notifyCount = 0;
      provider.unreadCount.addListener(() => notifyCount++);

      provider.setUnreadCount(0);
      expect(notifyCount, 0, reason: 'same value = no notify');

      provider.setUnreadCount(3);
      expect(notifyCount, 1);

      provider.setUnreadCount(3);
      expect(notifyCount, 1, reason: 'stable value = no notify');
    });

    test(
      'abi-3: structured payload populates notifications + imports counts',
      () async {
        final api = _FakeApiClient(
          notificationsValue: 2,
          importsActionableValue: 3,
        );
        final provider = ActivityReadProvider(api);

        await provider.refreshUnreadCount();

        expect(provider.notificationsCount.value, 2);
        expect(provider.importsActionableCount.value, 3);
        expect(provider.unreadCount.value, 5,
            reason: 'unreadCount is derived sum');
        expect(provider.structuredCountsAvailable.value, isTrue);
      },
    );

    test(
      'abi-3: old-client fallback keeps bell, suppresses per-tab badges',
      () async {
        final api = _FakeApiClient(unreadCountValue: 7);
        final provider = ActivityReadProvider(api);

        await provider.refreshUnreadCount();

        expect(provider.unreadCount.value, 7);
        expect(provider.notificationsCount.value, 0);
        expect(provider.importsActionableCount.value, 0);
        expect(provider.structuredCountsAvailable.value, isFalse);
      },
    );

    test(
      'abi-3: transition structured → legacy clears per-tab counts',
      () async {
        final api = _FakeApiClient(
          notificationsValue: 4,
          importsActionableValue: 1,
        );
        final provider = ActivityReadProvider(api);
        await provider.refreshUnreadCount();
        expect(provider.structuredCountsAvailable.value, isTrue);

        // Simulate a server rollback that returns only `{count}`.
        api.notificationsValue = null;
        api.importsActionableValue = null;
        api.unreadCountValue = 2;
        await provider.refreshUnreadCount();

        expect(provider.unreadCount.value, 2);
        expect(provider.notificationsCount.value, 0,
            reason: 'stale per-tab values must not leak under fallback');
        expect(provider.importsActionableCount.value, 0);
        expect(provider.structuredCountsAvailable.value, isFalse);
      },
    );

    test(
      'abi-3: 99+ rendering is the widget\'s job — provider keeps exact number',
      () async {
        final api = _FakeApiClient(
          notificationsValue: 50,
          importsActionableValue: 80,
        );
        final provider = ActivityReadProvider(api);
        await provider.refreshUnreadCount();
        expect(provider.unreadCount.value, 130,
            reason:
                'provider exposes the exact sum; badge-label truncation to "99+" '
                'is a render-layer concern in scaffold_with_bottom_nav.dart');
      },
    );

    // ────────────────────────────────────────────────────────────────
    // pfc-1: single 30s poll, decision matrix, disposer hygiene.
    // ────────────────────────────────────────────────────────────────

    test('pfc-1: startPolling is idempotent (exactly one Timer)', () async {
      final api = _FakeApiClient();
      final provider = ActivityReadProvider(api);

      expect(provider.hasActiveTimer, isFalse);
      provider.startPolling();
      expect(provider.hasActiveTimer, isTrue);

      // Second call is a no-op — the provider does NOT spawn a second
      // Timer. There's no observable second Timer handle, but we can
      // prove the invariant by round-tripping stop → start and by
      // asserting the call doesn't re-fire the cold-start _tick
      // (unreadCountCalls would jump from 1 → 2 if it did).
      // Flush the first immediate tick's microtask-queued future:
      await Future<void>.delayed(Duration.zero);
      final callsAfterFirstStart = api.unreadCountCalls;
      provider.startPolling();
      await Future<void>.delayed(Duration.zero);
      expect(api.unreadCountCalls, callsAfterFirstStart,
          reason: 'second startPolling must not re-fire cold-start tick');
      expect(provider.hasActiveTimer, isTrue);

      provider.stopPolling();
      expect(provider.hasActiveTimer, isFalse);
    });

    test(
      'pfc-1: _tick skips unread-count when a contributesUnreadCount '
      'subscriber is alive',
      () async {
        final api = _FakeApiClient();
        final provider = ActivityReadProvider(api);

        var callbackFires = 0;
        final dispose = provider.registerTickListener(
          () => callbackFires++,
          contributesUnreadCount: true,
        );
        expect(provider.activitiesFetchSubscriberCount, 1);

        await provider.debugTick();

        expect(callbackFires, 1,
            reason: 'listener fires on every tick');
        expect(api.unreadCountCalls, 0,
            reason:
                'unread-count is suppressed while a contributor is alive');

        dispose();
        expect(provider.activitiesFetchSubscriberCount, 0);

        await provider.debugTick();
        expect(api.unreadCountCalls, 1,
            reason:
                'once the contributor is disposed, the provider resumes '
                'its own unread-count fetch on each tick');
      },
    );

    test(
      'pfc-1: _tick fires unread-count when only non-contributing '
      'subscribers are alive (imports tab case)',
      () async {
        final api = _FakeApiClient();
        final provider = ActivityReadProvider(api);

        var callbackFires = 0;
        final dispose = provider.registerTickListener(
          () => callbackFires++,
          // Default contributesUnreadCount: false — imports tab fetches
          // do not carry the bell count.
        );
        expect(provider.activitiesFetchSubscriberCount, 0);

        await provider.debugTick();

        expect(callbackFires, 1);
        expect(api.unreadCountCalls, 1,
            reason:
                'non-contributing listeners must not suppress /unread-count');

        dispose();
      },
    );

    test(
      'pfc-1: disposer is idempotent — double-invoke is a no-op',
      () async {
        final api = _FakeApiClient();
        final provider = ActivityReadProvider(api);

        final dispose = provider.registerTickListener(
          () {},
          contributesUnreadCount: true,
        );
        expect(provider.tickListenerCount, 1);
        expect(provider.activitiesFetchSubscriberCount, 1);

        dispose();
        dispose(); // Double-invoke.

        expect(provider.tickListenerCount, 0);
        expect(provider.activitiesFetchSubscriberCount, 0,
            reason:
                'double-invoke must not drive the counter negative');
      },
    );

    test(
      'pfc-1: mixed contributor + non-contributor — contributor wins '
      'gating behaviour',
      () async {
        final api = _FakeApiClient();
        final provider = ActivityReadProvider(api);

        final disposeNotif = provider.registerTickListener(
          () {},
          contributesUnreadCount: true,
        );
        final disposeImp = provider.registerTickListener(() {});
        expect(provider.tickListenerCount, 2);
        expect(provider.activitiesFetchSubscriberCount, 1);

        await provider.debugTick();
        expect(api.unreadCountCalls, 0,
            reason:
                'while notifications_tab listener is alive, unread-count '
                'is suppressed even though imports_tab is also subscribed');

        disposeNotif();
        await provider.debugTick();
        expect(api.unreadCountCalls, 1,
            reason:
                'after notifications_tab unsubscribes, imports_tab alone '
                'does not suppress unread-count');

        disposeImp();
      },
    );

    // ────────────────────────────────────────────────────────────────
    // ffm-3: MutationBus reload suppresses the subsequent tick's own
    // `refreshUnreadCount` for 10 seconds. Tab-listener callbacks are
    // always invoked — only the bell-count round-trip is coalesced.
    // ────────────────────────────────────────────────────────────────

    test(
      'ffm-3: tick short-circuits refreshUnreadCount within 10s of a '
      'bus-driven reload',
      () async {
        final api = _FakeApiClient();
        final provider = ActivityReadProvider(api);

        // Fake clock at t=0.
        var now = 1_000_000;
        provider.debugSetClock(() => now);

        // t=0: tick fires, baseline network fetch.
        await provider.debugTick();
        expect(api.unreadCountCalls, 1);

        // t=+2s: MutationBus records a reload (imitated by driving the
        // timestamp forward and calling refreshUnreadCount directly, as
        // the bus subscription does).
        now += 2000;
        provider.debugSetClock(() => now);
        provider.debugSetLastMutationReloadAt(now);
        await provider.refreshUnreadCount();
        expect(api.unreadCountCalls, 2,
            reason: 'bus-driven reload always fetches');

        // t=+6s (4s after bus reload): tick should short-circuit.
        now += 4000;
        provider.debugSetClock(() => now);
        await provider.debugTick();
        expect(api.unreadCountCalls, 2,
            reason: 'within 10s window, tick suppresses its fetch');

        // t=+13s (11s after bus reload): window elapsed, tick re-runs.
        now += 7000;
        provider.debugSetClock(() => now);
        await provider.debugTick();
        expect(api.unreadCountCalls, 3,
            reason: 'past 10s window, tick resumes fetching');
      },
    );

    test(
      'ffm-3: fake-clock matrix — 10 ticks, 3 interleaved bus reloads, '
      'exactly 7 network round-trips from ticks (plus 3 from bus)',
      () async {
        final api = _FakeApiClient();
        final provider = ActivityReadProvider(api);

        var now = 0;
        provider.debugSetClock(() => now);

        // Drive 10 ticks spaced 30s apart, and 3 bus reloads scheduled
        // in the same tick window (so each ought to suppress exactly
        // the tick it precedes).
        final busAt = <int>{1, 4, 7}; // tick indices 1, 4, 7 get a bus reload
        var busCalls = 0;
        for (var i = 0; i < 10; i++) {
          if (busAt.contains(i)) {
            // Bus fires immediately before the tick — within the 10s
            // floor. Record the timestamp and fetch, as the real bus
            // handler does.
            provider.debugSetLastMutationReloadAt(now);
            await provider.refreshUnreadCount();
            busCalls++;
          }
          await provider.debugTick();
          now += 30_000; // advance 30s
          provider.debugSetClock(() => now);
        }

        expect(busCalls, 3);
        // Ticks: 10 scheduled, 3 suppressed by bus → 7 tick-driven
        // fetches. Total calls = 7 tick + 3 bus = 10.
        expect(api.unreadCountCalls, 10,
            reason: 'bus + surviving ticks account for every call');
      },
    );
  });
}
