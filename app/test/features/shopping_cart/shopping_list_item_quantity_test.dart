// cartqty1: the quantity parse must not be able to destroy the payload.
//
// The cart was unusable from at least 2026-04 to 2026-09 because
// `(json['quantity'] as num?)` threw on a Decimal-as-string, inside
// `fromJson`, taking the WHOLE list parse with it. The user saw an empty
// cart; the server returned 200; nothing was logged.
//
// The server side is fixed and no cart endpoint can emit a string today, so
// these tests pin a boundary rather than reproduce a live failure. They exist
// because the original defect arrived as an endpoint built without the
// serializer, and a new one would arrive the same way.
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list_item.dart';

Map<String, dynamic> row(Object? quantity) => {
      'id': 'item-1',
      'name': 'Bananas',
      'quantity': quantity,
      'is_checked': false,
    };

void main() {
  group('quantity parsing degrades instead of throwing', () {
    test('a JSON number parses', () {
      expect(ShoppingListItem.fromJson(row(2)).quantity, 2.0);
      expect(ShoppingListItem.fromJson(row(1.5)).quantity, 1.5);
    });

    test('THE ORIGINAL BUG: a Decimal-as-string parses, does not throw', () {
      // Pydantic v2 renders a bare Decimal like this.
      expect(ShoppingListItem.fromJson(row('1.5')).quantity, 1.5);
      expect(ShoppingListItem.fromJson(row('2')).quantity, 2.0);
    });

    test('null stays null', () {
      expect(ShoppingListItem.fromJson(row(null)).quantity, isNull);
    });

    test('an unparseable string degrades to null and keeps the row', () {
      final item = ShoppingListItem.fromJson(row('a handful'));
      expect(item.quantity, isNull);
      // The row survives with its identity intact — that is the point.
      expect(item.name, 'Bananas');
      expect(item.id, 'item-1');
    });

    test('a wrong-typed quantity degrades rather than throwing', () {
      for (final bad in <Object>[true, <int>[1], <String, int>{'a': 1}]) {
        expect(ShoppingListItem.fromJson(row(bad)).quantity, isNull,
            reason: 'quantity=$bad should degrade, not throw');
      }
    });
  });

  test('ONE bad row cannot take out the others', () {
    // The actual failure signature: not a missing amount, an empty cart.
    final rows = [row(1), row('not a number'), row(3)];
    final parsed = rows.map(ShoppingListItem.fromJson).toList();
    expect(parsed.length, 3);
    expect(parsed[0].quantity, 1.0);
    expect(parsed[1].quantity, isNull);
    expect(parsed[2].quantity, 3.0);
  });
}
