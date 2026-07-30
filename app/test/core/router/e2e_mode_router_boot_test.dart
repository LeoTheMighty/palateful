import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/di/injection.dart';
import 'package:palateful/core/router/app_router.dart';
import 'package:palateful/core/services/client_latency_ingest.dart';
import 'package:palateful/core/services/perf_navigator_observer.dart';

/// e2egetit regression suite.
///
/// Under `--dart-define=E2E_MODE=true` `main()` deliberately skips
/// `_bootstrapClientLatencyIngest()`, so `ClientLatencyIngest` is never
/// registered with GetIt. The router's `PerfNavigatorObserver` used to
/// resolve it unconditionally from a post-frame callback, which threw
///
///   Bad state: GetIt: Object/factory with type ClientLatencyIngest is
///   not registered inside GetIt.
///
/// on the very first frame — the router never finished building and no
/// driver test could find a single widget.
///
/// The same hole exists outside E2E: the bootstrap is `unawaited`, so a
/// route push that lands before the `PackageInfo.fromPlatform()` probe
/// resolves hits an empty GetIt too. Both cases are covered here by
/// simply never registering the singleton.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    GetIt.instance.reset();
    setupDependencies();
    // Mirror the E2E_MODE boot path: everything wired *except* the
    // client-latency pipeline.
    expect(GetIt.instance.isRegistered<ClientLatencyIngest>(), isFalse);
    resetRouter();
    resetPerfNavigatorObserver();
  });

  tearDown(() {
    resetRouter();
    resetPerfNavigatorObserver();
    GetIt.instance.reset();
  });

  testWidgets('router boots without ClientLatencyIngest registered',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(child: MaterialApp.router(routerConfig: appRouter)),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(tester.takeException(), isNull);
    // The first route actually rendered rather than dying mid-frame.
    expect(find.byType(Scaffold), findsWidgets);
  });

  testWidgets('perfNavigatorObserver is usable when ingest is absent',
      (tester) async {
    // `ScaffoldWithBottomNav` calls this on every bottom-tab swap.
    final observer = perfNavigatorObserver;
    expect(observer, isNotNull);
    observer!.reportTabSwap('/home');
    expect(tester.takeException(), isNull);
  });

  testWidgets('observer no-ops when its resolver yields null',
      (tester) async {
    final observer = PerfNavigatorObserver(
      ingestResolver: () => null,
      routePathResolver: () => '/home',
    );

    await tester.pumpWidget(MaterialApp(
      navigatorObservers: [observer],
      home: const Scaffold(body: Text('Home')),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(tester.takeException(), isNull);
    expect(find.text('Home'), findsOneWidget);
  });
}
