import 'package:palateful/core/utils/fraction_parser.dart';
import 'package:palateful/features/recipes/widgets/structured_ingredient_row.dart';

/// Convert one element from a `parsed_recipe.ingredients[]` or
/// `user_edits.ingredients[]` JSON entry into the structured
/// [IngredientRowData] consumed by the shared row widget.
///
/// Precedence rules:
/// * When both `name` and `text` are present, `name` wins — mirrors
///   `create_recipe_task._create_recipe_ingredient` so the import path
///   sees the same canonical value the row displays.
/// * When only `text` is present (legacy import-item rows), it populates
///   the name field — nothing is lost on import items extracted before
///   the structured shape existed.
/// * Empty/whitespace strings become `null` so downstream comparisons
///   don't treat `""` as a distinct "user cleared the field" value.
IngredientRowData ingredientDataFromJson(dynamic ing) {
  if (ing is! Map) {
    final raw = ing.toString().trim();
    return IngredientRowData(name: raw.isEmpty ? null : raw);
  }
  final nameRaw = ing['name'] as String?;
  final textRaw = ing['text'] as String?;
  final name = (nameRaw != null && nameRaw.trim().isNotEmpty)
      ? nameRaw.trim()
      : (textRaw != null && textRaw.trim().isNotEmpty ? textRaw.trim() : null);

  double? qty;
  final qtyRaw = ing['quantity'];
  if (qtyRaw is num) {
    qty = qtyRaw.toDouble();
  } else if (qtyRaw is String) {
    qty = parseFraction(qtyRaw);
  }

  final unitRaw = ing['unit'] as String?;
  final unit = (unitRaw != null && unitRaw.trim().isNotEmpty)
      ? unitRaw.trim()
      : null;

  final notesRaw = ing['notes'] as String?;
  final notes = (notesRaw != null && notesRaw.trim().isNotEmpty)
      ? notesRaw.trim()
      : null;

  final isOptional = ing['is_optional'] == true;

  return IngredientRowData(
    name: name,
    quantity: qty,
    unit: unit,
    notes: notes,
    isOptional: isOptional,
  );
}

/// Serialize an [IngredientRowData] into the `{name, quantity, unit, notes,
/// is_optional}` shape that `create_recipe_task` (and the soon-to-land
/// recipe-create/update endpoints via `bugs-imp-ing-5`) consume. Empty
/// fields go over the wire as `null` rather than `""` so the server's
/// "field missing" semantics match what the extractor itself emits.
Map<String, dynamic> ingredientRowToUserEditJson(IngredientRowData row) {
  return <String, dynamic>{
    'name': row.name,
    'quantity': row.quantity,
    'unit': row.unit,
    'notes': row.notes,
    'is_optional': row.isOptional,
  };
}

/// `true` when the row has any user-visible content worth persisting.
/// Fully-empty placeholder rows are dropped from the serialized payload.
bool ingredientRowHasContent(IngredientRowData row) {
  return (row.name?.isNotEmpty ?? false) ||
      row.quantity != null ||
      (row.unit?.isNotEmpty ?? false) ||
      (row.notes?.isNotEmpty ?? false);
}
