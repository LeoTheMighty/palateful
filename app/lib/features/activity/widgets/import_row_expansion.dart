import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/import_item_telemetry.dart';
import '../providers/import_item_telemetry_provider.dart';

/// Body rendered below a collapsed `ImportRow` when the row's id is in
/// the `importRowExpansionProvider` set.
///
/// irrd-4 ships the scaffold + lazy telemetry fetch + invalidation
/// wiring + a11y semantic group. The rich sub-widgets (StageTimeline,
/// ConfidenceBadge, RawTextPreview) land in irrd-5; the action
/// buttons (Review / Retry / View Recipe / Archive) land in irrd-6.
/// Until then, placeholder tiles mark the slot so integration tests
/// can assert presence without asserting fully-styled chrome.
class ImportRowExpansion extends ConsumerWidget {
  final String itemId;
  final String recipeName;

  /// Retry count from the list payload. Drives the "Retried N times"
  /// line; hidden when zero.
  final int retryCount;

  /// Last retry wallclock from the list payload (for the relative-time
  /// suffix in the retry line).
  final DateTime? lastRetryAt;

  /// Plain error blob, only rendered on failed rows.
  final String? errorMessage;

  /// Surface source-reference (url / photo / text) for the Source
  /// block. Rendering in irrd-5 / irrd-6.
  final String? sourceType;
  final String? sourceReference;

  const ImportRowExpansion({
    super.key,
    required this.itemId,
    required this.recipeName,
    this.retryCount = 0,
    this.lastRetryAt,
    this.errorMessage,
    this.sourceType,
    this.sourceReference,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final telemetry = ref.watch(importItemTelemetryProvider(itemId));
    final mediaQuery = MediaQuery.of(context);

    return Semantics(
      container: true,
      label: 'Import details for $recipeName',
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: mediaQuery.size.height * 0.6),
        child: Material(
          type: MaterialType.transparency,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(48, 4, 16, 16),
            child: SingleChildScrollView(
              child: telemetry.when(
                data: (t) => _Body(
                  telemetry: t,
                  retryCount: retryCount,
                  lastRetryAt: lastRetryAt,
                  errorMessage: errorMessage,
                  sourceType: sourceType,
                  sourceReference: sourceReference,
                ),
                loading: () => const _SkeletonBody(),
                error: (err, _) => _ErrorBody(
                  onRetry: () =>
                      ref.invalidate(importItemTelemetryProvider(itemId)),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Body extends StatelessWidget {
  final ImportItemTelemetry telemetry;
  final int retryCount;
  final DateTime? lastRetryAt;
  final String? errorMessage;
  final String? sourceType;
  final String? sourceReference;

  const _Body({
    required this.telemetry,
    required this.retryCount,
    required this.lastRetryAt,
    required this.errorMessage,
    required this.sourceType,
    required this.sourceReference,
  });

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // irrd-5 replaces this with `StageTimeline(telemetry: telemetry)`.
        _SlotTile(
          label: 'Stage timeline',
          subtitle:
              telemetry.stages.map((s) => '${s.stage}·${s.status}').join(' '),
        ),
        // irrd-5 replaces this with `ConfidenceBadge(...)`.
        const _SlotTile(
          label: 'Confidence badge',
          subtitle: 'rendered in irrd-5',
        ),
        // irrd-5 replaces this with `RawTextPreview(...)` per stage.
        _SlotTile(
          label: 'Raw text preview',
          subtitle: _previewSubtitle(telemetry),
        ),
        if (retryCount > 0) _retryLine(textTheme),
        if (errorMessage != null && errorMessage!.trim().isNotEmpty)
          _SlotTile(
            label: 'Error detail',
            subtitle: errorMessage!.trim(),
          ),
        if (sourceReference != null && sourceReference!.isNotEmpty)
          _SlotTile(
            label: 'Source',
            subtitle: '${sourceType ?? "reference"}: $sourceReference',
          ),
        // irrd-6 replaces this with the action-button row.
        const _SlotTile(
          label: 'Actions',
          subtitle: 'rendered in irrd-6',
        ),
      ],
    );
  }

  static String _previewSubtitle(ImportItemTelemetry t) {
    for (final stage in ['parsed', 'extracted']) {
      final entry = t.stage(stage);
      if (entry != null &&
          entry.rawOutputPreview != null &&
          entry.rawOutputPreview!.isNotEmpty) {
        final preview = entry.rawOutputPreview!;
        final head = preview.length > 60 ? '${preview.substring(0, 60)}…' : preview;
        return '$stage: $head';
      }
    }
    return 'no preview yet';
  }

  Widget _retryLine(TextTheme textTheme) {
    final suffix = lastRetryAt != null
        ? ' · last at ${_ago(lastRetryAt!)}'
        : '';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Text(
        'Retried $retryCount ${retryCount == 1 ? "time" : "times"}$suffix',
        style: textTheme.bodySmall,
      ),
    );
  }

  static String _ago(DateTime ts) {
    final local = ts.toLocal();
    final diff = DateTime.now().difference(local);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}

class _SlotTile extends StatelessWidget {
  final String label;
  final String subtitle;
  const _SlotTile({required this.label, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          Expanded(
            child: Text(
              subtitle,
              style: theme.textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}

class _SkeletonBody extends StatelessWidget {
  const _SkeletonBody();

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(
        5,
        (_) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            children: [
              Container(
                width: 120,
                height: 10,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Container(
                  height: 10,
                  decoration: BoxDecoration(
                    color: Theme.of(context)
                        .colorScheme
                        .surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorBody extends StatelessWidget {
  final VoidCallback onRetry;
  const _ErrorBody({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              "Couldn't load full details",
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          TextButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}
