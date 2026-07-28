import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/presigned_uploader.dart';
import 'package:palateful/features/recipes/add_recipe/state/receive_import_notifier.dart';
import 'package:palateful/features/recipes/add_recipe/state/receive_upload_coordinator.dart';

// sru-4 — the presigned-upload sequence for the PDF / audio / video
// branches of the receiving screen. Exercised through the coordinator
// rather than the widget because `File.stat` in the screen's initState
// stalls flutter_tester's fake-async zone (see the note at the top of
// receive_import_screen_test.dart); the coordinator owns every byte of
// the contract the AC cares about.

Response<dynamic> _ok(dynamic data) => Response<dynamic>(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

DioException _httpError(int status, {int? errorCode, String? message}) {
  return DioException(
    requestOptions: RequestOptions(path: ''),
    response: Response<dynamic>(
      requestOptions: RequestOptions(path: ''),
      statusCode: status,
      data: {
        if (errorCode != null) 'error_code': errorCode,
        if (message != null) 'error_message': message,
      },
    ),
    type: DioExceptionType.badResponse,
  );
}

/// Records every call and replays a scripted queue of outcomes.
class _FakeApi extends ApiClient {
  _FakeApi({
    this.uploadUrlResponse,
    this.uploadUrlError,
    List<Object>? importOutcomes,
  }) : importOutcomes = importOutcomes ?? [];

  final Response<dynamic>? uploadUrlResponse;
  final DioException? uploadUrlError;

  /// Each entry is either a [Response] to return or a [DioException] to
  /// throw. The last entry repeats once exhausted.
  final List<Object> importOutcomes;

  final List<Map<String, dynamic>> uploadUrlCalls = [];
  final List<Map<String, dynamic>> importCalls = [];

  @override
  Future<Response> getImportUploadUrl({
    required String filename,
    required String mimeType,
    required int sizeBytes,
  }) async {
    uploadUrlCalls.add({
      'filename': filename,
      'mime_type': mimeType,
      'size_bytes': sizeBytes,
    });
    if (uploadUrlError != null) throw uploadUrlError!;
    return uploadUrlResponse ??
        _ok({
          'upload_url': 'https://s3.example/put',
          's3_key': 'imports/user-1/abc.pdf',
          'required_headers': {'Content-Type': 'application/pdf'},
        });
  }

  @override
  Future<Response> postImportForBook(String bookId, Map<String, dynamic> body) async {
    importCalls.add({'book_id': bookId, ...body});
    final outcome = importOutcomes.isEmpty
        ? _ok({'id': 'job-1'})
        : importOutcomes[
            importCalls.length - 1 < importOutcomes.length
                ? importCalls.length - 1
                : importOutcomes.length - 1];
    if (outcome is DioException) throw outcome;
    return outcome as Response;
  }
}

class _FakeUploader implements PresignedUploader {
  _FakeUploader({this.result, this.error});

  final PresignedPutResult? result;
  final Object? error;

  final List<Map<String, dynamic>> puts = [];
  bool aborted = false;

  @override
  Future<PresignedPutResult> put({
    required String uploadUrl,
    required String filePath,
    required int sizeBytes,
    Map<String, String> headers = const {},
    void Function(int sent, int total)? onProgress,
  }) async {
    puts.add({
      'upload_url': uploadUrl,
      'file_path': filePath,
      'size_bytes': sizeBytes,
      'headers': headers,
    });
    if (error != null) throw error!;
    // Emit a couple of progress ticks so callers can assert byte-level
    // reporting without a socket.
    onProgress?.call(sizeBytes ~/ 2, sizeBytes);
    onProgress?.call(sizeBytes, sizeBytes);
    return result ?? const PresignedPutResult(statusCode: 200, etag: 'abc123');
  }

  @override
  void abort() => aborted = true;
}

ReceiveUploadCoordinator _coordinator(_FakeApi api, _FakeUploader uploader) {
  return ReceiveUploadCoordinator(
    api: api,
    uploader: uploader,
    // Keep the suite fast — the 500 ms production backoff is asserted
    // separately via the default constructor value.
    retryBackoff: Duration.zero,
  );
}

void main() {
  group('branch → source_type', () {
    test('maps the three upload branches and nothing else', () {
      expect(sourceTypeForBranch(ReceiveBranch.pdf), 'pdf');
      expect(sourceTypeForBranch(ReceiveBranch.audio), 'audio');
      expect(sourceTypeForBranch(ReceiveBranch.video), 'video_file');
      for (final b in [
        ReceiveBranch.url,
        ReceiveBranch.image,
        ReceiveBranch.spreadsheet,
        ReceiveBranch.text,
        ReceiveBranch.oversize,
        ReceiveBranch.unsupported,
      ]) {
        expect(sourceTypeForBranch(b), isNull, reason: b.name);
      }
    });
  });

  group('resolveUploadMimeType', () {
    test('trusts an accepted share-intent hint', () {
      expect(
        resolveUploadMimeType(mime: 'video/quicktime', filename: 'clip.mov'),
        'video/quicktime',
      );
    });

    test('falls back to the extension when the hint is unusable', () {
      expect(
        resolveUploadMimeType(
          mime: 'application/octet-stream',
          filename: 'recipe.pdf',
        ),
        'application/pdf',
      );
      expect(resolveUploadMimeType(path: '/tmp/voice.m4a'), 'audio/mp4');
      expect(resolveUploadMimeType(filename: 'reel.mp4'), 'video/mp4');
    });

    test('returns null when nothing maps', () {
      expect(resolveUploadMimeType(mime: 'application/zip', filename: 'a.zip'),
          isNull);
      expect(resolveUploadMimeType(), isNull);
    });
  });

  group('happy path', () {
    test('upload-url → PUT → /import with the {s3_key, etag} body shape',
        () async {
      final api = _FakeApi();
      final uploader = _FakeUploader();
      final progress = <List<int>>[];

      final result = await _coordinator(api, uploader).run(
        bookId: 'book-1',
        branch: ReceiveBranch.pdf,
        filePath: '/tmp/share/recipe.pdf',
        filename: 'recipe.pdf',
        sizeBytes: 2048,
        mimeHint: 'application/pdf',
        idempotencyKey: 'dedup-key-1',
        onProgress: (sent, total) => progress.add([sent, total]),
      );

      // 1 — upload-url carries the signed size + canonical mime.
      expect(api.uploadUrlCalls, hasLength(1));
      expect(api.uploadUrlCalls.single, {
        'filename': 'recipe.pdf',
        'mime_type': 'application/pdf',
        'size_bytes': 2048,
      });

      // 2 — the PUT goes to the minted URL with required_headers verbatim.
      expect(uploader.puts, hasLength(1));
      expect(uploader.puts.single['upload_url'], 'https://s3.example/put');
      expect(uploader.puts.single['file_path'], '/tmp/share/recipe.pdf');
      expect(uploader.puts.single['size_bytes'], 2048);
      expect(uploader.puts.single['headers'],
          {'Content-Type': 'application/pdf'});
      expect(progress, [
        [1024, 2048],
        [2048, 2048],
      ]);

      // 3 — /import claims the object.
      expect(api.importCalls, hasLength(1));
      expect(api.importCalls.single, {
        'book_id': 'book-1',
        'source_type': 'pdf',
        's3_key': 'imports/user-1/abc.pdf',
        'etag': 'abc123',
        'file_name': 'recipe.pdf',
        'mime_type': 'application/pdf',
        'idempotency_key': 'dedup-key-1',
      });

      expect(result.jobId, 'job-1');
      expect(result.s3Key, 'imports/user-1/abc.pdf');
      expect(result.etag, 'abc123');
    });

    test('video branch posts source_type=video_file', () async {
      final api = _FakeApi();
      await _coordinator(api, _FakeUploader()).run(
        bookId: 'book-1',
        branch: ReceiveBranch.video,
        filePath: '/tmp/share/clip.mov',
        filename: 'clip.mov',
        sizeBytes: 10,
        mimeHint: 'video/quicktime',
      );
      expect(api.importCalls.single['source_type'], 'video_file');
      expect(api.importCalls.single['mime_type'], 'video/quicktime');
    });

    test('omits etag when S3 did not return one', () async {
      final api = _FakeApi();
      final uploader =
          _FakeUploader(result: const PresignedPutResult(statusCode: 200));
      await _coordinator(api, uploader).run(
        bookId: 'book-1',
        branch: ReceiveBranch.audio,
        filePath: '/tmp/share/voice.m4a',
        filename: 'voice.m4a',
        sizeBytes: 10,
      );
      expect(api.importCalls.single.containsKey('etag'), isFalse);
    });
  });

  group('409 object_not_ready retry', () {
    test('retries /import 3× then succeeds', () async {
      final api = _FakeApi(importOutcomes: [
        _httpError(409, errorCode: kErrorCodeObjectNotReady),
        _httpError(409, errorCode: kErrorCodeObjectNotReady),
        _ok({'id': 'job-9'}),
      ]);
      final coordinator = _coordinator(api, _FakeUploader());

      final result = await coordinator.run(
        bookId: 'book-1',
        branch: ReceiveBranch.pdf,
        filePath: '/tmp/a.pdf',
        filename: 'a.pdf',
        sizeBytes: 10,
      );

      expect(api.importCalls, hasLength(3));
      expect(coordinator.importAttempts, 3);
      expect(result.jobId, 'job-9');
      // The PUT is never repeated — only the claim is retried.
      expect(api.uploadUrlCalls, hasLength(1));
    });

    test('gives up after 3 retries and surfaces objectNotReady', () async {
      final api = _FakeApi(importOutcomes: [
        _httpError(409,
            errorCode: kErrorCodeObjectNotReady, message: 'not visible yet'),
      ]);
      final coordinator = _coordinator(api, _FakeUploader());

      await expectLater(
        coordinator.run(
          bookId: 'book-1',
          branch: ReceiveBranch.pdf,
          filePath: '/tmp/a.pdf',
          filename: 'a.pdf',
          sizeBytes: 10,
        ),
        throwsA(isA<ReceiveUploadFailure>()
            .having((f) => f.code, 'code', ReceiveErrorCode.objectNotReady)
            .having((f) => f.message, 'message', 'not visible yet')),
      );
      // 1 initial attempt + 3 retries.
      expect(api.importCalls, hasLength(4));
      expect(coordinator.importAttempts, 4);
    });

    test('a 409 duplicate is terminal — never retried', () async {
      final api = _FakeApi(importOutcomes: [
        _httpError(409,
            errorCode: kErrorCodeDuplicateImport,
            message: 'This file has already been imported.'),
      ]);

      await expectLater(
        _coordinator(api, _FakeUploader()).run(
          bookId: 'book-1',
          branch: ReceiveBranch.pdf,
          filePath: '/tmp/a.pdf',
          filename: 'a.pdf',
          sizeBytes: 10,
        ),
        throwsA(isA<ReceiveUploadFailure>()
            .having((f) => f.code, 'code', ReceiveErrorCode.duplicate)),
      );
      expect(api.importCalls, hasLength(1));
    });

    test('default backoff is the epic-locked 500 ms', () {
      expect(
        ReceiveUploadCoordinator(api: _FakeApi(), uploader: _FakeUploader())
            .retryBackoff,
        const Duration(milliseconds: 500),
      );
      expect(
        ReceiveUploadCoordinator(api: _FakeApi(), uploader: _FakeUploader())
            .maxImportRetries,
        3,
      );
    });
  });

  group('error classification', () {
    test('413 on upload-url → tooLarge, no PUT attempted', () async {
      final api = _FakeApi(
        uploadUrlError:
            _httpError(413, errorCode: kErrorCodeFileTooLarge, message: 'big'),
      );
      final uploader = _FakeUploader();

      await expectLater(
        _coordinator(api, uploader).run(
          bookId: 'book-1',
          branch: ReceiveBranch.pdf,
          filePath: '/tmp/a.pdf',
          filename: 'a.pdf',
          sizeBytes: 10,
        ),
        throwsA(isA<ReceiveUploadFailure>()
            .having((f) => f.code, 'code', ReceiveErrorCode.tooLarge)),
      );
      expect(uploader.puts, isEmpty);
    });

    test('401 → unauthorized', () async {
      final api = _FakeApi(uploadUrlError: _httpError(401));
      await expectLater(
        _coordinator(api, _FakeUploader()).run(
          bookId: 'book-1',
          branch: ReceiveBranch.pdf,
          filePath: '/tmp/a.pdf',
          filename: 'a.pdf',
          sizeBytes: 10,
        ),
        throwsA(isA<ReceiveUploadFailure>()
            .having((f) => f.code, 'code', ReceiveErrorCode.unauthorized)),
      );
    });

    test('403 cross-user s3_key → unauthorized', () async {
      final api = _FakeApi(importOutcomes: [
        _httpError(403, errorCode: kErrorCodeCrossUserKey),
      ]);
      await expectLater(
        _coordinator(api, _FakeUploader()).run(
          bookId: 'book-1',
          branch: ReceiveBranch.pdf,
          filePath: '/tmp/a.pdf',
          filename: 'a.pdf',
          sizeBytes: 10,
        ),
        throwsA(isA<ReceiveUploadFailure>()
            .having((f) => f.code, 'code', ReceiveErrorCode.unauthorized)),
      );
    });

    test('a malformed upload-url response fails before the PUT', () async {
      final api = _FakeApi(uploadUrlResponse: _ok({'s3_key': 'imports/u/a.pdf'}));
      final uploader = _FakeUploader();
      await expectLater(
        _coordinator(api, uploader).run(
          bookId: 'book-1',
          branch: ReceiveBranch.pdf,
          filePath: '/tmp/a.pdf',
          filename: 'a.pdf',
          sizeBytes: 10,
        ),
        throwsA(isA<ReceiveUploadFailure>()
            .having((f) => f.code, 'code', ReceiveErrorCode.unknown)),
      );
      expect(uploader.puts, isEmpty);
    });

    test('connection failure (no response) → network', () async {
      final api = _FakeApi(
        uploadUrlError: DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.connectionError,
          message: 'offline',
        ),
      );
      await expectLater(
        _coordinator(api, _FakeUploader()).run(
          bookId: 'book-1',
          branch: ReceiveBranch.pdf,
          filePath: '/tmp/a.pdf',
          filename: 'a.pdf',
          sizeBytes: 10,
        ),
        throwsA(isA<ReceiveUploadFailure>()
            .having((f) => f.code, 'code', ReceiveErrorCode.network)),
      );
    });

    test('a non-2xx from S3 is a network failure, not a session failure',
        () async {
      final api = _FakeApi();
      final uploader =
          _FakeUploader(result: const PresignedPutResult(statusCode: 403));
      await expectLater(
        _coordinator(api, uploader).run(
          bookId: 'book-1',
          branch: ReceiveBranch.pdf,
          filePath: '/tmp/a.pdf',
          filename: 'a.pdf',
          sizeBytes: 10,
        ),
        throwsA(isA<ReceiveUploadFailure>()
            .having((f) => f.code, 'code', ReceiveErrorCode.network)),
      );
      expect(api.importCalls, isEmpty);
    });

    test('an unsupported file type never reaches the network', () async {
      final api = _FakeApi();
      final uploader = _FakeUploader();
      await expectLater(
        _coordinator(api, uploader).run(
          bookId: 'book-1',
          branch: ReceiveBranch.pdf,
          filePath: '/tmp/mystery',
          filename: 'mystery',
          sizeBytes: 10,
        ),
        throwsA(isA<ReceiveUploadFailure>()
            .having((f) => f.code, 'code', ReceiveErrorCode.unknown)),
      );
      expect(api.uploadUrlCalls, isEmpty);
      expect(uploader.puts, isEmpty);
    });

    test('a non-upload branch is rejected before any call', () async {
      final api = _FakeApi();
      await expectLater(
        _coordinator(api, _FakeUploader()).run(
          bookId: 'book-1',
          branch: ReceiveBranch.image,
          filePath: '/tmp/a.jpg',
          filename: 'a.jpg',
          sizeBytes: 10,
        ),
        throwsA(isA<ReceiveUploadFailure>()),
      );
      expect(api.uploadUrlCalls, isEmpty);
    });
  });

  group('abort', () {
    test('an aborted PUT propagates UploadAbortedException, not a failure',
        () async {
      final api = _FakeApi();
      final uploader = _FakeUploader(error: const UploadAbortedException());
      await expectLater(
        _coordinator(api, uploader).run(
          bookId: 'book-1',
          branch: ReceiveBranch.pdf,
          filePath: '/tmp/a.pdf',
          filename: 'a.pdf',
          sizeBytes: 10,
        ),
        throwsA(isA<UploadAbortedException>()),
      );
      expect(api.importCalls, isEmpty);
    });
  });

  group('normalizeEtag', () {
    test('strips S3 quoting and null-collapses empties', () {
      expect(normalizeEtag('"abc123"'), 'abc123');
      expect(normalizeEtag('abc123'), 'abc123');
      expect(normalizeEtag('  "d41d8"  '), 'd41d8');
      expect(normalizeEtag(null), isNull);
      expect(normalizeEtag('""'), isNull);
    });
  });
}
