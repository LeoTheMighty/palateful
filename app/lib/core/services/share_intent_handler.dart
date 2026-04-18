import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'auth_service.dart';
import 'error_reporter.dart';

/// Classifies a shared payload into a concrete in-app route.
///
/// The handler never calls `go()` itself — it just returns the target
/// route + the first-item snackbar copy (if multiple were dropped). The
/// caller (main.dart) owns navigation + the post-frame auth guard.
@immutable
class ShareRoute {
  const ShareRoute({required this.route, this.skippedCount = 0});

  /// Fully-formed go_router location including query string.
  final String route;

  /// Number of extra `SharedMediaFile`s ignored (only first processed).
  /// >0 triggers a "Only the first item was imported" snackbar.
  final int skippedCount;
}

/// Key used to persist a route string for replay on successful auth.
/// See `ShareIntentHandler.replayPendingRouteIfAny`.
@visibleForTesting
const kPendingSharePayloadKey = 'palateful_pending_share_payload';

/// Maximum payload size (bytes) at which we treat a `text/plain` share
/// as a potential URL-in-text and sniff for a `https?://` match. Beyond
/// this we treat it as a file share (prevents hijacking a large
/// clipboard that happens to contain a URL somewhere).
@visibleForTesting
const kUrlSniffMaxBytes = 4 * 1024;

/// Bytes to read from a text file when the plugin provides a path but no
/// payload preview — we inspect the first 2 KB only.
@visibleForTesting
const kTextHeadBytes = 2 * 1024;

/// MIME prefixes / exact types that the receiving screen can handle
/// today. Extension fallback handles shares from apps that supply
/// `application/octet-stream` or omit the MIME type entirely.
@visibleForTesting
const kSupportedMimePrefixes = {'image/', 'video/', 'audio/'};

@visibleForTesting
const kSupportedMimeExact = {
  'application/pdf',
  'text/csv',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
};

@visibleForTesting
const kImageExtensions = {'jpg', 'jpeg', 'png', 'heic', 'heif', 'webp', 'gif'};
@visibleForTesting
const kVideoExtensions = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v'};
@visibleForTesting
const kAudioExtensions = {'m4a', 'mp3', 'wav', 'aac', 'ogg', 'flac'};
@visibleForTesting
const kSpreadsheetExtensions = {'csv', 'xlsx', 'xls'};

/// Classifies and sandboxes an inbound list of `SharedMediaFile`s.
///
/// - Copies the first supported payload into
///   `<appDocs>/shared_inbox/<nonce>.<ext>` and returns a route pointing
///   at the sandbox path (never the OS-supplied temp URI).
/// - When auth is down at classify time, persists the route to
///   `SharedPreferences` so the app can replay it on the first
///   successful auth (sae-2 auth-race AC).
/// - Drops all but the first item; surfaces the skipped count so
///   callers can show a snackbar. Skipped sandbox files never get
///   written (we don't copy them in the first place).
class ShareIntentHandler {
  ShareIntentHandler({
    Future<Directory> Function()? appDocsDir,
    Future<SharedPreferences> Function()? prefs,
    AuthService? authService,
    Random? random,
  })  : _appDocsDir = appDocsDir ?? getApplicationDocumentsDirectory,
        _prefs = prefs ?? SharedPreferences.getInstance,
        _authService = authService,
        _random = random ?? Random.secure();

  final Future<Directory> Function() _appDocsDir;
  final Future<SharedPreferences> Function() _prefs;
  final AuthService? _authService;
  final Random _random;

