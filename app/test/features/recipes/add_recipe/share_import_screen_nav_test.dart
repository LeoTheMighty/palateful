import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/recipes/add_recipe/share_import_screen.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

/// Stub ApiClient that returns zero books so ShareImportScreen renders
/// the error state with a Close button. That is enough to exercise
/// the warm/cold terminal nav helper without wiring the full happy path.
class _StubApiClient extends ApiClient {
  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      _fakeResponse({'items': []});
}

void _registerFakes() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(_StubApiClient());
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  gi.registerSingleton<AuthService>(AuthService());
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
}

void main() {
  setUpAll(() async {
  });
  setUp(_registerFakes);
  tearDown(_unregister);

  group('ShareImportScreen — terminal nav', () {
    testWidgets('warm launch: Close returns to previous route',
        (tester) async {
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(
            path: '/',
            builder: (_, _) =>
                const Scaffold(body: Text('HOME')),
          ),
          GoRoute(
            path: '/share',
            builder: (_, _) => const ShareImportScreen(
              initialUrl: 'https://example.com/recipe',
            ),
          ),
        ],
      );

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      router.push('/share');
      await tester.pumpAndSettle();

      // Error-state Close button (exposed because there are no books).
      final closeButton = find.widgetWithText(OutlinedButton, 'Close');
      expect(closeButton, findsOneWidget);

      await tester.tap(closeButton);
      await tester.pumpAndSettle();

      // Warm launch returned to home.
      expect(find.text('HOME'), findsOneWidget);
    });

    testWidgets('cold launch: Close falls back to /', (tester) async {
      // No prior GoRouter location — share is the initial one.
      final router = GoRouter(
        initialLocation: '/share',
        routes: [
          GoRoute(
            path: '/',
            builder: (_, _) =>
                const Scaffold(body: Text('HOME')),
          ),
          GoRoute(
            path: '/share',
            builder: (_, _) => const ShareImportScreen(
              initialUrl: 'https://example.com/recipe',
            ),
          ),
        ],
      );

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      final closeButton = find.widgetWithText(OutlinedButton, 'Close');
      expect(closeButton, findsOneWidget);

      await tester.tap(closeButton);
      await tester.pumpAndSettle();

      // Cold launch: no prior route, landed on home via context.go('/').
      expect(find.text('HOME'), findsOneWidget);
    });
  });
}
