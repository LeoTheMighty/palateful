import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../../../core/services/api_client.dart';
import '../../../../core/theme/theme.dart';
import '../models/import_batch.dart';
import '../state/import_batches_provider.dart';

class ImportBatchesStrip extends ConsumerWidget {
  final ImportBatchesState state;

  const ImportBatchesStrip({super.key, required this.state});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final all = state.all;
    if (all.isEmpty) return const SizedBox.shrink();
    final colorScheme = Theme.of(context).colorScheme;
    final justStarted =
        ref.watch(importBatchesProvider.notifier).justStartedBatchIds;

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 4, bottom: 8),
            child: Text(
              'In progress',
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
          ...all.map(
            (b) => _ImportBatchRow(
              batch: b,
              isJustStarted: justStarted.contains(b.id),
            ),
          ),
        ],
      ),
    );
  }
}

class _ImportBatchRow extends ConsumerStatefulWidget {
  final ImportBatch batch;
  final bool isJustStarted;

  const _ImportBatchRow({required this.batch, required this.isJustStarted});

  @override
  ConsumerState<_ImportBatchRow> createState() => _ImportBatchRowState();
}

class _ImportBatchRowState extends ConsumerState<_ImportBatchRow> {
  bool _expanded = false;
  bool _retrying = false;

  ApiClient get _apiClient => getIt<ApiClient>();

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final batch = widget.batch;
    final summary = _summarizeStatus(batch);
    final isTappable = summary.isTappable;
    final isFailed = batch.status == 'failed';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: widget.isJustStarted
              ? colorScheme.primary
              : colorScheme.outlineVariant.withValues(alpha: 0.5),
          width: widget.isJustStarted ? 2 : 1,
        ),
      ),
      child: Column(
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () {
              if (isTappable) {
                _navigateToReview(context);
              } else {
                setState(() => _expanded = !_expanded);
              }
            },
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: summary.color.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(Icons.image_outlined,
                        size: 20, color: summary.color),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          summary.label,
                          style: TextStyle(
                            color: summary.color,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          _batchSubtitle(batch),
                          style: TextStyle(
                            color: context.appColors.textTertiary,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: Icon(
                      _expanded ? Icons.expand_less : Icons.expand_more,
                      size: 20,
                    ),
                    onPressed: () => setState(() => _expanded = !_expanded),
                    visualDensity: VisualDensity.compact,
                  ),
                ],
              ),
            ),
          ),
          if (isFailed) _buildFailedActions(context),
          if (_expanded) _buildExpanded(context),
        ],
      ),
    );
  }

  Widget _buildFailedActions(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
      child: Row(
        children: [
          Expanded(
            child: OutlinedButton.icon(
              onPressed: _retrying ? null : _handleRetry,
              icon: _retrying
                  ? SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          colorScheme.primary,
                        ),
                      ),
                    )
                  : const Icon(Icons.refresh, size: 16),
              label: Text(_retrying ? 'Retrying…' : 'Retry'),
              style: OutlinedButton.styleFrom(
                foregroundColor: colorScheme.primary,
                padding: const EdgeInsets.symmetric(vertical: 8),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: OutlinedButton.icon(
              onPressed: _retrying ? null : _handleDismiss,
              icon: Icon(
                Icons.close,
                size: 16,
                color: colorScheme.error,
              ),
              label: Text(
                'Dismiss',
                style: TextStyle(color: colorScheme.error),
              ),
              style: OutlinedButton.styleFrom(
                side: BorderSide(
                  color: colorScheme.error.withValues(alpha: 0.5),
                ),
                padding: const EdgeInsets.symmetric(vertical: 8),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Find every failed ImportItem under this batch's ImportJobs so we can
  /// retry or dismiss them individually via the per-item endpoints.
  Future<List<String>> _collectFailedItemIds() async {
    final batch = widget.batch;
    if (batch.importJobs.isEmpty) return const [];
    final futures = batch.importJobs.map(
      (ij) => _apiClient.listImportItems(ij.id, status: 'failed'),
    );
    final responses = await Future.wait(futures);
    final itemIds = <String>[];
    for (final r in responses) {
      final items = (r.data['items'] as List?) ?? const [];
      for (final raw in items) {
        if (raw is Map && raw['id'] != null) {
          itemIds.add(raw['id'].toString());
        }
      }
    }
    return itemIds;
  }

  Future<void> _handleRetry() async {
    if (!mounted) return;
    setState(() => _retrying = true);

    try {
      final itemIds = await _collectFailedItemIds();
      if (itemIds.isEmpty) {
        throw Exception('No failed items found to retry');
      }
      await Future.wait(
        itemIds.map((id) => _apiClient.retryImportItem(id)),
      );
      if (!mounted) return;
      // Refresh to pick up the new "processing" state from the server.
      await ref.read(importBatchesProvider.notifier).refresh();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Retrying import…'),
          duration: Duration(seconds: 2),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _retrying = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Retry failed: $e'),
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
      );
    }
  }

  Future<void> _handleDismiss() async {
    final batch = widget.batch;
    final notifier = ref.read(importBatchesProvider.notifier);

    // Optimistic: hide the row immediately. We keep a reference to the
    // batch so the snackbar undo can re-add it on local state only. If the
    // user waits out the snackbar, the backend dismissal is permanent.
    notifier.locallyRemoveBatch(batch.id);

    // Fire-and-forget the backend call, but still handle errors.
    Future<void> backendCall() async {
      try {
        final itemIds = await _collectFailedItemIds();
        await Future.wait(
          itemIds.map((id) => _apiClient.dismissImportItem(id)),
        );
      } catch (_) {
        // On backend failure, restore locally so the user sees the row again.
        if (mounted) notifier.locallyRestoreBatch(batch);
      }
    }

    unawaited(backendCall());

    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(
      SnackBar(
        content: const Text('Import dismissed'),
        duration: const Duration(seconds: 4),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () {
            // Local-only undo. If the backend dismissal already committed,
            // the next poll refresh will find nothing to show for this id
            // anyway, so the restore is purely optimistic UI.
            notifier.locallyRestoreBatch(batch);
          },
        ),
      ),
    );
  }

  Widget _buildExpanded(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final batch = widget.batch;

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (batch.errorMessage != null) ...[
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: colorScheme.errorContainer.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                batch.errorMessage!,
                style: TextStyle(
                  color: colorScheme.error,
                  fontSize: 12,
                ),
              ),
            ),
            const SizedBox(height: 8),
          ],
          // Per-recipe status — one row per logical recipe. This is the
          // user-facing detail; matches Import Activity's attention view.
          if (batch.importJobs.isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.only(top: 4, bottom: 6),
              child: Text(
                'Recipes in this batch',
                style: TextStyle(
                  color: context.appColors.textTertiary,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.4,
                ),
              ),
            ),
            ...batch.importJobs.asMap().entries.map(
                  (e) => _ImportJobRow(
                    index: e.key + 1,
                    job: e.value,
                  ),
                ),
            const SizedBox(height: 10),
          ],
          // OCR-level detail hidden by default — it's a debug view.
          _DebugSection(jobs: batch.jobs),
        ],
      ),
    );
  }

  void _navigateToReview(BuildContext context) {
    final batch = widget.batch;
    final reviewable = batch.importJobs.firstWhere(
      (ij) => ij.status == 'awaiting_review',
      orElse: () => batch.importJobs.isNotEmpty
          ? batch.importJobs.first
          : const ImportBatchImportJob(id: '', status: ''),
    );
    if (reviewable.id.isNotEmpty) {
      context.push('/recipes/import/review-list/${reviewable.id}');
    }
  }
}

