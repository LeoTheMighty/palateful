import 'dart:async';

import 'package:flutter/services.dart' show PlatformException;
import 'package:sensors_plus/sensors_plus.dart';

import '../services/error_reporter.dart';
import 'shake_recognizer.dart';

/// The only file in the app that imports sensors_plus (design § Recognizer).
///
/// Reads gravity-removed acceleration at the plugin's game interval (20 ms,
/// about 50 Hz; PRD FR-2) and hands it on as [MotionSample]s stamped with
/// the sensor's own event time.
///
/// A stream error, which is also how a device with no accelerometer
/// answers, ends motion for the life of this object: the stream closes after
/// one `shake.motion_unavailable` breadcrumb through [ErrorReporter.log],
/// and every later [samples] call returns an empty stream without asking
/// the platform again (PRD FR-1: a breadcrumb, not an error report, and no
/// UI). Hold one instance for the app session so "unavailable" means "for
/// the session".
///
/// Nothing subscribes to this yet; the shake host does (plan phase 4).
class MotionSource {
  bool _unavailable = false;

  /// False once the sensor stream has errored.
  bool get available => !_unavailable;

  /// A single-subscription stream of samples. Listening subscribes to the
  /// sensor; cancelling unsubscribes, so the platform samples only while
  /// someone listens.
  Stream<MotionSample> samples() {
    if (_unavailable) return const Stream<MotionSample>.empty();

    StreamSubscription<UserAccelerometerEvent>? upstream;
    late final StreamController<MotionSample> out;
    out = StreamController<MotionSample>(
      onListen: () {
        upstream = userAccelerometerEventStream(
          samplingPeriod: SensorInterval.gameInterval,
        ).listen(
          (e) => out.add(MotionSample(
            e.x,
            e.y,
            e.z,
            Duration(microseconds: e.timestamp.microsecondsSinceEpoch),
          )),
          onError: (Object error, StackTrace _) {
            _markUnavailable(error);
            out.close();
          },
          onDone: out.close,
          cancelOnError: true,
        );
      },
      onPause: () => upstream?.pause(),
      onResume: () => upstream?.resume(),
      onCancel: () => upstream?.cancel(),
    );
    return out.stream;
  }

  void _markUnavailable(Object error) {
    if (_unavailable) return;
    _unavailable = true;
    final code = error is PlatformException ? error.code : error.runtimeType;
    ErrorReporter.log('shake.motion_unavailable code=$code');
  }
}
