// E-3 (P0): a shake never interrupts what the user is doing.
// expectations.md E-3; PRD FR-5, FR-6. Run through ../E-3_no_interruption.sh,
// which pins this file.
//
// Each busy state is checked in its own boot, and each test ends by clearing
// the busy state and shaking again: that shake must prompt, or the "nothing
// appeared" above it proves nothing. On unbuilt code the busy checks pass
// for free and that closing shake is what fails, by name.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/router/app_router.dart';
import 'package:palateful/features/profile/widgets/feedback_sheet.dart';

import 'shake_harness.dart';

class _Busy extends StatefulWidget {
  const _Busy({super.key, required this.field});
  final TextEditingController field;
  @override
  State<_Busy> createState() => _BusyState();
}

class _BusyState extends State<_Busy> {
  int ticks = 0;
  Timer? _t;
  final focus = FocusNode();
  @override
  void initState() {
    super.initState();
    _t = Timer.periodic(const Duration(seconds: 1), (_) => setState(() => ticks++));
  }

  @override
  void dispose() {
    _t?.cancel();
    focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text('busy $ticks')),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: TextField(controller: widget.field, focusNode: focus),
        ),
      );
}

Future<GlobalKey<_BusyState>> _pushBusy(WidgetTester tester, TextEditingController c) async {
  final key = GlobalKey<_BusyState>();
  unawaited(rootNavigatorKey.currentState!
      .push(MaterialPageRoute<void>(builder: (_) => _Busy(key: key, field: c))));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 500));
  return key;
}

