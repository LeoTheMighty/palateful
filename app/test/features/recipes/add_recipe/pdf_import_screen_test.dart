import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/recipes/add_recipe/pdf_import_screen.dart';

// sru-3: regression — the share flow hands a pre-selected PDF path in
// via the `initialPath` constructor param (landed in sae-2). We can't
// integration-test the full pre-fill path in `flutter_tester` because
// `File.stat()` in initState stalls the default fake-async zone; the
// behavior is covered in the manual QA walkthrough. Here we assert
// the default (no-seed) render and that the `initialPath` param is
// structurally accepted.

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
  dotenv.loadFromString(
    envString:
        'API_BASE_URL=http://localhost:8000\n'
        'AUTH0_DOMAIN=test.auth0.com\n'
        'AUTH0_CLIENT_ID=test-client-id\n'
        'AUTH0_AUDIENCE=https://api.test/\n',
    isOptional: true,
  );

  setUp(_registerFakes);
  tearDown(_unregister);

  testWidgets('no initialPath → picker button shows default label',
      (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: PdfImportScreen()),
    );
    await tester.pump();
    expect(find.text('Choose PDF file'), findsOneWidget);
  });

  test('constructor accepts initialPath without throwing', () {
    expect(
      const PdfImportScreen(initialPath: '/sandbox/x.pdf').initialPath,
      '/sandbox/x.pdf',
    );
  });
}
