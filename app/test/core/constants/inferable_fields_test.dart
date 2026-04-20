import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/constants/inferable_fields.dart';

void main() {
  group('kInferableFields', () {
    test('has exactly 9 entries mirroring the backend allow-list', () {
      // Hand-synced with
      // `libraries/utils/utils/services/recipe_extractors/inference_prompt.py`
      // `INFERABLE_FIELDS`. Drift here fails the test so the sparkle
      // badge can't render on a field the server will reject.
      expect(kInferableFields.length, 9);
      expect(
        kInferableFields,
        equals({
          'prep_time_minutes',
          'cook_time_minutes',
          'total_time_minutes',
          'servings',
          'description',
          'cuisine',
          'category',
          'primary_vibe',
          'secondary_vibe',
        }),
      );
    });
  });

  group('decodeInferredFields', () {
    test('happy path: list of allow-listed strings → same as a set', () {
      expect(
        decodeInferredFields(['cook_time_minutes', 'servings']),
        equals({'cook_time_minutes', 'servings'}),
      );
    });

    test('filters out non-allow-list names', () {
      expect(
        decodeInferredFields(['cook_time_minutes', 'name', 'ingredients']),
        equals({'cook_time_minutes'}),
      );
    });

    test('filters out non-string entries', () {
      expect(
        decodeInferredFields(['cook_time_minutes', 42, null, true]),
        equals({'cook_time_minutes'}),
      );
    });

    test('null → empty set', () {
      expect(decodeInferredFields(null), isEmpty);
    });

    test('non-list → empty set', () {
      expect(decodeInferredFields('cook_time_minutes'), isEmpty);
      expect(decodeInferredFields({'cook_time_minutes': true}), isEmpty);
      expect(decodeInferredFields(42), isEmpty);
    });

    test('empty list → empty set', () {
      expect(decodeInferredFields(<Object?>[]), isEmpty);
    });

    test('returns a mutable set (callers mutate on edit)', () {
      final set = decodeInferredFields(['cook_time_minutes']);
      expect(() => set.remove('cook_time_minutes'), returnsNormally);
      expect(set, isEmpty);
    });
  });
}
