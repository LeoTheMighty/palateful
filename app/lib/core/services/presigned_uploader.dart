import 'dart:io';

import 'package:dio/dio.dart';

/// Outcome of a presigned S3 PUT.
class PresignedPutResult {
  const PresignedPutResult({required this.statusCode, this.etag});

  final int statusCode;

  /// S3's `ETag` response header with the surrounding quotes stripped —
  /// same normalization the iOS Share Extension applies (see
  /// `PalatefulShare/UploadService.swift`) so both clients hand the
  /// backend an identical `etag` value for the same object.
  final String? etag;

  bool get isSuccess => statusCode >= 200 && statusCode < 300;
}

/// Thrown when an in-flight PUT was cancelled by [PresignedUploader.abort]
/// — i.e. the user closed the receiving screen mid-upload. Callers should
/// swallow this rather than surfacing an error card: the screen is gone.
class UploadAbortedException implements Exception {
  const UploadAbortedException();

  @override
  String toString() => 'UploadAbortedException: upload cancelled by caller';
}

/// Streams a local file to a presigned S3 URL, reporting byte-level
/// progress and supporting a hard [abort].
///
/// Split out as an interface so the receiving screen's upload sequence is
/// unit-testable without a socket — see
/// `test/features/recipes/add_recipe/state/receive_upload_coordinator_test.dart`.
abstract class PresignedUploader {
  /// PUT [sizeBytes] of [filePath] to [uploadUrl].
  ///
  /// [headers] are the `required_headers` returned verbatim by
  /// `POST /v1/imports/upload-url` — they're part of the signature, so
  /// dropping or mutating one produces a 403 from S3.
  ///
  /// [onProgress] fires as chunks are handed to the socket.
  Future<PresignedPutResult> put({
    required String uploadUrl,
    required String filePath,
    required int sizeBytes,
    Map<String, String> headers = const {},
    void Function(int sent, int total)? onProgress,
  });

  /// Cancel any in-flight PUT and refuse subsequent ones.
  ///
  /// Called from the receiving screen's `dispose()`. Without it, closing
  /// the screen mid-upload leaves a half-written S3 object that nothing
  /// ever claims (the Epic 1 24 h lifecycle rule sweeps it, but that's a
  /// backstop, not the contract).
  void abort();
}

/// Dio-backed [PresignedUploader]. Deliberately uses its own [Dio]
/// instance rather than `ApiClient.dio`: the app client injects an
/// `Authorization` header on every request, and an extra header on a
/// presigned PUT invalidates the SigV4 signature.
class DioPresignedUploader implements PresignedUploader {
  DioPresignedUploader({Dio? dio})
      : _dio = dio ??
            Dio(BaseOptions(
              connectTimeout: const Duration(seconds: 15),
              // A 100 MB clip on a slow connection legitimately takes
              // minutes; the receive card shows byte progress the whole
              // time, so a short send timeout would be user-hostile.
              sendTimeout: const Duration(minutes: 10),
              receiveTimeout: const Duration(seconds: 60),
            ));

  final Dio _dio;
  CancelToken? _inFlight;
  bool _aborted = false;

  @override
  Future<PresignedPutResult> put({
    required String uploadUrl,
    required String filePath,
    required int sizeBytes,
    Map<String, String> headers = const {},
    void Function(int sent, int total)? onProgress,
  }) async {
    if (_aborted) throw const UploadAbortedException();

    final token = CancelToken();
    _inFlight = token;

    var sent = 0;
    final body = File(filePath).openRead().map((chunk) {
      sent += chunk.length;
      onProgress?.call(sent, sizeBytes);
      return chunk;
    });

    try {
      final response = await _dio.put<void>(
        uploadUrl,
        data: body,
        cancelToken: token,
        options: Options(
          headers: {
            ...headers,
            // Explicit because a Stream body carries no implicit length,
            // and the presigned URL signs the exact byte count.
            Headers.contentLengthHeader: sizeBytes,
          },
          responseType: ResponseType.plain,
          // S3 failures come back as an XML body we classify ourselves;
          // let every status through instead of wrapping it in a
          // DioException the caller would have to unwrap again.
          validateStatus: (_) => true,
        ),
      );
      return PresignedPutResult(
        statusCode: response.statusCode ?? 0,
        etag: normalizeEtag(response.headers.value('etag')),
      );
    } on DioException catch (e) {
      if (CancelToken.isCancel(e)) throw const UploadAbortedException();
      rethrow;
    } finally {
      if (identical(_inFlight, token)) _inFlight = null;
    }
  }

  @override
  void abort() {
    _aborted = true;
    _inFlight?.cancel('receiving screen disposed');
    _inFlight = null;
  }
}

/// Strip the quotes S3 wraps around `ETag` values. Returns `null` for a
/// null/empty header so the `/import` body simply omits `etag`.
String? normalizeEtag(String? raw) {
  if (raw == null) return null;
  final trimmed = raw.trim().replaceAll('"', '');
  return trimmed.isEmpty ? null : trimmed;
}
