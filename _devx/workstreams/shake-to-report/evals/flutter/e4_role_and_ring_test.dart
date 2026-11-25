// E-4 (P0): admins get the dev-request form; anyone uncertain gets the user
// path; the ring decides who is asked at all. expectations.md E-4; PRD FR-7,
// FR-8, FR-10. Run through ../E-4_role_and_ring.sh, which pins this file.
//
// The 0-prompt cases end by widening the ring and shaking again: that shake
// must prompt, or the 0 proves nothing. The admin case needs arq103's route
// on main (external gate X-1); a separate test names that on its own, so a
// missing route reads as a missing route.
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/router/app_router.dart';

import 'shake_harness.dart';

Future<void> _widenAndMustPrompt(ShakeHarness h, String state) async {
  h.http.ring = 'everyone';
  await h.refreshFlags();
  await h.waitOutCooldown();
  await h.shake();
  expect(h.prompts, 1,
      reason: red('E-4:$state:positive-control-no-prompt',
          'after widening the ring to everyone, a deliberate shake showed ${h.prompts} '
          'prompts, so the 0 above proves nothing (motion listeners=${h.motion.listens})'));
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(resetWorld);
  tearDown(tearDownWorld);

  registerHarnessControls();

  testWidgets('control: the route check can say yes and no',
      timeout: const Timeout(Duration(seconds: 60)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: true, ring: 'admins');
    expect(appRouter.configuration.findMatch(Uri.parse('/admin/feedback')).isError, isFalse);
    expect(appRouter.configuration.findMatch(Uri.parse('/admin/no-such-route')).isError, isTrue);
    await h.close();
  });

  testWidgets('E-4: the dev-request route is registered (external gate X-1)',
      timeout: const Timeout(Duration(seconds: 60)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: true, ring: 'admins');
    expect(appRouter.configuration.findMatch(Uri.parse(devRequestPath)).isError, isFalse,
        reason: red('E-4:x1-route-missing',
            '$devRequestPath is not a route on this tree: arq103 has not reached main'));
    await h.close();
  });

  testWidgets('E-4: admin, ring admins → Request → the dev-request form → back',
      timeout: const Timeout(Duration(seconds: 90)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: true, ring: 'admins');
    final start = h.location;
    await h.shake();
    expect(h.prompts, 1,
        reason: red('E-4:admin:no-prompt',
            'an admin shake showed ${h.prompts} prompts (motion listeners=${h.motion.listens})'));
    expect(h.promptText(adminPromptText), findsOneWidget,
        reason: red('E-4:admin:prompt-copy', 'the admin prompt does not read "$adminPromptText"'));
    await h.tapPrompt(adminPromptAction);
    expect(h.location, devRequestPath,
        reason: red('E-4:admin:not-routed', 'the admin landed on ${h.location}'));
    expect(h.routingError, isFalse,
        reason: red('E-4:admin:route-error', 'the router reports an error for $devRequestPath'));
    expect(h.sheets, 0, reason: red('E-4:admin:got-feedback', 'the admin got the feedback sheet'));
    appRouter.pop();
    await tester.pump(const Duration(milliseconds: 600));
    expect(h.location, start,
        reason: red('E-4:admin:not-returned', 'closing the form left the admin on ${h.location}'));
    await h.close();
  });

  testWidgets('E-4: non-admin, ring everyone → Report → feedback, never the form',
      timeout: const Timeout(Duration(seconds: 90)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    await h.shake();
    expect(h.prompts, 1,
        reason: red('E-4:user:no-prompt',
            'a user shake showed ${h.prompts} prompts (motion listeners=${h.motion.listens})'));
    expect(h.promptAction(userPromptAction), findsOneWidget,
        reason: red('E-4:user:prompt-action', 'the user prompt has no "$userPromptAction"'));
    await h.tapPrompt(userPromptAction);
    expect(h.sheets, 1, reason: red('E-4:user:no-sheet', '${h.sheets} sheets'));
    expect(h.location, isNot(devRequestPath),
        reason: red('E-4:user:got-admin-form', 'a non-admin reached $devRequestPath'));
    await h.close();
  });

  testWidgets('E-4: admin at the prompt, not at the tap → the user path',
      timeout: const Timeout(Duration(seconds: 90)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: true, ring: 'everyone');
    await h.shake();
    expect(h.promptText(adminPromptText), findsOneWidget,
        reason: red('E-4:flipped:no-admin-prompt',
            'an admin shake showed no "$adminPromptText" prompt '
            '(prompts=${h.prompts}, motion listeners=${h.motion.listens})'));
    h.auth.updateAdminState(false);
    await tester.pump();
    await h.tapPrompt(adminPromptAction);
    expect(h.location, isNot(devRequestPath),
        reason: red('E-4:flipped:got-admin-form', 'a revoked admin reached $devRequestPath'));
    expect(h.sheets, 1, reason: red('E-4:flipped:no-sheet', '${h.sheets} sheets; expected the user path'));
    await h.close();
  });

  testWidgets('E-4: ring off → no prompt, even for an admin',
      timeout: const Timeout(Duration(seconds: 120)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: true, ring: 'off');
    await h.shake();
    expect(h.prompts, 0, reason: red('E-4:ring-off:prompted', 'ring off still prompted an admin'));
    await _widenAndMustPrompt(h, 'ring-off');
    await h.close();
  });

  testWidgets('E-4: ring admins → no prompt for a non-admin',
      timeout: const Timeout(Duration(seconds: 120)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'admins');
    await h.shake();
    expect(h.prompts, 0, reason: red('E-4:ring-admins:prompted', 'ring admins prompted a non-admin'));
    await _widenAndMustPrompt(h, 'ring-admins');
    await h.close();
  });

  testWidgets('E-4: flags never answer → no prompt for a non-admin (default admins)',
      timeout: const Timeout(Duration(seconds: 120)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: null);
    await h.shake();
    expect(h.prompts, 0,
        reason: red('E-4:no-flags:prompted', 'with no flags answer a non-admin was prompted'));
    await _widenAndMustPrompt(h, 'no-flags');
    await h.close();
  });
}
