// E-2 (P0): everyday kitchen motion never prompts. expectations.md E-2;
// PRD FR-3, FR-4. Run through ../E-2_everyday_motion.sh, which pins this
// file.
//
// A 0-prompt check passes for free on an app that never prompts. So the
// same session ends with E-1's deliberate shake, and the eval fails unless
// that one prompts: on unbuilt code this eval is RED because it cannot yet
// see, and it says so.
import 'package:flutter_test/flutter_test.dart';

import 'shake_harness.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(resetWorld);
  tearDown(tearDownWorld);

  registerHarnessControls();

  testWidgets('E-2: eight everyday traces prompt 0 times; a deliberate shake '
      'in the same session prompts once',
      timeout: const Timeout(Duration(seconds: 240)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');

    final traces = <String, Trace>{
      'pocket walk 15 s': pocketWalk(const Duration(seconds: 15)),
      'jog 10 s': jog(const Duration(seconds: 10)),
      'stirring 15 s': stirring(const Duration(seconds: 15)),
      'counter knocks x8': counterKnocks(8),
      'hard set-down x3': [...hardSetDown(), ...hardSetDown(), ...hardSetDown()],
      'mallet pounding 10 s': malletPounding(const Duration(seconds: 10)),
      'near-miss: 3 reversals at 2.5 g': alternating(peaks: 4, amplitudeG: 2.5),
      'near-miss: 6 reversals at 1.8 g': alternating(peaks: 7, amplitudeG: 1.8),
    };
    var motionMs = 0;
    final falseTriggers = <String>[];
    for (final e in traces.entries) {
      await h.motion.play(tester, e.value);
      motionMs += e.value.length * 20;
      await tester.pump(const Duration(milliseconds: 300));
      if (h.prompts > 0) {
        falseTriggers.add(e.key);
        await h.motion.idle(tester, promptLifetime + const Duration(seconds: 1));
      }
      await h.waitOutCooldown();
    }
    diag('everyday motion ${motionMs ~/ 1000} s, false triggers: $falseTriggers, '
        'motion listeners=${h.motion.listens}');
    expect(motionMs, greaterThanOrEqualTo(60000),
        reason: 'EVAL-PRECONDITION the traces total ${motionMs ~/ 1000} s, the eval declares 60');

    // False triggers first: two ignored prompts mute the session (FR-4),
    // which would otherwise surface below as a blind positive control.
    expect(falseTriggers, isEmpty,
        reason: red('E-2:false-trigger', 'prompted on: $falseTriggers'));

    await h.shake();
    expect(h.prompts, 1,
        reason: red('E-2:positive-control-no-prompt',
            'the deliberate shake after the everyday traces showed ${h.prompts} prompts, so '
            'the 0 above proves nothing (motion listeners=${h.motion.listens})'));
    await h.close();
  });
}
