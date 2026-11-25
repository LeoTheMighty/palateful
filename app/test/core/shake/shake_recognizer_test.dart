// Trace tests for ShakeRecognizer: plan f89791 phase 3 (T3.4); PRD FR-3,
// FR-4; design § Recognizer.
//
// A recognizer that never fires passes every "no shake" test for free, so
// no such test stands alone here:
//   1. E-2's own traces, copied from the eval harness, each alone and then
//      replayed as E-2's whole session on the harness's clock, ending in
//      E-2's positive control. E-2 itself cannot run until the host exists
//      (phase 4); this is what it will get from the recognizer when it does.
//   2. A pair at every ShakeTuning edge, one sample on the edge and one just
//      past it, with opposite outcomes. Built from ShakeTuning.standard, so
//      a retune moves them with it.
//   3. The design's failure-handling rows: slower sampling, out-of-order
//      samples, a hole in the stream.
import 'dart:math' as math;

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/shake/shake_recognizer.dart';

// ---------------------------------------------------------------------------
// E-2's traces: lines 80-175 of
// _devx/workstreams/shake-to-report/evals/flutter/shake_harness.dart,
// unchanged (diff the two ranges to check). Copied, not imported: a test in
// app/test cannot import a file outside the package, and the harness is
// pinned by sha256, so it changes only through `devx revise`. If it does,
// copy it again.
// ---------------------------------------------------------------------------

const _g = 9.80665;
const _sampleEvery = Duration(milliseconds: 20);

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
// Feeding.
// ---------------------------------------------------------------------------

const tuning = ShakeTuning.standard;
const ms = Duration(milliseconds: 1);

/// E-2's eight traces, named and built as e2_everyday_motion_test.dart does.
Map<String, Trace> everydayTraces() => {
      'pocket walk 15 s': pocketWalk(const Duration(seconds: 15)),
      'jog 10 s': jog(const Duration(seconds: 10)),
      'stirring 15 s': stirring(const Duration(seconds: 15)),
      'counter knocks x8': counterKnocks(8),
      'hard set-down x3': [...hardSetDown(), ...hardSetDown(), ...hardSetDown()],
      'mallet pounding 10 s': malletPounding(const Duration(seconds: 10)),
      'near-miss: 3 reversals at 2.5 g': alternating(peaks: 4, amplitudeG: 2.5),
      'near-miss: 6 reversals at 1.8 g': alternating(peaks: 7, amplitudeG: 1.8),
    };

/// The eval harness's clock (`FakeMotion.play`): 20 ms added before every
/// sample, from 2026-11-25 UTC, and only samples move it — a `pump` with no
/// sample does not. sensors_plus 6.1 decodes that number into the event's
/// timestamp, so this is the time the recognizer will see in E-1…E-4.
class HarnessFeed {
  final recognizer = ShakeRecognizer();
  int _tUs = DateTime.utc(2026, 11, 25).microsecondsSinceEpoch;

  /// Plays [trace]; returns how many shakes it recognized.
  int play(Trace trace) {
    var n = 0;
    for (final s in trace) {
      _tUs += _sampleEvery.inMicroseconds;
      if (recognizer.add(MotionSample(s.x, s.y, s.z, Duration(microseconds: _tUs)))) n++;
    }
    return n;
  }

  int idle(Duration d) => play(still(d));
}

/// Feeds [samples] to one recognizer; returns the times it recognized at.
List<Duration> recognitions(Iterable<MotionSample> samples) {
  final r = ShakeRecognizer();
  return [
    for (final s in samples)
      if (r.add(s)) s.t,
  ];
}

MotionSample quiet(Duration t) => MotionSample(.04, -.03, .02, t);

/// One single-sample peak per entry of [apexes] (m/s²), apexes [every]
/// apart from [start], with weak samples every 20 ms between them and two
/// after the last, as a 50 Hz stream carries them.
List<MotionSample> strokes(
  List<List<double>> apexes, {
  Duration every = const Duration(milliseconds: 160),
  Duration start = Duration.zero,
}) {
  final out = <MotionSample>[];
  for (var k = 0; k < apexes.length; k++) {
    final t = start + every * k;
    final a = apexes[k];
    out.add(MotionSample(a[0], a[1], a[2], t));
    final next = k + 1 < apexes.length ? start + every * (k + 1) : t + _sampleEvery * 3;
    for (var q = t + _sampleEvery; q < next; q += _sampleEvery) {
      out.add(quiet(q));
    }
  }
  return out;
}

/// [count] single-sample peaks of [magnitude] along +x, −x, +x, …
List<MotionSample> shake(
  int count, {
  double magnitude = 2.5 * _g,
  Duration every = const Duration(milliseconds: 160),
  Duration start = Duration.zero,
}) =>
    strokes([
      for (var k = 0; k < count; k++) [k.isEven ? magnitude : -magnitude, 0, 0],
    ], every: every, start: start);

