import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/dynamic_column.dart';
import 'package:palateful/features/home/widgets/filter_bottom_sheet.dart';

void main() {
  group('dynamicColumnFor', () {
    test('lastCooked → "Last cooked" + relative date', () {
      final spec = dynamicColumnFor(SortOption.lastCooked);
      expect(spec.label, 'Last cooked');
      expect(spec.resolveValue({'last_cooked': null}), '—');
      expect(spec.resolveValue({}), '—');

      final twoDaysAgo = DateTime.now()
          .subtract(const Duration(days: 2))
          .toIso8601String();
      expect(spec.resolveValue({'last_cooked': twoDaysAgo}), '2d ago');
    });

    test('quickest → "Cook time" with prep + cook minutes', () {
      final spec = dynamicColumnFor(SortOption.quickest);
      expect(spec.label, 'Cook time');
      expect(
          spec.resolveValue({'prep_time': 10, 'cook_time': 20}), '30 min');
      expect(spec.resolveValue({'cook_time': 15}), '15 min');
      expect(spec.resolveValue({'prep_time': 0, 'cook_time': 0}), '—');
      expect(spec.resolveValue({}), '—');
    });

    test('newest → "Added" + relative date from created_at', () {
      final spec = dynamicColumnFor(SortOption.newest);
      expect(spec.label, 'Added');
      final yesterday = DateTime.now()
          .subtract(const Duration(days: 1))
          .toIso8601String();
      expect(spec.resolveValue({'created_at': yesterday}), 'Yesterday');
    });

    test('best → "Cooked" with times_cooked count', () {
      final spec = dynamicColumnFor(SortOption.best);
      expect(spec.label, 'Cooked');
      expect(spec.resolveValue({'times_cooked': 1}), '1×');
      expect(spec.resolveValue({'times_cooked': 7}), '7×');
      expect(spec.resolveValue({'times_cooked': 0}), '—');
      expect(spec.resolveValue({}), '—');
    });

    test('popular → "Popular" with score', () {
      final spec = dynamicColumnFor(SortOption.popular);
      expect(spec.label, 'Popular');
      expect(spec.resolveValue({'popularity': 4.7}), '4.7');
      expect(spec.resolveValue({}), '—');
    });

    test('random → falls back to "Last cooked" lens', () {
      final spec = dynamicColumnFor(SortOption.random);
      expect(spec.label, 'Last cooked');
      expect(spec.resolveValue({'last_cooked': null}), '—');
    });

    test('Just-now / minutes / hours buckets', () {
      final spec = dynamicColumnFor(SortOption.lastCooked);
      final now = DateTime.now();
      expect(
          spec.resolveValue({
            'last_cooked':
                now.subtract(const Duration(seconds: 30)).toIso8601String()
          }),
          'Just now');
      expect(
          spec.resolveValue({
            'last_cooked':
                now.subtract(const Duration(minutes: 10)).toIso8601String()
          }),
          '10m ago');
      expect(
          spec.resolveValue({
            'last_cooked':
                now.subtract(const Duration(hours: 5)).toIso8601String()
          }),
          '5h ago');
    });

    test('weeks / months / years buckets', () {
      final spec = dynamicColumnFor(SortOption.lastCooked);
      final now = DateTime.now();
      expect(
          spec.resolveValue({
            'last_cooked':
                now.subtract(const Duration(days: 14)).toIso8601String()
          }),
          '2w ago');
      expect(
          spec.resolveValue({
            'last_cooked':
                now.subtract(const Duration(days: 60)).toIso8601String()
          }),
          '2mo ago');
      expect(
          spec.resolveValue({
            'last_cooked':
                now.subtract(const Duration(days: 800)).toIso8601String()
          }),
          '2y ago');
    });

    test('future dates render as "—" rather than negative', () {
      final spec = dynamicColumnFor(SortOption.lastCooked);
      final tomorrow =
          DateTime.now().add(const Duration(days: 1)).toIso8601String();
      expect(spec.resolveValue({'last_cooked': tomorrow}), '—');
    });

    test('unparseable date returns "—"', () {
      final spec = dynamicColumnFor(SortOption.lastCooked);
      expect(spec.resolveValue({'last_cooked': 'not-a-date'}), '—');
    });
  });
}
