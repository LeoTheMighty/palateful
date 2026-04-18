import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/meals/models/meal.dart';

void main() {
  group('Meal.fromJson', () {
    test('round-trips a happy-path payload', () {
      final meal = Meal.fromJson({
        'id': 'meal-1',
        'name': 'Kale Salad Meal',
        'description': 'tonight',
        'recipe_book_id': 'book-1',
        'archived_at': null,
        'created_at': '2026-04-18T10:00:00Z',
        'updated_at': '2026-04-18T10:05:00Z',
        'components': [
          {
            'recipe_id': 'r1',
            'name': 'Kale Salad',
            'image_url': 'https://img/kale.jpg',
            'prep_time': 10,
            'cook_time': 0,
            'book_name': 'Dinners',
            'order_index': 0,
            'available': true,
            'last_known_name': null,
          },
          {
            'recipe_id': 'r2',
            'name': 'Lemon Dressing',
            'image_url': null,
            'prep_time': 5,
            'cook_time': null,
            'book_name': 'Dinners',
            'order_index': 1,
            'available': true,
          },
        ],
      });

      expect(meal.id, 'meal-1');
      expect(meal.name, 'Kale Salad Meal');
      expect(meal.description, 'tonight');
      expect(meal.isArchived, false);
      expect(meal.componentCount, 2);
      expect(meal.availableComponentCount, 2);
      expect(meal.components.first.displayName, 'Kale Salad');
      expect(meal.components.first.imageUrl, 'https://img/kale.jpg');
      expect(meal.components[1].cookTime, null);
    });

    test('handles archived meal + unavailable components', () {
      final meal = Meal.fromJson({
        'id': 'meal-1',
        'name': 'Old Meal',
        'recipe_book_id': 'book-1',
        'archived_at': '2026-04-18T12:00:00Z',
        'created_at': '2026-04-10T10:00:00Z',
        'updated_at': '2026-04-18T12:00:00Z',
        'components': [
          {
            'recipe_id': 'r1',
            'name': '',
            'order_index': 0,
            'available': false,
            'last_known_name': 'Deleted Recipe',
          },
        ],
      });

      expect(meal.isArchived, true);
      expect(meal.componentCount, 1);
      expect(meal.availableComponentCount, 0);
      expect(meal.components.first.available, false);
      expect(meal.components.first.displayName, 'Deleted Recipe');
    });

    test('empty components default to []', () {
      final meal = Meal.fromJson({
        'id': 'meal-1',
        'name': 'X',
        'recipe_book_id': 'book-1',
        'created_at': '2026-04-18T10:00:00Z',
        'updated_at': '2026-04-18T10:00:00Z',
      });
      expect(meal.components, isEmpty);
    });
  });

  group('Meal.copyWith', () {
    Meal _base() => Meal(
          id: 'meal-1',
          name: 'N',
          description: 'D',
          recipeBookId: 'b',
          archivedAt: DateTime(2026, 4, 18, 12),
          createdAt: DateTime(2026, 4, 1),
          updatedAt: DateTime(2026, 4, 18),
        );

    test('overrides name + description', () {
      final m = _base().copyWith(name: 'N2', description: 'D2');
      expect(m.name, 'N2');
      expect(m.description, 'D2');
    });

    test('clearArchivedAt wipes the archive flag', () {
      final m = _base().copyWith(clearArchivedAt: true);
      expect(m.archivedAt, null);
      expect(m.isArchived, false);
    });

    test('overrides components', () {
      final m = _base().copyWith(components: [
        const MealComponent(recipeId: 'x', name: 'x', orderIndex: 0)
      ]);
      expect(m.components.length, 1);
    });
  });

  group('MealSummary.fromJson', () {
    test('parses grid-tile payload', () {
      final s = MealSummary.fromJson({
        'id': 'meal-1',
        'name': 'Kale Salad Meal',
        'description': null,
        'recipe_book_id': 'book-1',
        'component_count': 2,
        'component_image_urls': [
          'https://img/a.jpg',
          'https://img/b.jpg',
        ],
        'archived_at': null,
        'updated_at': '2026-04-18T10:00:00Z',
      });
      expect(s.id, 'meal-1');
      expect(s.componentCount, 2);
      expect(s.componentImageUrls.length, 2);
      expect(s.isArchived, false);
    });

    test('handles archived + defaults', () {
      final s = MealSummary.fromJson({
        'id': 'meal-2',
        'name': 'X',
        'recipe_book_id': 'book-1',
        'archived_at': '2026-04-18T10:00:00Z',
        'updated_at': '2026-04-18T10:00:00Z',
      });
      expect(s.isArchived, true);
      expect(s.componentCount, 0);
      expect(s.componentImageUrls, isEmpty);
    });
  });
}
