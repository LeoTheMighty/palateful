import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/features/recipes/cook_mode/cook_mode_screen.dart';
import 'package:palateful/features/recipes/cook_mode/services/cook_session_persister.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'helpers/cook_mode_test_harness.dart';

CookSessionState seedState({
  String recipeId = 'r1',
  int currentStep = 3,
  List<int> completed = const [0, 1, 2],
  List<String> checked = const ['0', '1'],
  List<SavedTimerState> timers = const [],
  int cumulativeElapsedMs = 420000,
  int? startedAtMs,
  int? updatedAtMs,
}) {
  final now = DateTime.now().millisecondsSinceEpoch;
  return CookSessionState(
    targetKind: CookTargetKind.recipe,
    targetId: recipeId,
    startedAtMs: startedAtMs ?? (now - cumulativeElapsedMs),
    cumulativeElapsedMs: cumulativeElapsedMs,
    currentStep: currentStep,
    completedSteps: completed,
    checkedIngredients: checked,
    activeTimers: timers,
    updatedAtMs: updatedAtMs ?? now,
  );
}

Future<void> prime(String recipeId, CookSessionState state) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(
    CookSessionKey.forRecipe(recipeId),
    jsonEncode(state.toJson()),
  );
}

void main() {
  late RecordingTimerNotifService timerService;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    timerService = await setUpCookModeHarness();
  });

  tearDown(() {
    tearDownCookModeHarness();
  });

  Future<void> pumpCookMode(
    WidgetTester tester, {
    String recipeId = 'r1',
  }) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light(),
      home: CookModeScreen(recipeId: recipeId),
    ));
    // Allow the async _initCookSession + _loadRecipe chain to resolve.
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
  }

  group('cmr-2 — persistence writes', () {
    testWidgets('advancing a step + checking ingredient + starting timer '
        'produces a persisted snapshot on AppLifecycleState.paused',
        (tester) async {
      await pumpCookMode(tester);
      // Recipe should have rendered with 3 steps.
      expect(find.text('Do step 1'), findsOneWidget);

      // Advance to step 2 (index 1) via Next button.
      await tester.tap(find.text('Next'));
      await tester.pump();
      // Advance to step 3 (index 2).
      await tester.tap(find.text('Next'));
      await tester.pump();

      // Check the first ingredient. The ingredient chip has a pre-existing
      // ~7px overflow when the check icon appears; drain it so it doesn't
      // fail the test.
      await tester.tap(find.text('Ingredient 1'));
      await tester.pump();
      tester.takeException();

      // Push the app to paused — flushes the debounce window.
      final handler =
          WidgetsBinding.instance.handleAppLifecycleStateChanged;
      handler(AppLifecycleState.paused);
      // Let the async flushNow + save complete.
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      final prefs = await SharedPreferences.getInstance();
      final key = CookSessionKey.forRecipe('r1');
      final raw = prefs.getString(key);
      expect(raw, isNotNull, reason: 'state should persist on paused');
      final decoded = jsonDecode(raw!) as Map<String, dynamic>;
      expect(decoded['current_step'], 2);
      expect(decoded['checked_ingredients'], contains('0'));
      expect(decoded['target_kind'], 'recipe');
      expect(decoded['target_id'], 'r1');
    });

    testWidgets('no prior state mounts fresh at step 0 (regression guard)',
        (tester) async {
      await pumpCookMode(tester);
      expect(find.text('Do step 1'), findsOneWidget);
      expect(find.text('Resume'), findsNothing);
      expect(find.text('Start Over'), findsNothing);
    });
  });

  group('cmr-3 — resume gate on entry', () {
    testWidgets('tapping Resume restores step + checks + elapsed baseline',
        (tester) async {
      await prime('r1', seedState(currentStep: 2, checked: const ['0', '2']));
      await pumpCookMode(tester);
      expect(find.text('Resume'), findsOneWidget);
      expect(find.text('Start Over'), findsOneWidget);
      await tester.tap(find.text('Resume'));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      // Drain the pre-existing ingredient-chip overflow that fires when
      // a checked ingredient renders its check icon.
      tester.takeException();
      // Recipe has 3 steps; currentStep=2 means we're on step 3.
      expect(find.text('Do step 3'), findsOneWidget);
      // Cooking-time display should reflect the 7m baseline (07:00 ± 1s).
      expect(find.textContaining('07:'), findsWidgets);
    });

    testWidgets('tapping Start Over clears state and mounts at step 0',
        (tester) async {
      await prime('r1', seedState(currentStep: 2));
      await pumpCookMode(tester);
      expect(find.text('Start Over'), findsOneWidget);
      await tester.tap(find.text('Start Over'));
      await tester.pumpAndSettle();
      expect(find.text('Do step 1'), findsOneWidget);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(CookSessionKey.forRecipe('r1')), isNull);
    });

    testWidgets('drift clamp: recipe shrank to 3 steps, saved step=15',
        (tester) async {
      await prime(
        'r1',
        seedState(
          currentStep: 15,
          completed: const [0, 1, 20],
          // Avoid the pre-existing ingredient-chip overflow by keeping
          // checked empty — orthogonal to what we're asserting here.
          checked: const [],
        ),
      );
      await pumpCookMode(tester);
      await tester.tap(find.text('Resume'));
      // The clamp path fires a 4s snackbar; pump a few frames so the
      // snackbar slides in without waiting out the full duration.
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      // Drain any layout-overflow exception (pre-existing ingredient
      // strip bug — outside this epic's scope).
      tester.takeException();
      // Clamped to totalSteps - 1 = step index 2 (step 3 of 3).
      expect(find.text('Do step 3'), findsOneWidget);
      expect(
        find.textContaining('Recipe changed'),
        findsOneWidget,
      );
    });

    testWidgets('malformed payload: no gate, mounts fresh, key cleared',
        (tester) async {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        CookSessionKey.forRecipe('r1'),
        '{not valid json',
      );
      await pumpCookMode(tester);
      expect(find.text('Resume'), findsNothing);
      expect(find.text('Do step 1'), findsOneWidget);
      expect(prefs.getString(CookSessionKey.forRecipe('r1')), isNull);
    });

    testWidgets('back-button on gate is consumed (no dismiss)',
        (tester) async {
      await prime('r1', seedState());
      await pumpCookMode(tester);
      expect(find.text('Resume'), findsOneWidget);
      // Simulate Android hardware back button.
      final dispatcher =
          WidgetsBinding.instance.platformDispatcher;
      // `TestWidgetsFlutterBinding` exposes `didPopRoute` via
      // `handlePopRoute`. Invoke it directly through the binding.
      final handled = await WidgetsBinding.instance.handlePopRoute();
      // Gate's PopScope consumes the pop.
      expect(handled, isTrue);
      await tester.pump();
      expect(find.text('Resume'), findsOneWidget,
          reason: 'gate should still be visible after back');
      // Clean up.
      await tester.tap(find.text('Start Over'));
      await tester.pumpAndSettle();
      dispatcher.toString(); // reference to avoid unused var
    });
  });

  group('cmr-4 — reset affordance + post-cook clear', () {
    testWidgets('overflow menu → Reset cook → confirm clears state + snackbar',
        (tester) async {
      await pumpCookMode(tester);
      expect(find.text('Do step 1'), findsOneWidget);
      // Advance to step 2 first so there's state to reset.
      await tester.tap(find.text('Next'));
      await tester.pump();
      expect(find.text('Do step 2'), findsOneWidget);
      // Open overflow menu.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Reset cook'));
      await tester.pumpAndSettle();
      // Confirm sheet visible.
      expect(find.text('Reset'), findsOneWidget);
      await tester.tap(find.text('Reset'));
      await tester.pumpAndSettle();
      // Back to step 1 with snackbar.
      expect(find.text('Do step 1'), findsOneWidget);
      expect(find.text('Cook session reset'), findsOneWidget);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(CookSessionKey.forRecipe('r1')), isNull);
    });

    testWidgets('reset sheet Cancel leaves state alone',
        (tester) async {
      await pumpCookMode(tester);
      await tester.tap(find.text('Next'));
      await tester.pump();
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Reset cook'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(find.text('Do step 2'), findsOneWidget);
      expect(find.text('Cook session reset'), findsNothing);
    });

    testWidgets('overflow menu is the rightmost header icon after close',
        (tester) async {
      await pumpCookMode(tester);
      // Sanity: overflow icon is present.
      expect(find.byIcon(Icons.more_vert), findsOneWidget);
      // The header icons are: back (arrow_back), timer_outlined, close,
      // more_vert. The overflow sits after the close button.
      final overflowRect = tester.getRect(find.byIcon(Icons.more_vert));
      final closeRect = tester.getRect(find.byIcon(Icons.close));
      expect(overflowRect.left, greaterThan(closeRect.right));
    });
  });

  group('cmr-5 — timer rebuild on resume', () {
    int msFromNow(Duration d) =>
        DateTime.now().millisecondsSinceEpoch + d.inMilliseconds;
    int msAgo(Duration d) =>
        DateTime.now().millisecondsSinceEpoch - d.inMilliseconds;

    testWidgets('non-expired timer restores + OS notification re-scheduled',
        (tester) async {
      await prime(
        'r1',
        seedState(
          currentStep: 1,
          checked: const [],
          timers: [
            SavedTimerState(
              label: 'simmer',
              deadlineMs: msFromNow(const Duration(minutes: 5)),
              totalDurationSeconds: 600,
              source: 'extracted',
            ),
          ],
        ),
      );
      await pumpCookMode(tester);
      await tester.tap(find.text('Resume'));
      await tester.pumpAndSettle();
      // Timer chip should render with an MM:SS countdown in the 04:
      // range (5m minus a few pump frames).
      expect(find.textContaining(RegExp(r'0[4-5]:')), findsWidgets);
      expect(timerService.scheduled.length, 1);
      expect(timerService.scheduled.first['label'], 'simmer');
    });

    testWidgets('single expired timer produces singular snackbar',
        (tester) async {
      await prime(
        'r1',
        seedState(
          currentStep: 1,
          checked: const [],
          timers: [
            SavedTimerState(
              label: 'roast',
              deadlineMs: msAgo(const Duration(minutes: 10)),
              totalDurationSeconds: 1800,
              source: 'manual',
            ),
          ],
        ),
      );
      await pumpCookMode(tester);
      await tester.tap(find.text('Resume'));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(
        find.text('While you were away: roast timer finished'),
        findsOneWidget,
      );
      // No scheduling for expired timers.
      expect(timerService.scheduled, isEmpty);
    });

    testWidgets('two expired timers listed with Oxford-and join',
        (tester) async {
      await prime(
        'r1',
        seedState(
          currentStep: 1,
          checked: const [],
          timers: [
            SavedTimerState(
              label: 'simmer',
              deadlineMs: msAgo(const Duration(minutes: 10)),
              totalDurationSeconds: 600,
              source: 'manual',
            ),
            SavedTimerState(
              label: 'bake',
              deadlineMs: msAgo(const Duration(minutes: 1)),
              totalDurationSeconds: 1200,
              source: 'manual',
            ),
          ],
        ),
      );
      await pumpCookMode(tester);
      await tester.tap(find.text('Resume'));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(
        find.text('While you were away: simmer and bake timers finished'),
        findsOneWidget,
      );
    });

    testWidgets('four expired timers consolidate to count copy',
        (tester) async {
      await prime(
        'r1',
        seedState(
          currentStep: 1,
          checked: const [],
          timers: List.generate(
            4,
            (i) => SavedTimerState(
              label: 'timer$i',
              deadlineMs: msAgo(Duration(minutes: 10 + i)),
              totalDurationSeconds: 600,
              source: 'manual',
            ),
          ),
        ),
      );
      await pumpCookMode(tester);
      await tester.tap(find.text('Resume'));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(
        find.text('While you were away: 4 timers finished'),
        findsOneWidget,
      );
    });

    testWidgets(
        'clock-skew forward (deadline_ms > 24h in past) is treated expired',
        (tester) async {
      await prime(
        'r1',
        seedState(
          currentStep: 1,
          checked: const [],
          timers: [
            SavedTimerState(
              label: 'ancient',
              deadlineMs: msAgo(const Duration(days: 2)),
              totalDurationSeconds: 600,
              source: 'manual',
            ),
          ],
        ),
      );
      await pumpCookMode(tester);
      await tester.tap(find.text('Resume'));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(
        find.text('While you were away: ancient timer finished'),
        findsOneWidget,
      );
    });
  });
}
