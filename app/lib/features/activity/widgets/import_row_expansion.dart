import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/import_item_telemetry.dart';
import '../providers/import_item_telemetry_provider.dart';
import 'confidence_badge.dart';
import 'raw_text_preview.dart';
import 'stage_timeline.dart';

/// Body rendered below a collapsed `ImportRow` when the row's id is in
/// the `importRowExpansionProvider` set.
///
/// irrd-4 shipped the scaffold + lazy telemetry fetch + invalidation
/// wiring + a11y semantic group. irrd-5 swaps the `_SlotTile`
/// placeholders for the real rich-detail sub-widgets (StageTimeline,
/// ConfidenceBadge, RawTextPreview). Action buttons (Review / Retry /
/// View Recipe / Archive) land in irrd-6.
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
  /// block.
  final String? sourceType;
  final String? sourceReference;

  /// Confidence score + source threaded from the list payload
  /// (irrd-3 hoisted these to the response root). Null score renders
  /// a muted "Unavailable" badge.
  final double? confidenceScore;
  final String? confidenceSource;

  const ImportRowExpansion({
    super.key,
    required this.itemId,
    required this.recipeName,
    this.retryCount = 0,
    this.lastRetryAt,
    this.errorMessage,
    this.sourceType,
    this.sourceReference,
    this.confidenceScore,
    this.confidenceSource,
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
                  confidenceScore: confidenceScore,
                  confidenceSource: confidenceSource,
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
  final double? confidenceScore;
  final String? confidenceSource;

  const _Body({
    required this.telemetry,
    required this.retryCount,
    required this.lastRetryAt,
    required this.errorMessage,
    required this.sourceType,
    required this.sourceReference,
    required this.confidenceScore,
    required this.confidenceSource,
  });

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final parsed = telemetry.stage('parsed');
    final extracted = telemetry.stage('extracted');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        StageTimeline(telemetry: telemetry),
        const SizedBox(height: 10),
        Align(
          alignment: Alignment.centerLeft,
          child: ConfidenceBadge(
            score: confidenceScore,
            source: confidenceSource,
          ),
        ),
        const SizedBox(height: 10),
        if (parsed != null &&
            parsed.rawOutputPreview != null &&
            parsed.rawOutputPreview!.trim().isNotEmpty)
          RawTextPreview(
            label: 'Parsed text (OCR)',
            text: parsed.rawOutputPreview,
            truncated: parsed.truncated,
          ),
        if (extracted != null &&
            extracted.rawOutputPreview != null &&
            extracted.rawOutputPreview!.trim().isNotEmpty)
          RawTextPreview(
            label: 'Extracted recipe JSON',
            text: extracted.rawOutputPreview,
            truncated: extracted.truncated,
          ),
        if (retryCount > 0) _retryLine(textTheme),
        if (errorMessage != null && errorMessage!.trim().isNotEmpty)
          _ErrorTile(message: errorMessage!.trim()),
        if (sourceReference != null && sourceReference!.isNotEmpty)
          _SourceTile(sourceType: sourceType, reference: sourceReference!),
      ],
    );
  }

  Widget _retryLine(TextTheme textTheme) {
    final suffix = lastRetryAt != null ? ' · last at ${_ago(lastRetryAt!)}' : '';
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

class _ErrorTile extends StatelessWidget {
  final String message;

  const _ErrorTile({required this.message});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 96,
            child: Text(
              'Error detail',
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          Expanded(
            child: Text(
              message,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.error,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SourceTile extends StatelessWidget {
  final String? sourceType;
  final String reference;

  const _SourceTile({required this.sourceType, required this.reference});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 96,
            child: Text(
              'Source',
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          Expanded(
            child: Text(
              '${sourceType ?? "reference"}: $reference',
              style: theme.textTheme.bodySmall,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
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
