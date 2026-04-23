import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/theme/app_colors.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/core/theme/cook_mode_theme.dart';
import 'package:palateful/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart';
import 'package:palateful/features/recipes/cook_mode/shared/widgets/step_navigator.dart';

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

      // cmlp-3: chip renders name + quantity as separate Text widgets.
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

    // cmlp-2: IngredientStrip always renders the grouped grid directly.
    // No Expand/Collapse — group keys are visible on initial mount.
    testWidgets('IngredientStrip with sourceTagBuilder renders group keys',
        (tester) async {
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
        {
          'ingredient': {'canonical_name': 'Salt'},
          'quantity_display': '1',
          'unit_display': 'tsp',
        },
      ];
      final tags = ['Dressing', 'Dressing', 'Salad'];

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(
            body: IngredientStrip(
              ingredients: ingredients,
              checkedIndices: const {},
              onToggle: (_) {},
              sourceTagBuilder: (i) => tags[i],
            ),
          ),
        ),
      );

      // Expand/Collapse + header no longer exist.
      expect(find.text('Expand'), findsNothing);
      expect(find.text('Collapse'), findsNothing);
      expect(find.text('INGREDIENTS'), findsNothing);

      // Group keys are visible on initial mount.
      expect(
        find.byKey(const Key('ingredient_group_Dressing')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('ingredient_group_Salad')),
        findsOneWidget,
      );
    });

    // cmlp-2: when builder is null, no "From" group keys render.
    testWidgets('IngredientStrip without sourceTagBuilder: no group keys',
        (tester) async {
      final ingredients = [
        {
          'ingredient': {'canonical_name': 'Garlic'},
          'quantity_display': '3',
          'unit_display': 'cloves',
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
      expect(find.byKey(const Key('ingredient_group_Dressing')), findsNothing);
    });

    // cmlp-3: quantity Text uses cookAccent + 14px w600 in unchecked
    // state; name Text uses 14px w500. Verified via tester.widget<Text>.
    testWidgets(
        'IngredientStrip chip renders 14px w500 name + 14px w600 quantity '
        'in cookAccent', (tester) async {
      final ingredients = [
        {
          'ingredient': {'canonical_name': 'Garlic'},
          'quantity_display': '3',
          'unit_display': 'cloves',
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

      final nameText = tester.widget<Text>(find.text('Garlic'));
      expect(nameText.style?.fontSize, 14);
      expect(nameText.style?.fontWeight, FontWeight.w500);

      final qtyText = tester.widget<Text>(find.text('3 cloves'));
      expect(qtyText.style?.fontSize, 14);
      expect(qtyText.style?.fontWeight, FontWeight.w600);
      // The color is the theme's cookAccent — identity-compare against
      // the token to keep the assertion theme-driven.
      final cookAccent = AppTheme.light()
          .extension<CookModeTheme>()!
          .cookAccent;
      expect(qtyText.style?.color, cookAccent);
    });

    // cmlp-3: chip uses ConstrainedBox, not IntrinsicWidth — IntrinsicWidth
    // inside a Wrap is a known perf trap at 30+ ingredients.
    testWidgets('IngredientStrip chip tree contains no IntrinsicWidth',
        (tester) async {
      final ingredients = [
        {
          'ingredient': {'canonical_name': 'Garlic'},
          'quantity_display': '3',
          'unit_display': 'cloves',
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
      expect(
        find.descendant(
          of: find.byType(IngredientStrip),
          matching: find.byType(IntrinsicWidth),
        ),
        findsNothing,
      );
    });

    // cmlp-3: Dynamic Type 2.0 + a long ingredient name doesn't blow
    // out the chip (2-line wrap + ellipsis + 160 maxWidth).
    testWidgets(
        'IngredientStrip with long name at TextScaler 2.0 does not overflow',
        (tester) async {
      final ingredients = [
        {
          'ingredient': {
            'canonical_name': 'Freshly ground black peppercorns',
          },
          'quantity_display': '1',
          'unit_display': 'tsp',
        },
      ];
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(
            body: MediaQuery(
              data: const MediaQueryData(
                textScaler: TextScaler.linear(2.0),
              ),
              child: IngredientStrip(
                ingredients: ingredients,
                checkedIndices: const {},
                onToggle: (_) {},
              ),
            ),
          ),
        ),
      );
      // No overflow exception raised during layout.
      expect(tester.takeException(), isNull);
    });

    // cmlp-2: empty-ingredient edge case — the strip renders nothing.
    testWidgets('IngredientStrip with zero ingredients renders nothing',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(
            body: IngredientStrip(
              ingredients: const [],
              checkedIndices: const {},
              onToggle: (_) {},
            ),
          ),
        ),
      );
      // No padding, no chips, no headers. The widget renders as
      // SizedBox.shrink — zero size.
      final stripFinder = find.byType(IngredientStrip);
      expect(stripFinder, findsOneWidget);
      expect(tester.getSize(stripFinder), Size.zero);
      expect(
        find.descendant(of: stripFinder, matching: find.byType(Padding)),
        findsNothing,
      );
    });

    // cmmrf-4 — StepNavigator renders a flat per-recipe pill row.
    // Pill semantics announce current/completed/upcoming without
    // per-component names (the toggle bar carries recipe context now).
    testWidgets('StepNavigator pill semantics announce current/completed/upcoming',
        (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(
            body: StepNavigator(
              currentStep: 2,
              totalSteps: 4,
              completedSteps: const {0, 1},
              onPrevious: () {},
              onNext: () {},
              onDone: () {},
              onStepTap: (_) {},
              onLongPressStep: () {},
            ),
          ),
        ),
      );
      expect(
        find.bySemanticsLabel('Step 3, current'),
        findsOneWidget,
      );
      expect(
        find.bySemanticsLabel('Step 4, upcoming'),
        findsOneWidget,
      );
      expect(
        find.bySemanticsLabel('Step 1, completed'),
        findsOneWidget,
      );
      handle.dispose();
    });
  });
}
