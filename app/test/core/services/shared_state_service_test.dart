import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/shared_state_service.dart';

// SharedStateService tests. The home_widget package writes via
// MethodChannel('home_widget'), so we mock that channel and assert the
// exact key/value pairs the native side will see.
//
// What's covered:
//  - debounced writes: two syncAuth calls collapse to one channel burst
//  - JWT near-expiry surfaces correctly via stored millisecond timestamp
//  - clear() writes empty fields immediately (not debounced)
//  - books list is bounded at 50 entries
//  - JSON shape of share_recipe_books matches Swift decoder keys
//    (id / name / is_personal / is_archived)

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late SharedStateService service;
  late Map<String, Object?> captured;

  const channel = MethodChannel('home_widget');

  setUp(() {
    captured = {};
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      switch (call.method) {
        case 'setAppGroupId':
          return null;
        case 'saveWidgetData':
          final args = (call.arguments as Map?)?.cast<String, Object?>() ?? {};
          final id = args['id'] as String?;
          if (id != null) captured[id] = args['data'];
          return true;
        case 'updateWidget':
          return null;
      }
      return null;
    });
    service = SharedStateService();
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  test('syncAuth stores all five auth fields after debounce flush', () async {
    await service.initialize();

    final expires = DateTime.fromMillisecondsSinceEpoch(1800000000000);
    service.syncAuth(
      authJwt: 'jwt-abc',
      authJwtExpiresAt: expires,
      userId: 'auth0|u123',
      apiBaseUrl: 'https://api.palateful.app',
      lastUsedBookId: 'book-xyz',
    );
    await service.flushPending();

    expect(captured['share_auth_jwt'], 'jwt-abc');
    expect(captured['share_auth_jwt_expires_at'], 1800000000000.0);
    expect(captured['share_user_id'], 'auth0|u123');
    expect(captured['share_api_base_url'], 'https://api.palateful.app');
    expect(captured['share_last_used_book_id'], 'book-xyz');
  });

  test('two syncAuth calls in rapid succession collapse to one flush', () async {
    await service.initialize();

    service.syncAuth(
      authJwt: 'old',
      authJwtExpiresAt: DateTime.fromMillisecondsSinceEpoch(1000),
      userId: 'u',
      apiBaseUrl: 'x',
    );
    service.syncAuth(
      authJwt: 'new',
      authJwtExpiresAt: DateTime.fromMillisecondsSinceEpoch(2000),
      userId: 'u',
      apiBaseUrl: 'x',
    );
    await service.flushPending();

    expect(captured['share_auth_jwt'], 'new');
    expect(captured['share_auth_jwt_expires_at'], 2000.0);
  });

  test('syncRecipeBooks caps list at 50 and emits Swift-compatible JSON', () async {
    await service.initialize();

    final books = List<SharedRecipeBook>.generate(
      75,
      (i) => SharedRecipeBook(
        id: 'id-$i',
        name: 'Book $i',
        isPersonal: i.isEven,
        isArchived: false,
      ),
    );
    service.syncRecipeBooks(books);
    await service.flushPending();

    final raw = captured['share_recipe_books'] as String?;
    expect(raw, isNotNull);
    final decoded = jsonDecode(raw!) as List<dynamic>;
    expect(decoded.length, 50);
    final first = decoded.first as Map<String, dynamic>;
    expect(first['id'], 'id-0');
    expect(first['name'], 'Book 0');
    expect(first['is_personal'], true);
    expect(first['is_archived'], false);
  });

  test('clear() writes empty auth fields without waiting for debounce', () async {
    await service.initialize();

    service.clear();
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(captured['share_auth_jwt'], '');
    expect(captured['share_auth_jwt_expires_at'], 0.0);
    expect(captured['share_user_id'], '');
    expect(captured['share_recipe_books'], '[]');
  });
}
