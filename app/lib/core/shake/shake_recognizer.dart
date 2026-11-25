/// Shake recognition for shake-to-report (PRD FR-3, FR-4; design
/// § Recognizer).
///
/// Pure Dart on purpose: nothing here imports Flutter or sensors_plus, so a
/// unit test drives it with synthesized traces
/// (`test/core/shake/shake_recognizer_test.dart`). The sensor stays behind
/// `motion_source.dart`, the only file in the app that imports the plugin.
library;

/// Every number the recognizer uses. FR-3 says they live in one constants
/// block and change only through E-7 device runs, so [standard] is the one
/// place to retune; the trace tests build their near misses from it.
class ShakeTuning {
  const ShakeTuning({
    required this.peakThreshold,
    required this.minGap,
    required this.maxGap,
    required this.minReversals,
    required this.cooldown,
  });

  /// FR-3 / FR-4 as shipped.
  static const standard = ShakeTuning(
    peakThreshold: 19.6, // 2.0 g, m/s², gravity removed
    minGap: Duration(milliseconds: 70),
    maxGap: Duration(milliseconds: 500),
    minReversals: 4,
    cooldown: Duration(seconds: 3),
  );

  /// A sample is strong when its magnitude reaches this (m/s², inclusive).
  final double peakThreshold;

  /// Consecutive peaks count as a reversal only when their apexes are at
  /// least this far apart (inclusive). A knock's ringing is faster.
  final Duration minGap;

  /// …and at most this far apart (inclusive). This long with no strong
  /// sample also ends the run.
  final Duration maxGap;

  /// Reversals in one run that make a shake. Four reversals is five peaks.
  final int minReversals;

  /// After a recognition, input is ignored for this long (FR-4).
  final Duration cooldown;
}

/// One accelerometer reading with gravity removed, in m/s².
///
/// [t] is the sensor's own event time, measured from any fixed epoch. Only
/// differences between samples matter: the recognizer reads time from [t],
/// never from sample counts, so a stream slower than asked recognizes the
/// same shakes, later.
class MotionSample {
  const MotionSample(this.x, this.y, this.z, this.t);

  final double x, y, z;
  final Duration t;

  double get _magnitudeSquared => x * x + y * y + z * z;

  double _dot(MotionSample o) => x * o.x + y * o.y + z * o.z;

  @override
  String toString() => 'MotionSample($x, $y, $z, ${t.inMicroseconds}µs)';
}

/// FR-3 as an algorithm (design § Recognizer, steps 1–5). Feed it samples in
/// arrival order with [add]; it answers `true` on the sample that completes
/// a shake.
///
/// 1. A sample is **strong** when `|a| ≥ peakThreshold`.
/// 2. Consecutive strong samples form one **peak**, whose apex is its
///    largest sample: the apex gives the peak its direction and its time. A
///    strong sample pointing against the open peak (negative dot product)
///    closes it and opens a new one.
/// 3. When a peak closes, it is a **reversal** of the run's previous peak if
///    their directions' dot product is negative and their apexes are within
///    `[minGap, maxGap]` of each other. Otherwise the run restarts at it.
/// 4. More than `maxGap` with no strong sample ends the run.
/// 5. `minReversals` reversals is a recognition. Input is then ignored for
///    `cooldown`, and a new run starts.
///
/// "Apart" is apex to apex, not the quiet gap between peaks. A vigorous
/// shake is strong for most of each stroke, so its quiet gap can be a single
/// 20 ms sample while its apexes stay a stroke apart; measuring the quiet gap
/// would reject it as knock ringing. Step 2's "closes it and opens a new one"
/// exists for exactly that shake, whose opposite strokes have no weak sample
/// between them.
///
/// A sample whose time is earlier than the last one accepted is dropped
/// (design § Recognizer, failure handling).
class ShakeRecognizer {
  ShakeRecognizer({this.tuning = ShakeTuning.standard})
      : _thresholdSquared = tuning.peakThreshold * tuning.peakThreshold;

  final ShakeTuning tuning;
  final double _thresholdSquared;

  Duration? _lastT;
  Duration? _cooldownUntil;
  Duration? _lastStrongT;

  /// The apex of the peak still receiving strong samples.
  MotionSample? _open;

  /// The apex of the run's last closed peak.
  MotionSample? _previous;
  int _reversals = 0;

  /// Feeds one sample. Returns `true` when this sample completes a shake.
  bool add(MotionSample s) {
    final last = _lastT;
    if (last != null && s.t < last) return false;
    _lastT = s.t;

    final until = _cooldownUntil;
    if (until != null) {
      if (s.t < until) return false;
      _cooldownUntil = null;
    }

    // Step 4. Checked on every sample, so a hole in the stream ends the run
    // too: a strong sample after the hole opens a fresh peak instead of
    // joining one that ended long ago.
    final lastStrong = _lastStrongT;
    if (lastStrong != null && s.t - lastStrong > tuning.maxGap) {
      _endRun();
    }

    if (s._magnitudeSquared < _thresholdSquared) {
      final open = _open;
      if (open == null) return false;
      _open = null;
      return _close(open, s.t);
    }

    _lastStrongT = s.t;
    final open = _open;
    if (open == null) {
      _open = s;
      return false;
    }
    if (s._dot(open) < 0) {
      if (_close(open, s.t)) return true;
      _open = s;
      return false;
    }
    if (s._magnitudeSquared > open._magnitudeSquared) _open = s;
    return false;
  }

  /// Step 3 for a peak that just closed, at time [now]; step 5 if it
  /// completes the run.
  bool _close(MotionSample apex, Duration now) {
    final previous = _previous;
    _previous = apex;
    if (previous == null) {
      _reversals = 0;
      return false;
    }
    final gap = apex.t - previous.t;
    final reversal = apex._dot(previous) < 0 &&
        gap >= tuning.minGap &&
        gap <= tuning.maxGap;
    if (!reversal) {
      _reversals = 0;
      return false;
    }
    _reversals++;
    if (_reversals < tuning.minReversals) return false;
    _endRun();
    _cooldownUntil = now + tuning.cooldown;
    return true;
  }

  void _endRun() {
    _open = null;
    _previous = null;
    _reversals = 0;
    _lastStrongT = null;
  }
}
