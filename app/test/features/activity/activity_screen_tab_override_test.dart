import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/activity_screen.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';
import 'package:palateful/features/activity/providers/activity_tab_provider.dart';
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

  testWidgets('a tab-less screen auto-switches on the FIRST resolved counts',
      (tester) async {
    // The cold-start affordance, which the fix must not break.
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

  testWidgets('and NOT on later ones — the guess is one-shot', (tester) async {
    // These listeners live as long as the screen, and the bottom-nav
    // instance lives as long as the process. Before the one-shot, a
    // notification arriving twenty minutes later threw a user mid-scroll
    // from Imports to Notifications.
    _register();
    await tester.pumpWidget(_wrap(const ActivityScreen()));
    await tester.pump();

    final read = GetIt.instance<ActivityReadProvider>();
    read.notificationsCount.value = 0;
    read.importsActionableCount.value = 5;
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(_selectedTab(tester), _imports, reason: 'first resolve applies');

    // Later traffic on the other side.
    read.notificationsCount.value = 9;
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(_selectedTab(tester), _imports,
        reason: 'a later count change must not move the tab under the user');
  });

  testWidgets(
      'a tab-less screen does not drag an explicit-tab screen with it '
      '(acttab1 — the reported bug)', (tester) async {
    _register();

    // Both mounted in one tree, sharing the ProviderScope — the shape the
    // shell's IndexedStack produces when /activity was already visited
    // before the strip's push. The tab-less one owns the count listeners.
    await tester.pumpWidget(_wrapBoth(
      const ActivityScreen(),
      const ActivityScreen(initialTab: 'imports'),
    ));
    await tester.pump();

    // The counts the reported case produces: a pending PARSER BATCH is not
    // an ImportItem, so imports_actionable is 0 and any notification at all
    // resolves to Notifications.
    final read = GetIt.instance<ActivityReadProvider>();
    read.notificationsCount.value = 1;
    read.importsActionableCount.value = 0;
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    final selected = _selectedTabs(tester);
    expect(selected.length, 2, reason: 'both screens really are mounted');
    expect(selected.last, _imports,
        reason: 'the screen routed with ?tab=imports keeps its tab');
  });

  testWidgets('the latch is session-wide, and that is the trade-off',
      (tester) async {
    // Deliberate consequence, pinned so it is a decision and not a
    // surprise: once something chooses a tab on purpose, the count-based
    // guess stops firing for the session — including for a screen that
    // never had a `?tab=` of its own, because the provider is shared.
    //
    // Asserted on the PROVIDER, not on the second screen's TabBar: every
    // mounted screen follows the provider by design, so the tab-less
    // screen moving to Imports here is the shared state working, not the
    // guess winning. What the latch changes is whether the guess can write
    // at all.
    _register();
    await tester.pumpWidget(_wrapBoth(
      const ActivityScreen(initialTab: 'imports'),
      const ActivityScreen(),
    ));
    await tester.pump();

    final container = ProviderScope.containerOf(
      tester.element(find.byType(ActivityScreen).first),
    );
    expect(container.read(activityTabProvider), ActivityTab.imports);

    // Counts that strongly favour the other side. Pre-fix the tab-less
    // screen's listener writes Notifications here and both screens move.
    final read = GetIt.instance<ActivityReadProvider>();
    read.notificationsCount.value = 9;
    read.importsActionableCount.value = 0;
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(container.read(activityTabProvider), ActivityTab.imports,
        reason: 'the guess cannot overwrite a deliberate choice');
    expect(_selectedTabs(tester).first, _imports,
        reason: 'and the explicitly-routed screen is still showing it');
  });

  testWidgets('an UNRECOGNISED ?tab= does not latch anything',
      (tester) async {
    // `?tab=improts` from a truncated deep link or a stale push payload is
    // not a deliberate request. `fromWire` maps it to notifications, so it
    // used to latch the session there permanently — the reported bug,
    // re-entered through the front door.
    _register();
    await tester.pumpWidget(_wrapBoth(
      const ActivityScreen(initialTab: 'improts'),
      const ActivityScreen(),
    ));
    await tester.pump();

    final read = GetIt.instance<ActivityReadProvider>();
    read.notificationsCount.value = 0;
    read.importsActionableCount.value = 5;
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(_selectedTabs(tester).last, _imports,
        reason: 'the count-based guess still works after a typo tab');
  });

  testWidgets('reset() drops the latch, as sign-out does', (tester) async {
    _register();
    await tester.pumpWidget(_wrap(const ActivityScreen(initialTab: 'imports')));
    await tester.pump();

    final container = ProviderScope.containerOf(
      tester.element(find.byType(ActivityScreen)),
    );
    expect(container.read(activityTabProvider), ActivityTab.imports);

    container.read(activityTabProvider.notifier).reset();
    await tester.pump();

    expect(container.read(activityTabProvider), ActivityTab.notifications,
        reason: 'the next user starts from the cold-start default');
    // And the guess works again for them.
    container.read(activityTabProvider.notifier).suggestTab(ActivityTab.imports);
    expect(container.read(activityTabProvider), ActivityTab.imports,
        reason: 'suggestTab is no longer latched out');
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

/// Two ActivityScreens in one ProviderScope, mounted in the given order.
/// Keys force distinct Elements: two `ActivityScreen()`s with null keys and
/// the same runtimeType would have their State REUSED across a re-pump,
/// which is how an earlier draft of these tests ended up asserting nothing.
Widget _wrapBoth(Widget first, Widget second) => ProviderScope(
      child: MaterialApp(
        home: Column(
          children: [
            Expanded(child: KeyedSubtree(key: const ValueKey('a'), child: first)),
            Expanded(child: KeyedSubtree(key: const ValueKey('b'), child: second)),
          ],
        ),
      ),
    );
