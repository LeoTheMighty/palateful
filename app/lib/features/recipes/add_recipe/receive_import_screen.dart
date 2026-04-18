import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/services/error_reporter.dart';

/// Universal receiving screen for inbound shares.
///
/// This is a **placeholder** implementation owned jointly by sae-2
/// (routing target) and sae-3 (unsupported fallback). The full receiving
/// UX with byte-level progress, auto-retry on 409, and the delegation
/// matrix for PDF/audio/video is `sru-1` territory (epic-share-
/// receiving-ux). Keep the shape stable so that sru-1 can swap the body
/// without touching the route or query param contract.
///
/// Query param contract:
/// * `path`        — sandbox file path (Android sae-2 copies temp →
///                   `<appDocs>/shared_inbox/<uuid>.<ext>`).
/// * `mime`        — MIME type hint from the share intent.
/// * `unsupported` — `true` when the handler gave up (e.g. `.docx`).
/// * `filename`    — surfaced to the user in the unsupported state.
class ReceiveImportScreen extends StatefulWidget {
  const ReceiveImportScreen({
    super.key,
    this.path,
    this.mime,
    this.unsupported = false,
    this.filename,
  });

  final String? path;
  final String? mime;
  final bool unsupported;
  final String? filename;

  @override
  State<ReceiveImportScreen> createState() => _ReceiveImportScreenState();
}

class _ReceiveImportScreenState extends State<ReceiveImportScreen> {
  bool _fallbackToUnsupported = false;

  @override
  void initState() {
    super.initState();
    if (widget.unsupported) {
      // sae-3: fires the metrics-gate event for future */*-unlock.
      ErrorReporter.log(
        'share_intent_unsupported mime=${widget.mime ?? '?'} '
        'ext=${_extensionOf(widget.filename)} '
        'filename=${widget.filename ?? '?'}',
      );
    } else {
      WidgetsBinding.instance.addPostFrameCallback((_) => _routeByMime());
    }
  }

  String _extensionOf(String? filename) {
    if (filename == null) return '?';
    final idx = filename.lastIndexOf('.');
    if (idx <= 0 || idx == filename.length - 1) return '?';
    return filename.substring(idx + 1).toLowerCase();
  }

  void _routeByMime() {
    if (!mounted) return;
    final path = widget.path;
    final mime = (widget.mime ?? '').toLowerCase();

    String? target;
    if (path != null && path.isNotEmpty) {
      final encoded = Uri.encodeComponent(path);
      if (mime.startsWith('image/')) {
        target = '/recipes/add/photo?path=$encoded';
      } else if (mime == 'application/pdf') {
        target = '/recipes/add/pdf?path=$encoded';
      } else if (mime.startsWith('audio/')) {
        target = '/recipes/add/audio?path=$encoded';
      } else if (mime == 'text/csv' ||
          mime == 'application/vnd.ms-excel' ||
          mime ==
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
        target = '/recipes/add/spreadsheet?path=$encoded';
      }
      // video/* has no typed screen today (sru-5 adds VideoFileImportScreen).
      // Fall through to "unsupported" to avoid dropping the share silently.
    }

    if (target != null) {
      context.go(target);
    } else {
      // Unknown MIME / missing path reached the receive screen despite
      // the handler — render the unsupported state so the user isn't
      // stuck staring at a progress spinner.
      setState(() => _fallbackToUnsupported = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.unsupported || _fallbackToUnsupported) {
      return _UnsupportedCard(
        filename: widget.filename,
        onPasteText: () => context.go('/recipes/add/text'),
        onClose: () => context.go('/'),
      );
    }
    return const _ReceivingCard();
  }
}

class _ReceivingCard extends StatelessWidget {
  const _ReceivingCard();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Receiving shared file…'),
          ],
        ),
      ),
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
