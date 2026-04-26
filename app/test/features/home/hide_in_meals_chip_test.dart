import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/hide_in_meals_chip.dart';

void main() {
  Future<void> pumpChip(
    WidgetTester tester, {
    required int visibleCount,
    required int hiddenCount,
    required bool active,
    VoidCallback? onTap,
  }) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: HideInMealsChip(
          visibleCount: visibleCount,
          hiddenCount: hiddenCount,
          active: active,
          onTap: onTap ?? () {},
        ),
      ),
    ));
  }

  group('HideInMealsChip — copy', () {
    testWidgets('active + meals present → "N recipes · M hidden in meals"',
        (tester) async {
      await pumpChip(tester,
          visibleCount: 32, hiddenCount: 8, active: true);
      expect(find.text('32 recipes · 8 hidden in meals'), findsOneWidget);
      expect(find.byIcon(Icons.visibility_off_outlined), findsOneWidget);
    });

    testWidgets('inactive + meals present → "N recipes · M shown in meals"',
        (tester) async {
      await pumpChip(tester,
          visibleCount: 40, hiddenCount: 8, active: false);
      expect(find.text('40 recipes · 8 shown in meals'), findsOneWidget);
      expect(find.byIcon(Icons.visibility_outlined), findsOneWidget);
    });

    testWidgets('active + no meals → "N recipes" only', (tester) async {
      await pumpChip(tester,
          visibleCount: 32, hiddenCount: 0, active: true);
      expect(find.text('32 recipes'), findsOneWidget);
      expect(find.textContaining('hidden'), findsNothing);
    });

    testWidgets('inactive + no meals → "N recipes" only', (tester) async {
      await pumpChip(tester,
          visibleCount: 32, hiddenCount: 0, active: false);
      expect(find.text('32 recipes'), findsOneWidget);
      expect(find.textContaining('shown'), findsNothing);
    });

    testWidgets('singular noun for visibleCount==1', (tester) async {
      await pumpChip(tester,
          visibleCount: 1, hiddenCount: 0, active: true);
      expect(find.text('1 recipe'), findsOneWidget);
    });
  });

  group('HideInMealsChip — interaction', () {
    testWidgets('tap fires onTap', (tester) async {
      var taps = 0;
      await pumpChip(tester,
          visibleCount: 5,
          hiddenCount: 1,
          active: true,
          onTap: () => taps++);
      await tester.tap(find.byKey(const ValueKey('hide_in_meals_chip')));
      await tester.pump();
      expect(taps, 1);
    });
  });

  group('HideInMealsEmptyState', () {
    testWidgets('renders celebratory copy + show-all CTA', (tester) async {
      var shown = 0;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: HideInMealsEmptyState(onShowAll: () => shown++),
        ),
      ));
      expect(find.text('Everything is in a Meal'), findsOneWidget);
      expect(find.text('Show all recipes'), findsOneWidget);
      expect(find.byIcon(Icons.celebration_outlined), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('hide_in_meals_show_all')));
      await tester.pump();
      expect(shown, 1);
    });
  });
}
