// E-1 (P0): a deliberate shake opens feedback over the current screen.
// expectations.md E-1; PRD FR-2, FR-3, FR-5, FR-7, FR-9. Run through
// ../E-1_user_path.sh, which pins this file.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'shake_harness.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(resetWorld);
  tearDown(tearDownWorld);

  registerHarnessControls();

  testWidgets('E-1: shake → prompt → Report → sheet over the same screen → '
      'submits route and trigger shake',
      timeout: const Timeout(Duration(seconds: 90)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    final start = h.location;

    await h.shake();
    expect(h.prompts, 1,
        reason: red('E-1:no-prompt', 'a deliberate shake showed ${h.prompts} prompts; '
            'motion listeners=${h.motion.listens}'));
    expect(h.promptText(userPromptText), findsOneWidget,
        reason: red('E-1:prompt-copy', 'the prompt does not read "$userPromptText"'));
    expect(h.promptAction(userPromptAction), findsOneWidget,
        reason: red('E-1:prompt-action', 'the prompt has no "$userPromptAction" action'));

    await h.tapPrompt(userPromptAction);
    expect(h.sheets, 1,
        reason: red('E-1:no-sheet', 'tapping $userPromptAction opened ${h.sheets} sheets'));
    expect(h.location, start,
        reason: red('E-1:navigated', 'the sheet replaced the screen: $start → ${h.location}'));

    await tester.enterText(find.byKey(const Key('feedback_body_field')), 'the timer reset itself');
    await tester.pump();
    await tester.tap(find.byKey(const Key('feedback_send_button')));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    final posts = h.http.feedbackPosts;
    expect(posts.length, 1,
        reason: red('E-1:no-submit', '${posts.length} POST /v1/users/me/feedback calls'));
    final ctx = (posts.single['context'] as Map?) ?? const {};
    expect(ctx['route'], start,
        reason: red('E-1:route-context', 'context.route is ${ctx['route']}, not $start'));
    expect(ctx['trigger'], 'shake',
        reason: red('E-1:trigger-context', 'context.trigger is ${ctx['trigger']}, not shake'));
    await h.close();
  });

  testWidgets('E-1: an ignored prompt fades in 4 s and leaves the screen as it was',
      timeout: const Timeout(Duration(seconds: 90)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    final start = h.location;

    await h.shake();
    // Without this, "gone after 4 s" passes on an app that never prompts.
    expect(h.prompts, 1,
        reason: red('E-1:no-prompt', 'a deliberate shake showed ${h.prompts} prompts; '
            'motion listeners=${h.motion.listens}'));

    await h.motion.idle(tester, promptLifetime + const Duration(milliseconds: 800));
    expect(h.prompts, 0,
        reason: red('E-1:prompt-lingers', 'the prompt is still up after ${promptLifetime.inSeconds} s'));
    expect(h.sheets, 0, reason: red('E-1:sheet-without-tap', 'a sheet opened without a tap'));
    expect(h.location, start,
        reason: red('E-1:navigated', 'an ignored prompt moved the screen: $start → ${h.location}'));
    await h.close();
  });
}
