// Shared harness for shake-to-report's P0 evals (plan f89791). Pinned by
// sha256 in ../lib/run_flutter_eval.sh: changing it is `devx revise`.
//
// It boots the REAL app root (`PalatefulApp`, app/lib/main.dart) in a widget
// test, signed in, and drives it from outside:
//   - motion arrives on sensors_plus's platform channels
//     (`dev.fluttercommunity.plus/sensors/user_accel` and `/accelerometer`,
//     payload [x, y, z, timestamp_us], PRD FR-2 / design RQ9);
//   - HTTP is a fake Dio adapter: `/v1/flags/perf` answers with the ring
//     under test, `/v1/users/me` with a user, `POST /v1/users/me/feedback`
//     is recorded, and every other request stays pending (answering them
//     instantly makes retry loops spin forever inside the test clock);
//   - it looks only at what a user would see: a prompt by its PRD copy
//     (FR-5), the existing `FeedbackSheet`, the router location.
// Nothing here imports code that does not exist on main today, so the evals
// compile and RUN on unbuilt code and fail on assertions, not on imports.
//
// Every eval file calls `registerHarnessControls()`: tests named
// `control: …` that must pass on unbuilt code. They prove the harness can
// boot the app, deliver motion, find a prompt-shaped snackbar and find the
// sheet. If one fails, the runner reports EVAL-BLIND (exit 3), never RED.

import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart' show AuthorizationStatus;
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
import 'package:palateful/core/services/perf_flags_service.dart';
import 'package:palateful/core/services/push_notification_service.dart';
import 'package:palateful/features/home/recipe_list_view.dart';
import 'package:palateful/features/profile/widgets/feedback_sheet.dart';
import 'package:palateful/main.dart';
import 'package:palateful/providers/theme_mode_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

// ---------------------------------------------------------------------------
// The contract the evals read, copied from the PRD (not from code).
// ---------------------------------------------------------------------------

/// FR-5 prompt copy.
const userPromptText = 'Send feedback?';
const userPromptAction = 'Report';
const adminPromptText = 'File a dev request?';
const adminPromptAction = 'Request';

/// FR-7: arq103's route (`AdminDevRequestNewScreen.routePath`).
const devRequestPath = '/admin/dev-requests/new';

/// FR-5: the prompt dismisses itself after this long.
const promptLifetime = Duration(seconds: 4);

/// FR-4: the recognizer ignores motion this long after a recognition.
const cooldown = Duration(seconds: 3);

const _g = 9.80665;
const _sampleEvery = Duration(milliseconds: 20);

/// Marker every RED assertion carries; the runner counts only these.
String red(String id, String what) => 'SHAKE-RED[$id] $what';

void diag(String msg) => debugPrint('SHAKE-DIAG $msg');

// ---------------------------------------------------------------------------
// Motion traces (m/s², gravity removed). Built from the PRD's FR-3 numbers:
// peaks ≥ 2.0 g, ≥ 4 reversals, peaks 70–500 ms apart.
// ---------------------------------------------------------------------------

class Sample {
  final double x, y, z;
  const Sample(this.x, this.y, this.z);
}

typedef Trace = List<Sample>;

int _n(Duration d) => d.inMilliseconds ~/ _sampleEvery.inMilliseconds;

/// Still, with sensor noise.
Trace still(Duration d) => List.generate(_n(d), (i) {
      final r = math.Random(i);
      return Sample((r.nextDouble() - .5) * .1, (r.nextDouble() - .5) * .1,
          (r.nextDouble() - .5) * .1);
    });

