import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/router/route_redaction.dart';

void main() {
  group('isRouteRedacted', () {
    test('null / empty is considered redacted', () {
      expect(isRouteRedacted(null), isTrue);
      expect(isRouteRedacted(''), isTrue);
    });

    test('template placeholders pass through', () {
      expect(isRouteRedacted('/recipes/:id'), isTrue);
      expect(isRouteRedacted('/recipes/{id}/edit'), isTrue);
    });

    test('UUID segments fail', () {
      expect(
        isRouteRedacted(
          '/recipes/550e8400-e29b-41d4-a716-446655440000',
        ),
        isFalse,
      );
    });

    test('4-plus-digit segments fail', () {
      expect(isRouteRedacted('/invoices/123456'), isFalse);
      expect(isRouteRedacted('/invoices/1234'), isFalse);
    });

    test('short numeric segments are allowed (versioning, page counts)',
        () {
      expect(isRouteRedacted('/v1/users'), isTrue);
      expect(isRouteRedacted('/page/42'), isTrue);
    });

    test('query string + fragment ignored', () {
      expect(
        isRouteRedacted('/recipes/:id?foo=bar#bottom'),
        isTrue,
      );
      expect(
        isRouteRedacted(
          '/recipes/550e8400-e29b-41d4-a716-446655440000?foo=bar',
        ),
        isFalse,
      );
    });
  });

  group('redactRoute', () {
    test('null / empty pass through', () {
      expect(redactRoute(null), isNull);
      expect(redactRoute(''), '');
    });

    test('replaces UUID + long-numeric with :id', () {
      expect(
        redactRoute('/recipes/550e8400-e29b-41d4-a716-446655440000/edit'),
        '/recipes/:id/edit',
      );
      expect(
        redactRoute('/invoices/98765/items/2468'),
        '/invoices/:id/items/:id',
      );
    });

    test('strips query + fragment', () {
      expect(
        redactRoute('/recipes/abc?q=1#frag'),
        '/recipes/abc',
      );
    });

    test('idempotent on already-redacted routes', () {
      expect(redactRoute('/recipes/:id'), '/recipes/:id');
      expect(redactRoute('/users/{id}/edit'), '/users/{id}/edit');
    });
  });
}
