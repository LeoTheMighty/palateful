import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';

/// What kind of handoff the receiving screen will perform.
enum ReceiveBranch {
  /// Direct URL import — call API, then route to Activity Hub.
  url,

  /// Image → `PhotoCaptureScreen(initialPath: ...)`.
  image,

  /// PDF → upload + `/import` → Activity Hub (sru-4).
  pdf,

  /// Audio → upload + `/import` → Activity Hub (sru-4).
  audio,

  /// Video file → upload + `/import` with `source_type=video_file` (sru-4/5).
  video,

  /// Spreadsheet → `SpreadsheetImportScreen(initialPath: ...)`.
  spreadsheet,

  /// Plain text file — inline into `TextPasteImportScreen` or treated as URL.
  text,

  /// Over the 100 MB presigned-upload cap.
  oversize,

  /// Unknown or unsupported (.docx / .zip / etc).
  unsupported,
}

/// Stage of the receiving UX lifecycle.
enum ReceivePhase { detecting, uploading, navigating, error }

/// All possible error codes surfaced on the receiving screen. Each maps
/// to a distinct user-facing copy string per the epic's "machine-readable
/// error codes" principle.
enum ReceiveErrorCode {
  network,
  unauthorized,
  tooLarge,
  objectNotReady,
  duplicate,
  rateLimited,
  unknown,
}

@immutable
class ReceiveImportState {
  const ReceiveImportState({
    required this.phase,
    this.branch,
    this.uploadedBytes = 0,
    this.totalBytes = 0,
    this.errorCode,
    this.errorMessage,
    this.destination,
    this.dedupKey,
  });

  final ReceivePhase phase;
  final ReceiveBranch? branch;
  final int uploadedBytes;
  final int totalBytes;
  final ReceiveErrorCode? errorCode;
  final String? errorMessage;

  /// Where the screen will navigate to when phase becomes `navigating`.
  final String? destination;

  /// `sha256(path + mtime + size)` — the sru-1 dedup key. Used both as
  /// the `s3_key` suffix (so a second PUT to the same key is a no-op in
  /// S3) and to guard against OS double-fire of the share intent.
  final String? dedupKey;

  ReceiveImportState copyWith({
    ReceivePhase? phase,
    ReceiveBranch? branch,
    int? uploadedBytes,
    int? totalBytes,
    ReceiveErrorCode? errorCode,
    String? errorMessage,
    String? destination,
    String? dedupKey,
  }) {
    return ReceiveImportState(
      phase: phase ?? this.phase,
      branch: branch ?? this.branch,
      uploadedBytes: uploadedBytes ?? this.uploadedBytes,
      totalBytes: totalBytes ?? this.totalBytes,
      errorCode: errorCode ?? this.errorCode,
      errorMessage: errorMessage ?? this.errorMessage,
      destination: destination ?? this.destination,
      dedupKey: dedupKey ?? this.dedupKey,
    );
  }
}

/// Content-type detection table. Drives `detectBranch` from either the
/// MIME hint or the path extension when MIME is absent.
///
/// Regression-tested against `.jpg .heic .pdf .mp3 .m4a .wav .mp4 .mov
/// .csv .xlsx .txt .docx .zip .rtf` plus the missing-MIME path.
@visibleForTesting
const Map<String, ReceiveBranch> kMimeToBranch = {
  // images
  'image/jpeg': ReceiveBranch.image,
  'image/jpg': ReceiveBranch.image,
  'image/png': ReceiveBranch.image,
  'image/gif': ReceiveBranch.image,
  'image/webp': ReceiveBranch.image,
  'image/heic': ReceiveBranch.image,
  'image/heif': ReceiveBranch.image,
  // documents
  'application/pdf': ReceiveBranch.pdf,
  // audio
  'audio/mpeg': ReceiveBranch.audio,
  'audio/mp4': ReceiveBranch.audio,
  'audio/x-m4a': ReceiveBranch.audio,
  'audio/wav': ReceiveBranch.audio,
  'audio/x-wav': ReceiveBranch.audio,
  'audio/aac': ReceiveBranch.audio,
  'audio/ogg': ReceiveBranch.audio,
  'audio/webm': ReceiveBranch.audio,
  // video
  'video/mp4': ReceiveBranch.video,
  'video/quicktime': ReceiveBranch.video,
  'video/x-m4v': ReceiveBranch.video,
  'video/webm': ReceiveBranch.video,
  // spreadsheets
  'text/csv': ReceiveBranch.spreadsheet,
  'application/vnd.ms-excel': ReceiveBranch.spreadsheet,
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
      ReceiveBranch.spreadsheet,
  // text
  'text/plain': ReceiveBranch.text,
};

@visibleForTesting
const Map<String, ReceiveBranch> kExtensionToBranch = {
  'jpg': ReceiveBranch.image,
  'jpeg': ReceiveBranch.image,
  'png': ReceiveBranch.image,
  'gif': ReceiveBranch.image,
  'webp': ReceiveBranch.image,
  'heic': ReceiveBranch.image,
  'heif': ReceiveBranch.image,
  'pdf': ReceiveBranch.pdf,
  'mp3': ReceiveBranch.audio,
  'm4a': ReceiveBranch.audio,
  'wav': ReceiveBranch.audio,
  'aac': ReceiveBranch.audio,
  'ogg': ReceiveBranch.audio,
  'mp4': ReceiveBranch.video,
  'mov': ReceiveBranch.video,
  'm4v': ReceiveBranch.video,
  'webm': ReceiveBranch.video,
  'csv': ReceiveBranch.spreadsheet,
  'xlsx': ReceiveBranch.spreadsheet,
  'xls': ReceiveBranch.spreadsheet,
  'txt': ReceiveBranch.text,
  // Explicitly unsupported — declared here so the table covers the full
  // regression surface from the epic's AC.
  'docx': ReceiveBranch.unsupported,
  'doc': ReceiveBranch.unsupported,
  'zip': ReceiveBranch.unsupported,
  'rtf': ReceiveBranch.unsupported,
};

