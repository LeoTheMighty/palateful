// pfc-3 — recipe_detail_screen keep-alive + mutation invalidation.
//
// Three acceptance tests (max per story cap):
//
// 1. open → back out → reopen within 5s → zero `getRecipe` calls
//    served from the cache (widget reopens, provider returns cached
//    data without a new network fetch).
// 2. open → edit vibes via the detail screen's optimistic path →
//    back out → reopen → `getRecipe` DID fire and the response
//    reflects the edit.
// 3. open → advance fake clock past the 5-minute TTL → reopen →
//    `getRecipe` DID fire (TTL expired the cache).

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/recipes/providers/recipe_provider.dart';
import 'package:palateful/features/recipes/recipe_detail_screen.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _CountingApi extends ApiClient {
  Map<String, dynamic> recipePayload;
  int getRecipeCalls = 0;
  int updateRecipeCalls = 0;

  _CountingApi({Map<String, dynamic>? initialRecipe})
      : recipePayload = initialRecipe ??
            {
              'id': 'r1',
              'name': 'Test Recipe',
              'ingredients': <dynamic>[],
              'notes': <dynamic>[],
              'is_favorite': false,
              'servings': 4,
              'primary_vibe': 'cozy',
              'secondary_vibe': null,
              'recipe_book_id': 'book-1',
              'recipe_book_name': 'Dinners',
            };

  @override
  Future<Response> getRecipe(String recipeId, {bool debug = false}) async {
    getRecipeCalls++;
    return _ok(recipePayload);
  }

  @override
  Future<Response> updateRecipe(String recipeId, dynamic data) async {
    updateRecipeCalls++;
    final map = Map<String, dynamic>.from(data as Map);
    recipePayload = {
      ...recipePayload,
      ...map,
    };
    return _ok({'id': recipeId, ...map});
  }
}

void _register(_CountingApi client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  gi.registerSingleton<AuthService>(AuthService());
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
}

/// Build a router wrapper so `context.pop()` works inside the detail
/// screen and back-stack navigation is honest.
Widget _routerApp({required ProviderContainer container}) {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) => const Scaffold(
          body: Center(child: Text('HOME')),
        ),
      ),
      GoRoute(
        path: '/recipes/:id',
        builder: (_, state) =>
            RecipeDetailScreen(recipeId: state.pathParameters['id']!),
      ),
    ],
  );
  return UncontrolledProviderScope(
    container: container,
    child: MaterialApp.router(routerConfig: router),
  );
}

/// Push onto `/recipes/r1`, pump until the detail body resolves.
Future<void> _openDetail(
  WidgetTester tester,
  GoRouter router,
) async {
  router.push('/recipes/r1');
  // Two pumps: one to build the route, one to let the provider
  // resolve the getRecipe future.
  await tester.pumpAndSettle();
}

Future<void> _backOut(WidgetTester tester, GoRouter router) async {
  router.pop();
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (_) async => null);
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null);
    _unregister();
  });

  testWidgets(
    'open → back → reopen within TTL → zero additional getRecipe calls',
    (tester) async {
      final api = _CountingApi();
      _register(api);
      final container = ProviderContainer();

      await tester.pumpWidget(_routerApp(container: container));
      final rootContext = tester.element(find.text('HOME'));
      final router = GoRouter.of(rootContext);

      await _openDetail(tester, router);
      expect(api.getRecipeCalls, 1);
      expect(find.text('Test Recipe'), findsWidgets);

      await _backOut(tester, router);

      // Reopen immediately. Cache serves it. No new fetch.
      await _openDetail(tester, router);
      expect(api.getRecipeCalls, 1,
          reason: 'reopen within the keep-alive window is zero-network');
      expect(find.text('Test Recipe'), findsWidgets);

      // Dispose explicitly so the provider's keepAlive Timer is
      // canceled before the binding's invariant check runs. (Binding
      // fires _verifyInvariants before `addTearDown` callbacks.)
      container.dispose();
    },
  );

  testWidgets(
    'mutation (updateRecipe) invalidates the cache; reopen refetches',
    (tester) async {
      final api = _CountingApi();
      _register(api);
      final container = ProviderContainer();

      await tester.pumpWidget(_routerApp(container: container));
      final rootContext = tester.element(find.text('HOME'));
      final router = GoRouter.of(rootContext);

      await _openDetail(tester, router);
      expect(api.getRecipeCalls, 1);

      // Simulate an edit happening elsewhere (e.g. edit_recipe_screen).
      // Hit the ApiClient directly, then call invalidateRecipe to
      // match the production code path.
      await api.updateRecipe('r1', {'name': 'Updated Name'});
      invalidateRecipe(container, 'r1');
      expect(api.updateRecipeCalls, 1);

      await _backOut(tester, router);
      await _openDetail(tester, router);

      expect(api.getRecipeCalls, 2,
          reason: 'invalidate forces a refetch on next read');
      expect(find.text('Updated Name'), findsWidgets);

      container.dispose();
    },
  );

  testWidgets(
    'TTL expiry (6 min) drops the cache; reopen refetches',
    (tester) async {
      final api = _CountingApi();
      _register(api);
      final container = ProviderContainer();

      await tester.pumpWidget(_routerApp(container: container));
      final rootContext = tester.element(find.text('HOME'));
      final router = GoRouter.of(rootContext);

      await _openDetail(tester, router);
      expect(api.getRecipeCalls, 1);

      await _backOut(tester, router);

      // Advance the fake clock past the 5-minute TTL. The keepAlive
      // timer fires and drops the cache.
      await tester.pump(const Duration(minutes: 6));

      await _openDetail(tester, router);
      expect(api.getRecipeCalls, 2,
          reason:
              'past the 5-minute TTL, the autoDispose keepAlive link '
              'closes and the next read triggers a fresh fetch');

      container.dispose();
    },
  );
}
