// hmp-4 — FilterBottomSheet extensions: Show type. (The "Hide
// components" toggle previously lived in the sheet too; it moved to
// the HideInMealsChip surface in epic recipe-list-organization /
// Story 5. The default value is now ON.)
//
// Pure widget tests. Validates the sheet exposes the Show control,
// that state plumbs through onApply, and that Clear all resets it.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/filter_bottom_sheet.dart';
import 'package:palateful/features/home/widgets/meal_filter_bar.dart';

Future<HomeFilterState?> _openSheetAndApply(
  WidgetTester tester, {
  required HomeFilterState initial,
  required Future<void> Function(WidgetTester) interact,
}) async {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
  HomeFilterState? captured;
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: Builder(
        builder: (context) => ElevatedButton(
          onPressed: () => FilterBottomSheet.show(
            context: context,
            initialState: initial,
            onApply: (s) => captured = s,
          ),
          child: const Text('open'),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
  await interact(tester);
  await tester.ensureVisible(find.text('Apply'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Apply'));
  await tester.pumpAndSettle();
  return captured;
}

void main() {
  testWidgets('defaults — sheet renders Show row; Hide toggle removed',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => ElevatedButton(
            onPressed: () => FilterBottomSheet.show(
              context: context,
              initialState: HomeFilterState.defaults,
              onApply: (_) {},
            ),
            child: const Text('open'),
          ),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    expect(find.text('Show'), findsOneWidget);
    expect(find.text('All'), findsWidgets); // Show's "All" + Meals' "All"
    expect(find.text('Recipes only'), findsOneWidget);
    expect(find.text('Meals only'), findsOneWidget);
    // Story 5: the hide-components toggle moved to HideInMealsChip.
    expect(find.text('Hide components of Meals'), findsNothing);
    expect(
      find.byKey(const ValueKey('hide-components-of-meals-toggle')),
      findsNothing,
    );
  });

  testWidgets('Apply "Meals only" — state flows through onApply',
      (tester) async {
    final state = await _openSheetAndApply(
      tester,
      initial: HomeFilterState.defaults,
      interact: (t) async {
        await t.tap(find.text('Meals only'));
        await t.pumpAndSettle();
      },
    );
    expect(state, isNotNull);
    expect(state!.showType, ShowTypeFilter.mealsOnly);
    // Story 5: hide-components default flipped to ON; the sheet
    // round-trips the value but no longer surfaces a control for it.
    expect(state.hideComponentsOfMeals, isTrue);
    expect(state.isDefault, isFalse);
  });

  testWidgets('Clear all resets fields to (now hide-ON) defaults',
      (tester) async {
    final state = await _openSheetAndApply(
      tester,
      initial: const HomeFilterState(
        meal: MealFilter.dinner,
        vibe: null,
        sort: SortOption.newest,
        showType: ShowTypeFilter.mealsOnly,
        // Story 5: cleared defaults put hide back to ON, so we start
        // from hide=false to make Clear All visibly different.
        hideComponentsOfMeals: false,
      ),
      interact: (t) async {
        await t.tap(find.text('Clear all'));
        await t.pumpAndSettle();
      },
    );
    expect(state, isNotNull);
    expect(state!.isDefault, isTrue);
    expect(state.hideComponentsOfMeals, isTrue);
  });

  test('HomeFilterState.isDefault reflects new defaults', () {
    expect(
      const HomeFilterState(
        meal: MealFilter.all,
        vibe: null,
        sort: SortOption.best,
        showType: ShowTypeFilter.mealsOnly,
        hideComponentsOfMeals: true,
      ).isDefault,
      isFalse,
    );
    // Story 5: hide-components default is now true, so an explicit
    // false value is non-default.
    expect(
      const HomeFilterState(
        meal: MealFilter.all,
        vibe: null,
        sort: SortOption.best,
        showType: ShowTypeFilter.all,
        hideComponentsOfMeals: false,
      ).isDefault,
      isFalse,
    );
    expect(HomeFilterState.defaults.isDefault, isTrue);
    expect(HomeFilterState.defaults.hideComponentsOfMeals, isTrue);
  });
}