  /// Classify the share payload. Returns `null` when nothing
  /// actionable was found (empty list, zero-length text).
  Future<ShareRoute?> resolve(List<SharedMediaFile> files) async {
    if (files.isEmpty) return null;

    final first = files.first;
    final skipped = files.length - 1;
    final rawPath = first.path.trim();
    if (rawPath.isEmpty) return null;

    final mime = (first.mimeType ?? '').trim().toLowerCase();

    // 1. Path itself is a URL (URL shares from Chrome / share-a-link).
    if (rawPath.startsWith('http://') || rawPath.startsWith('https://')) {
      return ShareRoute(
        route: '/recipes/add/share?url=${Uri.encodeComponent(rawPath)}',
        skippedCount: skipped,
      );
    }

    // 2. URL-in-text gate — only when:
    //    (a) MIME is text/plain or absent, AND
    //    (b) the payload is not a real file on disk, AND
    //    (c) payload (or file head) is <= 4 KB.
    //
    // The rawPath for text/plain shares is usually the text itself
    // (receive_sharing_intent packages it as a "path" — it's literally
    // the text). When a file exists we treat it as a file share and
    // only sniff the head inline.
    final bool isTextish = mime.isEmpty || mime == 'text/plain' || mime == 'text/*';
    final bool pathIsRealFile = await _fileExists(rawPath);
    if (isTextish) {
      String? sniffSource;
      if (!pathIsRealFile) {
        if (rawPath.length <= kUrlSniffMaxBytes) {
          sniffSource = rawPath;
        }
      } else {
        // Small text file — read the first 2 KB and inspect.
        final stat = await File(rawPath).stat();
        if (stat.size <= kUrlSniffMaxBytes) {
          sniffSource = await _readHead(rawPath, kTextHeadBytes);
        }
      }
      if (sniffSource != null) {
        final match = RegExp(r'https?://\S+').firstMatch(sniffSource);
        if (match != null) {
          return ShareRoute(
            route: '/recipes/add/share?url=${Uri.encodeComponent(match.group(0)!)}',
            skippedCount: skipped,
          );
        }
      }
    }

    // 3. No file on disk and nothing URL-like — nothing we can import.
    if (!pathIsRealFile) {
      return null;
    }

    // 4. File share: figure out MIME + extension, copy to sandbox,
    //    build the receive-screen route.
    final ext = _extractExtension(rawPath);
    final effectiveMime = _pickEffectiveMime(mime, ext);
    final filename = rawPath.split(Platform.pathSeparator).last;

    String? sandboxPath;
    try {
      sandboxPath = await _copyToSandbox(rawPath, ext);
    } catch (e, st) {
      // Surface OEM-specific SecurityExceptions with the MIME type
      // attached so we can tell Xiaomi/Samsung breakages apart in
      // Crashlytics.
      ErrorReporter.report(
        e,
        st,
        area: 'share.intent',
        operation: 'copyToSandbox',
        extras: {
          'share_intent_mime': effectiveMime.isEmpty ? 'unknown' : effectiveMime,
          'share_intent_ext': ext,
        },
      );
      // Fall back to an unsupported route with the filename so the
      // receiving screen tells the user what went wrong instead of
      // silently dropping the share.
      return ShareRoute(
        route:
            '/recipes/add/receive?unsupported=true&filename=${Uri.encodeComponent(filename)}',
        skippedCount: skipped,
      );
    }

    if (_isSupportedMime(effectiveMime) ||
        _isSupportedExtension(ext)) {
      final mimeForRoute = effectiveMime.isEmpty
          ? _inferMimeFromExtension(ext)
          : effectiveMime;
      return ShareRoute(
        route:
            '/recipes/add/receive?path=${Uri.encodeComponent(sandboxPath)}&mime=${Uri.encodeComponent(mimeForRoute)}',
        skippedCount: skipped,
      );
    }

    // 5. Supported-by-sheet-manifest but not by handler: unsupported
    //    fallback. The receiving screen (sae-3) renders copy + Paste
    //    Text escape hatch.
    return ShareRoute(
      route:
          '/recipes/add/receive?unsupported=true&filename=${Uri.encodeComponent(filename)}',
      skippedCount: skipped,
    );
  }

