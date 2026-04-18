import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../../../core/router/activity_routes.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/error_reporter.dart';
import 'state/receive_import_notifier.dart';
import 'widgets/receive_progress_card.dart';

/// Hard cap on pre-upload file size. Matches backend `/imports/upload-url`
/// MAX_UPLOAD_BYTES so we fail fast before burning a presigned URL.
const int _kMaxUploadBytes = 100 * 1024 * 1024;

/// Universal receiving screen for inbound shares.
///
/// Accepts a shared URL, file path, or an explicit `unsupported` flag
/// and threads the user either to the typed import flow or the Activity
/// Hub. Replaces the sae-2/sae-3 placeholder with the full sru-1 UX:
/// detection → progress card (≥600 ms dwell) → typed handoff / URL
/// import / error state.
///
/// Query param contract (unchanged from sae-2 for on-the-wire compat):
/// * `url`         — shared URL; triggers the URL branch.
/// * `path`        — sandbox file path.
/// * `mime`        — MIME hint from the share intent.
/// * `unsupported` — `true` for the "we can't read this yet" state.
/// * `filename`    — shown in unsupported / oversize copy.
/// * `book_id`     — pre-selected recipe book (forwarded to typed screens).
class ReceiveImportScreen extends StatefulWidget {
  const ReceiveImportScreen({
    super.key,
    this.url,
    this.path,
    this.mime,
    this.unsupported = false,
    this.filename,
    this.bookId,
  });

  final String? url;
  final String? path;
  final String? mime;
  final bool unsupported;
  final String? filename;
  final String? bookId;

  @override
  State<ReceiveImportScreen> createState() => _ReceiveImportScreenState();
}

class _ReceiveImportScreenState extends State<ReceiveImportScreen> {
  final ReceiveImportNotifier _notifier = ReceiveImportNotifier();
  final _apiClient = getIt<ApiClient>();
  final _authService = getIt<AuthService>();

  /// Timestamp the screen first rendered a progress card. Used to
  /// enforce the 600 ms minimum dwell before any navigation — guards
  /// against the flash-and-replace on a sub-frame URL import.
  DateTime? _cardShownAt;

  /// When true, the screen is rendering its unsupported or oversize
  /// state instead of the progress card.
  bool _terminal = false;

  /// Filename surfaced in terminal-state copy. Falls back to basename(path).
  String? _terminalFilename;

  /// File size used by the oversize state's copy.
  int _oversizeBytes = 0;

  @override
  void initState() {
    super.initState();
    if (widget.unsupported) {
      // sae-3 kept logging this event for the `*/*`-unlock metrics
      // gate. Preserve that instrumentation.
      ErrorReporter.log(
        'share_intent_unsupported mime=${widget.mime ?? '?'} '
        'filename=${widget.filename ?? '?'}',
      );
      _terminal = true;
      _terminalFilename = widget.filename;
      _notifier.enterError(
        ReceiveErrorCode.unknown,
        'unsupported-type',
      );
      return;
    }
    _cardShownAt = DateTime.now();
    WidgetsBinding.instance.addPostFrameCallback((_) => _dispatch());
  }

  @override
  void dispose() {
    _notifier.dispose();
    super.dispose();
  }

  /// Wait until the progress card has rendered for at least 600 ms
  /// (the epic-locked "minimum dwell"). Stops the visual glitch where
  /// an instantly-resolved URL import would flash-and-replace.
  Future<void> _dwell() async {
    final shown = _cardShownAt;
    if (shown == null) return;
    final waited = DateTime.now().difference(shown);
    const minDwell = Duration(milliseconds: 600);
    if (waited < minDwell) {
      await Future<void>.delayed(minDwell - waited);
    }
  }