/// `peaks` alternating peaks along x, `amplitudeG` each, `spacing` apart:
/// a sine whose half-period is `spacing`.
Trace alternating({
  required int peaks,
  required double amplitudeG,
  Duration spacing = const Duration(milliseconds: 160),
}) {
  // Peaks at halfMs/2 + k·halfMs, alternating in sign. At 160 ms and 2.5 g,
  // 3 samples per peak reach 2 g (60, 80, 100 ms into each half-period).
  final halfMs = spacing.inMilliseconds;
  final total = Duration(milliseconds: halfMs * peaks);
  return List.generate(_n(total), (i) {
    final tMs = i * _sampleEvery.inMilliseconds;
    return Sample(amplitudeG * _g * math.sin(math.pi * tMs / halfMs), 0, 0);
  });
}

/// E-1's deliberate shake: 6 alternating 2.5 g peaks, 160 ms apart.
Trace deliberateShake() => alternating(peaks: 6, amplitudeG: 2.5);

/// Walking with the phone in a pocket: ±0.4 g at 2 Hz.
Trace pocketWalk(Duration d) => List.generate(_n(d), (i) {
      final t = i * .02;
      return Sample(.1 * _g * math.sin(2 * math.pi * 1 * t), 0,
          .4 * _g * math.sin(2 * math.pi * 2 * t));
    });

/// Jogging: a +3 g footfall every 357 ms, then the flight phase, bounded
/// by free fall at -1 g. Strong peaks, all the same direction.
Trace jog(Duration d) => List.generate(_n(d), (i) {
      final ms = (i * 20) % 357;
      final z = ms < 40
          ? 3.0 * _g
          : ms < 200
              ? -0.9 * _g
              : 0.0;
      return Sample(0, 0, z);
    });

/// Stirring with the phone in an apron pocket: ±0.6 g at 3 Hz on x and y.
Trace stirring(Duration d) => List.generate(_n(d), (i) {
      final t = i * .02;
      return Sample(.6 * _g * math.sin(2 * math.pi * 3 * t),
          .6 * _g * math.cos(2 * math.pi * 3 * t), 0);
    });

/// One impact: a spike, then ringing that reverses every sample (20 ms,
/// faster than FR-3's 70 ms floor).
Trace impact({required double spikeG, required double ringG, int rings = 3}) => [
      Sample(0, 0, spikeG * _g),
      for (var k = 1; k <= rings; k++)
        Sample(0, 0, (k.isOdd ? -1 : 1) * ringG * _g),
    ];

/// Knocks on the counter, 600 ms apart.
Trace counterKnocks(int count) => [
      for (var k = 0; k < count; k++) ...[
        ...impact(spikeG: 4, ringG: 2.5),
        ...still(const Duration(milliseconds: 520)),
      ],
    ];

/// Lift, a short drop at free fall, a hard landing.
Trace hardSetDown() => [
      ...List.generate(15, (_) => const Sample(0, 0, .5 * _g)),
      ...List.generate(8, (_) => const Sample(0, 0, -1.0 * _g)),
      ...impact(spikeG: 5, ringG: 2.2, rings: 4),
      ...still(const Duration(milliseconds: 600)),
    ];

/// A mallet on the same counter, 2.5 pounds a second.
Trace malletPounding(Duration d) {
  final out = <Sample>[];
  while (out.length < _n(d)) {
    out
      ..addAll(impact(spikeG: 3, ringG: 2.1))
      ..addAll(still(const Duration(milliseconds: 320)));
  }
  return out;
}

// ---------------------------------------------------------------------------
// Fake motion: sensors_plus's channels.
// ---------------------------------------------------------------------------

class FakeMotion {
  static const userAccel = EventChannel('dev.fluttercommunity.plus/sensors/user_accel');
  static const accel = EventChannel('dev.fluttercommunity.plus/sensors/accelerometer');
  static const method = MethodChannel('dev.fluttercommunity.plus/sensors/method');

  MockStreamHandlerEventSink? _user, _raw;
  int listens = 0;
  int cancels = 0;
  int _tUs = DateTime.utc(2026, 11, 25).microsecondsSinceEpoch;

