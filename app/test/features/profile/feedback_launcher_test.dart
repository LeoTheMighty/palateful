// E-8 (P1): feedback sends from wherever the user is.
// _devx/workstreams/shake-to-report/expectations.md E-8; PRD FR-9; plan
// shk102 (T2.5).
//
// Two halves:
//   - the app root: the REAL `PalatefulApp` is pumped signed in, so a test
//     fails if the flush calls in `main.dart` are removed, not only if the
//     launcher breaks. Profile is a lazily built tab branch, so booting at
//     `/` never builds it — that is how "0 builds of Profile" is observed.
//   - Profile's tile and flush, through the same real app, checked on the
//     wire (the POST body), which is what the server sees.
// Plus unit tests of the launcher with its dependencies injected.
//
// The app-boot recipe (GetIt reset awaited, fake push service, the provider
// overrides of `main()`, mocked sharing-intent channels, an HTTP adapter
// that leaves unknown requests pending) is design research RQ13's.

import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart'
    show AuthorizationStatus;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:palateful/core/di/injection.dart';
import 'package:palateful/core/router/app_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/error_reporter.dart';
import 'package:palateful/core/services/perf_flags_service.dart';
import 'package:palateful/core/services/push_notification_service.dart';
import 'package:palateful/features/home/recipe_list_view.dart';
import 'package:palateful/features/profile/profile_screen.dart';
import 'package:palateful/features/profile/services/feedback_cache_service.dart';
import 'package:palateful/features/profile/services/feedback_launcher.dart';
import 'package:palateful/features/profile/services/profile_service.dart';
import 'package:palateful/features/profile/widgets/feedback_sheet.dart';
import 'package:palateful/main.dart';
import 'package:palateful/providers/theme_mode_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

// ---------------------------------------------------------------------------
// Fakes
// ---------------------------------------------------------------------------

const _feedbackPath = '/v1/users/me/feedback';

/// Answers `/v1/users/me` and the feedback POST; every other request stays
/// pending (answering them instantly makes retry loops spin forever inside
/// the test clock — RQ13).
class _FakeHttp implements HttpClientAdapter {
  final List<RequestOptions> requests = [];

  List<Map<String, dynamic>> get feedbackPosts => [
        for (final r in requests)
          if (r.method == 'POST' && r.path.endsWith(_feedbackPath))
            Map<String, dynamic>.from(
                (r.data is String ? jsonDecode(r.data as String) : r.data)
                    as Map),
      ];

  @override
  Future<ResponseBody> fetch(RequestOptions o, Stream<Uint8List>? body,
      Future<void>? cancel) async {
    requests.add(o);
    Object? json;
    var status = 200;
    if (o.method == 'GET' && o.path.endsWith('/v1/users/me')) {
      json = {
        'id': '34000000-0000-0000-0000-000000000001',
        'name': 'Launcher User',
        'email': 'launcher@example.test',
        'username': 'launcher',
        'is_admin': false,
        'has_completed_onboarding': true,
      };
    } else if (o.method == 'POST' && o.path.endsWith(_feedbackPath)) {
      status = 201;
      json = {'id': '34000000-0000-0000-0000-0000000000f1'};
    } else {
      return Completer<ResponseBody>().future;
    }
    return ResponseBody.fromString(jsonEncode(json), status, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    });
  }

  @override
  void close({bool force = false}) {}
}

/// The real service reads `FirebaseMessaging.instance` in a field
/// initializer, so it cannot exist in a test.
class _FakePush implements PushNotificationService {
  @override
  void setNavigatorKey(GlobalKey<NavigatorState> key) {}
  @override
  Future<AuthorizationStatus> ensureRegistered({bool autoPrompt = false}) async =>
      AuthorizationStatus.notDetermined;
  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

/// For the unit tests: records submissions, optionally failing some.
class _RecordingApi extends ApiClient {
  _RecordingApi({this.failBodies = const {}, this.gate});

  final Set<String> failBodies;

  /// When set, every submission waits on it, so a test can hold a flush
  /// open and make a second call while the first is running.
  final Completer<void>? gate;
  final List<Map<String, dynamic>> calls = [];

