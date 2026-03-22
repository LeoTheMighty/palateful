import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/profile/profile_screen.dart';
import 'package:palateful/providers/theme_mode_provider.dart' show FontStyleNotifier, FontStyle, ThemeModeNotifier, fontStyleProvider, themeModeProvider;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

Map<String, dynamic> _fakeMeResponse() => {
      'id': 'user-1',
      'email': 'test@example.com',
      'name': 'Test User',
      'username': 'testuser',
      'picture': null,
      'has_completed_onboarding': true,
      'default_recipe_book_id': null,
      'created_at': '2026-01-01T00:00:00Z',
      'username_changed_at': null,
      'pending_invitation_count': 0,
    };

class _SlowFakeApiClient extends ApiClient {
  final void Function() onExport;
  _SlowFakeApiClient({required this.onExport});

  @override
  Future<Response> getMe() async => _fakeResponse(_fakeMeResponse());

  @override
  Future<Response> exportRecipes() async {
    onExport();
    await Future.delayed(const Duration(milliseconds: 500));
    return _fakeResponse({'exported_at': '', 'recipe_count': 0, 'book_count': 0, 'books': []});
  }
}

class _FakeAuthService extends AuthService {
  @override
  Future<void> logout() async {}
}

class _FakeApiClient extends ApiClient {
  bool exportCalled = false;
  bool shouldThrow = false;

  @override
  Future<Response> getMe() async => _fakeResponse(_fakeMeResponse());

  @override
  Future<Response> exportRecipes() async {
    exportCalled = true;
    if (shouldThrow) throw Exception('network error');
    return _fakeResponse({
      'exported_at': '2026-03-19T12:00:00Z',
      'recipe_count': 3,
      'book_count': 1,
      'books': [],
    });
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(_FakeApiClient());
    if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
    gi.registerSingleton<AuthService>(_FakeAuthService());
  });

  tearDown(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  });

  group('Export Collection tile', () {
    testWidgets('"Export Collection" tile is visible in Recipes section',
        (tester) async {
      await tester.pumpWidget(ProviderScope(
          overrides: [
            themeModeProvider
                .overrideWith(() => ThemeModeNotifier(ThemeMode.system)),
            fontStyleProvider
                .overrideWith(() => FontStyleNotifier(FontStyle.classic)),
          ],
          child: const MaterialApp(home: ProfileScreen()),
        ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Export Collection'), findsOneWidget);
    });

    testWidgets('tapping tile calls exportRecipes() on the API client',
        (tester) async {
      final fakeClient = GetIt.instance<ApiClient>() as _FakeApiClient;

      await tester.pumpWidget(ProviderScope(
          overrides: [
            themeModeProvider
                .overrideWith(() => ThemeModeNotifier(ThemeMode.system)),
            fontStyleProvider
                .overrideWith(() => FontStyleNotifier(FontStyle.classic)),
          ],
          child: const MaterialApp(home: ProfileScreen()),
        ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.ensureVisible(find.text('Export Collection'));
      await tester.tap(find.text('Export Collection'));
      await tester.pumpAndSettle();

      expect(fakeClient.exportCalled, isTrue);
    });

    testWidgets('double-tap does not call exportRecipes() twice',
        (tester) async {
      int callCount = 0;
      final gi = GetIt.instance;
      if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
      final slowClient = _SlowFakeApiClient(onExport: () => callCount++);
      gi.registerSingleton<ApiClient>(slowClient);

      await tester.pumpWidget(ProviderScope(
          overrides: [
            themeModeProvider
                .overrideWith(() => ThemeModeNotifier(ThemeMode.system)),
            fontStyleProvider
                .overrideWith(() => FontStyleNotifier(FontStyle.classic)),
          ],
          child: const MaterialApp(home: ProfileScreen()),
        ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.ensureVisible(find.text('Export Collection'));
      // Tap twice in rapid succession
      await tester.tap(find.text('Export Collection'));
      await tester.pump();
      await tester.tap(find.text('Export Collection'));
      await tester.pumpAndSettle();

      expect(callCount, 1);
    });

    testWidgets('error shows "Export failed — please try again" snackbar',
        (tester) async {
      final fakeClient = GetIt.instance<ApiClient>() as _FakeApiClient;
      fakeClient.shouldThrow = true;

      await tester.pumpWidget(ProviderScope(
          overrides: [
            themeModeProvider
                .overrideWith(() => ThemeModeNotifier(ThemeMode.system)),
            fontStyleProvider
                .overrideWith(() => FontStyleNotifier(FontStyle.classic)),
          ],
          child: const MaterialApp(home: ProfileScreen()),
        ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.ensureVisible(find.text('Export Collection'));
      await tester.tap(find.text('Export Collection'));
      await tester.pumpAndSettle();

      expect(
        find.text('Export failed — please try again'),
        findsOneWidget,
      );
    });
  });
}
