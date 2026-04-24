import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/recipes/add_recipe/text_paste_import_screen.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

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
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(_registerFakes);
  tearDown(_unregister);

  testWidgets('initialText pre-fills textarea', (tester) async {
    const seed = 'Paste from a shared text file';
    await tester.pumpWidget(
      const MaterialApp(home: TextPasteImportScreen(initialText: seed)),
    );
    await tester.pump();

    expect(find.text(seed), findsOneWidget);
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller?.text,
      seed,
    );
  });

  testWidgets('no initialText → textarea empty', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: TextPasteImportScreen()),
    );
    await tester.pump();

    expect(
      tester.widget<TextField>(find.byType(TextField)).controller?.text,
      '',
    );
  });
}
