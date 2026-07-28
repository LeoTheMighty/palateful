import 'package:flutter/material.dart';

import '../state/receive_import_notifier.dart';

/// Full-screen progress card shown during the share-receiving handoff.
/// Copy is driven by branch + phase; a minimum dwell of 600 ms (owned
/// by the screen) keeps this from flash-and-replacing when a URL import
/// resolves in under a frame.
class ReceiveProgressCard extends StatelessWidget {
  const ReceiveProgressCard({
    super.key,
    required this.state,
    this.hostname,
  });

  final ReceiveImportState state;

  /// Only used for the URL branch: "Importing recipe from `<hostname>`".
  final String? hostname;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final progress = _progressFraction(state);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              mainAxisSize: MainAxisSize.min,
              children: [
                _BranchIcon(branch: state.branch),
                const SizedBox(height: 20),
                Text(
                  _headline(state, hostname: hostname),
                  style: theme.textTheme.titleLarge,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                if (progress != null)
                  LinearProgressIndicator(value: progress)
                else
                  const CircularProgressIndicator(),
                if (state.phase == ReceivePhase.uploading &&
                    state.totalBytes > 0) ...[
                  const SizedBox(height: 12),
                  Text(
                    '${_formatBytes(state.uploadedBytes)} / '
                    '${_formatBytes(state.totalBytes)}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  double? _progressFraction(ReceiveImportState s) {
    if (s.phase != ReceivePhase.uploading) return null;
    if (s.totalBytes <= 0) return null;
    return (s.uploadedBytes / s.totalBytes).clamp(0.0, 1.0);
  }

  String _headline(ReceiveImportState s, {String? hostname}) {
    // sru-4: the upload branches stage their copy so the card never sits
    // on a stale "Reading your PDF" while 80 MB crawls up to S3. Percent
    // is only shown once we know the total — a 0-byte total would render
    // a permanent "Uploading… 0%".
    if (s.phase == ReceivePhase.uploading && s.totalBytes > 0) {
      final pct = ((s.uploadedBytes / s.totalBytes) * 100).clamp(0, 100).round();
      return 'Uploading… $pct%';
    }
    if (s.phase == ReceivePhase.sending) return 'Sending to Palateful…';

    switch (s.branch) {
      case ReceiveBranch.url:
        final host = hostname ?? 'the web';
        return 'Importing recipe from $host';
      case ReceiveBranch.image:
        return 'Reading your recipe photo';
      case ReceiveBranch.pdf:
        return 'Reading your PDF';
      case ReceiveBranch.audio:
        return 'Transcribing audio…';
      case ReceiveBranch.video:
        return 'Extracting recipe from video';
      case ReceiveBranch.spreadsheet:
        return 'Reading your spreadsheet';
      case ReceiveBranch.text:
        return 'Reading your recipe';
      case null:
      case ReceiveBranch.oversize:
      case ReceiveBranch.unsupported:
        return 'Receiving shared file…';
    }
  }
}

class _BranchIcon extends StatelessWidget {
  const _BranchIcon({required this.branch});
  final ReceiveBranch? branch;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.primary;
    final icon = switch (branch) {
      ReceiveBranch.url => Icons.link,
      ReceiveBranch.image => Icons.photo,
      ReceiveBranch.pdf => Icons.picture_as_pdf,
      ReceiveBranch.audio => Icons.mic,
      ReceiveBranch.video => Icons.videocam,
      ReceiveBranch.spreadsheet => Icons.table_chart,
      ReceiveBranch.text => Icons.description,
      _ => Icons.share,
    };
    return Icon(icon, size: 48, color: color);
  }
}

String _formatBytes(int bytes) {
  if (bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  var size = bytes.toDouble();
  var unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit++;
  }
  return '${size.toStringAsFixed(size >= 10 || unit == 0 ? 0 : 1)} ${units[unit]}';
}

/// Shared-with-sru-2 helper for the oversize state copy.
String formatBytes(int bytes) => _formatBytes(bytes);
