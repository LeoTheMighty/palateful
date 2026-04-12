import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

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

class _ImportBatchRow extends StatefulWidget {
  final ImportBatch batch;
  final bool isJustStarted;

  const _ImportBatchRow({required this.batch, required this.isJustStarted});

  @override
  State<_ImportBatchRow> createState() => _ImportBatchRowState();
}

class _ImportBatchRowState extends State<_ImportBatchRow> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final batch = widget.batch;
    final summary = _summarizeStatus(batch);
    final isTappable = summary.isTappable;

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
                          '${batch.jobs.length} photo${batch.jobs.length == 1 ? '' : 's'}'
                          ' · ${batch.groupCount} recipe${batch.groupCount == 1 ? '' : 's'}',
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
          if (_expanded) _buildExpanded(context),
        ],
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
          ...batch.jobs.map((j) => _JobDebugRow(job: j)),
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