  void install(WidgetTester tester) {
    final m = tester.binding.defaultBinaryMessenger;
    m.setMockMethodCallHandler(method, (call) async => null);
    m.setMockStreamHandler(
        userAccel,
        MockStreamHandler.inline(
          onListen: (_, sink) {
            listens++;
            _user = sink;
          },
          onCancel: (_) {
            cancels++;
            _user = null;
          },
        ));
    m.setMockStreamHandler(
        accel,
        MockStreamHandler.inline(
          onListen: (_, sink) {
            listens++;
            _raw = sink;
          },
          onCancel: (_) {
            cancels++;
            _raw = null;
          },
        ));
  }

  bool get subscribed => _user != null || _raw != null;

  /// Sends one sample per 20 ms of test time, pumping between samples.
  Future<void> play(WidgetTester tester, Trace trace) async {
    for (final s in trace) {
      _tUs += _sampleEvery.inMicroseconds;
      _user?.success(<double>[s.x, s.y, s.z, _tUs.toDouble()]);
      _raw?.success(<double>[s.x, s.y, s.z + _g, _tUs.toDouble()]);
      await tester.pump(_sampleEvery);
    }
  }

  Future<void> idle(WidgetTester tester, Duration d) => play(tester, still(d));
}

// ---------------------------------------------------------------------------
// Fake HTTP.
// ---------------------------------------------------------------------------

class FakeHttp implements HttpClientAdapter {
  /// `null` = the flags request never answers.
  String? ring;
  bool isAdmin;
  final List<RequestOptions> requests = [];
  FakeHttp({required this.ring, required this.isAdmin});

  List<Map<String, dynamic>> get feedbackPosts => [
        for (final r in requests)
          if (r.method == 'POST' && r.path.endsWith('/v1/users/me/feedback'))
            Map<String, dynamic>.from(
                (r.data is String ? jsonDecode(r.data as String) : r.data) as Map),
      ];

