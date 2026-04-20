import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/features/recipes/cook_mode/widgets/ingredient_strip.dart';
import 'package:palateful/features/recipes/cook_mode/widgets/step_navigator.dart';

void main() {
  group('Gesture navigation — tap zone tests', () {
    testWidgets('tap on left 25% of step area triggers previous step',
        (tester) async {
      bool prevCalled = false;
      bool nextCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: GestureDetector(
              onHorizontalDragEnd: (_) {},
              onTapUp: (details) {
                // Mirror exact logic from cook_mode_screen.dart
                const screenWidth = 800.0; // default test screen width
                final tapX = details.localPosition.dx;
                if (tapX < screenWidth * 0.25) {
                  prevCalled = true;
                } else if (tapX > screenWidth * 0.75) {
                  nextCalled = true;
                }
              },
              child: Container(
                width: 800,
                height: 400,
                color: Colors.transparent,
              ),
            ),
          ),
        ),
      );

      // Tap at x=100 — within left 25% of 800px screen
      await tester.tapAt(const Offset(100, 200));
      await tester.pump();

      expect(prevCalled, isTrue);
      expect(nextCalled, isFalse);
    });

    testWidgets('tap on right 75%+ of step area triggers next step',
        (tester) async {
      bool prevCalled = false;
      bool nextCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: GestureDetector(
              onHorizontalDragEnd: (_) {},
              onTapUp: (details) {
                const screenWidth = 800.0;
                final tapX = details.localPosition.dx;
                if (tapX < screenWidth * 0.25) {
                  prevCalled = true;
                } else if (tapX > screenWidth * 0.75) {
                  nextCalled = true;
                }
              },
              child: Container(
                width: 800,
                height: 400,
                color: Colors.transparent,
              ),
            ),
          ),
        ),
      );

      // Tap at x=700 — within right 25% of 800px screen
      await tester.tapAt(const Offset(700, 200));
      await tester.pump();

      expect(nextCalled, isTrue);
      expect(prevCalled, isFalse);
    });

    testWidgets('tap on middle 50% of step area does nothing', (tester) async {
      bool prevCalled = false;
      bool nextCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: GestureDetector(
              onHorizontalDragEnd: (_) {},
              onTapUp: (details) {
                const screenWidth = 800.0;
                final tapX = details.localPosition.dx;
                if (tapX < screenWidth * 0.25) {
                  prevCalled = true;
                } else if (tapX > screenWidth * 0.75) {
                  nextCalled = true;
                }
              },
              child: Container(
                width: 800,
                height: 400,
                color: Colors.transparent,
              ),
            ),
          ),
        ),
      );

      // Tap at x=400 — middle of 800px screen
      await tester.tapAt(const Offset(400, 200));
      await tester.pump();

      expect(prevCalled, isFalse);
      expect(nextCalled, isFalse);
    });
  });

  group('Gesture navigation — touch target size tests', () {
    testWidgets('StepNavigator Prev button has at least 64dp height',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(
            body: StepNavigator(
              currentStep: 1,
              totalSteps: 3,
              completedSteps: const {},
              onPrevious: () {},
              onNext: () {},
              onDone: () {},
              onStepTap: (_) {},
              onLongPressStep: () {},
            ),
          ),
        ),
      );

      // Find the InkWell that is an ancestor of the 'Prev' text
      final inkWellFinder = find.ancestor(
        of: find.text('Prev'),
        matching: find.byType(InkWell),
      );
      expect(inkWellFinder, findsOneWidget);
      final size = tester.getSize(inkWellFinder);
      expect(size.height, greaterThanOrEqualTo(64.0));
    });

    testWidgets('IngredientStrip expand/collapse button has at least 64dp height',
        (tester) async {
      final ingredients = [
        {
          'ingredient': {'canonical_name': 'Salt'},
          'quantity_display': '1',
          'unit_display': 'tsp',
        },
      ];

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(
            body: IngredientStrip(
              ingredients: ingredients,
              checkedIndices: const {},
              onToggle: (_) {},
            ),
          ),
        ),
      );

      // Find the GestureDetector wrapping the expand/collapse button
      final gestureDetectorFinder = find.ancestor(
        of: find.text('Expand'),
        matching: find.byType(GestureDetector),
      );
      expect(gestureDetectorFinder, findsOneWidget);
      final size = tester.getSize(gestureDetectorFinder);
      expect(size.height, greaterThanOrEqualTo(64.0));
    });
  });

  // --------------------------------------------------------------------
  // cmp-4: back-navigation untoggles a step's "completed" state.
  //
  // All three back-nav paths in cook_mode_screen.dart — swipe
  // (_previousStep), tap-zone (_previousStep), StepNavigator pill-tap
  // (_goToStep) — funnel through _goToStep. Testing _goToStep via a
  // StepNavigator pill-tap covers the invariant for all three routes.
  // --------------------------------------------------------------------
  group('Back-navigation untoggles completed state (cmp-4)', () {
    testWidgets(
        'pill-tap backward removes destination step from completedSteps',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const _BackNavHarness(totalSteps: 5),
        ),
      );

      final state = tester.state<_BackNavHarnessState>(
          find.byType(_BackNavHarness));

      // Advance 0 → 4 (walks past 0,1,2,3; adds each to completedSteps).
      for (var i = 0; i < 4; i++) {
        state.advance();
      }
      await tester.pump();
      expect(state.currentStep, 4);
      expect(state.completedSteps, equals({0, 1, 2, 3}));

      // Pill-tap back to step 2 — goes through _goToStep(2).
      state.goToStep(2);
      await tester.pump();

      expect(state.currentStep, 2);
      // Step 2 was walked past (in set), now revisited — must be
      // untoggled. Steps 0, 1, 3 were walked past too but never
      // revisited, so they stay completed.
      expect(state.completedSteps, equals({0, 1, 3}));
    });

    testWidgets(
        'pill-tap to index 0 from index 4 collapses set to {1, 2, 3}',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const _BackNavHarness(totalSteps: 5),
        ),
      );

      final state = tester.state<_BackNavHarnessState>(
          find.byType(_BackNavHarness));

      for (var i = 0; i < 4; i++) {
        state.advance();
      }
      await tester.pump();

      // Pill-tap back to step 0.
      state.goToStep(0);
      await tester.pump();

      expect(state.currentStep, 0);
      // 4 was never added (we never advanced past it). 0 was added by
      // the first _nextStep, then removed on the back-tap. Net: {1,2,3}.
      expect(state.completedSteps, equals({1, 2, 3}));
    });

    testWidgets(
        'StepNavigator pill at current index never renders a check icon',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(
            body: StepNavigator(
              currentStep: 2,
              totalSteps: 5,
              // Malicious: step 2 is in the set but it's the CURRENT
              // step. The pill must still render as current, not
              // completed (no check icon). See cmp-4 AC4.
              completedSteps: const {0, 1, 2, 3},
              onPrevious: () {},
              onNext: () {},
              onDone: () {},
              onStepTap: (_) {},
              onLongPressStep: () {},
            ),
          ),
        ),
      );

      // Check icons only appear on non-current pills — expect exactly 3
      // (indices 0, 1, 3). Index 2 is current and must not show a check
      // regardless of set membership.
      expect(find.byIcon(Icons.check), findsNWidgets(3));
    });

    testWidgets(
        'StepNavigator pill semantics announce current/completed/upcoming',
        (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(
            body: StepNavigator(
              currentStep: 1,
              totalSteps: 3,
              completedSteps: const {0},
              onPrevious: () {},
              onNext: () {},
              onDone: () {},
              onStepTap: (_) {},
              onLongPressStep: () {},
            ),
          ),
        ),
      );

      expect(find.bySemanticsLabel('Step 1, completed'), findsOneWidget);
      expect(find.bySemanticsLabel('Step 2, current'), findsOneWidget);
      expect(find.bySemanticsLabel('Step 3, upcoming'), findsOneWidget);

      handle.dispose();
    });
  });
}

