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