  @override
  Future<ResponseBody> fetch(RequestOptions o, Stream<Uint8List>? body,
      Future<void>? cancel) async {
    requests.add(o);
    Object? json;
    var status = 200;
    if (o.path.endsWith('/v1/flags/perf')) {
      if (ring == null) return Completer<ResponseBody>().future;
      json = {'ingest_enabled': true, 'sampling_rate': 1.0, 'shake_report': ring};
    } else if (o.method == 'GET' && o.path.endsWith('/v1/users/me')) {
      json = {
        'id': '34000000-0000-0000-0000-000000000001',
        'name': 'Eval User',
        'email': 'eval@example.test',
        'is_admin': isAdmin,
        'has_completed_onboarding': true,
      };
    } else if (o.method == 'POST' && o.path.endsWith('/v1/users/me/feedback')) {
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
/// initializer (push_notification_service.dart:74), so it cannot exist in a
/// test. `PalatefulApp` calls these two (main.dart:427, :447).
class _FakePush implements PushNotificationService {
  @override
  void setNavigatorKey(GlobalKey<NavigatorState> key) {}
  @override
  Future<AuthorizationStatus> ensureRegistered({bool autoPrompt = false}) async =>
      AuthorizationStatus.notDetermined;
  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

// ---------------------------------------------------------------------------
// The harness.
// ---------------------------------------------------------------------------

/// Call from `setUp`. GetIt's reset is async: un-awaited, it wipes the new
/// registrations a microtask later (measured; design RQ13).
Future<void> resetWorld() async {
  GoogleFonts.config.allowRuntimeFetching = false;
  SharedPreferences.setMockInitialValues({});
  await GetIt.instance.reset();
  setupDependencies();
  GetIt.instance.unregister<PushNotificationService>();
  GetIt.instance.registerSingleton<PushNotificationService>(_FakePush());
  resetRouter();
  resetPerfNavigatorObserver();
}

Future<void> tearDownWorld() async {
  if (GetIt.instance.isRegistered<PerfFlagsService>()) {
    GetIt.instance<PerfFlagsService>().dispose();
  }
  resetRouter();
  resetPerfNavigatorObserver();
  await GetIt.instance.reset();
}

class ShakeHarness {
  final WidgetTester tester;
  final FakeHttp http;
  final FakeMotion motion;
  ShakeHarness._(this.tester, this.http, this.motion);

  AuthService get auth => GetIt.instance<AuthService>();
  PerfFlagsService get flags => GetIt.instance<PerfFlagsService>();

  /// Boots `PalatefulApp` signed in and onboarded, the way `main()` does:
  /// the provider overrides of `app/lib/main.dart:300-308` and the flags
  /// fetch of `app/lib/main.dart:97`.
  static Future<ShakeHarness> boot(
    WidgetTester tester, {
    required bool isAdmin,
    required String? ring,
    String startRoute = '/',
  }) async {
    final http = FakeHttp(ring: ring, isAdmin: isAdmin);
    final motion = FakeMotion()..install(tester);
    final m = tester.binding.defaultBinaryMessenger;
    m.setMockMethodCallHandler(
        const MethodChannel('receive_sharing_intent/messages'), (call) async => null);
    m.setMockStreamHandler(const EventChannel('receive_sharing_intent/events-media'),
        MockStreamHandler.inline(onListen: (_, __) {}));
    // Online. The sheet asks before it opens (profile_screen.dart:81-88).
    m.setMockMethodCallHandler(const MethodChannel('dev.fluttercommunity.plus/connectivity'),
        (call) async => call.method == 'check' ? <String>['wifi'] : null);
    m.setMockStreamHandler(const EventChannel('dev.fluttercommunity.plus/connectivity_status'),
        MockStreamHandler.inline(onListen: (_, __) {}));

    final api = GetIt.instance<ApiClient>();
    api.dio.httpClientAdapter = http;
    api.setAuthToken('eval-token');
    final auth = GetIt.instance<AuthService>();
    auth.setAccessToken('eval-token');
    auth.updateOnboardingState(hasCompletedOnboarding: true);
    auth.updateAdminState(isAdmin);

    await tester.runAsync(() => GetIt.instance<PerfFlagsService>().initialize());

    tester.binding.platformDispatcher.defaultRouteNameTestValue = startRoute;
    await tester.pumpWidget(ProviderScope(overrides: [
      themeModeProvider.overrideWith(() => ThemeModeNotifier(ThemeMode.light)),
      fontStyleProvider.overrideWith(() => FontStyleNotifier(FontStyle.classic)),
      recipeListViewProvider.overrideWith(() => RecipeListViewNotifier(RecipeListView.grid)),
    ], child: const PalatefulApp()));
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump(const Duration(milliseconds: 300));
    final h = ShakeHarness._(tester, http, motion);
    diag('booted at ${h.location}; motion listeners so far: ${motion.listens}');
    return h;
  }

  /// Re-reads the flags (as the 5-minute refresh would) after `http.ring`
  /// changed.
  Future<void> refreshFlags() async {
    await tester.runAsync(() => flags.initialize());
    await tester.pump(const Duration(milliseconds: 100));
  }

  String get location => appRouter.routerDelegate.currentConfiguration.uri.path;
  bool get routingError => appRouter.routerDelegate.currentConfiguration.isError;

  Finder promptAction(String label) =>
      find.descendant(of: find.byType(SnackBar), matching: find.text(label));
  Finder promptText(String text) =>
      find.descendant(of: find.byType(SnackBar), matching: find.text(text));
  int get prompts => find.byType(SnackBar).evaluate().length;
  int get sheets => find.byType(FeedbackSheet).evaluate().length;

  /// A deliberate shake, then a second to let a prompt animate in.
  Future<void> shake() async {
    await motion.play(tester, deliberateShake());
    await tester.pump(const Duration(milliseconds: 500));
    diag('after shake: listeners=${motion.listens} subscribed=${motion.subscribed} '
        'prompts=$prompts sheets=$sheets location=$location');
  }

  /// Lets the cooldown pass, with still samples flowing.
  Future<void> waitOutCooldown() =>
      motion.idle(tester, cooldown + const Duration(milliseconds: 500));

  Future<void> tapPrompt(String label) async {
    await tester.tap(promptAction(label));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 600));
  }

  /// Unmounts the app and drains its timers, so a test ends clean.
  Future<void> close() async {
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 10));
  }
}