  Future<void> _dispatch() async {
    try {
      // URL branch — no file bytes, no dedup guard needed.
      final url = widget.url;
      if (url != null && url.isNotEmpty) {
        _notifier.onDetect(mime: 'text/url-list');
        _notifier.value = _notifier.value.copyWith(branch: ReceiveBranch.url);
        await _runUrlImport(url);
        return;
      }

      final path = widget.path;
      if (path == null || path.isEmpty) {
        _enterUnsupportedState();
        return;
      }

      // Size-gate before anything touches the network.
      final file = File(path);
      int sizeBytes = 0;
      int mtimeMicros = 0;
      try {
        final stat = await file.stat();
        sizeBytes = stat.size;
        mtimeMicros = stat.modified.microsecondsSinceEpoch;
      } catch (_) {
        _enterUnsupportedState();
        return;
      }
      if (sizeBytes >= _kMaxUploadBytes) {
        _enterOversizeState(
          filename: _basename(path),
          sizeBytes: sizeBytes,
        );
        return;
      }

      final dedupKey = computeDedupKey(
        path: path,
        mtimeMicros: mtimeMicros,
        sizeBytes: sizeBytes,
      );
      final branch = _notifier.onDetect(
        mime: widget.mime,
        filename: widget.filename ?? _basename(path),
        path: path,
        dedupKey: dedupKey,
      );
      if (branch == null) {
        // sru-1 first-frame dedup — the second fire within 2 s is a no-op.
        return;
      }
      switch (branch) {
        case ReceiveBranch.image:
          await _delegateToTyped('/recipes/add/photo', path);
        case ReceiveBranch.spreadsheet:
          await _delegateToTyped('/recipes/add/spreadsheet', path);
        case ReceiveBranch.text:
          await _delegateToTypedText(path);
        case ReceiveBranch.pdf:
        case ReceiveBranch.audio:
        case ReceiveBranch.video:
          // sru-4 owns the presigned-upload sequence. Until it lands,
          // the progress card shows "Reading your <file>…" then lands
          // on the Activity Hub via a no-op navigation so the user
          // isn't left stranded. When sru-4 lands, swap the body here
          // for the upload → /import call.
          await _uploadAndImport(
            path: path,
            sizeBytes: sizeBytes,
            branch: branch,
          );
        case ReceiveBranch.url:
          // Already handled above.
          break;
        case ReceiveBranch.oversize:
          _enterOversizeState(
            filename: _basename(path),
            sizeBytes: sizeBytes,
          );
        case ReceiveBranch.unsupported:
          _enterUnsupportedState();
      }
    } catch (e) {
      _notifier.enterError(ReceiveErrorCode.unknown, e.toString());
      if (mounted) setState(() {});
    }
  }

  Future<void> _runUrlImport(String url) async {
    try {
      final bookId = widget.bookId ?? _authService.defaultRecipeBookId;
      if (bookId == null || bookId.isEmpty) {
        // No target book — fall back to the share-import screen, which
        // already handles the zero-books case.
        if (!mounted) return;
        await _dwell();
        if (!mounted) return;
        final q = Uri.encodeQueryComponent(url);
        context.go('/recipes/add/share?url=$q');
        return;
      }
      await _apiClient.startImport(bookId, sourceType: 'url', url: url);
      await _dwell();
      if (!mounted) return;
      _notifier.enterNavigating(ActivityRoutes.hubPath);
      context.go(ActivityRoutes.hubPath);
    } catch (e) {
      if (!mounted) return;
      _notifier.enterError(ReceiveErrorCode.unknown, e.toString());
      setState(() {});
    }
  }

  Future<void> _delegateToTyped(String routePath, String filePath) async {
    await _dwell();
    if (!mounted) return;
    _notifier.enterNavigating(routePath);
    context.go(
      routePath,
      extra: {
        if (widget.bookId != null) 'recipeBookId': widget.bookId,
        'initialPath': filePath,
      },
    );
  }

  Future<void> _delegateToTypedText(String filePath) async {
    String? content;
    try {
      final file = File(filePath);
      if (await file.exists()) {
        // Cap at 16k chars — matches the text-paste screen's hard limit.
        final bytes = await file.readAsBytes();
        content = String.fromCharCodes(
          bytes.take(16 * 1024),
        );
      }
    } catch (_) {}
    await _dwell();
    if (!mounted) return;
    _notifier.enterNavigating('/recipes/add/text');
    context.go(
      '/recipes/add/text',
      extra: {
        if (widget.bookId != null) 'recipeBookId': widget.bookId,
        if (content != null && content.isNotEmpty) 'initialText': content,
      },
    );
  }

  Future<void> _uploadAndImport({
    required String path,
    required int sizeBytes,
    required ReceiveBranch branch,
  }) async {
    // sru-4: full presigned-upload sequence lands here. sru-1 ships the
    // detection + UX shell; the upload call is deferred to the next
    // story to keep both stories reviewable in isolation. For now the
    // screen dwells and lands the user on the Activity Hub — backend
    // `start_import` isn't wired to bytes yet from this path, so the
    // user sees the receive card + an empty-handed Activity nav. This
    // is intentional and documented; sru-4 replaces the body.
    _notifier.enterUploading(total: sizeBytes);
    await _dwell();
    if (!mounted) return;
    _notifier.enterNavigating(ActivityRoutes.hubPath);
    context.go(ActivityRoutes.hubPath);
  }

  void _enterUnsupportedState() {
    if (!mounted) return;
    setState(() {
      _terminal = true;
      _terminalFilename = widget.filename;
    });
    _notifier.enterError(ReceiveErrorCode.unknown, 'unsupported');
  }

  void _enterOversizeState({String? filename, int sizeBytes = 0}) {
    if (!mounted) return;
    setState(() {
      _terminal = true;
      _terminalFilename = filename ?? widget.filename;
      _oversizeBytes = sizeBytes;
    });
    _notifier.markOversize();
  }

