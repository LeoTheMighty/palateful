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
  // riip-7: backend annotates parsed_recipe ingredients with
  // `pending_review_ingredient: true` when the canonical was auto-created
  // via find-or-create. Flutter treats omitted == false.
  final pendingReviewIngredient = ing['pending_review_ingredient'] == true;

  return IngredientRowData(
    name: name,
    quantity: qty,
    unit: unit,
    notes: notes,
    isOptional: isOptional,
    pendingReviewIngredient: pendingReviewIngredient,
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

/// Hydrate a GET-recipe response's `ingredients[]` entry — which uses the
/// `{ingredient: {id, canonical_name}, quantity_display, unit_display, ...}`
/// shape — into the editor's [IngredientRowData] shape. The
/// `ingredient_id` is preserved so the edit screen's save payload can
/// send it back and the backend's resolve_ingredient helper uses the
/// existing canonical row instead of re-creating it via find-or-create.
///
/// Legacy rows (no `quantity_display` / `unit_display` / `notes`) hydrate
/// with `canonical_name` in the Name field and empty qty/unit/notes —
/// nothing is lost. See bugs-imp-ing-4 AC4.
IngredientRowData ingredientRowFromGetRecipe(
  Map<String, dynamic> entry, {
  required double? Function(String) parseQty,
}) {
  final ingredientId = entry['ingredient'] is Map
      ? (entry['ingredient']['id'] as String?)
      : null;
  final canonicalName = entry['ingredient'] is Map
      ? (entry['ingredient']['canonical_name'] as String?)
      : null;
  final qtyDisplay = entry['quantity_display'];
  double? qty;
  if (qtyDisplay is num) {
    qty = qtyDisplay.toDouble();
  } else if (qtyDisplay is String) {
    qty = parseQty(qtyDisplay);
  }
  final unitDisplay = entry['unit_display'] as String?;
  final notes = entry['notes'] as String?;
  final isOptional = entry['is_optional'] == true;
  return IngredientRowData(
    name: (canonicalName != null && canonicalName.trim().isNotEmpty)
        ? canonicalName
        : null,
    quantity: qty,
    unit: (unitDisplay != null && unitDisplay.trim().isNotEmpty)
        ? unitDisplay
        : null,
    notes: (notes != null && notes.trim().isNotEmpty) ? notes : null,
    isOptional: isOptional,
    ingredientId: ingredientId,
  );
}

/// Serialize a row from the edit screen into a payload for the
/// recipe-update endpoint. Preserves `ingredient_id` when the row came
/// from existing data; for net-new rows, only `name` is sent and the
/// backend's resolve_ingredient helper runs find-or-create.
Map<String, dynamic> ingredientRowToEditSavePayload(IngredientRowData row) {
  final payload = ingredientRowToUserEditJson(row);
  if (row.ingredientId != null) {
    payload['ingredient_id'] = row.ingredientId;
  }
  return payload;
}