  /// Persist a resolved route so the next authenticated launch can
  /// replay it. Used when auth isn't ready at classify time.
  Future<void> persistPending(String route) async {
    try {
      final sp = await _prefs();
      await sp.setString(kPendingSharePayloadKey, route);
    } catch (e, st) {
      ErrorReporter.report(e, st,
          area: 'share.intent', operation: 'persistPending');
    }
  }

  /// If a pending route was persisted while the user was unauthenticated,
  /// return + clear it. Returns null when nothing is pending.
  Future<String?> consumePending() async {
    try {
      final sp = await _prefs();
      final route = sp.getString(kPendingSharePayloadKey);
      if (route != null) {
        await sp.remove(kPendingSharePayloadKey);
      }
      return route;
    } catch (e, st) {
      ErrorReporter.report(e, st,
          area: 'share.intent', operation: 'consumePending');
      return null;
    }
  }

  /// True iff the caller's auth service reports authenticated. Surfaced
  /// as a method so main.dart can guard navigation with the same check
  /// the handler uses when deciding whether to persist vs. dispatch.
  bool get isAuthenticated => _authService?.isAuthenticated ?? true;

  Future<String> _copyToSandbox(String src, String ext) async {
    final dir = await _appDocsDir();
    final inbox = Directory('${dir.path}${Platform.pathSeparator}shared_inbox');
    if (!await inbox.exists()) {
      await inbox.create(recursive: true);
    }
    final nonce = _nonce();
    final suffix = ext.isEmpty ? '' : '.$ext';
    final dest = '${inbox.path}${Platform.pathSeparator}$nonce$suffix';
    await File(src).copy(dest);
    return dest;
  }

  String _nonce() {
    final ts = DateTime.now().microsecondsSinceEpoch.toRadixString(36);
    final rand = _random.nextInt(0xFFFFFFFF).toRadixString(36);
    return '${ts}_$rand';
  }

  Future<bool> _fileExists(String path) async {
    try {
      return await File(path).exists();
    } catch (_) {
      return false;
    }
  }

  Future<String> _readHead(String path, int maxBytes) async {
    try {
      final raf = await File(path).open();
      try {
        final stat = await File(path).stat();
        final len = stat.size < maxBytes ? stat.size : maxBytes;
        final bytes = await raf.read(len);
        return String.fromCharCodes(bytes);
      } finally {
        await raf.close();
      }
    } catch (_) {
      return '';
    }
  }

  String _extractExtension(String path) {
    final name = path.split(Platform.pathSeparator).last;
    final dot = name.lastIndexOf('.');
    if (dot <= 0 || dot == name.length - 1) return '';
    return name.substring(dot + 1).toLowerCase();
  }

  String _pickEffectiveMime(String mime, String ext) {
    if (mime.isEmpty || mime == 'application/octet-stream') {
      return _inferMimeFromExtension(ext);
    }
    return mime;
  }

  String _inferMimeFromExtension(String ext) {
    if (kImageExtensions.contains(ext)) return 'image/$ext';
    if (kVideoExtensions.contains(ext)) return 'video/$ext';
    if (kAudioExtensions.contains(ext)) return 'audio/$ext';
    if (ext == 'pdf') return 'application/pdf';
    if (ext == 'csv') return 'text/csv';
    if (ext == 'xls') return 'application/vnd.ms-excel';
    if (ext == 'xlsx') {
      return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    }
    return '';
  }

  bool _isSupportedMime(String mime) {
    if (mime.isEmpty) return false;
    for (final prefix in kSupportedMimePrefixes) {
      if (mime.startsWith(prefix)) return true;
    }
    return kSupportedMimeExact.contains(mime);
  }

  bool _isSupportedExtension(String ext) {
    return kImageExtensions.contains(ext) ||
        kVideoExtensions.contains(ext) ||
        kAudioExtensions.contains(ext) ||
        kSpreadsheetExtensions.contains(ext) ||
        ext == 'pdf';
  }
}