/// The deliberate shake's motion — a sine of [amplitudeG] whose half-period
/// is 160 ms, as `alternating` builds it — sampled every [period].
List<MotionSample> sampledSine({
  required Duration period,
  double amplitudeG = 2.5,
  int peaks = 6,
}) {
  const half = Duration(milliseconds: 160);
  return [
    for (var t = Duration.zero; t < half * peaks; t += period)
      MotionSample(
          amplitudeG * _g * math.sin(math.pi * t.inMicroseconds / half.inMicroseconds), 0, 0, t),
  ];
}

void main() {
  group("E-2's traces", () {
    test("the copy is E-2's 60 s of everyday motion", () {
      // e2_everyday_motion_test.dart's EVAL-PRECONDITION.
      final samples = everydayTraces().values.fold<int>(0, (n, t) => n + t.length);
      expect(samples * _sampleEvery.inMilliseconds, greaterThanOrEqualTo(60000));
    });

    for (final e in everydayTraces().entries) {
      test('${e.key}: no shake', () {
        expect(HarnessFeed().play(e.value), 0);
      });
    }

    test("the deliberate shake (E-1's and E-2's positive control) is exactly one shake", () {
      expect(HarnessFeed().play(deliberateShake()), 1);
    });

    test("E-2's session: eight everyday traces recognize nothing, then the deliberate "
        'shake recognizes once', () {
      final f = HarnessFeed();
      final falseTriggers = <String>[];
      for (final e in everydayTraces().entries) {
        // play, then the eval's waitOutCooldown(): cooldown + 500 ms of still.
        final n = f.play(e.value) + f.idle(const Duration(milliseconds: 3500));
        if (n > 0) falseTriggers.add(e.key);
      }
      expect(falseTriggers, isEmpty);
      expect(f.play(deliberateShake()), 1,
          reason: "E-2's positive control: the same recognizer, after the everyday traces");
    });

    test("E-1/E-4's rhythm: shake, waitOutCooldown, shake — both recognize", () {
      final f = HarnessFeed();
      expect(f.play(deliberateShake()), 1);
      expect(f.idle(const Duration(milliseconds: 3500)), 0);
      expect(f.play(deliberateShake()), 1,
          reason: "the eval's 3.5 s wait must outlast the cooldown, measured from the "
              'recognizing sample');
    });
  });

  group('ShakeTuning edges: each pair has opposite outcomes', () {
    test('peakThreshold: peaks exactly at it are strong', () {
      expect(recognitions(shake(5, magnitude: tuning.peakThreshold)), hasLength(1));
    });
    test('peakThreshold: peaks 0.01 m/s² under it are not', () {
      expect(recognitions(shake(5, magnitude: tuning.peakThreshold - .01)), isEmpty);
    });
    test('peakThreshold is on the magnitude, not on any one axis', () {
      final c = 2.5 * _g / math.sqrt(3); // ≈ 1.44 g on each axis
      expect(c, lessThan(tuning.peakThreshold));
      expect(
          recognitions(strokes([
            for (var k = 0; k < 5; k++) k.isEven ? [c, c, c] : [-c, -c, -c],
          ])),
          hasLength(1));
    });

    test('minGap: apexes exactly minGap apart reverse', () {
      expect(recognitions(shake(5, every: tuning.minGap)), hasLength(1));
    });
    test('minGap: 1 ms closer, they do not', () {
      expect(recognitions(shake(5, every: tuning.minGap - ms)), isEmpty);
    });

    test('maxGap: apexes exactly maxGap apart reverse', () {
      expect(recognitions(shake(5, every: tuning.maxGap)), hasLength(1));
    });
    test('maxGap: 1 ms further, they do not', () {
      expect(recognitions(shake(5, every: tuning.maxGap + ms)), isEmpty);
    });

    // A peak strong from 0 to 200 ms, largest first, so its apex is at 0
    // and its last strong sample at 200: the quiet before the next peak is
    // under maxGap even when the apexes are not.
    List<MotionSample> longPeakThen(Duration nextApex) => [
          for (var k = 0; k <= 10; k++) MotionSample((3.0 - .08 * k) * _g, 0, 0, _sampleEvery * k),
          for (var q = _sampleEvery * 11; q < nextApex; q += _sampleEvery) quiet(q),
          ...strokes([
            for (var k = 0; k < 4; k++) [k.isEven ? -2.5 * _g : 2.5 * _g, 0, 0],
          ], start: nextApex),
        ];
    test('maxGap is apex to apex: a long peak reverses with one exactly maxGap after its apex', () {
      expect(recognitions(longPeakThen(tuning.maxGap)), hasLength(1));
    });
    test('maxGap is apex to apex: not with one maxGap + 60 ms after it, though the quiet '
        'between them is only 360 ms', () {
      expect(tuning.maxGap + ms * 60 - _sampleEvery * 10, lessThan(tuning.maxGap),
          reason: 'precondition: step 4 must not be what rejects it');
      expect(recognitions(longPeakThen(tuning.maxGap + ms * 60)), isEmpty);
    });

    test('minReversals: exactly that many reversals is a shake', () {
      expect(recognitions(shake(tuning.minReversals + 1)), hasLength(1));
    });
    test('minReversals: one fewer is not', () {
      expect(recognitions(shake(tuning.minReversals)), isEmpty);
    });

    // A shake, then a second one whose first apex lands [after] the first's
    // recognition, with weak samples flowing in between.
    List<MotionSample> twoShakes(Duration after) {
      final first = shake(5);
      final second = recognitions(first).single + after;
      return [
        ...first,
        for (var q = first.last.t + _sampleEvery; q < second; q += _sampleEvery) quiet(q),
        ...shake(5, start: second),
      ];
    }

    test('cooldown: a shake whose first apex lands exactly as it ends is a second shake', () {
      expect(recognitions(twoShakes(tuning.cooldown)), hasLength(2));
    });
    test('cooldown: 1 ms earlier, its first peak is ignored and the rest is a reversal short', () {
      expect(recognitions(twoShakes(tuning.cooldown - ms)), hasLength(1));
    });
    test('cooldown: one long shake (12 peaks, 1.8 s) is one recognition', () {
      expect(recognitions(shake(12)), hasLength(1));
    });
  });

  group('direction', () {
    test('peaks all in one direction never reverse', () {
      expect(recognitions(strokes([for (var k = 0; k < 8; k++) [2.5 * _g, 0, 0]])), isEmpty);
    });
    test('a peak at right angles to the last is not a reversal', () {
      expect(
          recognitions(strokes([
            for (var k = 0; k < 8; k++) k.isEven ? [2.5 * _g, 0, 0] : [0, 2.5 * _g, 0],
          ])),
          isEmpty);
    });
    test('a vigorous 6 g shake, strong through most of each stroke, is a shake', () {
      // One weak sample between strokes: the quiet gap is 40 ms, under minGap,
      // while the apexes stay 160 ms apart.
      expect(recognitions(sampledSine(period: _sampleEvery, amplitudeG: 6)), hasLength(1));
    });
    test("a peak is timed and aimed by its largest sample, not its first", () {
      // Apexes 80 ms apart throughout. P1 and P3 open 20 ms before their
      // apex, so timed by their first sample they would sit 60 ms after the
      // peak before them: under minGap.
      MotionSample x(double gs, int atMs) => MotionSample(gs * _g, 0, 0, ms * atMs);
      final s = [
        x(3, 0), quiet(ms * 20), quiet(ms * 40), //               P0 +x, apex 0
        x(-2.1, 60), x(-3, 80), quiet(ms * 100), quiet(ms * 120), quiet(ms * 140), // P1 apex 80
        x(3, 160), quiet(ms * 180), quiet(ms * 200), //            P2 apex 160
        x(-2.1, 220), x(-3, 240), quiet(ms * 260), quiet(ms * 280), quiet(ms * 300), // P3 apex 240
        x(3, 320), quiet(ms * 340), quiet(ms * 360), //            P4 apex 320
      ];
      expect(recognitions(s), hasLength(1));
    });
    test('strokes with no weak sample between them: an opposite strong sample closes the '
        'open peak and opens the next', () {
      final s = [
        for (var i = 0; i < 7 * 6; i++)
          MotionSample(((i ~/ 7).isEven ? 3 : -3) * _g, 0, 0, _sampleEvery * i),
        quiet(_sampleEvery * 42),
      ];
      expect(s.take(42).every((x) => x.x.abs() >= tuning.peakThreshold), isTrue,
          reason: 'precondition: no weak sample until the end');
      expect(recognitions(s), hasLength(1));
    });
  });

  group('failure handling', () {
    for (final period in [20, 40, 60]) {
      test('the deliberate shake sampled every $period ms is one shake: time comes from '
          'timestamps, not sample counts', () {
        expect(recognitions(sampledSine(period: ms * period)), hasLength(1));
      });
    }

    test('a sample stamped earlier than the last one is dropped, and does not break the run', () {
      final s = shake(5); // apexes at 0, 160, 320, 480, 640 ms
      final i = s.indexWhere((x) => x.t == ms * 340);
      // Strong and pointing against the third peak: kept, it would open a
      // peak a second in the past and restart the run.
      final stale = MotionSample(-2.5 * _g, 0, 0, ms * 320 - const Duration(seconds: 1));
      expect(recognitions([...s.sublist(0, i + 1), stale, ...s.sublist(i + 1)]), hasLength(1));
    });

    test('a hole longer than maxGap in the stream ends the run (step 4): a stale strong '
        'sample before it does not swallow the first peak of the shake after it', () {
      // Same direction as the shake's first peak and larger, so if the run
      // survived the hole, that peak would join it and keep its apex at 0.
      final stale = MotionSample(3 * _g, 0, 0, Duration.zero);
      expect(recognitions([stale, ...shake(5, start: tuning.maxGap + ms * 60)]), hasLength(1));
    });
  });
}
