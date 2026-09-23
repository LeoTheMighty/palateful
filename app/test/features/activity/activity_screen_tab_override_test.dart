import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/activity_screen.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';

/// acttab1 — where the tap to "imports in progress" actually loses its tab.
///
/// `activity_tab_push_test` already ruled the router out: a push with
/// `?tab=imports` builds a FRESH screen and delivers the parameter. So the
/// loss happens after construction, and these tests go after the two
/// mechanisms that can cause it:
///
/// 1. A screen built WITHOUT `?tab=` registers listeners on the two counts
///    (`activity_screen.dart` initState) and auto-switches when they
///    resolve. `activityTabProvider` is app-scoped, so that switch moves
///    EVERY mounted screen, including one that was given an explicit tab.
/// 2. Counts resolving late on the explicit screen's own instance.
///
/// The second is already guarded (listeners are only registered when the
/// route had no `?tab=`). The first is not, and in the reported case it is
/// exactly what fires: a pending parser batch contributes 0 to
/// `imports_actionable` (that counts ImportItems), so the tie resolves to
/// Notifications and drags the Imports screen with it.
/// `ActivityTab.values` order: notifications first, imports second.
const _notifications = 0;
const _imports = 1;

void main() {
  tearDown(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    if (gi.isRegistered<ActivityReadProvider>()) {
      gi.unregister<ActivityReadProvider>();
    }
  });

  testWidgets('an explicit tab survives counts resolving afterwards',
      (tester) async {
    _register();
    await tester.pumpWidget(_wrap(const ActivityScreen(initialTab: 'imports')));
    await tester.pump();
    expect(_selectedTab(tester), _imports);

    // Counts land after mount. This screen was given a tab, so nothing here
    // should move it — even when the counts say Notifications.
    final read = GetIt.instance<ActivityReadProvider>();
    read.notificationsCount.value = 3;
    read.importsActionableCount.value = 0;
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(_selectedTab(tester), _imports);
  });

  testWidgets('a tab-less screen still auto-switches on resolved counts',
      (tester) async {
    // The behaviour that must NOT be broken by the fix: arriving at
    // /activity with no ?tab= picks the busier side.
    _register();
    await tester.pumpWidget(_wrap(const ActivityScreen()));
    await tester.pump();

    final read = GetIt.instance<ActivityReadProvider>();
    read.notificationsCount.value = 0;
    read.importsActionableCount.value = 5;
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(_selectedTab(tester), _imports);
  });

  testWidgets('the latch is session-wide, and that is the trade-off',
      (tester) async {
    // Deliberate consequence, pinned so it is a decision and not a
    // surprise: once anything chooses a tab on purpose — a route's ?tab=
    // or the user's own swipe — the count-based guess stops firing for
    // the rest of the session, on every screen, because the provider is
    // app-scoped. The guess is a cold-start affordance ("abi-4: cold-start
    // fallback"); overriding a deliberate choice with it is the rug-pull
    // this story exists to stop. If that ever needs to be per-screen, the
    // provider has to stop being shared first.
    _register();
    await tester.pumpWidget(_wrap(const ActivityScreen(initialTab: 'imports')));
    await tester.pump();
    expect(_selectedTab(tester), _imports);

    // A later screen with no ?tab=, and counts that would have said
    // Notifications.
    await tester.pumpWidget(_wrap(const ActivityScreen()));
    await tester.pump();
    final read = GetIt.instance<ActivityReadProvider>();
    read.notificationsCount.value = 9;
    read.importsActionableCount.value = 0;
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(_selectedTab(tester), _imports,
        reason: 'the earlier deliberate choice still holds');
  });

  testWidgets(
      'a tab-less screen does not drag an explicit-tab screen with it '
      '(acttab1 — the reported bug)', (tester) async {
    _register();

    // Both mounted at once, sharing one ProviderScope — the shape the
    // IndexedStack produces when /activity was visited before the strip's
    // push. The tab-less one registers the count listeners.
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: Column(
            children: const [
              Expanded(child: ActivityScreen()),
              Expanded(child: ActivityScreen(initialTab: 'imports')),
            ],
          ),
        ),
      ),
    );
    await tester.pump();

    // The counts the reported case produces: a pending PARSER BATCH is not
    // an ImportItem, so imports_actionable is 0 and the tie — or any
    // notification at all — resolves to Notifications.
    final read = GetIt.instance<ActivityReadProvider>();
    read.notificationsCount.value = 1;
    read.importsActionableCount.value = 0;
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    // The explicitly-routed screen must still be on Imports. Before the
    // fix the app-scoped provider carries the tab-less screen's
    // auto-switch into it, which is how Leo's tap lands on an empty
    // Notifications tab.
    final selected = _selectedTabs(tester);
    expect(selected.length, 2, reason: 'both screens mounted');
    expect(selected.last, _imports,
        reason: 'the screen routed with ?tab=imports keeps its tab');
  });
}

// ---------------------------------------------------------------------------

/// The selected tab index of the only mounted ActivityScreen.
int _selectedTab(WidgetTester tester) => _selectedTabs(tester).single;

/// One index per mounted `TabBar`, in mount order. 0 = Notifications,
/// 1 = Imports (`ActivityTab.values` order).
List<int> _selectedTabs(WidgetTester tester) => tester
    .widgetList<TabBar>(find.byType(TabBar))
    .map((b) => b.controller?.index ?? -1)
    .toList();

Response<dynamic> _resp(dynamic data) =>
    Response(data: data, requestOptions: RequestOptions(path: ''), statusCode: 200);

class _FakeApiClient extends ApiClient {
  @override
  Future<Response> getActivities({int limit = 50, int offset = 0}) async =>
      _resp({'activities': const []});

  @override
  Future<Response> listImportJobs({
    String? status,
    int limit = 20,
    int offset = 0,
    bool includeArchived = false,
    bool archivedOnly = false,
    String? cursor,
  }) async =>
      _resp({'jobs': const []});

  @override
  Future<Response> listImportItemsBatch(
    List<String> jobIds, {
    String? status,
    bool includeArchived = false,
  }) async =>
      _resp({'items': const []});

  @override
  Future<Response> listParserBatches({
    bool activeOnly = false,
    int limit = 20,
  }) async =>
      _resp({'batches': const []});

  @override
  Future<Response> getImportItemsSeeAllCount() async =>
      _resp({'archived': 0, 'read_and_old_completed': 0, 'total': 0});

  @override
  Future<Response> getActivitiesSeeAllCount() async => _resp({'total': 0});

  @override
  Future<Response> getUnreadActivityCount() async =>
      _resp({'unread': 0, 'imports_actionable': 0});

  @override
  Future<Response> markAllActivitiesRead() async => _resp({'updated': 0});
}

void _register() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(_FakeApiClient());
  if (gi.isRegistered<ActivityReadProvider>()) {
    gi.unregister<ActivityReadProvider>();
  }
  gi.registerLazySingleton<ActivityReadProvider>(
    () => ActivityReadProvider(gi<ApiClient>()),
  );
  if (!gi.isRegistered<BatchParserService>()) {
    gi.registerLazySingleton<BatchParserService>(() => BatchParserService());
  }
}

Widget _wrap(Widget child) =>
    ProviderScope(child: MaterialApp(home: child));