// ---------------------------------------------------------------------------
// Controls — must pass on unbuilt code.
// ---------------------------------------------------------------------------

/// The channel names sensors_plus declares, written out again here on
/// purpose (plus_plugins `sensors_plus_platform_interface/lib/src/
/// method_channel_sensors.dart`, design RQ9). The control below must not
/// reuse `FakeMotion`'s constants: when it did, a typo in them passed the
/// control, because mock and subscriber agreed with each other and not with
/// the plugin (caught by the runner's blind-harness negative control).
const pluginUserAccelChannel = 'dev.fluttercommunity.plus/sensors/user_accel';
const pluginAccelChannel = 'dev.fluttercommunity.plus/sensors/accelerometer';
const pluginMethodChannel = 'dev.fluttercommunity.plus/sensors/method';

void registerHarnessControls() {
  testWidgets("control: fake motion arrives on sensors_plus's own channel, sample for sample",
      (tester) async {
    expect(FakeMotion.userAccel.name, pluginUserAccelChannel,
        reason: "the harness fakes a channel sensors_plus does not use");
    expect(FakeMotion.accel.name, pluginAccelChannel,
        reason: "the harness fakes a channel sensors_plus does not use");
    expect(FakeMotion.method.name, pluginMethodChannel,
        reason: "the harness fakes a channel sensors_plus does not use");
    final motion = FakeMotion()..install(tester);
    final got = <List<double>>[];
    final sub = const EventChannel(pluginUserAccelChannel)
        .receiveBroadcastStream()
        .listen((e) => got.add((e as List).cast<double>()));
    await tester.pump();
    final trace = deliberateShake();
    await motion.play(tester, trace);
    expect(motion.listens, 1, reason: 'the mock channel saw no listen');
    expect(got.length, trace.length, reason: 'samples were lost on the way');
    expect(got.map((s) => s[0]).reduce(math.max), greaterThan(2.0 * _g),
        reason: 'the deliberate trace does not reach 2 g');
    unawaited(sub.cancel());
  });

  testWidgets('control: the real app boots signed in, no exception',
      timeout: const Timeout(Duration(seconds: 60)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    expect(tester.takeException(), isNull);
    expect(h.location, '/');
    expect(find.byType(Scaffold), findsWidgets);
    await h.close();
  });

  testWidgets('control: a prompt-shaped snackbar is found and its action taps',
      timeout: const Timeout(Duration(seconds: 60)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    var tapped = 0;
    ScaffoldMessenger.of(tester.element(find.byType(Scaffold).last)).showSnackBar(
      SnackBar(
        content: const Text(userPromptText),
        behavior: SnackBarBehavior.floating,
        duration: promptLifetime,
        action: SnackBarAction(label: userPromptAction, onPressed: () => tapped++),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(h.prompts, 1);
    expect(h.promptText(userPromptText), findsOneWidget);
    await h.tapPrompt(userPromptAction);
    expect(tapped, 1);
    await h.close();
  });

  testWidgets("control: the sheet finder sees the sheet Profile's tile opens",
      timeout: const Timeout(Duration(seconds: 60)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    appRouter.go('/profile');
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    final tile = find.text('Send Feedback');
    expect(tile, findsOneWidget, reason: "Profile shows no 'Send Feedback' tile");
    await tester.ensureVisible(tile);
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(tile);
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }
    expect(h.sheets, 1, reason: "tapping Profile's tile showed ${h.sheets} sheets");
    await h.close();
  });
}
