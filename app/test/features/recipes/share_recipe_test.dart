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
  bool shareRecipeCalled = false;
  String? lastShareRecipeId;
  bool shouldThrow = false;

  @override
  Future<Response> shareRecipe(String recipeId) async {
    shareRecipeCalled = true;
    lastShareRecipeId = recipeId;
    if (shouldThrow) throw Exception('network error');
    return _fakeResponse({
      'share_token': 'tok12345678901234',
      'deep_link': 'https://palateful.app/recipes/shared/tok12345678901234',
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

  group('ShareService — shareRecipe', () {
    test('calls shareRecipe on the API client with correct recipeId', () async {
      final service = ShareService(apiClient: fakeClient);

      // shareRecipe calls Share.share() which is a platform channel — will
      // throw MissingPluginException in unit tests. We only verify the API
      // call happens before the share sheet.
      try {
        await service.shareRecipe(
          recipeId: 'recipe-1',
          recipeName: 'Pasta',
          context: _FakeBuildContext(),
        );
      } catch (_) {
        // Expected: MissingPluginException from Share.share
      }

      expect(fakeClient.shareRecipeCalled, isTrue);
      expect(fakeClient.lastShareRecipeId, 'recipe-1');
    });

    test('propagates API errors', () async {
      fakeClient.shouldThrow = true;
      final service = ShareService(apiClient: fakeClient);

      expect(
        () => service.shareRecipe(
          recipeId: 'recipe-1',
          recipeName: 'Pasta',
          context: _FakeBuildContext(),
        ),
        throwsException,
      );
    });
  });
}

/// Minimal fake BuildContext for ShareService (only needs findRenderObject).
class _FakeBuildContext extends Fake implements BuildContext {
  @override
  RenderObject? findRenderObject() => null;
}