  @override
  Future<Response> submitFeedback({
    required String body,
    String? category,
    Map<String, dynamic>? context,
  }) async {
    calls.add({'body': body, 'category': category, 'context': context});
    if (gate != null) await gate!.future;
    if (failBodies.contains(body)) {
      throw DioException(
        requestOptions: RequestOptions(path: _feedbackPath),
        response: Response(
            requestOptions: RequestOptions(path: _feedbackPath),
            statusCode: 422),
        type: DioExceptionType.badResponse,
      );
    }
    return Response(
      requestOptions: RequestOptions(path: _feedbackPath),
      statusCode: 201,
      data: {'id': 'feedback-1'},
    );
  }
}

// ---------------------------------------------------------------------------
// The real app, booted signed in.
// ---------------------------------------------------------------------------

Future<void> _resetWorld() async {
  GoogleFonts.config.allowRuntimeFetching = false;
  SharedPreferences.setMockInitialValues({});
  await GetIt.instance.reset();
  setupDependencies();
  GetIt.instance.unregister<PushNotificationService>();
  GetIt.instance.registerSingleton<PushNotificationService>(_FakePush());
  resetRouter();
  resetPerfNavigatorObserver();
}

Future<void> _tearDownWorld() async {
  if (GetIt.instance.isRegistered<PerfFlagsService>()) {
    GetIt.instance<PerfFlagsService>().dispose();
  }
  resetRouter();
  resetPerfNavigatorObserver();
  await GetIt.instance.reset();
}

class _App {
  _App(this.tester, this.http);
  final WidgetTester tester;
  final _FakeHttp http;

  AuthService get auth => GetIt.instance<AuthService>();
  String get location => appRouter.routerDelegate.currentConfiguration.uri.path;

  /// Profile's State, built or not. `skipOffstage: false` so a Profile
  /// branch kept alive behind another tab still counts.
  int get profileBuilds =>
      find.byType(ProfileScreen, skipOffstage: false).evaluate().length;

  Future<void> settle([int rounds = 10]) async {
    for (var i = 0; i < rounds; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
  }

  /// A real resume: the app leaves the foreground and comes back.
  Future<void> resume() async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await settle();
  }

  Future<void> close() async {
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 10));
  }
}

/// Boots `PalatefulApp` the way `main()` does. Sends NO lifecycle event, so
/// the cold-start test sees only what `initState` does.
Future<_App> _boot(
  WidgetTester tester, {
  String startRoute = '/',
  bool online = true,
}) async {
  final http = _FakeHttp();
  final m = tester.binding.defaultBinaryMessenger;
  m.setMockMethodCallHandler(
      const MethodChannel('receive_sharing_intent/messages'), (call) async => null);
  m.setMockStreamHandler(const EventChannel('receive_sharing_intent/events-media'),
      MockStreamHandler.inline(onListen: (_, _) {}));
  m.setMockMethodCallHandler(
      const MethodChannel('dev.fluttercommunity.plus/connectivity'),
      (call) async => call.method == 'check'
          ? <String>[online ? 'wifi' : 'none']
          : null);
  m.setMockStreamHandler(
      const EventChannel('dev.fluttercommunity.plus/connectivity_status'),
      MockStreamHandler.inline(onListen: (_, _) {}));

  final api = GetIt.instance<ApiClient>();
  api.dio.httpClientAdapter = http;
  api.setAuthToken('launcher-token');
  final auth = GetIt.instance<AuthService>();
  auth.setAccessToken('launcher-token');
  auth.updateOnboardingState(hasCompletedOnboarding: true);
  auth.updateAdminState(false);

  tester.binding.platformDispatcher.defaultRouteNameTestValue = startRoute;
  await tester.pumpWidget(ProviderScope(overrides: [
    themeModeProvider.overrideWith(() => ThemeModeNotifier(ThemeMode.light)),
    fontStyleProvider.overrideWith(() => FontStyleNotifier(FontStyle.classic)),
    recipeListViewProvider
        .overrideWith(() => RecipeListViewNotifier(RecipeListView.grid)),
  ], child: const PalatefulApp()));
  final app = _App(tester, http);
  await app.settle(3);
  return app;
}

