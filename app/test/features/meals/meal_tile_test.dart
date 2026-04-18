import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/widgets/meal_tile.dart';

MealSummary _summary({
  int componentCount = 2,
  List<String> images = const [],
  String name = 'Kale Salad Meal',
  String? description,
  bool archived = false,
}) =>
    MealSummary(
      id: 'meal-1',
      name: name,
      recipeBookId: 'book-1',
      componentCount: componentCount,
      componentImageUrls: images,
      description: description,
      archivedAt: archived ? DateTime(2026, 4, 18, 12) : null,
      updatedAt: DateTime(2026, 4, 18, 10),
    );

Widget _wrap(Widget w) => MaterialApp(
      home: Scaffold(body: Center(child: SizedBox(width: 300, child: w))),
    );

void main() {
  testWidgets('renders name + N recipes badge', (tester) async {
    await tester.pumpWidget(_wrap(
      MealTile(meal: _summary(componentCount: 3), onTap: () {}),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Kale Salad Meal'), findsOneWidget);
    expect(find.text('3 recipes'), findsOneWidget);
  });

  testWidgets('renders 2-up collage with 2 components', (tester) async {
    await tester.pumpWidget(_wrap(
      MealTile(
        meal: _summary(componentCount: 2, images: []),
        onTap: () {},
      ),
    ));
    await tester.pumpAndSettle();

    // Two placeholder icons — one per cell.
    expect(find.byIcon(Icons.restaurant), findsNWidgets(2));
  });

  testWidgets('renders +N overlay at 5+ components', (tester) async {
    await tester.pumpWidget(_wrap(
      MealTile(meal: _summary(componentCount: 6), onTap: () {}),
    ));
    await tester.pumpAndSettle();

    expect(find.text('+2'), findsOneWidget);
  });

  testWidgets('description appears when non-empty', (tester) async {
    await tester.pumpWidget(_wrap(
      MealTile(
        meal: _summary(description: 'A quick weeknight combo'),
        onTap: () {},
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('A quick weeknight combo'), findsOneWidget);
  });

  testWidgets('tap fires onTap', (tester) async {
    bool tapped = false;
    await tester.pumpWidget(_wrap(
      MealTile(meal: _summary(), onTap: () => tapped = true),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Kale Salad Meal'));
    await tester.pump();
    expect(tapped, true);
  });
}