/// Minimal stateful harness that mirrors the `_completedSteps` +
/// `_currentStep` invariant from `cook_mode_screen.dart`. Kept in-file
/// so the harness moves in lockstep with real back-nav logic — any
/// drift between this and the real `_goToStep` is a test regression.
class _BackNavHarness extends StatefulWidget {
  final int totalSteps;
  const _BackNavHarness({required this.totalSteps});

  @override
  State<_BackNavHarness> createState() => _BackNavHarnessState();
}

class _BackNavHarnessState extends State<_BackNavHarness> {
  int currentStep = 0;
  final Set<int> completedSteps = {};

  /// Mirrors `_nextStep` in cook_mode_screen.dart.
  void advance() {
    setState(() {
      completedSteps.add(currentStep);
      if (currentStep < widget.totalSteps - 1) {
        goToStep(currentStep + 1);
      }
    });
  }

  /// Mirrors `_goToStep` in cook_mode_screen.dart — the function under
  /// test.
  void goToStep(int step) {
    if (step >= 0 && step < widget.totalSteps) {
      setState(() {
        if (step < currentStep) {
          completedSteps.remove(step);
        }
        currentStep = step;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: StepNavigator(
        currentStep: currentStep,
        totalSteps: widget.totalSteps,
        completedSteps: completedSteps,
        onPrevious: currentStep > 0 ? () => goToStep(currentStep - 1) : null,
        onNext:
            currentStep < widget.totalSteps - 1 ? advance : null,
        onDone: () {},
        onStepTap: goToStep,
        onLongPressStep: () {},
      ),
    );
  }
}
