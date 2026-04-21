import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list_item.dart';

void main() {
  group('ShoppingListItem.fromJson defensive parsing', () {
    test('name falls back to empty string when null', () {
      final item = ShoppingListItem.fromJson({
        'id': 'item-1',
        'name': null,
      });
      expect(item.id, 'item-1');
      expect(item.name, '');
    });

    test('name falls back to empty string when key is absent', () {
      final item = ShoppingListItem.fromJson({
        'id': 'item-1',
      });
      expect(item.name, '');
    });

    test('malformed checked_at returns null instead of throwing', () {
      final item = ShoppingListItem.fromJson({
        'id': 'item-1',
        'name': 'Milk',
        'checked_at': 'not-a-date',
      });
      expect(item.checkedAt, isNull);
    });

    test('malformed due_at returns null instead of throwing', () {
      final item = ShoppingListItem.fromJson({
        'id': 'item-1',
        'name': 'Milk',
        'due_at': 'not-a-date',
      });
      expect(item.dueAt, isNull);
    });

    test('valid ISO-8601 checked_at parses correctly', () {
      final item = ShoppingListItem.fromJson({
        'id': 'item-1',
        'name': 'Milk',
        'checked_at': '2026-01-15T10:00:00.000Z',
      });
      expect(item.checkedAt, DateTime.parse('2026-01-15T10:00:00.000Z'));
    });
  });
}
