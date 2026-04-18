/// Curated catalog of measurement units for ingredient editing.
///
/// Order is intentional (most common first). This list is the single source
/// of truth for the unit dropdown across Review Import, the recipe wizard,
/// and the recipe edit screen (NFR43). Custom units typed by users do NOT
/// get persisted back into this list — they apply per-ingredient-row only.
const List<String> kCuratedUnits = <String>[
  'cup',
  'tbsp',
  'tsp',
  'oz',
  'fl oz',
  'ml',
  'l',
  'g',
  'kg',
  'lb',
  'each',
  'pinch',
  'dash',
  'clove',
  'slice',
];

/// Returns the curated units filtered by a prefix/substring match.
/// Matching is case-insensitive and trims whitespace. Empty query returns
/// the full catalog.
List<String> filterCuratedUnits(String query) {
  final trimmed = query.trim().toLowerCase();
  if (trimmed.isEmpty) return kCuratedUnits;
  return kCuratedUnits.where((u) => u.toLowerCase().contains(trimmed)).toList();
}

/// Hardcoded fallback alias → canonical map for the Flutter `UnitInput`
/// coerce-on-blur path (riip-5). Mirrors the top ~20 aliases seeded in
/// `services/migrator/migrations/versions/20260418040000_create_unit_aliases.py`
/// so the widget can coerce typed text immediately at app start, before
/// the live `GET /v1/units/aliases` fetch lands.
///
/// The live alias map (`SessionAliasMap.aliases`) replaces this fallback
/// when the server response arrives, so adding aliases server-side does
/// not require an app release.
const Map<String, String> kFallbackUnitAliases = <String, String>{
  // Volume full names + plurals
  'tablespoon': 'tbsp',
  'tablespoons': 'tbsp',
  'teaspoon': 'tsp',
  'teaspoons': 'tsp',
  'cups': 'cup',
  'fluid ounce': 'fl oz',
  'fluid ounces': 'fl oz',
  'milliliter': 'ml',
  'milliliters': 'ml',
  'liter': 'l',
  'liters': 'l',
  // Weight full names + plurals
  'gram': 'g',
  'grams': 'g',
  'kilogram': 'kg',
  'kilograms': 'kg',
  'pound': 'lb',
  'pounds': 'lb',
  'ounce': 'oz',
  'ounces': 'oz',
  'milligram': 'mg',
  'milligrams': 'mg',
};
