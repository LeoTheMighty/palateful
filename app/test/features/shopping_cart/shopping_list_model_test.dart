import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list.dart';

void main() {
  group('ShoppingList.fromJson', () {
    test('parses a complete valid JSON object', () {
      final json = {
        'id': 'list-1',
        'name': 'Weekly Groceries',
        'status': 'active',
        'owner_id': 'user-1',
        'is_shared': false,
        'items': [],
        'members': [],
        'created_at': '2024-01-01T00:00:00.000Z',
        'updated_at': '2024-01-02T00:00:00.000Z',
      };

      final list = ShoppingList.fromJson(json);
      expect(list.id, 'list-1');
      expect(list.name, 'Weekly Groceries');
      expect(list.updatedAt, DateTime.parse('2024-01-02T00:00:00.000Z'));
    });

    test('name falls back to empty string when null', () {
      final json = {
        'id': 'list-1',
        'name': null,
        'status': 'active',
        'owner_id': 'user-1',
        'items': [],
        'members': [],
        'created_at': '2024-01-01T00:00:00.000Z',
        'updated_at': '2024-01-01T00:00:00.000Z',
      };

      final list = ShoppingList.fromJson(json);
      expect(list.name, '');
    });

    test('name falls back to empty string when key is absent', () {
      final json = <String, dynamic>{
        'id': 'list-1',
        'status': 'active',
        'owner_id': 'user-1',
        'items': [],
        'members': [],
        'created_at': '2024-01-01T00:00:00.000Z',
        'updated_at': '2024-01-01T00:00:00.000Z',
      };

      final list = ShoppingList.fromJson(json);
      expect(list.name, '');
    });

    test('updated_at is parsed correctly', () {
      final json = {
        'id': 'list-1',
        'name': 'Test',
        'status': 'active',
        'owner_id': 'user-1',
        'items': [],
        'members': [],
        'created_at': '2024-03-01T10:00:00.000Z',
        'updated_at': '2024-03-15T18:30:00.000Z',
      };

      final list = ShoppingList.fromJson(json);
      expect(list.updatedAt.month, 3);
      expect(list.updatedAt.day, 15);
    });
  });
}
