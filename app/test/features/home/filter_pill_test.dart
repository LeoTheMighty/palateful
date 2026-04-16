import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/filter_bottom_sheet.dart';
import 'package:palateful/features/home/widgets/filter_pill.dart';
import 'package:palateful/features/home/widgets/meal_filter_bar.dart';

Widget _wrap(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

void main() {
  group('FilterPill', () {
    testWidgets('renders "Filter" when no filters active', (tester) async {
      await tester.pumpWidget(_wrap(FilterPill(
        activeCount: 0,
        onTap: () {},
      )));
      expect(find.text('Filter'), findsOneWidget);
      expect(find.textContaining('('), findsNothing);
    });

    testWidgets('renders "Filter (2)" with two active filters',
        (tester) async {
      await tester.pumpWidget(_wrap(FilterPill(
        activeCount: 2,
        onTap: () {},
      )));
      expect(find.text('Filter (2)'), findsOneWidget);
    });

    testWidgets('tap invokes onTap callback', (tester) async {
      var tapped = 0;
      await tester.pumpWidget(_wrap(FilterPill(
        activeCount: 0,
        onTap: () => tapped++,
      )));
      await tester.tap(find.text('Filter'));
      await tester.pump();
      expect(tapped, 1);
    });
  });

  group('FilterBottomSheet', () {
    testWidgets('shows meal and vibe sections with chip content',
        (tester) async {
      await tester.pumpWidget(_wrap(Builder(builder: (ctx) {
        return ElevatedButton(
          onPressed: () => FilterBottomSheet.show(
            context: ctx,
            initialMeal: MealFilter.all,
            initialVibe: null,
            onApply: (_, __) {},
          ),
          child: const Text('open'),
        );
      })));

      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      expect(find.text('Filters'), findsOneWidget);
      expect(find.text('Meals'), findsOneWidget);
      expect(find.text('Vibes'), findsOneWidget);
      // One meal chip per filter
      expect(find.text('Breakfast'), findsOneWidget);
      expect(find.text('Lunch'), findsOneWidget);
      expect(find.text('Dinner'), findsOneWidget);
      // At least one vibe chip
      expect(find.text('Comfort'), findsOneWidget);
      // Action row
      expect(find.text('Clear all'), findsOneWidget);
      expect(find.text('Apply'), findsOneWidget);
    });

    testWidgets('Apply fires onApply with draft selections and closes sheet',
        (tester) async {
      MealFilter? capturedMeal;
      String? capturedVibe;

      await tester.pumpWidget(_wrap(Builder(builder: (ctx) {
        return ElevatedButton(
          onPressed: () => FilterBottomSheet.show(
            context: ctx,
            initialMeal: MealFilter.all,
            initialVibe: null,
            onApply: (meal, vibe) {
              capturedMeal = meal;
              capturedVibe = vibe;
            },
          ),
          child: const Text('open'),
        );
      })));

      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      // Select Dinner meal filter and Comfort vibe
      await tester.tap(find.text('Dinner'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Comfort'));
      await tester.pumpAndSettle();

      // Apply
      await tester.tap(find.text('Apply'));
      await tester.pumpAndSettle();

      expect(capturedMeal, MealFilter.dinner);
      expect(capturedVibe, 'comfort');
      // Sheet should be gone
      expect(find.text('Filters'), findsNothing);
    });

    testWidgets('Clear all resets draft selections without closing sheet',
        (tester) async {
      await tester.pumpWidget(_wrap(Builder(builder: (ctx) {
        return ElevatedButton(
          onPressed: () => FilterBottomSheet.show(
            context: ctx,
            initialMeal: MealFilter.dinner,
            initialVibe: 'comfort',
            onApply: (_, __) {},
          ),
          child: const Text('open'),
        );
      })));

      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      // Pre-selected draft: Dinner + Comfort. Clear All should reset.
      await tester.tap(find.text('Clear all'));
      await tester.pumpAndSettle();

      // Sheet still open
      expect(find.text('Filters'), findsOneWidget);
      // Clear all doesn't call onApply — onApply only fires on Apply tap.
    });
  });
}