/// Classify a share payload into a receiving branch.
///
/// Precedence:
/// 1. MIME hint (share intents carry one on both iOS and Android).
/// 2. Extension off the filename or path when MIME is missing.
/// 3. Fall through to `unsupported`.
ReceiveBranch detectBranch({String? mime, String? filename, String? path}) {
  final lowered = (mime ?? '').toLowerCase().trim();
  if (lowered.isNotEmpty) {
    final exact = kMimeToBranch[lowered];
    if (exact != null) return exact;
    // Wildcards (image/*, audio/*, video/*) — match the prefix.
    if (lowered.startsWith('image/')) return ReceiveBranch.image;
    if (lowered.startsWith('audio/')) return ReceiveBranch.audio;
    if (lowered.startsWith('video/')) return ReceiveBranch.video;
  }

  final ext = _extensionOf(filename) ?? _extensionOf(path);
  if (ext != null) {
    final match = kExtensionToBranch[ext];
    if (match != null) return match;
  }

  return ReceiveBranch.unsupported;
}

String? _extensionOf(String? value) {
  if (value == null || value.isEmpty) return null;
  final idx = value.lastIndexOf('.');
  if (idx <= 0 || idx == value.length - 1) return null;
  return value.substring(idx + 1).toLowerCase();
}

/// Compute the dedup key from file metadata. Exposed for tests + reuse
/// as the `s3_key` suffix so a second PUT to the same key is a no-op.
String computeDedupKey({
  required String path,
  required int mtimeMicros,
  required int sizeBytes,
}) {
  final raw = '$path|$mtimeMicros|$sizeBytes';
  return sha256.convert(utf8.encode(raw)).toString();
}

/// Tracks recently-seen dedup keys within a 2-second sliding window.
/// A second `onDetect` with the same key inside the window is a no-op —
/// the OS sometimes fires share intents twice in quick succession.
class _DedupGuard {
  final Map<String, DateTime> _seen = {};

  bool shouldProcess(String key, {Duration ttl = const Duration(seconds: 2)}) {
    final now = DateTime.now();
    _seen.removeWhere((_, seen) => now.difference(seen) > ttl);
    if (_seen.containsKey(key)) return false;
    _seen[key] = now;
    return true;
  }
}

/// State machine driving the receiving screen. Pure plumbing — the
/// screen wires the async side-effects (API call, presigned PUT, typed
/// screen handoff) around it.
class ReceiveImportNotifier extends ValueNotifier<ReceiveImportState> {
  ReceiveImportNotifier()
      : super(const ReceiveImportState(phase: ReceivePhase.detecting));

  final _DedupGuard _dedup = _DedupGuard();

  /// Enter the detecting state and emit the branch. Returns `null` if
  /// this is a duplicate fire within the dedup window.
  ReceiveBranch? onDetect({
    String? mime,
    String? filename,
    String? path,
    String? dedupKey,
  }) {
    if (dedupKey != null && !_dedup.shouldProcess(dedupKey)) {
      return null;
    }
    final branch = detectBranch(mime: mime, filename: filename, path: path);
    value = value.copyWith(
      phase: ReceivePhase.detecting,
      branch: branch,
      dedupKey: dedupKey,
    );
    return branch;
  }

  void enterUploading({int total = 0}) {
    value = value.copyWith(
      phase: ReceivePhase.uploading,
      uploadedBytes: 0,
      totalBytes: total,
    );
  }

  void updateUploadProgress({required int uploaded, int? total}) {
    value = value.copyWith(
      phase: ReceivePhase.uploading,
      uploadedBytes: uploaded,
      totalBytes: total ?? value.totalBytes,
    );
  }

  void enterNavigating(String destination) {
    value = value.copyWith(
      phase: ReceivePhase.navigating,
      destination: destination,
    );
  }

  void enterError(ReceiveErrorCode code, String message) {
    value = value.copyWith(
      phase: ReceivePhase.error,
      errorCode: code,
      errorMessage: message,
    );
  }

  void markOversize() {
    value = value.copyWith(
      phase: ReceivePhase.error,
      branch: ReceiveBranch.oversize,
      errorCode: ReceiveErrorCode.tooLarge,
    );
  }
}

/// Pure helper — picks the right error code for a failed upload-url or
/// /import response. Keeps the screen free of HTTP-status bookkeeping.
ReceiveErrorCode classifyHttpStatus(int status) {
  if (status == 401 || status == 403) return ReceiveErrorCode.unauthorized;
  if (status == 413) return ReceiveErrorCode.tooLarge;
  if (status == 409) return ReceiveErrorCode.objectNotReady;
  if (status == 429) return ReceiveErrorCode.rateLimited;
  return ReceiveErrorCode.unknown;
}