Future<void> _closingShakeMustPrompt(ShakeHarness h, String state) async {
  await h.waitOutCooldown();
  await h.shake();
  expect(h.prompts, 1,
      reason: red('E-3:$state:positive-control-no-prompt',
          'with "$state" cleared, a deliberate shake showed ${h.prompts} prompts, so the '
          '0 above proves nothing (motion listeners=${h.motion.listens})'));
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(resetWorld);
  tearDown(tearDownWorld);

  registerHarnessControls();

  testWidgets('E-3: typing — a focused field with text gets no prompt and keeps '
      'its text and focus',
      timeout: const Timeout(Duration(seconds: 90)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    final c = TextEditingController();
    final busy = await _pushBusy(tester, c);
    await tester.tap(find.byType(TextField));
    await tester.enterText(find.byType(TextField), 'half a recipe');
    await tester.pump();
    final focusedBefore = FocusManager.instance.primaryFocus;
    expect(busy.currentState!.focus.hasFocus, isTrue,
        reason: 'EVAL-PRECONDITION the field did not take focus');
    final loc = h.location;

    await h.shake();
    expect(h.prompts, 0, reason: red('E-3:typing:prompted', 'a prompt appeared while typing'));
    expect(c.text, 'half a recipe', reason: red('E-3:typing:text-changed', 'text became "${c.text}"'));
    expect(FocusManager.instance.primaryFocus, same(focusedBefore),
        reason: red('E-3:typing:focus-moved', 'the shake moved focus'));
    expect(h.location, loc, reason: red('E-3:typing:navigated', '$loc → ${h.location}'));

    busy.currentState!.focus.unfocus();
    await tester.pump();
    await _closingShakeMustPrompt(h, 'typing');
    await h.close();
  });

  testWidgets('E-3: a dialog on the root navigator gets no prompt',
      timeout: const Timeout(Duration(seconds: 90)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    unawaited(showDialog<void>(
        context: rootNavigatorKey.currentContext!,
        builder: (_) => const AlertDialog(content: Text('Delete this recipe?'))));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byType(AlertDialog), findsOneWidget,
        reason: 'EVAL-PRECONDITION the dialog did not open');

    await h.shake();
    expect(h.prompts, 0, reason: red('E-3:dialog:prompted', 'a prompt appeared over a dialog'));
    expect(find.byType(AlertDialog), findsOneWidget,
        reason: red('E-3:dialog:dismissed', 'the shake closed the dialog'));

    rootNavigatorKey.currentState!.pop();
    await tester.pump(const Duration(milliseconds: 400));
    await _closingShakeMustPrompt(h, 'dialog');
    await h.close();
  });

  testWidgets("E-3: a bottom sheet on a tab's navigator gets no prompt",
      timeout: const Timeout(Duration(seconds: 90)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    final tabCtx = tester.element(find.byType(Scaffold).last);
    final tabNav = Navigator.of(tabCtx);
    expect(tabNav, isNot(same(rootNavigatorKey.currentState)),
        reason: "EVAL-PRECONDITION the context is not under a tab's navigator");
    unawaited(showModalBottomSheet<void>(
        context: tabCtx, builder: (_) => const SizedBox(height: 200, child: Text('Sort by'))));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Sort by'), findsOneWidget,
        reason: 'EVAL-PRECONDITION the sheet did not open');

    await h.shake();
    expect(h.prompts, 0, reason: red('E-3:tab-sheet:prompted', "a prompt appeared over a tab's sheet"));
    expect(find.text('Sort by'), findsOneWidget,
        reason: red('E-3:tab-sheet:dismissed', 'the shake closed the sheet'));

    tabNav.pop();
    await tester.pump(const Duration(milliseconds: 400));
    await _closingShakeMustPrompt(h, 'tab-sheet');
    await h.close();
  });

  testWidgets('E-3: with the feedback sheet already open, a second shake adds nothing',
      timeout: const Timeout(Duration(seconds: 90)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    await h.shake();
    expect(h.prompts, 1,
        reason: red('E-3:sheet-open:no-first-prompt',
            'the first shake showed ${h.prompts} prompts (motion listeners=${h.motion.listens})'));
    await h.tapPrompt(userPromptAction);
    expect(h.sheets, 1, reason: red('E-3:sheet-open:no-sheet', '${h.sheets} sheets after the tap'));

    await h.waitOutCooldown();
    await h.shake();
    expect(h.prompts, 0, reason: red('E-3:sheet-open:prompted', 'a prompt appeared over the sheet'));
    expect(h.sheets, 1, reason: red('E-3:sheet-open:stacked', '${h.sheets} sheets after a second shake'));
    await h.close();
  });

  testWidgets('E-3: the screen beneath keeps its State, timer and text through an '
      'ignored prompt and an opened-and-closed sheet',
      timeout: const Timeout(Duration(seconds: 120)), (tester) async {
    final h = await ShakeHarness.boot(tester, isAdmin: false, ring: 'everyone');
    final c = TextEditingController(text: 'two cups of flour');
    final busy = await _pushBusy(tester, c);
    final state0 = busy.currentState!;
    final loc = h.location;

    await h.shake();
    expect(h.prompts, 1,
        reason: red('E-3:timer:no-prompt',
            'a deliberate shake showed ${h.prompts} prompts (motion listeners=${h.motion.listens})'));
    final ticksAtPrompt = state0.ticks;
    await h.motion.idle(tester, promptLifetime + const Duration(milliseconds: 800));
    expect(h.prompts, 0, reason: red('E-3:timer:prompt-lingers', 'the prompt did not fade'));
    expect(busy.currentState, same(state0), reason: red('E-3:timer:state-lost', 'the State was rebuilt'));
    expect(state0.ticks, greaterThan(ticksAtPrompt),
        reason: red('E-3:timer:stopped', 'the timer stopped while the prompt was up'));

    await h.waitOutCooldown();
    await h.shake();
    expect(h.prompts, 1,
        reason: red('E-3:timer:no-second-prompt', 'the second shake showed ${h.prompts} prompts'));
    await h.tapPrompt(userPromptAction);
    expect(h.sheets, 1, reason: red('E-3:timer:no-sheet', '${h.sheets} sheets after the tap'));
    final ticksAtSheet = state0.ticks;
    await tester.pump(const Duration(seconds: 2));
    // Close it the way back or a swipe-down does: pop the sheet's own route.
    // (A barrier tap is not reliable: Profile's sheet is scroll-controlled
    // and can fill the screen.)
    Navigator.of(tester.element(find.byType(FeedbackSheet))).pop();
    for (var i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    diag('after closing the sheet: sheets=${h.sheets}');
    expect(h.sheets, 0, reason: red('E-3:timer:sheet-stuck', 'the sheet did not close'));

    expect(busy.currentState, same(state0), reason: red('E-3:timer:state-lost', 'the State was rebuilt'));
    expect(state0.ticks, greaterThan(ticksAtSheet),
        reason: red('E-3:timer:stopped', 'the timer stopped under the sheet'));
    expect(c.text, 'two cups of flour', reason: red('E-3:timer:text-changed', 'text became "${c.text}"'));
    expect(h.location, loc, reason: red('E-3:timer:navigated', '$loc → ${h.location}'));
    await h.close();
  });
}
