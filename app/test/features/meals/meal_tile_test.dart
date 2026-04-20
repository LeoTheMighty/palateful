import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/widgets/meal_tile.dart';

MealSummary _summary({
  int componentCount = 2,
  List<String> images = const [],
  List<String> recipeIds = const [],
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
      componentRecipeIds: recipeIds,
      description: description,
      archivedAt: archived ? DateTime(2026, 4, 18, 12) : null,
      updatedAt: DateTime(2026, 4, 18, 10),
    );

Widget _wrap(Widget w) => MaterialApp(
      home: Scaffold(body: Center(child: SizedBox(width: 300, child: w))),
    );

void main() {
  group('MealTile v2 — no resolver (backward-compat)', () {
    testWidgets('falls back to "(N recipes)" chip-row text', (tester) async {
      await tester.pumpWidget(_wrap(
        MealTile(meal: _summary(componentCount: 3), onTap: () {}),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Kale Salad Meal'), findsOneWidget);
      expect(find.text('(3 recipes)'), findsOneWidget);
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
  });

  group('MealTile v2 — chip row from resolver', () {
    testWidgets('1 component renders single name', (tester) async {
      final names = {'r1': 'Kale Salad'};
      await tester.pumpWidget(_wrap(
        MealTile(
          meal: _summary(componentCount: 1, recipeIds: ['r1']),
          onTap: () {},
          componentNameResolver: (id) => names[id],
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Kale Salad'), findsOneWidget);
    });

    testWidgets('2 components join with middle dot', (tester) async {
      final names = {'r1': 'Kale Salad', 'r2': 'Lemon Dressing'};
      await tester.pumpWidget(_wrap(
        MealTile(
          meal: _summary(componentCount: 2, recipeIds: ['r1', 'r2']),
          onTap: () {},
          componentNameResolver: (id) => names[id],
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Kale Salad · Lemon Dressing'), findsOneWidget);
    });

    testWidgets('3 components collapse to "+1"', (tester) async {
      final names = {'r1': 'Kale Salad', 'r2': 'Lemon Dressing', 'r3': 'Miso'};
      await tester.pumpWidget(_wrap(
        MealTile(
          meal: _summary(componentCount: 3, recipeIds: ['r1', 'r2', 'r3']),
          onTap: () {},
          componentNameResolver: (id) => names[id],
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Kale Salad · Lemon Dressing · +1'), findsOneWidget);
    });

    testWidgets('5 components collapse to "+3"', (tester) async {
      final names = {
        'r1': 'A',
        'r2': 'B',
        'r3': 'C',
        'r4': 'D',
        'r5': 'E',
      };
      await tester.pumpWidget(_wrap(
        MealTile(
          meal: _summary(
            componentCount: 5,
            recipeIds: const ['r1', 'r2', 'r3', 'r4', 'r5'],
          ),
          onTap: () {},
          componentNameResolver: (id) => names[id],
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('A · B · +3'), findsOneWidget);
    });

    testWidgets('unresolvable component appends single "(archived)"',
        (tester) async {
      // r2 and r3 unresolved — only one (archived) suffix should land.
      final names = {'r1': 'Kale Salad'};
      await tester.pumpWidget(_wrap(
        MealTile(
          meal: _summary(componentCount: 3, recipeIds: ['r1', 'r2', 'r3']),
          onTap: () {},
          componentNameResolver: (id) => names[id],
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Kale Salad · (archived)'), findsOneWidget);
    });

    testWidgets('all-unresolvable falls back to "(N recipes)"',
        (tester) async {
      await tester.pumpWidget(_wrap(
        MealTile(
          meal: _summary(componentCount: 2, recipeIds: ['ra', 'rb']),
          onTap: () {},
          componentNameResolver: (_) => null,
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('(2 recipes)'), findsOneWidget);
    });
  });

  group('MealTile v2 — chrome', () {
    testWidgets('renders "Meal" pill with layers icon', (tester) async {
      await tester.pumpWidget(_wrap(
        MealTile(meal: _summary(), onTap: () {}),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Meal'), findsOneWidget);
      expect(find.byIcon(Icons.layers_outlined), findsOneWidget);
    });

    testWidgets('accent border is 2px on Card shape', (tester) async {
      await tester.pumpWidget(_wrap(
        MealTile(meal: _summary(), onTap: () {}),
      ));
      await tester.pumpAndSettle();
      final card = tester.widget<Card>(find.byType(Card).first);
      final shape = card.shape as RoundedRectangleBorder;
      expect(shape.side.width, 2);
    });

    testWidgets('favorite star hidden when onFavoriteToggle is null',
        (tester) async {
      await tester.pumpWidget(_wrap(
        MealTile(meal: _summary(), onTap: () {}),
      ));
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.favorite), findsNothing);
      expect(find.byIcon(Icons.favorite_border), findsNothing);
    });

    testWidgets('favorite star renders + tap fires onFavoriteToggle',
        (tester) async {
      var toggled = 0;
      await tester.pumpWidget(_wrap(
        MealTile(
          meal: _summary(),
          onTap: () {},
          isFavorited: false,
          onFavoriteToggle: () => toggled++,
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.favorite_border), findsOneWidget);
      await tester.tap(find.byIcon(Icons.favorite_border));
      await tester.pump();
      expect(toggled, 1);
    });

    testWidgets('favorited state uses filled heart icon', (tester) async {
      await tester.pumpWidget(_wrap(
        MealTile(
          meal: _summary(),
          onTap: () {},
          isFavorited: true,
          onFavoriteToggle: () {},
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.favorite), findsOneWidget);
      expect(find.byIcon(Icons.favorite_border), findsNothing);
    });

    testWidgets('selected:true overlays the collage with a check_circle',
        (tester) async {
      await tester.pumpWidget(_wrap(
        MealTile(meal: _summary(), onTap: () {}, selected: true),
      ));
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.check_circle), findsOneWidget);
    });

    testWidgets('selected:false hides the checkmark', (tester) async {
      await tester.pumpWidget(_wrap(
        MealTile(meal: _summary(), onTap: () {}),
      ));
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.check_circle), findsNothing);
    });
  });
}
