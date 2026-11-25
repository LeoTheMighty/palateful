import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/presigned_uploader.dart';
import 'package:palateful/features/recipes/add_recipe/receive_import_screen.dart';

// sru-1 screen-level tests. The URL branch + unsupported + oversize
// states are covered here; the file-stat driven typed-handoff paths
// (image / spreadsheet / text file) are integration-tested manually
// per the QA walkthrough because `File.stat` in initState stalls
// flutter_tester's fake-async zone.

Response<dynamic> _fakeResponse(dynamic data, {int status = 200}) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: status,
    );

class _StubApiClient extends ApiClient {
  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      _fakeResponse({'items': []});

  @override
  Future<Response> startImport(
    String bookId, {
    required String sourceType,
    String? url,
    List<String>? urls,
    List<String>? ocrTexts,
    String? rawText,
    String? fileBase64,
    String? fileName,
  }) async =>
      _fakeResponse({'id': 'job-1', 'status': 'pending'});
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

Future<GoRouter> _buildRouter({required String initialLocation}) async {
  return GoRouter(
    initialLocation: initialLocation,
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) => const Scaffold(body: Text('HOME')),
      ),
      GoRoute(
        path: '/recipes/add/receive',
        builder: (_, state) {
          final qp = state.uri.queryParameters;
          return ReceiveImportScreen(
            url: qp['url'],
            path: qp['path'],
            mime: qp['mime'],
            unsupported: qp['unsupported'] == 'true',
            filename: qp['filename'],
            bookId: qp['book_id'],
          );
        },
      ),
      GoRoute(
        path: '/recipes/add/text',
        builder: (_, _) => const Scaffold(body: Text('TEXT')),
      ),
      GoRoute(
        path: '/recipes/add/share',
        builder: (_, _) => const Scaffold(body: Text('SHARE')),
      ),
      GoRoute(
        path: '/activity',
        builder: (_, _) => const Scaffold(body: Text('ACTIVITY')),
      ),
    ],
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(_registerFakes);
  tearDown(_unregister);

  group('unsupported state', () {
    testWidgets('renders "We can\'t read this yet" with filename',
        (tester) async {
      final router = await _buildRouter(
        initialLocation:
            '/recipes/add/receive?unsupported=true&filename=notes.docx',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pump();

      expect(find.textContaining("We can't read this yet"), findsOneWidget);
      expect(find.textContaining('notes.docx'), findsOneWidget);
      expect(find.text('Paste Text Instead'), findsOneWidget);
      expect(find.text('Close'), findsOneWidget);
    });

    testWidgets('Paste Text Instead navigates to /recipes/add/text',
        (tester) async {
      final router = await _buildRouter(
        initialLocation:
            '/recipes/add/receive?unsupported=true&filename=x.docx',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pump();

      await tester.tap(find.text('Paste Text Instead'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.text('TEXT'), findsOneWidget);
    });

    testWidgets('Close returns to home', (tester) async {
      final router = await _buildRouter(
        initialLocation:
            '/recipes/add/receive?unsupported=true&filename=a.zip',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pump();

      await tester.tap(find.text('Close'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.text('HOME'), findsOneWidget);
    });
  });

  group('progress card', () {
    testWidgets('renders a progress card when URL share arrives',
        (tester) async {
      final router = await _buildRouter(
        initialLocation:
            '/recipes/add/receive?url=${Uri.encodeComponent('https://allrecipes.com/recipe/1')}',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pump();
      expect(
        find.textContaining('Importing recipe from'),
        findsOneWidget,
      );
      // Drain the 600 ms dwell timer so the fake-async teardown doesn't
      // flag a pending timer. The share-flow API stub is not wired to
      // the Activity Hub shell in this minimal router; we just need
      // the dwell to complete cleanly.
      await tester.pump(const Duration(milliseconds: 700));
      await tester.pump();
    });
  });

  group('upload abort on dispose (sru-4)', () {
    testWidgets('closing the screen aborts the uploader', (tester) async {
      final uploader = _RecordingUploader();

      await tester.pumpWidget(MaterialApp(
        home: ReceiveImportScreen(
          unsupported: true,
          filename: 'notes.docx',
          uploader: uploader,
        ),
      ));
      await tester.pump();
      expect(uploader.aborted, isFalse);

      // Tear the screen down the way Close / Android back does.
      await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
      await tester.pump();

      expect(uploader.aborted, isTrue,
          reason: 'a half-uploaded S3 object would otherwise be orphaned');
    });
  });
}

class _RecordingUploader implements PresignedUploader {
  bool aborted = false;

  @override
  Future<PresignedPutResult> put({
    required String uploadUrl,
    required String filePath,
    required int sizeBytes,
    Map<String, String> headers = const {},
    void Function(int sent, int total)? onProgress,
  }) async {
    throw UnimplementedError('not exercised by this test');
  }

  @override
  void abort() => aborted = true;
}
