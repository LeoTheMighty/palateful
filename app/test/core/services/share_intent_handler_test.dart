import 'dart:io';
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/share_intent_handler.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';
import 'package:shared_preferences/shared_preferences.dart';

// Lightweight unit tests for ShareIntentHandler. Covers:
//  - the routing matrix (image / pdf / audio / spreadsheet / video / url)
//  - URL-in-text gate (small text file with URL inside)
//  - URL-in-text gate does NOT trigger on large text shares
//  - multi-item skippedCount surfacing
//  - sandbox copy survives deletion of the source file
//  - auth-race pending-payload persist + consume round trip
//
// The handler is built without an AuthService so `isAuthenticated` is
// effectively true — auth-race scenarios are covered via persist /
// consume directly.

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory sandbox;

  Future<Directory> fakeAppDocs() async => sandbox;

  ShareIntentHandler buildHandler({bool authenticated = true}) {
    return ShareIntentHandler(
      appDocsDir: fakeAppDocs,
      prefs: () => SharedPreferences.getInstance(),
      authService: null,
      random: Random(42),
    );
  }

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    sandbox = await Directory.systemTemp.createTemp('sae2_test_');
  });

  tearDown(() async {
    if (await sandbox.exists()) {
      await sandbox.delete(recursive: true);
    }
  });

  SharedMediaFile fileOnDisk(File f, {String? mime}) {
    return SharedMediaFile(
      path: f.path,
      mimeType: mime,
      type: SharedMediaType.file,
    );
  }

  Future<File> writeFixture(String name, List<int> bytes) async {
    final f = File('${sandbox.path}${Platform.pathSeparator}$name');
    await f.writeAsBytes(bytes);
    return f;
  }

  group('URL routing', () {
    test('https path routes directly to /recipes/add/share', () async {
      final handler = buildHandler();
      final route = await handler.resolve([
        SharedMediaFile(
          path: 'https://allrecipes.com/foo',
          type: SharedMediaType.url,
        ),
      ]);
      expect(route, isNotNull);
      expect(route!.route, startsWith('/recipes/add/share?url='));
      expect(Uri.decodeComponent(route.route.split('url=').last),
          'https://allrecipes.com/foo');
      expect(route.skippedCount, 0);
    });

    test('url-in-text: small text/plain payload with embedded URL → share',
        () async {
      final handler = buildHandler();
      final route = await handler.resolve([
        SharedMediaFile(
          path: 'look at this recipe https://example.com/pasta yum',
          mimeType: 'text/plain',
          type: SharedMediaType.text,
        ),
      ]);
      expect(route, isNotNull);
      expect(route!.route, contains('/recipes/add/share?url='));
      expect(Uri.decodeComponent(route.route.split('url=').last),
          'https://example.com/pasta');
    });

    test('url-in-text: large payload (>4KB) is NOT sniffed', () async {
      final handler = buildHandler();
      final big = 'x' * 5000 + ' https://example.com/hidden';
      final route = await handler.resolve([
        SharedMediaFile(
          path: big,
          mimeType: 'text/plain',
          type: SharedMediaType.text,
        ),
      ]);
      // Not a real file and not under 4 KB → nothing to route.
      expect(route, isNull);
    });
  });

  group('MIME routing → /recipes/add/receive', () {
    test('image/jpeg file routes to /receive with path+mime', () async {
      final handler = buildHandler();
      final src = await writeFixture('photo.jpg', [0xFF, 0xD8, 0xFF, 0x00]);
      final route = await handler.resolve([
        fileOnDisk(src, mime: 'image/jpeg'),
      ]);
      expect(route, isNotNull);
      expect(route!.route, startsWith('/recipes/add/receive?path='));
      expect(route.route, contains('&mime=image%2Fjpeg'));
      // path should point to sandbox inbox, not the original file.
      final pathParam = Uri.parse('https://x${route.route}').queryParameters['path'];
      expect(pathParam, isNotNull);
      expect(pathParam, contains('shared_inbox'));
      expect(pathParam, isNot(src.path));
      expect(await File(pathParam!).exists(), isTrue);
    });

    test('application/pdf routes to /receive', () async {
      final handler = buildHandler();
      final src = await writeFixture('cookbook.pdf', [0x25, 0x50, 0x44, 0x46]);
      final route = await handler.resolve([
        fileOnDisk(src, mime: 'application/pdf'),
      ]);
      expect(route, isNotNull);
      expect(route!.route, contains('&mime=application%2Fpdf'));
    });

    test('audio/mpeg routes to /receive', () async {
      final handler = buildHandler();
      final src = await writeFixture('voicenote.mp3', [0x49, 0x44, 0x33]);
      final route = await handler.resolve([
        fileOnDisk(src, mime: 'audio/mpeg'),
      ]);
      expect(route, isNotNull);
      expect(route!.route, contains('&mime=audio%2Fmpeg'));
    });

    test('text/csv routes to /receive (spreadsheet branch)', () async {
      final handler = buildHandler();
      final src = await writeFixture('import.csv', 'a,b,c\n'.codeUnits);
      final route = await handler.resolve([
        fileOnDisk(src, mime: 'text/csv'),
      ]);
      expect(route, isNotNull);
      expect(route!.route, contains('&mime=text%2Fcsv'));
    });

    test('video/mp4 routes to /receive', () async {
      final handler = buildHandler();
      final src = await writeFixture('clip.mp4', [0x00, 0x00, 0x00, 0x20]);
      final route = await handler.resolve([
        fileOnDisk(src, mime: 'video/mp4'),
      ]);
      expect(route, isNotNull);
      expect(route!.route, contains('&mime=video%2Fmp4'));
    });

    test('MIME missing → extension fallback produces inferred MIME', () async {
      final handler = buildHandler();
      final src = await writeFixture('photo.jpg', [0xFF, 0xD8]);
      final route = await handler.resolve([
        fileOnDisk(src, mime: null),
      ]);
      expect(route, isNotNull);
      expect(route!.route, contains('&mime=image%2Fjpg'));
    });
  });

  group('unsupported fallback', () {
    test('.docx routes to unsupported=true with filename', () async {
      final handler = buildHandler();
      final src = await writeFixture('notes.docx', [0x50, 0x4B, 0x03, 0x04]);
      final route = await handler.resolve([
        fileOnDisk(
          src,
          mime:
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ),
      ]);
      expect(route, isNotNull);
      expect(route!.route, contains('unsupported=true'));
      expect(route.route, contains('filename=notes.docx'));
    });
  });

  group('sandbox survival', () {
    test('route points at sandbox copy even after source is deleted',
        () async {
      final handler = buildHandler();
      final src = await writeFixture('photo.jpg', [0xFF, 0xD8]);
      final route = await handler.resolve([
        fileOnDisk(src, mime: 'image/jpeg'),
      ]);
      final pathParam =
          Uri.parse('https://x${route!.route}').queryParameters['path']!;
      // Source deleted as if the OS share context expired mid-navigate.
      await src.delete();
      expect(await File(pathParam).exists(), isTrue);
    });
  });

  group('multi-item', () {
    test('ACTION_SEND_MULTIPLE with 3 items: first processed, 2 skipped',
        () async {
      final handler = buildHandler();
      final a = await writeFixture('a.jpg', [0xFF]);
      final b = await writeFixture('b.jpg', [0xFF]);
      final c = await writeFixture('c.jpg', [0xFF]);
      final route = await handler.resolve([
        fileOnDisk(a, mime: 'image/jpeg'),
        fileOnDisk(b, mime: 'image/jpeg'),
        fileOnDisk(c, mime: 'image/jpeg'),
      ]);
      expect(route, isNotNull);
      expect(route!.skippedCount, 2);
      // Only first file copied into sandbox.
      final inbox =
          Directory('${sandbox.path}${Platform.pathSeparator}shared_inbox');
      final contents = await inbox.list().toList();
      expect(contents.length, 1);
    });
  });

  group('auth-race replay', () {
    test('persist then consume round-trips the pending route', () async {
      final handler = buildHandler();
      await handler.persistPending(
        '/recipes/add/receive?path=/tmp/x.jpg&mime=image%2Fjpeg',
      );
      final first = await handler.consumePending();
      expect(first,
          '/recipes/add/receive?path=/tmp/x.jpg&mime=image%2Fjpeg');
      // Second consume clears it.
      final second = await handler.consumePending();
      expect(second, isNull);
    });

    test('no pending → consumePending returns null', () async {
      final handler = buildHandler();
      expect(await handler.consumePending(), isNull);
    });
  });

  group('empty / degenerate inputs', () {
    test('empty list → null', () async {
      final handler = buildHandler();
      expect(await handler.resolve([]), isNull);
    });

    test('empty string path → null', () async {
      final handler = buildHandler();
      expect(
        await handler.resolve([
          SharedMediaFile(path: '   ', type: SharedMediaType.text),
        ]),
        isNull,
      );
    });
  });
}
