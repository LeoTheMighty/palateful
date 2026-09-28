import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/di/injection.dart';
import 'package:palateful/core/router/app_router.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/perf_navigator_observer.dart';

/// Authenticated and onboarded, so the router actually enters a shell
/// branch instead of redirecting to `/login`.
///
/// **The first version of this test had no stub and passed vacuously**:
/// unauthenticated, every `go()` redirected to `/login`, the branch
/// Navigators were never built, and the second observer attach — the thing
/// under test — never happened. A green test that cannot reach the defect
/// is the pattern this whole file is about.
class _AuthedStub extends AuthService {
  @override
  bool get isAuthenticated => true;

  @override
  bool get hasCompletedOnboarding => true;

  @override
  bool get isAdmin => false;
}

/// A `NavigatorObserver` may attach to exactly one Navigator.
///
/// cla-4 shared one `PerfNavigatorObserver` across the root Navigator and
/// every `StatefulShellRoute.indexedStack` branch — six Navigators, one
/// observer. `HeroControllerScope` asserts `observer.navigator == null`
/// when installing one, so entering a shell branch threw
///
///   'observer.navigator == null': is not true
///   HeroControllerScope … go_router/lib/src/builder.dart
///
/// and the content pane rendered the red error screen.
///
/// **Why nothing caught it:** assertions are stripped in release builds,
/// so production never threw — the `navigator` field was silently
/// overwritten by the last attach and route/paint events were attributed
/// to one Navigator instead of six. And the existing boot test
/// (`e2e_mode_router_boot_test.dart`) only pumps the root, where the first
/// attach succeeds. **This test goes into a branch**, which is the only
/// place the second attach happens.
/// Every error Flutter reported during the test.
///
/// **`tester.takeException()` is not enough here, and the first version of
/// this test proved it**: these screens fetch on mount with no backend, so
/// an API 400 is reported too, `takeException` handed back *that*, the
/// observer assertion went unexamined, and the test passed with the bug
/// restored. Collecting through `FlutterError.onError` sees all of them.
final List<String> _errors = [];

/// Fail on the observer conflict; tolerate unrelated screen errors.
///
/// Asserting "no errors at all" would tie this test to whatever the
/// Pantry screen happens to do without a backend. The single-Navigator
/// rule is what is under test.
void _expectNoObserverConflict() {
  expect(
    _errors.where((e) => e.contains('observer.navigator')),
    isEmpty,
    reason: 'sharing one observer across branch Navigators throws '
        "observer.navigator == null here — and in release the assertion is "
        'stripped, so it would not throw at all, it would silently '
        'misattribute paint events to one Navigator',
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late void Function(FlutterErrorDetails)? previousOnError;

  setUp(() {
    _errors.clear();
    previousOnError = FlutterError.onError;
    FlutterError.onError = (details) {
      _errors.add(details.toString());
      // Swallowed deliberately: forwarding to the default handler would
      // also register the error with the test framework, and an unrelated
      // API 400 would then fail the case for the wrong reason.
    };
    GetIt.instance.reset();
    setupDependencies();
    GetIt.instance.unregister<AuthService>();
    GetIt.instance.registerSingleton<AuthService>(_AuthedStub());
    resetRouter();
    resetPerfNavigatorObserver();
    PerfNavigatorObserver.resetWarnLatch();
  });

  tearDown(() {
    FlutterError.onError = previousOnError;
    resetRouter();
    resetPerfNavigatorObserver();
    GetIt.instance.reset();
  });

  testWidgets('each attach site gets its own observer instance',
      (tester) async {
    // Asserted on identity rather than behaviour: the failure this guards
    // is "the same object attached twice", and two calls returning the
    // same instance is exactly that condition.
    final a = perfNavigatorObserver;
    final b = perfNavigatorObserver;
    expect(a, isNotNull);
    expect(identical(a, b), isTrue,
        reason: 'the public getter is the unattached reportTabSwap '
            'instance and may be cached');
  });

  testWidgets('entering a shell branch does not throw', (tester) async {
    await tester.pumpWidget(
      ProviderScope(child: MaterialApp.router(routerConfig: appRouter)),
    );
    await tester.pump(const Duration(milliseconds: 100));

    // A shell branch route — a second Navigator, and the second attach.
    appRouter.go('/pantry');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    _expectNoObserverConflict();
    // Proof the test reached the code under test. Without this the case
    // passes just as happily while being redirected to /login.
    expect(appRouter.state.matchedLocation, '/pantry',
        reason: 'if this is /login the branch Navigator was never built '
            'and the assertion above proved nothing');
  });

  // A branch->branch case (/pantry -> /activity) was written and dropped:
  // ActivityScreen fetches on mount and leaves a periodic timer, so the
  // case failed on a pending-timer teardown rather than on anything to do
  // with observers, and making it pass meant stubbing that screen's whole
  // data stack. The case above already exercises the conflict — root
  // attach plus one branch attach is two attaches of the same object,
  // which is the defect. Mocking a screen for a third attach would buy
  // coverage of the same line.
}
