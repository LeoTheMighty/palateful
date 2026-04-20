/// efi-5 — client-side allow-list of recipe-root fields the extractor
/// may best-guess ("infer"). Mirrors the backend
/// `INFERABLE_FIELDS` tuple in
/// `libraries/utils/utils/services/recipe_extractors/inference_prompt.py`.
///
/// Keep the two in sync by hand — a contract test in
/// `app/test/core/constants/inferable_fields_test.dart` pins the size
/// and content so a drift is caught immediately.
const Set<String> kInferableFields = {
  'prep_time_minutes',
  'cook_time_minutes',
  'total_time_minutes',
  'servings',
  'description',
  'cuisine',
  'category',
  'primary_vibe',
  'secondary_vibe',
};

/// Decode an API response's `inferred_fields` value into a mutable
/// `Set<String>`. Always returns a set (never null). Filters out any
/// entry not in [kInferableFields] so a malformed legacy payload can't
/// smuggle a bogus name onto the UI.
Set<String> decodeInferredFields(Object? raw) {
  if (raw is! List) return <String>{};
  final out = <String>{};
  for (final item in raw) {
    if (item is String && kInferableFields.contains(item)) {
      out.add(item);
    }
  }
  return out;
}
