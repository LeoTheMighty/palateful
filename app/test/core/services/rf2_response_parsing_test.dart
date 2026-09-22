import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';

/// rf-2: client-side contract tests for the expanded response shapes.
///
/// The Flutter app reads these responses as raw `Map<String, dynamic>`
/// (no strongly-typed model layer). What matters is that the known
/// fields are present under the expected keys, and that the `item` /
/// full-recipe / full-meal expansions can be read without crashes when
/// the server supplies them — and that missing expansions (old server,
/// pre-rf-2 rollout) gracefully degrade.
void main() {
  group('rf-2 dismiss response', () {
    test('legacy top-level fields are still present', () {
      final body = _dismissGoldenResponse();
      expect(body['item_id'], 'imp-123');
      expect(body['dismissed_at'], isA<String>());
      expect(body['job_dismissed'], isFalse);
    });

    test('new `item` field carries the full ImportItemSummary shape', () {
      final body = _dismissGoldenResponse();
      final item = body['item'] as Map<String, dynamic>;
      expect(item['id'], 'imp-123');
      expect(item['status'], 'failed');
      expect(item['source_type'], 'url');
      expect(item['source_url'], 'https://example.com/r');
      expect(item['error_message'], 'parser_timeout');
      expect(item.containsKey('needs_review'), isTrue);
      expect(item.containsKey('ai_cost_cents'), isTrue);
    });

    test('missing `item` (pre-rf-2 server) does not crash clients', () {
      final body = Map<String, dynamic>.from(_dismissGoldenResponse());
      body.remove('item');
      expect(body['item'], isNull);
      // Client fallback: read legacy fields and trigger invalidate-and-refetch.
      expect(body['item_id'], 'imp-123');
    });
  });

  group('rf-2 favorite recipe response', () {
    test('full recipe payload with is_favorite nested', () {
      final body = _favoriteRecipeGoldenResponse();
      expect(body['id'], 'rec-abc');
      expect(body['is_favorite'], isTrue);
      expect(body['ingredients'], isA<List<dynamic>>());
      expect(body['steps'], isA<List<dynamic>>());
      expect(body['notes'], isA<List<dynamic>>());
    });

    test('pre-rf-2 shape `{is_favorite: bool}` still legible', () {
      final body = {'is_favorite': false};
      expect(body['is_favorite'], isFalse);
    });
  });

  group('rf-2 favorite meal response', () {
    test('full meal payload with components + is_favorite nested', () {
      final body = _favoriteMealGoldenResponse();
      expect(body['id'], 'meal-1');
      expect(body['is_favorite'], isTrue);
      expect(body['components'], isA<List<dynamic>>());
      expect(body['recipe_book_id'], 'book-1');
    });
  });
}

// ---------------------------------------------------------------------------
// Golden server responses — hand-crafted to mirror the production Pydantic
// output. When the backend Response models change, update these fixtures
// and the accompanying assertions above.
// ---------------------------------------------------------------------------

/// Base instant for every timestamp in this file's golden responses.
///
/// These fixtures live inside raw JSON string literals, so they cannot
/// carry a Dart `// age-independent` comment without making the JSON
/// unparseable — the escape hatch here is a computed value, not a marker.
/// Nothing in this file compares them to `now` today (the tests only
/// `jsonDecode` and assert on field presence/type), but these bodies are
/// the golden shapes fed to the import/recipe surfaces that DO age:
/// `imports_tab.dart`'s 30-day `completed`/`skipped` cutoff and the
/// relative-date formatters (`import_row_expansion.dart:214`,
/// `stage_timeline.dart:226`). Anchoring to `now` keeps the goldens
/// replayable against those surfaces instead of rotting out of range.
final DateTime _fixtureBase =
    DateTime.now().toUtc().subtract(const Duration(hours: 2));

/// A fixture timestamp `minutesAfterBase` past [_fixtureBase]. Offsets
/// preserve the original fixtures' relative ordering — the dismissed
/// import item was created five minutes before it was dismissed.
String _at(int minutesAfterBase) =>
    _fixtureBase.add(Duration(minutes: minutesAfterBase)).toIso8601String();

Map<String, dynamic> _dismissGoldenResponse() =>
    jsonDecode(_dismissGoldenJson) as Map<String, dynamic>;

final _dismissGoldenJson = '''
{
  "item_id": "imp-123",
  "dismissed_at": "${_at(5)}",
  "job_dismissed": false,
  "item": {
    "id": "imp-123",
    "status": "failed",
    "source_type": "url",
    "source_url": "https://example.com/r",
    "recipe_name": null,
    "error_message": "parser_timeout",
    "needs_review": false,
    "ai_cost_cents": 0,
    "created_at": "${_at(0)}"
  }
}
''';

Map<String, dynamic> _favoriteRecipeGoldenResponse() =>
    jsonDecode(_favoriteRecipeGoldenJson) as Map<String, dynamic>;

final _favoriteRecipeGoldenJson = '''
{
  "id": "rec-abc",
  "name": "Test Recipe",
  "description": null,
  "instructions": null,
  "servings": 2,
  "prep_time": 10,
  "cook_time": 20,
  "image_url": null,
  "source_url": null,
  "tags": [],
  "primary_vibe": null,
  "secondary_vibe": null,
  "can_edit": true,
  "is_favorite": true,
  "ingredients": [],
  "steps": [],
  "notes": [],
  "created_at": "${_at(5)}",
  "updated_at": "${_at(5)}",
  "version_count": 0,
  "forked_from_recipe_id": null,
  "forked_from_book_id": null,
  "forked_from_recipe_name": null,
  "forked_from_book_name": null,
  "inferred_fields": [],
  "debug": null
}
''';

Map<String, dynamic> _favoriteMealGoldenResponse() =>
    jsonDecode(_favoriteMealGoldenJson) as Map<String, dynamic>;

final _favoriteMealGoldenJson = '''
{
  "id": "meal-1",
  "name": "Test Dinner",
  "description": null,
  "recipe_book_id": "book-1",
  "archived_at": null,
  "created_at": "${_at(5)}",
  "updated_at": "${_at(5)}",
  "components": [],
  "is_favorite": true
}
''';
