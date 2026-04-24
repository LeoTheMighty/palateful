import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/recipes/add_recipe/photo_capture_screen.dart';

// sru-3: see pdf_import_screen_test.dart. File.readAsBytes in initState
// stalls fake-async — the integration is exercised by the receive-
// screen widget test and the manual QA walkthrough.

class _StubApiClient extends ApiClient {
  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      Response(
        data: {'items': []},
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
      );
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
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(_registerFakes);
  tearDown(_unregister);

  testWidgets('no initialPath → picker empty state visible',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: PhotoCaptureScreen()),
      ),
    );
    await tester.pump();
    expect(find.text('Tap to select images'), findsOneWidget);
  });

  test('constructor accepts initialPath without throwing', () {
    expect(
      const PhotoCaptureScreen(initialPath: '/sandbox/x.jpg').initialPath,
      '/sandbox/x.jpg',
    );
  });
}
