import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/widgets/meal_tile.dart';
import 'package:palateful/features/recipe_books/widgets/book_recipe_card.dart';
import 'package:palateful/shared/widgets/mixed_card_metrics.dart';

/// rbv101 — the book-detail mixed grid interleaves recipes and meals.
/// Both tile types must render at the same size in every layout the
/// screen can pick (single-column `Column` on phones, `GridView` on
/// tablet/desktop), regardless of how much text each one carries.

Map<String, dynamic> _recipe({
  String name = 'Roast Chicken',
  int? prepTime,
  int? cookTime,
  int? servings,
  List<String> tags = const [],
}) =>
    <String, dynamic>{
      'id': 'recipe-1',
      'name': name,
      'image_url': null,
      'prep_time': prepTime,
      'cook_time': cookTime,
      'servings': servings,
      'tags': tags,
    };

MealSummary _meal({
  String name = 'Sunday Dinner',
  String? description,
  int componentCount = 2,
}) =>
    MealSummary(
      id: 'meal-1',
      name: name,
      recipeBookId: 'book-1',
      componentCount: componentCount,
      componentImageUrls: const [],
      componentRecipeIds: const [],
      description: description,
      updatedAt: DateTime(2026, 4, 18, 10),
    );

/// Mirrors the book-detail single-column branch: cards stacked in a
/// plain `Column`, each free to pick its own height.
Widget _singleColumn(List<Widget> cards) => MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: Column(children: cards),
        ),
      ),
    );

/// Mirrors the book-detail multi-column branch.
Widget _grid(List<Widget> cards, {int columns = 2}) => MaterialApp(
      home: Scaffold(
        body: GridView.builder(
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
            mainAxisExtent: kMixedCardExtent,
          ),
          itemCount: cards.length,
          itemBuilder: (context, i) => cards[i],
        ),
      ),
    );

Future<void> _setPhone(WidgetTester tester) async {
  tester.view.physicalSize = const Size(390 * 3, 844 * 3);
  tester.view.devicePixelRatio = 3.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
}

void main() {
  group('book-detail mixed cards — uniform sizing (rbv101)', () {
    testWidgets('recipe card and meal tile match in the single-column layout',
        (tester) async {
      await _setPhone(tester);

      await tester.pumpWidget(_singleColumn([
        BookRecipeCard(
          recipe: _recipe(prepTime: 15, cookTime: 45, servings: 4, tags: const [
            'dinner',
            'chicken',
            'roast',
          ]),
          onTap: () {},
        ),
        MealTile(meal: _meal(), onTap: () {}),
      ]));
      await tester.pumpAndSettle();

      final recipeSize = tester.getSize(find.byType(BookRecipeCard));
      final mealSize = tester.getSize(find.byType(MealTile));

      expect(recipeSize.height, mealSize.height,
          reason: 'meals and recipes must be the same size in the book view');
      expect(recipeSize.height, kMixedCardHeight);
      expect(mealSize.height, kMixedCardHeight);
    });

    testWidgets('card height is content-independent', (tester) async {
      await _setPhone(tester);

      // Minimal content on both sides — no metadata, no tags, no
      // description — must still produce the same box.
      await tester.pumpWidget(_singleColumn([
        BookRecipeCard(recipe: _recipe(name: 'Toast'), onTap: () {}),
        MealTile(meal: _meal(name: 'Snack', componentCount: 0), onTap: () {}),
      ]));
      await tester.pumpAndSettle();

      expect(tester.getSize(find.byType(BookRecipeCard)).height,
          kMixedCardHeight);
      expect(tester.getSize(find.byType(MealTile)).height, kMixedCardHeight);
    });

    testWidgets('long content does not overflow the fixed card box',
        (tester) async {
      await _setPhone(tester);

      await tester.pumpWidget(_singleColumn([
        BookRecipeCard(
          recipe: _recipe(
            name: 'A very long recipe name that will certainly wrap around',
            prepTime: 120,
            cookTime: 240,
            servings: 12,
            tags: const [
              'weeknight',
              'comfort-food',
              'one-pan',
              'kid-friendly',
              'make-ahead',
              'freezer-friendly',
            ],
          ),
          onTap: () {},
        ),
        MealTile(
          meal: _meal(
            name: 'An extremely long meal name that keeps on going and going',
            description:
                'A long description that would push the tile taller than '
                'its recipe neighbour if the info block were not fixed.',
            componentCount: 6,
          ),
          onTap: () {},
        ),
      ]));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(tester.getSize(find.byType(BookRecipeCard)).height,
          kMixedCardHeight);
      expect(tester.getSize(find.byType(MealTile)).height, kMixedCardHeight);
    });

    testWidgets('typical content is not clipped by the fixed info block',
        (tester) async {
      await _setPhone(tester);

      await tester.pumpWidget(_singleColumn([
        BookRecipeCard(
          recipe: _recipe(
            prepTime: 15,
            cookTime: 45,
            servings: 4,
            tags: const ['dinner', 'chicken'],
          ),
          onTap: () {},
        ),
        MealTile(
          meal: _meal(description: 'Roast + two sides'),
          onTap: () {},
        ),
      ]));
      await tester.pumpAndSettle();

      // The card body is everything above the bottom margin.
      final recipeBodyBottom =
          tester.getRect(find.byType(BookRecipeCard)).top +
              kMixedCardHeroHeight +
              kMixedCardInfoHeight;
      expect(tester.getRect(find.byType(Chip).last).bottom,
          lessThanOrEqualTo(recipeBodyBottom),
          reason: 'recipe tag row must fit inside kMixedCardInfoHeight');

      final mealBodyBottom = tester.getRect(find.byType(MealTile)).top +
          kMixedCardHeroHeight +
          kMixedCardInfoHeight;
      expect(
          tester
              .getRect(find.byKey(const ValueKey('meal-tile-chips')))
              .bottom,
          lessThanOrEqualTo(mealBodyBottom),
          reason: 'meal chip line must fit inside kMixedCardInfoHeight');
    });

    testWidgets('grid cells match the card height so nothing is clipped',
        (tester) async {
      tester.view.physicalSize = const Size(1200 * 2, 1000 * 2);
      tester.view.devicePixelRatio = 2.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(_grid([
        BookRecipeCard(
          recipe: _recipe(prepTime: 15, cookTime: 45, servings: 4),
          onTap: () {},
        ),
        MealTile(meal: _meal(description: 'Roast + sides'), onTap: () {}),
      ], columns: 3));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      final recipeSize = tester.getSize(find.byType(BookRecipeCard));
      final mealSize = tester.getSize(find.byType(MealTile));
      expect(recipeSize, mealSize);
      expect(recipeSize.height, kMixedCardExtent);
    });
  });
}