/// Boots the app, runs [body], and always unmounts it. A failed expectation
/// must not leave `PalatefulApp` mounted: its `dispose` would then run in the
/// next test, after GetIt was reset, and fail that test for no reason of its
/// own (seen while proving these tests against broken code).
Future<void> _withApp(
  WidgetTester tester,
  Future<void> Function(_App app) body, {
  bool online = true,
}) async {
  final app = await _boot(tester, online: online);
  try {
    await body(app);
  } finally {
    await app.close();
  }
}

/// What a shake on another screen would have queued while offline.
Future<void> _queueFromElsewhere(String body) => FeedbackCacheService()
    .queueFeedback(body: body, category: 'bug', context: {
      'platform': 'android',
      'route': '/recipes',
      'trigger': 'shake',
    });

Future<int> _queueLength() async =>
    (await FeedbackCacheService().getPendingFeedback()).length;

Future<void> _openProfileTile(_App app) async {
  appRouter.go('/profile');
  await app.settle();
  final tile = find.text('Send Feedback');
  expect(tile, findsOneWidget, reason: "Profile shows no 'Send Feedback' tile");
  await app.tester.ensureVisible(tile);
  await app.tester.pump(const Duration(milliseconds: 300));
  await app.tester.tap(tile);
  await app.settle();
}

Future<void> _submitSheet(_App app, String body) async {
  await app.tester.enterText(find.byKey(const Key('feedback_body_field')), body);
  await app.tester.pump();
  await app.tester.tap(find.byKey(const Key('feedback_send_button')));
  await app.settle();
}

