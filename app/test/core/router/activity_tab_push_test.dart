import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

/// acttab1, first task — SETTLED, and it rules a suspect out.
///
/// The question: does `context.push('/activity?tab=imports')` from another
/// shell branch build a FRESH screen (so `initialTab` is honoured) or reuse
/// the Activity branch's existing one (so `initialTab` is ignored outright,
/// since `ActivityScreen` has no `didUpdateWidget`)?
///
/// **Measured: fresh.** The route builder is called with `tab=imports` and
/// the new screen renders, even when the branch had already been visited
/// without a `?tab=`. Recorded build sequence for that case:
/// `[null, imports, null]` — the new route builds with the tab, and the
/// earlier tab-less route rebuilds behind it in the IndexedStack, which is
/// why "the last build" is a misleading thing to assert on.
///
/// So router reuse is NOT the bug. Whatever sends Leo to Notifications
/// happens after construction, inside `ActivityScreen` and the app-scoped
/// `activityTabProvider` — which is what `activity_screen_tab_override_test`
/// goes after.
///
/// These tests assert go_router's behaviour, not Palateful's, on a minimal
/// `StatefulShellRoute.indexedStack` mirroring `app_router.dart`'s shape
/// without the app's DI. If go_router changes here, the real fix's premise
/// changes with it, and this file is where that surfaces.
void main() {
  late List<String?> activityBuilds;
  late int activityBuildCount;

  Widget buildApp() {
    activityBuilds = [];
    activityBuildCount = 0;

    final homeKey = GlobalKey<NavigatorState>();
    final activityKey = GlobalKey<NavigatorState>();

    final router = GoRouter(
      initialLocation: '/',
      routes: [
        StatefulShellRoute.indexedStack(
          builder: (context, state, shell) => Scaffold(body: shell),
          branches: [
            StatefulShellBranch(
              navigatorKey: homeKey,
              routes: [
                GoRoute(
                  path: '/',
                  builder: (_, _) => const Text('HOME'),
                ),
              ],
            ),
            StatefulShellBranch(
              navigatorKey: activityKey,
              routes: [
                GoRoute(
                  path: '/activity',
                  builder: (_, state) {
                    final tab = state.uri.queryParameters['tab'];
                    activityBuilds.add(tab);
                    activityBuildCount++;
                    return _ActivityProbe(initialTab: tab);
                  },
                ),
              ],
            ),
          ],
        ),
      ],
    );

    return MaterialApp.router(routerConfig: router);
  }

  testWidgets('pushing /activity?tab=imports from another branch builds the '
      'Activity route with the tab in hand', (tester) async {
    await tester.pumpWidget(buildApp());
    await tester.pumpAndSettle();
    expect(find.text('HOME'), findsOneWidget);

    final context = tester.element(find.text('HOME'));
    context.push('/activity?tab=imports');
    await tester.pumpAndSettle();

    // Whatever go_router does about branch state, the route builder must at
    // least see the query parameter. If this fails, the bug is upstream of
    // ActivityScreen entirely.
    expect(activityBuilds, contains('imports'));
    expect(find.text('PROBE:imports'), findsOneWidget);
  });

  testWidgets('a push after the branch already rendered still delivers the '
      'new tab (fresh vs reused)', (tester) async {
    await tester.pumpWidget(buildApp());
    await tester.pumpAndSettle();

    // Visit Activity WITHOUT a tab first — the state the spec says is
    // load-bearing: an instance built with no `?tab=` is the one that
    // registers count listeners and can auto-switch.
    var context = tester.element(find.text('HOME'));
    context.push('/activity');
    await tester.pumpAndSettle();
    expect(find.text('PROBE:none'), findsOneWidget);
    final buildsAfterFirst = activityBuildCount;

    // Now push again WITH an explicit tab, as the Add Recipe strip does.
    context = tester.element(find.text('PROBE:none'));
    context.push('/activity?tab=imports');
    await tester.pumpAndSettle();

    // NOT `activityBuilds.last`: the tab-less route rebuilds behind the new
    // one inside the IndexedStack, so the last entry is null even though the
    // new route built correctly. Asserting on `.last` here is what made this
    // test first report "reused" when the truth is the opposite.
    expect(activityBuilds, contains('imports'),
        reason: 'the second push reaches the builder with its tab');
    expect(activityBuildCount, greaterThan(buildsAfterFirst),
        reason: 'a fresh build means initialTab is honoured; no new build '
            'would mean the widget is reused and initialTab ignored, which '
            'would be a different bug with a different fix');
    expect(find.text('PROBE:imports'), findsOneWidget,
        reason: 'and the freshly-built screen is the one on screen');
  });
}

/// Stands in for `ActivityScreen`, recording only what it was constructed
/// with. Deliberately dumb: this file is measuring the router, not the
/// screen's own tab logic.
class _ActivityProbe extends StatefulWidget {
  const _ActivityProbe({this.initialTab});

  final String? initialTab;

  @override
  State<_ActivityProbe> createState() => _ActivityProbeState();
}

class _ActivityProbeState extends State<_ActivityProbe> {
  late String _tab = widget.initialTab ?? 'none';

  @override
  Widget build(BuildContext context) => Text('PROBE:$_tab');
}
