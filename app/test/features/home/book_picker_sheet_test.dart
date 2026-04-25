import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/book_picker_sheet.dart';

void main() {
  group('sortBooksForPicker', () {
    final books = <Map<String, dynamic>>[
      {
        'id': 'a',
        'name': 'Apple Crisps',
        'is_system': false,
        'user_role': 'owner',
      },
      {
        'id': 'b',
        'name': 'Trying Out',
        'is_system': true,
        'user_role': 'owner',
      },
      {
        'id': 'c',
        'name': "Mom's Recipes",
        'is_system': false,
        'user_role': 'editor',
      },
      {
        'id': 'd',
        'name': "Friend's Cookbook",
        'is_system': false,
        'user_role': 'viewer',
      },
    ];

    test('pins system books first, drops viewer-role rows', () {
      final sorted = sortBooksForPicker(books);
      expect(sorted.map((b) => b['id']).toList(), ['b', 'a', 'c']);
    });

    test('respects excludeBookId', () {
      final sorted = sortBooksForPicker(books, excludeBookId: 'b');
      expect(sorted.map((b) => b['id']).toList(), ['a', 'c']);
    });

    test('keeps multiple system books alphabetical', () {
      final extra = [
        ...books,
        {
          'id': 'sys2',
          'name': 'Archive Bin',
          'is_system': true,
          'user_role': 'owner',
        },
      ];
      final sorted = sortBooksForPicker(extra);
      // Two system books — Archive Bin sorts before Trying Out.
      expect(sorted.first['id'], 'sys2');
      expect(sorted[1]['id'], 'b');
    });
  });
}