class _JobDebugRow extends StatefulWidget {
  final ImportBatchJob job;

  const _JobDebugRow({required this.job});

  @override
  State<_JobDebugRow> createState() => _JobDebugRowState();
}

class _JobDebugRowState extends State<_JobDebugRow> {
  bool _showText = false;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final job = widget.job;
    final hasText = job.extractedText != null && job.extractedText!.isNotEmpty;

    return Container(
      margin: const EdgeInsets.only(top: 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: colorScheme.outlineVariant.withValues(alpha: 0.4),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  job.displayName,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 6),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: _statusColor(job.status, context).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  job.status,
                  style: TextStyle(
                    fontSize: 10,
                    color: _statusColor(job.status, context),
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
          if (job.errorMessage != null) ...[
            const SizedBox(height: 4),
            Text(
              job.errorMessage!,
              style: TextStyle(
                fontSize: 11,
                color: colorScheme.error,
              ),
            ),
          ],
          if (hasText) ...[
            const SizedBox(height: 4),
            GestureDetector(
              onTap: () => setState(() => _showText = !_showText),
              child: Row(
                children: [
                  Icon(
                    _showText ? Icons.expand_less : Icons.expand_more,
                    size: 14,
                    color: colorScheme.primary,
                  ),
                  const SizedBox(width: 2),
                  Text(
                    _showText ? 'Hide extracted text' : 'Show extracted text',
                    style: TextStyle(
                      color: colorScheme.primary,
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
            if (_showText)
              Container(
                margin: const EdgeInsets.only(top: 4),
                padding: const EdgeInsets.all(8),
                constraints: const BoxConstraints(maxHeight: 200),
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: SingleChildScrollView(
                  child: SelectableText(
                    job.extractedText!,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                    ),
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }

  Color _statusColor(String status, BuildContext context) {
    final c = Theme.of(context).colorScheme;
    final appColors = context.appColors;
    switch (status) {
      case 'succeeded':
        return appColors.success;
      case 'failed':
        return c.error;
      case 'running':
      case 'submitted':
        return appColors.info;
      default:
        return appColors.textTertiary;
    }
  }
}

class _StatusSummary {
  final String label;
  final Color color;
  final bool isTappable;

  const _StatusSummary({
    required this.label,
    required this.color,
    required this.isTappable,
  });
}

/// Subtitle that reports live progress by import-job status instead of the
/// abstract "N photos · M recipes" count. Matches Import Activity phrasing.
String _batchSubtitle(ImportBatch batch) {
  if (batch.importJobs.isEmpty) {
    // Pre-ingest: only parser jobs exist. Show OCR progress.
    final done = batch.jobs
        .where((j) => j.status == 'succeeded' || j.status == 'failed')
        .length;
    return 'Reading text · $done of ${batch.jobs.length}';
  }
  int review = 0;
  int processing = 0;
  int completed = 0;
  int failed = 0;
  for (final ij in batch.importJobs) {
    switch (ij.status) {
      case 'awaiting_review':
        review++;
        break;
      case 'completed':
        completed++;
        break;
      case 'failed':
        failed++;
        break;
      default:
        processing++;
    }
  }
  final parts = <String>[
    if (review > 0) '$review ready',
    if (processing > 0) '$processing processing',
    if (completed > 0) '$completed imported',
    if (failed > 0) '$failed failed',
  ];
  return parts.isEmpty
      ? '${batch.groupCount} recipe${batch.groupCount == 1 ? '' : 's'}'
      : parts.join(' · ');
}

/// Single per-recipe row inside an expanded batch — mirrors the Import
/// Activity attention-view row: number, status chip, inline review tap
/// when awaiting_review.
class _ImportJobRow extends StatelessWidget {
  final int index;
  final ImportBatchImportJob job;

  const _ImportJobRow({required this.index, required this.job});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final (label, color) = _labelAndColor(job.status, context);
    final tappable = job.status == 'awaiting_review';

    return InkWell(
      onTap: tappable
          ? () => context.push('/recipes/import/review-list/${job.id}')
          : null,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
        child: Row(
          children: [
            Container(
              width: 22,
              height: 22,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: colorScheme.surface,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(
                  color: colorScheme.outlineVariant.withValues(alpha: 0.5),
                ),
              ),
              child: Text(
                '$index',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: context.appColors.textTertiary,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Recipe $index',
                style: const TextStyle(fontSize: 13),
              ),
            ),
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                label,
                style: TextStyle(
                  color: color,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            if (tappable) ...[
              const SizedBox(width: 6),
              Icon(
                Icons.chevron_right,
                size: 18,
                color: colorScheme.primary,
              ),
            ],
          ],
        ),
      ),
    );
  }

  (String, Color) _labelAndColor(String status, BuildContext context) {
    final c = Theme.of(context).colorScheme;
    final app = context.appColors;
    switch (status) {
      case 'awaiting_review':
        return ('Ready to review', app.info);
      case 'completed':
        return ('Imported', app.success);
      case 'failed':
        return ('Failed', c.error);
      case 'processing':
      case 'matching':
      case 'extracting':
        return ('Processing', app.warning);
      case 'pending':
        return ('Queued', app.textTertiary);
      default:
        return (status, app.textTertiary);
    }
  }
}

/// Collapsible OCR-level debug section — hidden by default so the
/// expanded row reads as a user-facing recipe list, not engineer output.
class _DebugSection extends StatefulWidget {
  final List<ImportBatchJob> jobs;

  const _DebugSection({required this.jobs});

  @override
  State<_DebugSection> createState() => _DebugSectionState();
}

class _DebugSectionState extends State<_DebugSection> {
  bool _show = false;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    if (widget.jobs.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextButton.icon(
          onPressed: () => setState(() => _show = !_show),
          icon: Icon(
            _show ? Icons.expand_less : Icons.expand_more,
            size: 16,
          ),
          label: Text(
            _show ? 'Hide OCR details' : 'Show OCR details',
            style: const TextStyle(fontSize: 11),
          ),
          style: TextButton.styleFrom(
            foregroundColor: colorScheme.onSurfaceVariant,
            padding: const EdgeInsets.symmetric(horizontal: 4),
            visualDensity: VisualDensity.compact,
          ),
        ),
        if (_show)
          ...widget.jobs.map((j) => _JobDebugRow(job: j)),
      ],
    );
  }
}

_StatusSummary _summarizeStatus(ImportBatch batch) {
  final ocrDoneCount = batch.jobs
      .where((j) => j.status == 'succeeded' || j.status == 'failed')
      .length;
  final hasReviewable =
      batch.importJobs.any((ij) => ij.status == 'awaiting_review');

  if (batch.status == 'succeeded' || hasReviewable) {
    return _StatusSummary(
      label: 'Ready to review',
      color: const Color(0xFF1976D2),
      isTappable: true,
    );
  }
  if (batch.status == 'failed') {
    return const _StatusSummary(
      label: 'Failed',
      color: Color(0xFFD32F2F),
      isTappable: false,
    );
  }
  if (batch.status == 'partial') {
    final ready = batch.importJobs.length;
    final total = batch.groupCount;
    return _StatusSummary(
      label: '$ready of $total recipes ready',
      color: const Color(0xFFF57C00),
      isTappable: true,
    );
  }
  // Submitted / running / pending
  if (ocrDoneCount < batch.jobs.length) {
    return _StatusSummary(
      label: 'Reading text $ocrDoneCount/${batch.jobs.length}',
      color: const Color(0xFFF57C00),
      isTappable: false,
    );
  }
  return const _StatusSummary(
    label: 'Structuring recipe',
    color: Color(0xFF1976D2),
    isTappable: false,
  );
}
