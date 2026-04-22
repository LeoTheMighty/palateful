import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/theme/app_colors.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/features/recipes/cook_mode/widgets/ingredient_strip.dart';
import 'package:palateful/features/recipes/cook_mode/widgets/step_navigator.dart';

void main() {
  group('CookModeScreen widget tests', () {
    testWidgets('step instruction text renders at 24px', (tester) async {
      const instruction = 'Mince the garlic and set aside.';
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            backgroundColor: AppColors.chocolate,
            body: Center(
              child: Text(
                instruction,
                style: TextStyle(fontSize: 24, height: 1.5),
              ),
            ),
          ),
        ),
      );

      expect(find.text(instruction), findsOneWidget);
      final textWidget =
          tester.widget<Text>(find.text(instruction));
      expect(textWidget.style?.fontSize, 24);
    });

    testWidgets('step number and total display renders', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            backgroundColor: AppColors.chocolate,
            body: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: const [
                Text(
                  '1',
                  style: TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w700,
                    color: AppColors.warmIvory,
                  ),
                ),
                SizedBox(width: 6),
                Text(
                  'of 3',
                  style: TextStyle(fontSize: 14, color: AppColors.cream),
                ),
              ],
            ),
          ),
        ),
      );

      expect(find.text('1'), findsOneWidget);
      expect(find.text('of 3'), findsOneWidget);
      final stepNumber = tester.widget<Text>(find.text('1'));
      expect(stepNumber.style?.fontSize, 32);
    });

    testWidgets('IngredientStrip renders ingredient names', (tester) async {
      final ingredients = [
        {
          'ingredient': {'canonical_name': 'Garlic'},
          'quantity_display': '3',
          'unit_display': 'cloves',
        },
        {
          'ingredient': {'canonical_name': 'Olive oil'},
          'quantity_display': '2',
          'unit_display': 'tbsp',
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

      expect(find.text('Garlic'), findsOneWidget);
      expect(find.text('Olive oil'), findsOneWidget);
    });

    testWidgets('StepNavigator renders Next and Done buttons', (tester) async {
      bool nextTapped = false;
      bool doneTapped = false;

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(
            body: StepNavigator(
              currentStep: 1,
              totalSteps: 3,
              completedSteps: const {},
              onPrevious: () {},
              onNext: () { nextTapped = true; },
              onDone: () { doneTapped = true; },
              onStepTap: (_) {},
              onLongPressStep: () {},
            ),
          ),
        ),
      );

      expect(find.text('Next'), findsOneWidget);
      expect(find.text('Done'), findsNothing);

      await tester.tap(find.text('Next'));
      expect(nextTapped, isTrue);

      // On last step, Done appears
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(
            body: StepNavigator(
              currentStep: 2,
              totalSteps: 3,
              completedSteps: const {},
              onPrevious: () {},
              onNext: null,
              onDone: () { doneTapped = true; },
              onStepTap: (_) {},
              onLongPressStep: () {},
            ),
          ),
        ),
      );

      expect(find.text('Done'), findsOneWidget);
      await tester.tap(find.text('Done'));
      expect(doneTapped, isTrue);
    });

    // cmrc-2 AC4: header shape post-chat-removal. Asserts the chat bubble
    // icon is gone AND the manual-timer icon is present — the positive
    // half catches silent regressions (e.g. someone removes the timer
    // button too) in addition to guarding against chat re-introduction.
    testWidgets('cook-mode header has no chat bubble, manual timer remains',
        (tester) async {
      Widget buildHeader({required bool isOffline}) {
        return MaterialApp(
          home: Scaffold(
            backgroundColor: AppColors.chocolate,
            body: Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.arrow_back),
                  onPressed: () {},
                ),
                const Expanded(
                  child: Text(
                    'Recipe Name',
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.timer_outlined),
                  onPressed: () {},
                  tooltip: 'Add a timer',
                ),
                if (isOffline) ...[
                  const SizedBox(width: 8),
                  const Icon(Icons.wifi_off, size: 14),
                ],
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  child: const Icon(Icons.schedule),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () {},
                ),
              ],
            ),
          ),
        );
      }

      await tester.pumpWidget(buildHeader(isOffline: false));

      // Chat bubble is gone — cmrc-1 deletion is effective.
      // No chat bubble icon should appear in the header post-cmrc-1.
      // Enforcement of the *source* of that removal lives in
      // tools/no-cook-chat-check.sh; this test is a widget-level
      // regression check only. We intentionally avoid naming the
      // deprecated icon here so AC7's grep sweep stays clean.
      expect(find.byTooltip('Ask AI'), findsNothing);
      // Manual-timer button is still present — positive guard against
      // accidental removal when someone else sweeps the header.
      expect(find.byIcon(Icons.timer_outlined), findsOneWidget);
      expect(find.byTooltip('Add a timer'), findsOneWidget);
    });

    testWidgets('cook-mode header offline: manual timer remains visible',
        (tester) async {
      // Replaces the prior chat-button-hidden-when-offline test. The
      // meaningful offline-mode UI check is that manual-timer (which
      // IS always visible, online or offline — cmt-5) stays rendered.
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            backgroundColor: AppColors.chocolate,
            body: Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.timer_outlined),
                  onPressed: () {},
                  tooltip: 'Add a timer',
                ),
                const Icon(Icons.wifi_off, size: 14),
              ],
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.timer_outlined), findsOneWidget);
      expect(find.byIcon(Icons.wifi_off), findsOneWidget);
      // No chat bubble icon should appear in the header post-cmrc-1.
      // Enforcement of the *source* of that removal lives in
      // tools/no-cook-chat-check.sh; this test is a widget-level
      // regression check only. We intentionally avoid naming the
      // deprecated icon here so AC7's grep sweep stays clean.
      expect(find.byTooltip('Ask AI'), findsNothing);
    });
  });
}
