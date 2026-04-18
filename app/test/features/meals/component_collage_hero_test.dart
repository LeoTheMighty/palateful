import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/widgets/component_collage_hero.dart';

MealComponent _c(int i, {bool available = true, String? imageUrl}) =>
    MealComponent(
      recipeId: 'r$i',
      name: 'R$i',
      orderIndex: i,
      available: available,
      imageUrl: imageUrl,
    );

Widget _wrap(Widget w) => MaterialApp(
      home: Scaffold(
        body: SizedBox(
          height: 200,
          width: 300,
          child: w,
        ),
      ),
    );

void main() {
  testWidgets('empty components list does not crash', (tester) async {
    await tester.pumpWidget(_wrap(
      const ComponentCollageHero(components: []),
    ));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.restaurant), findsOneWidget);
  });

  testWidgets('2 components renders two cells', (tester) async {
    await tester.pumpWidget(_wrap(
      ComponentCollageHero(components: [_c(0), _c(1)]),
    ));
    await tester.pumpAndSettle();

    // Both are placeholders (no image URLs).
    expect(find.byIcon(Icons.restaurant), findsNWidgets(2));
  });

  testWidgets('3 components renders three cells', (tester) async {
    await tester.pumpWidget(_wrap(
      ComponentCollageHero(components: [_c(0), _c(1), _c(2)]),
    ));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.restaurant), findsNWidgets(3));
  });

  testWidgets('4 components renders 4 cells without +N overlay',
      (tester) async {
    await tester.pumpWidget(_wrap(
      ComponentCollageHero(components: [_c(0), _c(1), _c(2), _c(3)]),
    ));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.restaurant), findsNWidgets(4));
    expect(find.textContaining('+'), findsNothing);
  });

  testWidgets('6 components renders +2 overlay', (tester) async {
    await tester.pumpWidget(_wrap(
      ComponentCollageHero(
        components: [_c(0), _c(1), _c(2), _c(3), _c(4), _c(5)],
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('+2'), findsOneWidget);
  });

  testWidgets('partial unavailability shows "N of M" chip', (tester) async {
    await tester.pumpWidget(_wrap(
      ComponentCollageHero(
        components: [_c(0, available: false), _c(1)],
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('1 of 2'), findsOneWidget);
  });

  testWidgets('all-unavailable shows blocking chip', (tester) async {
    await tester.pumpWidget(_wrap(
      ComponentCollageHero(
        components: [
          _c(0, available: false),
          _c(1, available: false),
        ],
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('All components unavailable'), findsOneWidget);
  });

  testWidgets('1 component + aspectRatio wraps with AspectRatio widget',
      (tester) async {
    await tester.pumpWidget(_wrap(
      ComponentCollageHero(
        components: [_c(0)],
        aspectRatio: 16 / 9,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.byType(AspectRatio), findsOneWidget);
  });
}
