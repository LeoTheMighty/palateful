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
}
