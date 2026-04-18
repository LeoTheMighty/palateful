import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/features/recipes/add_recipe/receive_import_screen.dart';

// Tests for the sae-3 receive-import placeholder. We verify:
//  - unsupported=true renders the "We can't read this yet" state with the
//    filename and both action buttons
//  - supported MIME types forward to the typed screen with path preserved
//  - unknown/missing MIME with no unsupported flag falls back to the
//    unsupported card (never leaves the user stuck on a spinner)
//
// Navigation targets are asserted via a GoRouter with stub destination
// screens; the test fires Router.of(...).go in initState so we use
// pumpAndSettle.

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  Future<GoRouter> buildRouter({
    required String initialLocation,
  }) async {
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
              path: qp['path'],
              mime: qp['mime'],
              unsupported: qp['unsupported'] == 'true',
              filename: qp['filename'],
            );
          },
        ),
        GoRoute(
          path: '/recipes/add/photo',
          builder: (_, state) {
            final path = state.uri.queryParameters['path'] ?? '';
            return Scaffold(body: Text('PHOTO $path'));
          },
        ),
        GoRoute(
          path: '/recipes/add/pdf',
          builder: (_, state) {
            final path = state.uri.queryParameters['path'] ?? '';
            return Scaffold(body: Text('PDF $path'));
          },
        ),
        GoRoute(
          path: '/recipes/add/audio',
          builder: (_, state) {
            final path = state.uri.queryParameters['path'] ?? '';
            return Scaffold(body: Text('AUDIO $path'));
          },
        ),
        GoRoute(
          path: '/recipes/add/spreadsheet',
          builder: (_, state) {
            final path = state.uri.queryParameters['path'] ?? '';
            return Scaffold(body: Text('SPREADSHEET $path'));
          },
        ),
        GoRoute(
          path: '/recipes/add/text',
          builder: (_, _) => const Scaffold(body: Text('TEXT')),
        ),
      ],
    );
  }

  group('unsupported state', () {
    testWidgets('renders "We can\'t read this yet" with filename',
        (tester) async {
      final router = await buildRouter(
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
      final router = await buildRouter(
        initialLocation:
            '/recipes/add/receive?unsupported=true&filename=x.docx',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pump();

      await tester.tap(find.text('Paste Text Instead'));
      await tester.pumpAndSettle();

      expect(find.text('TEXT'), findsOneWidget);
    });
  });

  group('forward by MIME', () {
    testWidgets('image/jpeg → /recipes/add/photo with path preserved',
        (tester) async {
      final router = await buildRouter(
        initialLocation:
            '/recipes/add/receive?path=%2Fsandbox%2Ffoo.jpg&mime=image%2Fjpeg',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      expect(find.textContaining('PHOTO /sandbox/foo.jpg'), findsOneWidget);
    });

    testWidgets('application/pdf → /recipes/add/pdf', (tester) async {
      final router = await buildRouter(
        initialLocation:
            '/recipes/add/receive?path=%2Fsandbox%2Fdoc.pdf&mime=application%2Fpdf',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      expect(find.textContaining('PDF /sandbox/doc.pdf'), findsOneWidget);
    });

    testWidgets('audio/mpeg → /recipes/add/audio', (tester) async {
      final router = await buildRouter(
        initialLocation:
            '/recipes/add/receive?path=%2Fsandbox%2Fnote.mp3&mime=audio%2Fmpeg',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      expect(find.textContaining('AUDIO /sandbox/note.mp3'), findsOneWidget);
    });

    testWidgets('text/csv → /recipes/add/spreadsheet', (tester) async {
      final router = await buildRouter(
        initialLocation:
            '/recipes/add/receive?path=%2Fsandbox%2Fdata.csv&mime=text%2Fcsv',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('SPREADSHEET /sandbox/data.csv'),
        findsOneWidget,
      );
    });
  });

  group('unroutable fallback', () {
    testWidgets('unknown MIME (application/octet-stream) → unsupported card',
        (tester) async {
      final router = await buildRouter(
        initialLocation:
            '/recipes/add/receive?path=%2Fsandbox%2Fx.bin&mime=application%2Foctet-stream',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      // Receive screen falls back to the "we can't read this" state.
      expect(find.textContaining("We can't read this yet"), findsOneWidget);
    });

    testWidgets('video/* without typed screen → unsupported card',
        (tester) async {
      final router = await buildRouter(
        initialLocation:
            '/recipes/add/receive?path=%2Fsandbox%2Fclip.mp4&mime=video%2Fmp4',
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      expect(find.textContaining("We can't read this yet"), findsOneWidget);
    });
  });
}
