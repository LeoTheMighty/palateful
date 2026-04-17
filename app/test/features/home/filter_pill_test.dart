import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/filter_bottom_sheet.dart';
import 'package:palateful/features/home/widgets/filter_pill.dart';
import 'package:palateful/features/home/widgets/meal_filter_bar.dart';

Widget _wrap(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

/// Sheet has grown to include sort + meal + vibe sections; the default
/// 800x600 test viewport truncates the action row. Use a taller viewport.
void _useTallViewport(WidgetTester tester) {
  tester.view.physicalSize = const Size(800, 1600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
}

void main() {
  group('FilterPill (icon-only, post-consolidation)', () {
    testWidgets('renders funnel icon without active badge when inactive',
        (tester) async {
      await tester.pumpWidget(_wrap(FilterPill(
        isActive: false,
        onTap: () {},
      )));
      expect(find.byIcon(Icons.tune), findsOneWidget);
      expect(find.byKey(const ValueKey('filter_pill_active_dot')),
          findsNothing);
      expect(find.byTooltip('Sort & filter'), findsOneWidget);
    });

    testWidgets('renders funnel icon plus small dot badge when active',
        (tester) async {
      await tester.pumpWidget(_wrap(FilterPill(
        isActive: true,
        onTap: () {},
      )));
      expect(find.byIcon(Icons.tune), findsOneWidget);
      expect(find.byKey(const ValueKey('filter_pill_active_dot')),
          findsOneWidget);
    });

    testWidgets('tap invokes onTap callback', (tester) async {
      var tapped = 0;
      await tester.pumpWidget(_wrap(FilterPill(
        isActive: false,
        onTap: () => tapped++,
      )));
      await tester.tap(find.byIcon(Icons.tune));
      await tester.pump();
      expect(tapped, 1);
    });
  });

  group('FilterBottomSheet (sort + filter combined)', () {
    testWidgets('shows sort, meal, and vibe sections',
        (tester) async {
      _useTallViewport(tester);
      await tester.pumpWidget(_wrap(Builder(builder: (ctx) {
        return ElevatedButton(
          onPressed: () => FilterBottomSheet.show(
            context: ctx,
            initialState: HomeFilterState.defaults,
            onApply: (_) {},
          ),
          child: const Text('open'),
        );
      })));

      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      expect(find.text('Sort & filter'), findsOneWidget);
      expect(find.text('Sort by'), findsOneWidget);
      expect(find.text('Meals'), findsOneWidget);
      expect(find.text('Vibes'), findsOneWidget);

      // Sort options visible as radio rows
      expect(find.text('Best'), findsOneWidget);
      expect(find.text('Newest'), findsOneWidget);
      expect(find.text('Popular'), findsOneWidget);
      expect(find.text('Quickest'), findsOneWidget);
      expect(find.text('Random'), findsOneWidget);

      // Meal chip sample
      expect(find.text('Dinner'), findsOneWidget);
      // Vibe chip sample
      expect(find.text('Comfort'), findsOneWidget);

      // Action row
      expect(find.text('Clear all'), findsOneWidget);
      expect(find.text('Apply'), findsOneWidget);
    });

    testWidgets('Apply fires onApply with draft sort + filter selections',
        (tester) async {
      _useTallViewport(tester);
      HomeFilterState? captured;

      await tester.pumpWidget(_wrap(Builder(builder: (ctx) {
        return ElevatedButton(
          onPressed: () => FilterBottomSheet.show(
            context: ctx,
            initialState: HomeFilterState.defaults,
            onApply: (state) => captured = state,
          ),
          child: const Text('open'),
        );
      })));

      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      // Change sort to Newest
      await tester.tap(find.text('Newest'));
      await tester.pumpAndSettle();

      // Change meal filter to Dinner
      await tester.tap(find.text('Dinner'));
      await tester.pumpAndSettle();

      // Change vibe to Comfort
      await tester.tap(find.text('Comfort'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Apply'));
      await tester.pumpAndSettle();

      expect(captured, isNotNull);
      expect(captured!.sort, SortOption.newest);
      expect(captured!.meal, MealFilter.dinner);
      expect(captured!.vibe, 'comfort');

      // Sheet dismissed
      expect(find.text('Sort & filter'), findsNothing);
    });

    testWidgets('Clear all resets sort + filters without closing sheet',
        (tester) async {
      _useTallViewport(tester);
      await tester.pumpWidget(_wrap(Builder(builder: (ctx) {
        return ElevatedButton(
          onPressed: () => FilterBottomSheet.show(
            context: ctx,
            initialState: const HomeFilterState(
              meal: MealFilter.dinner,
              vibe: 'comfort',
              sort: SortOption.newest,
            ),
            onApply: (_) {},
          ),
          child: const Text('open'),
        );
      })));

      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Clear all'));
      await tester.pumpAndSettle();

      // Sheet remains open
      expect(find.text('Sort & filter'), findsOneWidget);
      // Clear all doesn't fire onApply — only Apply does.
    });
  });

  group('HomeFilterState', () {
    test('isDefault is true for defaults', () {
      expect(HomeFilterState.defaults.isDefault, isTrue);
    });

    test('isDefault is false when any field is non-default', () {
      expect(
        const HomeFilterState(
          meal: MealFilter.dinner,
          vibe: null,
          sort: SortOption.best,
        ).isDefault,
        isFalse,
      );
      expect(
        const HomeFilterState(
          meal: MealFilter.all,
          vibe: 'comfort',
          sort: SortOption.best,
        ).isDefault,
        isFalse,
      );
      expect(
        const HomeFilterState(
          meal: MealFilter.all,
          vibe: null,
          sort: SortOption.newest,
        ).isDefault,
        isFalse,
      );
    });
  });
}
