import 'package:dio/dio.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/services/share_service.dart';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApiClient extends ApiClient {
  bool createInviteLinkCalled = false;
  bool shareShoppingListCalled = false;

  @override
  Future<Response> createInviteLink(Map<String, dynamic> data) async {
    createInviteLinkCalled = true;
    return _fakeResponse({
      'link': 'https://palateful.app/invite/abc123',
      'deep_link': 'palateful://invite/abc123',
    });
  }

  @override
  Future<Response> shareShoppingList(String listId) async {
    shareShoppingListCalled = true;
    return _fakeResponse({
      'share_code': 'ABC123',
      'deep_link': 'palateful://shopping-list/join/ABC123',
    });
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  setUpAll(() async {
  });

  late _FakeApiClient fakeClient;

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    fakeClient = _FakeApiClient();
    gi.registerSingleton<ApiClient>(fakeClient);
  });

  tearDown(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  });

  group('ShareService — shareRecipeBook', () {
    test('calls createInviteLink on the API client', () async {
      final service = ShareService(apiClient: fakeClient);

      try {
        await service.shareRecipeBook(
          recipeBookId: 'book-1',
          recipeBookName: 'My Book',
          context: _FakeBuildContext(),
        );
      } catch (_) {
        // Expected: MissingPluginException from Share.share
      }

      expect(fakeClient.createInviteLinkCalled, isTrue);
    });
  });

  group('ShareService — shareShoppingList', () {
    test('calls shareShoppingList on the API client', () async {
      final service = ShareService(apiClient: fakeClient);

      try {
        await service.shareShoppingList(
          listId: 'list-1',
          listName: 'Groceries',
          context: _FakeBuildContext(),
        );
      } catch (_) {
        // Expected: MissingPluginException from Share.share
      }

      expect(fakeClient.shareShoppingListCalled, isTrue);
    });
  });
}

/// Minimal fake BuildContext for ShareService.
class _FakeBuildContext extends Fake implements BuildContext {
  @override
  RenderObject? findRenderObject() => null;
}
