import 'dart:async';

import 'package:dio/dio.dart';

import '../../../../core/services/api_client.dart';
import '../../../../core/services/presigned_uploader.dart';
import 'receive_import_notifier.dart';

/// Backend `ErrorCode` values this flow reacts to. Mirrors
/// `libraries/utils/utils/classes/error_code.py` (share / file-upload
/// block, 290-299). HTTP status alone can't separate "S3 hasn't caught
/// up yet" (retry) from "already imported" (don't) — both are 409.
const int kErrorCodeFileTooLarge = 290;
const int kErrorCodeUnsupportedMime = 291;
const int kErrorCodeObjectNotReady = 292;
const int kErrorCodeCrossUserKey = 293;
const int kErrorCodeDuplicateImport = 294;

/// Branch → backend `source_type`. `null` means the branch doesn't go
/// through the presigned-upload path at all.
String? sourceTypeForBranch(ReceiveBranch branch) {
  switch (branch) {
    case ReceiveBranch.pdf:
      return 'pdf';
    case ReceiveBranch.audio:
      return 'audio';
    case ReceiveBranch.video:
      return 'video_file';
    case ReceiveBranch.url:
    case ReceiveBranch.image:
    case ReceiveBranch.spreadsheet:
    case ReceiveBranch.text:
    case ReceiveBranch.oversize:
    case ReceiveBranch.unsupported:
      return null;
  }
}

/// Canonical extension → mime for the upload branches. Share intents on
/// Android frequently arrive with `application/octet-stream` or no MIME
/// at all, and `POST /imports/upload-url` 400s on anything it can't map
/// to an extension — so we resolve to a known-good mime here rather than
/// forwarding whatever the OS handed us.
///
/// Keys are the same extensions `kExtensionToBranch` routes to the pdf /
/// audio / video branches; values are all present in the backend's
/// `_MIME_EXT` table (`api/v1/import_job/get_upload_url.py`).
const Map<String, String> kUploadExtensionToMime = {
  'pdf': 'application/pdf',
  'mp3': 'audio/mpeg',
  'm4a': 'audio/mp4',
  'wav': 'audio/wav',
  'aac': 'audio/aac',
  'ogg': 'audio/ogg',
  'mp4': 'video/mp4',
  'mov': 'video/quicktime',
  'm4v': 'video/x-m4v',
  'webm': 'video/webm',
};

/// Mimes the backend accepts on the upload branches. A share-intent hint
/// is only trusted when it's in here.
const Set<String> kUploadAcceptedMimes = {
  'application/pdf',
  'audio/mpeg',
  'audio/mp4',
  'audio/x-m4a',
  'audio/wav',
  'audio/x-wav',
  'audio/aac',
  'audio/ogg',
  'audio/webm',
  'video/mp4',
  'video/quicktime',
  'video/x-m4v',
  'video/webm',
};

/// Pick the mime to sign the presigned URL with. Prefers the share
/// intent's hint when the backend accepts it, else derives from the
/// filename/path extension. `null` means "we can't upload this".
String? resolveUploadMimeType({String? mime, String? filename, String? path}) {
  final hint = (mime ?? '').toLowerCase().trim();
  if (kUploadAcceptedMimes.contains(hint)) return hint;

  final ext = _extensionOf(filename) ?? _extensionOf(path);
  if (ext == null) return null;
  return kUploadExtensionToMime[ext];
}

String? _extensionOf(String? value) {
  if (value == null || value.isEmpty) return null;
  final idx = value.lastIndexOf('.');
  if (idx <= 0 || idx == value.length - 1) return null;
  return value.substring(idx + 1).toLowerCase();
}

/// A completed upload → `/import` handoff.
class ReceiveUploadResult {
  const ReceiveUploadResult({
    required this.jobId,
    required this.s3Key,
    this.etag,
  });

  final String jobId;
  final String s3Key;
  final String? etag;
}

/// A terminal failure of the upload sequence, already classified into the
/// error code the receiving screen renders copy for.
class ReceiveUploadFailure implements Exception {
  const ReceiveUploadFailure(this.code, this.message);

  final ReceiveErrorCode code;
  final String message;

  @override
  String toString() => 'ReceiveUploadFailure(${code.name}): $message';
}

/// Drives the epic's locked upload contract for the pure-upload branches
/// (PDF / audio / video):
///
/// 1. `POST /v1/imports/upload-url` → `{upload_url, s3_key, required_headers}`
/// 2. `PUT` the file bytes to S3, capturing the `ETag` response header
/// 3. `POST /v1/recipe-books/{book}/import` with `{s3_key, etag, source_type}`
///
/// Step 3 races S3's read-after-write visibility: the backend HeadObjects
/// the key and returns `409 OBJECT_NOT_READY` when it isn't there yet.
/// That single case is retried [maxImportRetries] times with
/// [retryBackoff] between attempts; every other failure is terminal.
class ReceiveUploadCoordinator {
  ReceiveUploadCoordinator({
    required ApiClient api,
    required PresignedUploader uploader,
    this.retryBackoff = const Duration(milliseconds: 500),
    this.maxImportRetries = 3,
  })  : _api = api,
        _uploader = uploader;

  final ApiClient _api;
  final PresignedUploader _uploader;
  final Duration retryBackoff;
  final int maxImportRetries;

  /// Number of `/import` attempts the last [run] made. Exposed for tests
  /// and for the QA walkthrough's retry assertion.
  int get importAttempts => _importAttempts;
  int _importAttempts = 0;