// ---------------------------------------------------------------------------

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('E-8 app root — the queue flushes whichever screen is mounted', () {
    setUp(_resetWorld);
    tearDown(_tearDownWorld);

    testWidgets(
        'cold start: an item queued before launch sends once, signed in, '
        'with no resume event and Profile never built',
        timeout: const Timeout(Duration(seconds: 60)), (tester) async {
      await _queueFromElsewhere('queued before launch');
      expect(await _queueLength(), 1);

      await _withApp(tester, (app) async {
        await app.settle();

        final posts = app.http.feedbackPosts;
        expect(posts.length, 1,
            reason: 'a cold start with one queued item made ${posts.length} '
                'feedback POSTs; the app root does not flush at startup');
        expect(posts.single['body'], 'queued before launch');
        expect(posts.single['context'],
            {'platform': 'android', 'route': '/recipes', 'trigger': 'shake'},
            reason: 'the flush must send the context the item was queued with');
        expect(await _queueLength(), 0);
        expect(app.location, '/');
        expect(app.profileBuilds, 0, reason: 'Profile was built');
      });
    });

    testWidgets(
        'resume: an item queued while running sends in one POST on resume, '
        'with Profile never built',
        timeout: const Timeout(Duration(seconds: 60)), (tester) async {
      await _withApp(tester, (app) async {
        await _queueFromElsewhere('queued while offline');
        await app.settle();
        // Nothing sends it until something flushes: the startup flush ran on an
        // empty queue, so the POST below can only come from the resume.
        expect(app.http.feedbackPosts, isEmpty);
        expect(await _queueLength(), 1);

        await app.resume();

        final posts = app.http.feedbackPosts;
        expect(posts.length, 1,
            reason: 'a resume with one queued item made ${posts.length} '
                'feedback POSTs; the app root does not flush on resume');
        expect(posts.single['body'], 'queued while offline');
        expect(await _queueLength(), 0);
        expect(app.location, '/');
        expect(app.profileBuilds, 0, reason: 'Profile was built');
      });
    });

    testWidgets('resume while offline sends nothing and keeps the item',
        timeout: const Timeout(Duration(seconds: 60)), (tester) async {
      await _withApp(tester, (app) async {
        await _queueFromElsewhere('still offline');
        await app.resume();

        expect(app.http.feedbackPosts, isEmpty);
        expect(await _queueLength(), 1);
      }, online: false);
    });

    testWidgets('resume while signed out sends nothing and keeps the item',
        timeout: const Timeout(Duration(seconds: 60)), (tester) async {
      await _withApp(tester, (app) async {
        await _queueFromElsewhere('signed out');
        app.auth.setAccessToken('');
        expect(app.auth.isAuthenticated, isFalse);
        await app.settle();
        await app.resume();

        expect(app.http.feedbackPosts, isEmpty,
            reason: 'the app root flushed with no session');
        expect(await _queueLength(), 1);
      });
    });
  });

  group("E-8 Profile — looks and behaves as before, through the launcher", () {
    setUp(_resetWorld);
    tearDown(_tearDownWorld);

    testWidgets(
        "Profile's tile opens one sheet whose context carries trigger profile "
        'and route /profile',
        timeout: const Timeout(Duration(seconds: 60)), (tester) async {
      await _withApp(tester, (app) async {
        await _openProfileTile(app);

        expect(find.byType(FeedbackSheet), findsOneWidget,
            reason: "tapping Profile's tile did not open exactly one sheet");
        final sheet = tester.widget<FeedbackSheet>(find.byType(FeedbackSheet));
        expect(sheet.trigger, FeedbackTrigger.profile);
        expect(sheet.currentRoute, '/profile');
        expect(sheet.isOffline, isFalse);

        await _submitSheet(app, 'the tile still works');

        final posts = app.http.feedbackPosts;
        expect(posts.length, 1);
        expect(posts.single['body'], 'the tile still works');
        // On the wire: what the server's FeedbackContext validates.
        expect(posts.single['context'],
            {'platform': 'android', 'route': '/profile', 'trigger': 'profile'});
        expect(find.byType(FeedbackSheet), findsNothing,
            reason: 'the sheet did not close after sending');
        expect(find.text('Thanks — feedback sent'), findsOneWidget);
        expect(app.location, '/profile');
      });
    });

    testWidgets("Profile's tile offline queues instead of sending, as before",
        timeout: const Timeout(Duration(seconds: 60)), (tester) async {
      await _withApp(tester, (app) async {
        await _openProfileTile(app);

        final sheet = tester.widget<FeedbackSheet>(find.byType(FeedbackSheet));
        expect(sheet.isOffline, isTrue);
        await _submitSheet(app, 'offline from profile');

        expect(app.http.feedbackPosts, isEmpty);
        final pending = await FeedbackCacheService().getPendingFeedback();
        expect(pending, hasLength(1));
        expect(pending.single['context'],
            {'platform': 'android', 'route': '/profile', 'trigger': 'profile'});
        expect(find.text("Saved — we'll send it when you're back online."),
            findsOneWidget);
      }, online: false);
    });

    testWidgets(
        'on Profile, a resume sends a queued item exactly once and Profile '
        'still announces it',
        timeout: const Timeout(Duration(seconds: 60)), (tester) async {
      await _withApp(tester, (app) async {
        appRouter.go('/profile');
        await app.settle();
        // The finder the other tests rely on for "never built" can see Profile.
        expect(app.profileBuilds, 1);

        await _queueFromElsewhere('sent on resume');
        await app.resume();

        // Profile and the app root both observe this resume. Two independent
        // flushes would each read the queue and send the item twice.
        final posts = app.http.feedbackPosts;
        expect(posts.length, 1,
            reason: 'one queued item made ${posts.length} POSTs on one resume');
        expect(await _queueLength(), 0);
        expect(find.text('Sent queued feedback'), findsOneWidget,
            reason: 'Profile no longer announces what its flush sent');
      });
    });
  });

  group('FeedbackLauncher', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
      ErrorReporter.testReportHook = null;
    });
    tearDown(() {
      ErrorReporter.testReportHook = null;
      debugDefaultTargetPlatformOverride = null;
    });

    FeedbackLauncher launcher(_RecordingApi api, {bool offline = false}) =>
        FeedbackLauncher(
          isOffline: () async => offline,
          apiClient: () => api,
          profileService: () => ProfileService(api),
        );

    test('platform is web on web, whatever OS the browser reports', () {
      for (final os in TargetPlatform.values) {
        expect(feedbackPlatform(isWeb: true, platform: os), 'web',
            reason: 'web read as $os');
      }
    });

    test('platform off web comes from defaultTargetPlatform', () {
      expect(feedbackPlatform(isWeb: false, platform: TargetPlatform.iOS), 'ios');
      expect(feedbackPlatform(isWeb: false, platform: TargetPlatform.android),
          'android');
      expect(feedbackPlatform(isWeb: false, platform: TargetPlatform.macOS), isNull);
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
      expect(feedbackPlatform(isWeb: false), 'ios');
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      expect(feedbackPlatform(isWeb: false), 'android');
    });

    test('the route is sent without its query string or fragment', () {
      expect(routePath('/profile'), '/profile');
      expect(routePath('/recipes/abc?tab=notes'), '/recipes/abc');
      expect(routePath('/recipes/abc#step-3'), '/recipes/abc');
      expect(routePath('/search?q=a#b'), '/search');
    });

    testWidgets('open() passes route and trigger to the sheet', (tester) async {
      final api = _RecordingApi();
      final l = launcher(api);
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (ctx) => TextButton(
              onPressed: () => l.open(ctx,
                  trigger: FeedbackTrigger.shake, route: '/recipes/abc?tab=x'),
              child: const Text('open'),
            ),
          ),
        ),
      ));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      final sheet = tester.widget<FeedbackSheet>(find.byType(FeedbackSheet));
      expect(sheet.trigger, FeedbackTrigger.shake);
      expect(sheet.currentRoute, '/recipes/abc');

      await tester.enterText(find.byKey(const Key('feedback_body_field')), 'x');
      await tester.pump();
      await tester.tap(find.byKey(const Key('feedback_send_button')));
      await tester.pumpAndSettle();
      expect(api.calls.single['context'],
          containsPair('trigger', 'shake'));
      expect(api.calls.single['context'], containsPair('route', '/recipes/abc'));
    });

    test('a failed send stays queued and is reported; the rest send', () async {
      final reports = <String?>[];
      ErrorReporter.testReportHook =
          (e, st, {area, operation, extras, fatal = false}) =>
              reports.add('$area/$operation');
      final cache = FeedbackCacheService();
      await cache.queueFeedback(body: 'refused');
      await cache.queueFeedback(body: 'fine');
      final api = _RecordingApi(failBodies: {'refused'});

      final sent = await launcher(api).flushQueue();

      expect(sent, 1);
      expect(api.calls.map((c) => c['body']), ['refused', 'fine']);
      final pending = await cache.getPendingFeedback();
      expect(pending.map((e) => e['body']), ['refused']);
      expect(reports, ['feedback/flushQueue.submit'],
          reason: 'the failed send was swallowed, not reported');
    });

    test('a malformed queue entry is reported, and flushQueue does not throw',
        () async {
      final reports = <String?>[];
      ErrorReporter.testReportHook =
          (e, st, {area, operation, extras, fatal = false}) =>
              reports.add('$area/$operation');
      SharedPreferences.setMockInitialValues({
        'palateful_pending_feedback': jsonEncode([
          {'body': 42},
        ]),
      });

      expect(await launcher(_RecordingApi()).flushQueue(), 0);
      expect(reports, ['feedback/flushQueue']);
    });

    test('offline: nothing is sent and the queue is kept', () async {
      final cache = FeedbackCacheService();
      await cache.queueFeedback(body: 'wait');
      final api = _RecordingApi();

      expect(await launcher(api, offline: true).flushQueue(), 0);
      expect(api.calls, isEmpty);
      expect(await cache.hasPending(), isTrue);
    });

    test('concurrent flushes share one run; a later call runs again',
        () async {
      final cache = FeedbackCacheService();
      await cache.queueFeedback(body: 'once');
      final gate = Completer<void>();
      final api = _RecordingApi(gate: gate);
      final l = launcher(api);

      final first = l.flushQueue();
      // Let the first run reach the network before the second call lands.
      await pumpEventQueue();
      expect(api.calls, hasLength(1));
      final second = l.flushQueue();
      gate.complete();

      expect(await Future.wait([first, second]), [1, 1]);
      expect(api.calls, hasLength(1), reason: 'the item was sent twice');

      await cache.queueFeedback(body: 'later');
      expect(await l.flushQueue(), 1,
          reason: 'a finished flush left the launcher stuck on its result');
      expect(api.calls.map((c) => c['body']), ['once', 'later']);
    });
  });
}