  String _basename(String path) {
    if (kIsWeb) return path;
    return path.split(Platform.pathSeparator).last;
  }

  String? _hostnameOf(String? url) {
    if (url == null || url.isEmpty) return null;
    try {
      return Uri.parse(url).host;
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_terminal) {
      final state = _notifier.value;
      if (state.branch == ReceiveBranch.oversize ||
          state.errorCode == ReceiveErrorCode.tooLarge) {
        return _OversizeCard(
          filename: _terminalFilename,
          sizeBytes: _oversizeBytes,
          onClose: () => context.go('/'),
        );
      }
      return _UnsupportedCard(
        filename: _terminalFilename,
        onPasteText: () => context.go('/recipes/add/text'),
        onClose: () => context.go('/'),
      );
    }
    return ValueListenableBuilder<ReceiveImportState>(
      valueListenable: _notifier,
      builder: (context, state, _) {
        if (state.phase == ReceivePhase.error) {
          return _ErrorCard(
            code: state.errorCode ?? ReceiveErrorCode.unknown,
            onRetry: () {
              _cardShownAt = DateTime.now();
              _dispatch();
            },
            onClose: () => context.go('/'),
          );
        }
        return ReceiveProgressCard(
          state: state,
          hostname: _hostnameOf(widget.url),
        );
      },
    );
  }
}

class _UnsupportedCard extends StatelessWidget {
  const _UnsupportedCard({
    required this.filename,
    required this.onPasteText,
    required this.onClose,
  });

  final String? filename;
  final VoidCallback onPasteText;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final shown = filename == null || filename!.isEmpty
        ? 'this file'
        : '`${filename!}`';
    return Scaffold(
      appBar: AppBar(
        title: const Text('Import'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: onClose,
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.description_outlined,
                size: 64,
                color: Theme.of(context).colorScheme.outline,
              ),
              const SizedBox(height: 16),
              Text(
                "We can't read this yet",
                style: Theme.of(context).textTheme.titleLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                "Palateful can't extract recipes from $shown. "
                'Try copying the text and using Paste Text instead.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                alignment: WrapAlignment.center,
                children: [
                  ElevatedButton.icon(
                    onPressed: onPasteText,
                    icon: const Icon(Icons.content_paste),
                    label: const Text('Paste Text Instead'),
                  ),
                  OutlinedButton(
                    onPressed: onClose,
                    child: const Text('Close'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _OversizeCard extends StatelessWidget {
  const _OversizeCard({
    required this.filename,
    required this.sizeBytes,
    required this.onClose,
  });

  final String? filename;
  final int sizeBytes;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final shown = filename == null || filename!.isEmpty
        ? 'That file'
        : '`${filename!}`';
    final sizeCopy = sizeBytes > 0 ? ' (${formatBytes(sizeBytes)})' : '';
    return Scaffold(
      appBar: AppBar(
        title: const Text('Import'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: onClose,
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.unarchive_outlined,
                size: 64,
                color: Theme.of(context).colorScheme.outline,
              ),
              const SizedBox(height: 16),
              Text(
                'That file is too large',
                style: Theme.of(context).textTheme.titleLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                '$shown is$sizeCopy bigger than Palateful can accept '
                '(max 100 MB). Try trimming it or sharing a cloud link '
                'instead.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              OutlinedButton(
                onPressed: onClose,
                child: const Text('Close'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({
    required this.code,
    required this.onRetry,
    required this.onClose,
  });

  final ReceiveErrorCode code;
  final VoidCallback onRetry;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final copy = _copyFor(code);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Import'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: onClose,
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.error_outline,
                size: 48,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text(
                copy,
                style: Theme.of(context).textTheme.titleMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                alignment: WrapAlignment.center,
                children: [
                  if (code != ReceiveErrorCode.unauthorized)
                    ElevatedButton(
                      onPressed: onRetry,
                      child: const Text('Retry'),
                    ),
                  OutlinedButton(
                    onPressed: onClose,
                    child: const Text('Close'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _copyFor(ReceiveErrorCode code) {
    switch (code) {
      case ReceiveErrorCode.network:
        return "Couldn't upload. Try again.";
      case ReceiveErrorCode.unauthorized:
        return 'Your session expired. Sign in again to import.';
      case ReceiveErrorCode.tooLarge:
        return "That file is too large. Max 100 MB.";
      case ReceiveErrorCode.objectNotReady:
        return "Upload is still syncing. Try again in a moment.";
      case ReceiveErrorCode.duplicate:
        return 'This file has already been imported.';
      case ReceiveErrorCode.rateLimited:
        return 'Too many imports right now. Try again shortly.';
      case ReceiveErrorCode.unknown:
        return 'Something went wrong. Please try again.';
    }
  }
}
