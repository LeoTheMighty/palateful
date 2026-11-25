// MotionSource through sensors_plus's own platform channels: what the
// adapter hands on, and what one stream error does (design § Recognizer,
// failure handling; PRD FR-1).
import 'dart:async';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/error_reporter.dart';
import 'package:palateful/core/shake/motion_source.dart';
import 'package:palateful/core/shake/shake_recognizer.dart';

// Written out rather than taken from the plugin: a mock keyed on the
// plugin's own constant agrees with it whatever it says (the eval harness's
// channel control learned this). sensors_plus_platform_interface 2.0.2,
// lib/src/method_channel_sensors.dart.
const _userAccel = EventChannel('dev.fluttercommunity.plus/sensors/user_accel');
const _method = MethodChannel('dev.fluttercommunity.plus/sensors/method');

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

  late List<String> breadcrumbs;
  late List<MethodCall> calls;
  MockStreamHandlerEventSink? platform;
  var listens = 0;
  var cancels = 0;

  setUp(() {
    breadcrumbs = [];
    calls = [];
    platform = null;
    listens = 0;
    cancels = 0;
    ErrorReporter.testLogHook = breadcrumbs.add;
    messenger.setMockMethodCallHandler(_method, (call) async {
      calls.add(call);
      return null;
    });
    messenger.setMockStreamHandler(
      _userAccel,
      MockStreamHandler.inline(
        onListen: (_, sink) {
          listens++;
          platform = sink;
        },
        onCancel: (_) {
          cancels++;
          platform = null;
        },
      ),
    );
  });

  tearDown(() {
    ErrorReporter.testLogHook = null;
    messenger.setMockMethodCallHandler(_method, null);
    messenger.setMockStreamHandler(_userAccel, null);
  });

  final t0 = DateTime.utc(2026, 11, 25).microsecondsSinceEpoch;

  test("samples carry the event's own x, y, z and timestamp, asked for at 20 ms", () async {
    final source = MotionSource();
    final got = <MotionSample>[];
    final sub = source.samples().listen(got.add);
    await pumpEventQueue();
    expect(listens, 1, reason: 'listening must subscribe to the user_accel channel');
    expect(calls.map((c) => '${c.method}:${c.arguments}'),
        ['setUserAccelerometerSamplingPeriod:20000']);

    platform!.success(<double>[1.5, -2.5, 19.75, (t0 + 20000).toDouble()]);
    platform!.success(<double>[0, 0, 0, (t0 + 40000).toDouble()]);
    await pumpEventQueue();
    expect(got, hasLength(2));
    expect([got[0].x, got[0].y, got[0].z], [1.5, -2.5, 19.75]);
    expect(got.map((s) => s.t.inMicroseconds), [t0 + 20000, t0 + 40000]);

    await sub.cancel();
    await pumpEventQueue();
    expect(cancels, 1, reason: 'cancelling must unsubscribe from the platform');
    expect(breadcrumbs, isEmpty);
    expect(source.available, isTrue);
  });

  test('a stream error ends the stream after one breadcrumb, and motion stays off for this '
      'source', () async {
    final source = MotionSource();
    final got = <MotionSample>[];
    final errors = <Object>[];
    final done = Completer<void>();
    source.samples().listen(got.add, onError: errors.add, onDone: done.complete);
    await pumpEventQueue();

    platform!.success(<double>[1, 2, 3, (t0 + 20000).toDouble()]);
    platform!.error(code: 'NO_SENSOR', message: 'No Accelerometer found');
    await pumpEventQueue();

    expect(got, hasLength(1));
    expect(done.isCompleted, isTrue, reason: 'the stream must end');
    expect(errors, isEmpty, reason: "the adapter handles the error; it is not the listener's");
    expect(cancels, 1, reason: 'the platform stream must be cancelled');
    expect(breadcrumbs, ['shake.motion_unavailable code=NO_SENSOR']);
    expect(source.available, isFalse);

    // Later subscriptions — a resume, a sign-in — ask the platform nothing
    // and log nothing.
    expect(await source.samples().toList(), isEmpty);
    expect(listens, 1);
    expect(breadcrumbs, hasLength(1));
  });

  test('motion_source.dart is the only file in lib/ that imports sensors_plus, and the '
      'recognizer imports nothing', () {
    final import = RegExp(r'''^\s*(import|export)\s+['"]package:sensors_plus''', multiLine: true);
    final importers = [
      for (final f in Directory('lib').listSync(recursive: true).whereType<File>())
        if (f.path.endsWith('.dart') && import.hasMatch(f.readAsStringSync())) f.path,
    ];
    // Exact, not "at most one": the scan has to find the adapter, or it
    // could be passing because it sees nothing.
    expect(importers, ['lib/core/shake/motion_source.dart']);
    expect(
        RegExp(r'^\s*(import|export)\s', multiLine: true)
            .hasMatch(File('lib/core/shake/shake_recognizer.dart').readAsStringSync()),
        isFalse,
        reason: 'the recognizer is pure Dart: traces drive it with no Flutter or plugin');
  });
}
