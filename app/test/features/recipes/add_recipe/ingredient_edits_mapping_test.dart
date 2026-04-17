import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/features/recipes/add_recipe/ingredient_edits_mapping.dart';
import 'package:palateful/features/recipes/widgets/structured_ingredient_row.dart';

void main() {
  group('ingredientDataFromJson', () {
    test('fully structured entry — all fields hydrate', () {
      final row = ingredientDataFromJson({
        'name': 'butter',
        'text': '1/3 cup melted butter',
        'quantity': 0.333,
        'unit': 'cup',
        'notes': 'melted',
        'is_optional': false,
      });
      expect(row.name, 'butter');
      expect(row.quantity, closeTo(0.333, 1e-9));
      expect(row.unit, 'cup');
      expect(row.notes, 'melted');
      expect(row.isOptional, isFalse);
    });

    test('name wins over text when both present', () {
      final row = ingredientDataFromJson({
        'name': 'butter',
        'text': 'cup melted butter',
      });
      expect(row.name, 'butter');
    });

    test('legacy entry — text-only populates name', () {
      final row = ingredientDataFromJson({'text': '2 cups flour'});
      expect(row.name, '2 cups flour');
      expect(row.quantity, isNull);
    });

    test('legacy entry — whitespace name falls back to text', () {
      final row = ingredientDataFromJson({
        'name': '   ',
        'text': '2 cups flour',
      });
      expect(row.name, '2 cups flour');
    });

    test('quantity as fraction string is parsed', () {
      final row = ingredientDataFromJson({
        'name': 'butter',
        'quantity': '1 1/2',
      });
      expect(row.quantity, 1.5);
    });

    test('is_optional=true flows through', () {
      final row = ingredientDataFromJson({
        'name': 'butter',
        'is_optional': true,
      });
      expect(row.isOptional, isTrue);
    });

    test('empty strings → null, not ""', () {
      final row = ingredientDataFromJson({
        'name': '',
        'unit': '',
        'notes': '',
      });
      expect(row.name, isNull);
      expect(row.unit, isNull);
      expect(row.notes, isNull);
    });

    test('non-map falls back to text-as-name', () {
      final row = ingredientDataFromJson('2 cups flour');
      expect(row.name, '2 cups flour');
    });
  });

  group('ingredientRowToUserEditJson', () {
    test('serializes all fields; empty fields are null (not "")', () {
      const r = IngredientRowData(
        name: 'butter',
        quantity: 0.5,
        unit: 'cup',
        notes: 'melted',
        isOptional: true,
      );
      expect(ingredientRowToUserEditJson(r), {
        'name': 'butter',
        'quantity': 0.5,
        'unit': 'cup',
        'notes': 'melted',
        'is_optional': true,
      });
    });

    test('null fields serialize as null (not omitted)', () {
      const r = IngredientRowData(name: 'butter');
      expect(ingredientRowToUserEditJson(r), {
        'name': 'butter',
        'quantity': null,
        'unit': null,
        'notes': null,
        'is_optional': false,
      });
    });
  });

  group('ingredientRowHasContent', () {
    test('fully empty row → false', () {
      expect(ingredientRowHasContent(const IngredientRowData()), isFalse);
    });
    test('any populated field → true', () {
      expect(
          ingredientRowHasContent(const IngredientRowData(name: 'x')), isTrue);
      expect(
          ingredientRowHasContent(const IngredientRowData(quantity: 1)), isTrue);
      expect(
          ingredientRowHasContent(const IngredientRowData(unit: 'cup')), isTrue);
      expect(
          ingredientRowHasContent(const IngredientRowData(notes: 'n')), isTrue);
    });
    test('is_optional alone is not content — it is a flag, not data', () {
      expect(
          ingredientRowHasContent(const IngredientRowData(isOptional: true)),
          isFalse);
    });
  });

  group('round-trip fixture', () {
    test('parsed_recipe entry → row → user_edit entry preserves key fields', () {
      final parsed = {
        'name': 'butter',
        'text': '1/3 cup melted butter',
        'quantity': 0.333,
        'unit': 'cup',
        'notes': 'melted',
        'is_optional': false,
      };
      final row = ingredientDataFromJson(parsed);
      final edit = ingredientRowToUserEditJson(row);
      // `text` is intentionally dropped — the structured fields replace it.
      expect(edit['name'], 'butter');
      expect(edit['quantity'], closeTo(0.333, 1e-9));
      expect(edit['unit'], 'cup');
      expect(edit['notes'], 'melted');
      expect(edit['is_optional'], isFalse);
    });
  });

  group('ingredientRowFromGetRecipe', () {
    double? parse(String s) {
      // Minimal stand-in; real callers pass `parseFraction`.
      if (s == '1 1/2') return 1.5;
      if (s == '0.5') return 0.5;
      return null;
    }

    test('structured row hydrates all fields + ingredient_id', () {
      final entry = {
        'ingredient': {'id': 'ing-123', 'canonical_name': 'butter'},
        'quantity_display': '1 1/2',
        'unit_display': 'cup',
        'notes': 'melted',
        'is_optional': false,
      };
      final row = ingredientRowFromGetRecipe(entry, parseQty: parse);
      expect(row.name, 'butter');
      expect(row.quantity, 1.5);
      expect(row.unit, 'cup');
      expect(row.notes, 'melted');
      expect(row.isOptional, isFalse);
      expect(row.ingredientId, 'ing-123');
    });

    test('legacy ingredient — only canonical_name populated', () {
      final entry = {
        'ingredient': {'id': 'ing-legacy', 'canonical_name': 'flour'},
        // No quantity_display / unit_display / notes.
      };
      final row = ingredientRowFromGetRecipe(entry, parseQty: parse);
      expect(row.name, 'flour');
      expect(row.quantity, isNull);
      expect(row.unit, isNull);
      expect(row.notes, isNull);
      expect(row.ingredientId, 'ing-legacy');
    });

    test('empty unit/notes hydrate as null', () {
      final entry = {
        'ingredient': {'id': 'x', 'canonical_name': 'salt'},
        'quantity_display': '0.5',
        'unit_display': '',
        'notes': '',
      };
      final row = ingredientRowFromGetRecipe(entry, parseQty: parse);
      expect(row.unit, isNull);
      expect(row.notes, isNull);
      expect(row.quantity, 0.5);
    });

    test('numeric quantity_display is accepted without parser fallback', () {
      final entry = {
        'ingredient': {'id': 'x', 'canonical_name': 'salt'},
        'quantity_display': 2,
      };
      final row = ingredientRowFromGetRecipe(entry, parseQty: parse);
      expect(row.quantity, 2);
    });
  });

  group('ingredientRowToEditSavePayload', () {
    test('existing row includes ingredient_id', () {
      const r = IngredientRowData(
        name: 'butter',
        quantity: 0.5,
        unit: 'cup',
        ingredientId: 'ing-123',
      );
      final payload = ingredientRowToEditSavePayload(r);
      expect(payload['ingredient_id'], 'ing-123');
      expect(payload['name'], 'butter');
    });

    test('net-new row omits ingredient_id (relies on resolve_ingredient)', () {
      const r = IngredientRowData(name: 'paprika', quantity: 1, unit: 'tsp');
      final payload = ingredientRowToEditSavePayload(r);
      expect(payload.containsKey('ingredient_id'), isFalse);
      expect(payload['name'], 'paprika');
    });
  });
}