  Future<ReceiveUploadResult> run({
    required String bookId,
    required ReceiveBranch branch,
    required String filePath,
    required String filename,
    required int sizeBytes,
    String? mimeHint,
    String? idempotencyKey,
    void Function(int sent, int total)? onProgress,
    void Function()? onUploaded,
  }) async {
    _importAttempts = 0;

    final sourceType = sourceTypeForBranch(branch);
    if (sourceType == null) {
      throw ReceiveUploadFailure(
        ReceiveErrorCode.unknown,
        '${branch.name} does not use the presigned-upload path',
      );
    }

    final mimeType = resolveUploadMimeType(
      mime: mimeHint,
      filename: filename,
      path: filePath,
    );
    if (mimeType == null) {
      throw const ReceiveUploadFailure(
        ReceiveErrorCode.unknown,
        'Unsupported file type for upload',
      );
    }

    // 1 — mint the presigned URL.
    final Response<dynamic> urlResponse;
    try {
      urlResponse = await _api.getImportUploadUrl(
        filename: filename,
        mimeType: mimeType,
        sizeBytes: sizeBytes,
      );
    } on DioException catch (e) {
      throw _classify(e, fallback: "Couldn't start the upload.");
    }

    final body = urlResponse.data;
    final uploadUrl = body is Map ? body['upload_url'] as String? : null;
    final s3Key = body is Map ? body['s3_key'] as String? : null;
    if (uploadUrl == null || s3Key == null) {
      throw const ReceiveUploadFailure(
        ReceiveErrorCode.unknown,
        'Malformed upload-url response',
      );
    }
    final requiredHeaders = <String, String>{
      if (body is Map && body['required_headers'] is Map)
        for (final e in (body['required_headers'] as Map).entries)
          '${e.key}': '${e.value}',
    };

    // 2 — PUT the bytes. `UploadAbortedException` propagates untouched:
    // the screen is disposing, there's nothing left to render an error on.
    final PresignedPutResult put;
    try {
      put = await _uploader.put(
        uploadUrl: uploadUrl,
        filePath: filePath,
        sizeBytes: sizeBytes,
        headers: requiredHeaders,
        onProgress: onProgress,
      );
    } on UploadAbortedException {
      rethrow;
    } on DioException catch (e) {
      throw _classify(e, fallback: "Couldn't upload. Try again.");
    }
    if (!put.isSuccess) {
      // S3's own failures aren't API failures — a 403 here means an
      // expired or mis-signed URL, not a dead session, so don't route
      // the user to a "sign in again" card.
      throw ReceiveUploadFailure(
        put.statusCode == 413
            ? ReceiveErrorCode.tooLarge
            : ReceiveErrorCode.network,
        'S3 returned ${put.statusCode}',
      );
    }

    // 3 — claim the object. `onUploaded` is the screen's cue to swap the
    // byte bar for the "Sending to Palateful…" stage; the claim (plus
    // any 409 retries) can take seconds, and parking a determinate bar
    // at 100% for that long reads as a hang.
    onUploaded?.call();

    final importBody = <String, dynamic>{
      'source_type': sourceType,
      's3_key': s3Key,
      if (put.etag != null) 'etag': put.etag,
      'file_name': filename,
      'mime_type': mimeType,
      if (idempotencyKey != null) 'idempotency_key': idempotencyKey,
    };

    while (true) {
      _importAttempts++;
      try {
        final response = await _api.postImportForBook(bookId, importBody);
        final data = response.data;
        return ReceiveUploadResult(
          jobId: (data is Map ? data['id'] as String? : null) ?? '',
          s3Key: s3Key,
          etag: put.etag,
        );
      } on DioException catch (e) {
        final failure = _classify(e, fallback: 'Import failed.');
        final canRetry = failure.code == ReceiveErrorCode.objectNotReady &&
            _importAttempts <= maxImportRetries;
        if (!canRetry) throw failure;
        await Future<void>.delayed(retryBackoff);
      }
    }
  }

  /// Map a Dio failure onto the receiving screen's error taxonomy. The
  /// backend's numeric `error_code` wins where it's present; HTTP status
  /// is the fallback.
  ReceiveUploadFailure _classify(
    DioException e, {
    required String fallback,
  }) {
    final response = e.response;
    final status = response?.statusCode;
    if (status == null) {
      return ReceiveUploadFailure(
        ReceiveErrorCode.network,
        e.message ?? fallback,
      );
    }

    final data = response?.data;
    final errorCode = data is Map ? data['error_code'] : null;
    final message =
        (data is Map ? data['error_message'] as String? : null) ?? fallback;

    switch (errorCode) {
      case kErrorCodeObjectNotReady:
        return ReceiveUploadFailure(ReceiveErrorCode.objectNotReady, message);
      case kErrorCodeDuplicateImport:
        return ReceiveUploadFailure(ReceiveErrorCode.duplicate, message);
      case kErrorCodeFileTooLarge:
        return ReceiveUploadFailure(ReceiveErrorCode.tooLarge, message);
      case kErrorCodeUnsupportedMime:
        return ReceiveUploadFailure(ReceiveErrorCode.unknown, message);
      case kErrorCodeCrossUserKey:
        return ReceiveUploadFailure(ReceiveErrorCode.unauthorized, message);
    }

    // No (or unrecognized) error_code — an untagged 409 is the
    // conservative "S3 hasn't caught up" reading, which the retry loop
    // handles and gives up on after `maxImportRetries`.
    if (status == 409) {
      return ReceiveUploadFailure(ReceiveErrorCode.objectNotReady, message);
    }
    return ReceiveUploadFailure(classifyHttpStatus(status), message);
  }
}
