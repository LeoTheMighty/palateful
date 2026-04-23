/// Shared per-screen perf-audit test scaffold.
///
/// Each per-screen test follows this shape:
///
/// ```dart
/// late _PerfAuditScreenHarness h;
///
/// setUp(() { h = setUpPerfAuditScreen(); });
/// tearDown(() { h.dispose(); });
///
/// test('screen X cold-start fires the expected GETs', () async {
///   await h.container.read(someTopLevelProvider.future);
///   expect(h.counts['GET /v1/...'], 1);
///   h.emitCsv();  // AC4: per-endpoint CSV for eyeballing / budget capture
/// });
/// ```
///
/// Why provider-level instead of `app.main()` + widget pump:
///   1. `app.main()` runs dotenv / Firebase / push-notif init which is
///      wrong shape for a `flutter-tester` target.
///   2. The perf budget's contract is "how many GETs does this screen's
///      data layer fire on cold start" — that's what a Riverpod provider
///      read measures. UI taps don't add to the cold-start budget;
///      separate tests cover interaction paths where relevant.
///   3. Fast (<1s per test) + hermetic — no HttpClient, no platform
///      channels, no flaky widget-tree settling.
///
/// The scope divergence from the epic text is called out in
/// `ptd-2-perf-audit-home.md`.
library;

import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:palateful/core/di/injection.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_service.dart';
import 'package:palateful/features/recipes/services/cooking_log_service.dart';
import 'package:palateful/features/recipes/services/recipe_service.dart';

import 'harness.dart';

/// Screen-harness bundle returned by [setUpPerfAuditScreen]. Owns the
/// ProviderContainer + the request counter.
class PerfAuditScreenHarness {
  PerfAuditScreenHarness({
    required this.container,
    required this.counter,
    required this.apiClient,
  });

  final ProviderContainer container;
  final PerfAuditRequestCounter counter;
  final ApiClient apiClient;

  Map<String, int> get counts => counter.countsByEndpoint();
  int get total => counter.total;

  /// AC4: emit observed counts as CSV. The ptd-4 bin/perf-audit
  /// collects these prints, merges across screens, and diffs against
  /// the budget yaml. Sorted for deterministic output.
  void emitCsv({String screenName = 'unknown'}) {
    final sorted = counts.entries.toList()
      ..sort((a, b) => a.key.compareTo(b.key));
    for (final entry in sorted) {
      // Format: screen,endpoint,count
      // Wrapped in a sentinel so bin/perf-audit can grep the test log
      // without confusing the output for user-facing prints.
      // ignore: avoid_print
      print('PERF_AUDIT_CSV,$screenName,${entry.key},${entry.value}');
    }
  }

  void dispose() {
    container.dispose();
    // Leave getIt registrations alone — the next setUp will reassign
    // them. Synchronous reset is unreliable because getIt.reset() is
    // async.
  }
}

/// Install the fresh harness: reset getIt, register a mocked ApiClient +
/// the service layer the providers rely on, attach the mock adapter +
/// counter, return a fresh ProviderContainer.
PerfAuditScreenHarness setUpPerfAuditScreen({String? fixtureDir}) {
  // getIt.reset() is async — calling it synchronously from setUp races
  // the next registerSingleton. Use allowReassignment so repeat calls
  // just replace the singleton, and reset individual lazy entries we
  // own below.
  getIt.allowReassignment = true;

  // `Environment` getters read `dotenv.env`; absent load = NotInitializedError.
  // `testLoad` seeds the map without touching the filesystem. Only the
  // keys the construction path reads need to be present; the mock
  // adapter intercepts every outbound request so `API_BASE_URL` is
  // irrelevant at runtime — this is just to keep the Dio constructor
  // from throwing.
  if (!dotenv.isInitialized) {
    dotenv.loadFromString(envString: '''
API_BASE_URL=http://perf-audit.mock
AUTH0_DOMAIN=perf-audit.example.com
AUTH0_CLIENT_ID=perf-audit-client
AUTH0_AUDIENCE=https://perf-audit.example.com
''');
  }

  // Core services — same shape as setupDependencies() but without the
  // side-effectful plugins (Firebase, HomeWidget, push notif).
  // AuthService's constructor reads dotenv for AUTH0_DOMAIN /
  // AUTH0_CLIENT_ID — seeded above — and then instantiates an Auth0
  // handle with those placeholder strings. No network calls happen at
  // construction time, so it's safe in flutter-tester.
  getIt.registerSingleton<AuthService>(AuthService());

  final apiClient = ApiClient();
  apiClient.setAuthToken('e2e-test-token');
  getIt.registerSingleton<ApiClient>(apiClient);

  // Service layer (lazy — providers instantiate on first .read()).
  // Re-register on every setUp so each test gets a service bound to
  // the *current* fresh apiClient, not a leftover from a prior test.
  if (getIt.isRegistered<RecipeBookService>()) {
    getIt.resetLazySingleton<RecipeBookService>();
  } else {
    getIt.registerLazySingleton<RecipeBookService>(
      () => RecipeBookService(getIt<ApiClient>()),
    );
  }
  if (getIt.isRegistered<MealService>()) {
    getIt.resetLazySingleton<MealService>();
  } else {
    getIt.registerLazySingleton<MealService>(
      () => MealService(getIt<ApiClient>()),
    );
  }
  if (getIt.isRegistered<RecipeService>()) {
    getIt.resetLazySingleton<RecipeService>();
  } else {
    getIt.registerLazySingleton<RecipeService>(
      () => RecipeService(getIt<ApiClient>()),
    );
  }
  if (getIt.isRegistered<CookingLogService>()) {
    getIt.resetLazySingleton<CookingLogService>();
  } else {
    getIt.registerLazySingleton<CookingLogService>(
      () => CookingLogService(getIt<ApiClient>()),
    );
  }

  final harness = installPerfAuditHarness(apiClient.dio, fixtureDir: fixtureDir);
  final container = ProviderContainer();

  return PerfAuditScreenHarness(
    container: container,
    counter: harness.counter,
    apiClient: apiClient,
  );
}

