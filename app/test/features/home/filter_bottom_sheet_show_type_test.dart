// hmp-4 — FilterBottomSheet extensions: Show type + Hide components.
//
// Pure widget tests. Validates the sheet exposes the two new controls,
// that state plumbs through onApply, and that Clear all resets both.

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
  testWidgets('defaults — sheet renders Show + Hide rows at their defaults',
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
    expect(find.text('Hide components of Meals'), findsOneWidget);

    // Switch renders OFF by default.
    final sw = tester.widget<SwitchListTile>(
      find.byKey(const ValueKey('hide-components-of-meals-toggle')),
    );
    expect(sw.value, isFalse);
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
    expect(state.hideComponentsOfMeals, isFalse);
    expect(state.isDefault, isFalse);
  });

  testWidgets('Apply hide-components toggle ON — flows through', (tester) async {
    final state = await _openSheetAndApply(
      tester,
      initial: HomeFilterState.defaults,
      interact: (t) async {
        await t.tap(
          find.byKey(const ValueKey('hide-components-of-meals-toggle')),
        );
        await t.pumpAndSettle();
      },
    );
    expect(state, isNotNull);
    expect(state!.hideComponentsOfMeals, isTrue);
    expect(state.showType, ShowTypeFilter.all);
    expect(state.isDefault, isFalse);
  });

  testWidgets('Clear all resets new fields alongside existing ones',
      (tester) async {
    final state = await _openSheetAndApply(
      tester,
      initial: const HomeFilterState(
        meal: MealFilter.dinner,
        vibe: null,
        sort: SortOption.newest,
        showType: ShowTypeFilter.mealsOnly,
        hideComponentsOfMeals: true,
      ),
      interact: (t) async {
        await t.tap(find.text('Clear all'));
        await t.pumpAndSettle();
      },
    );
    expect(state, isNotNull);
    expect(state!.isDefault, isTrue);
  });

  test('HomeFilterState.isDefault reflects new fields', () {
    expect(
      const HomeFilterState(
        meal: MealFilter.all,
        vibe: null,
        sort: SortOption.best,
        showType: ShowTypeFilter.mealsOnly,
        hideComponentsOfMeals: false,
      ).isDefault,
      isFalse,
    );
    expect(
      const HomeFilterState(
        meal: MealFilter.all,
        vibe: null,
        sort: SortOption.best,
        showType: ShowTypeFilter.all,
        hideComponentsOfMeals: true,
      ).isDefault,
      isFalse,
    );
    expect(HomeFilterState.defaults.isDefault, isTrue);
  });
}
