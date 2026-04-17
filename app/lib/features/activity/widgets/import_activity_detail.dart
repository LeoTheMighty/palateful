// ─────────────────────────────────────────────────────────────────────────────
// Import-item field audit (bugs-act-2, 2026-04-16)
//
// Produced by auditing `GetImportItem.Response` in services/api/src/api/v1/
// import_job/get_import_item.py against the hierarchical-render requirement
// in the story. Every field in the response schema is assigned one of three
// dispositions: `rendered`, `annotated-not-shown`, or
// `MISSING-needs-backend`. Policy: no silent drops.
//
// Response fields (from GetImportItem.Response):
//   id                  → annotated-not-shown: internal DB id, not user-meaningful
//   status              → rendered: "current stage" in hierarchy (header chip)
//   source_type         → rendered: icon in source row
//   source_reference    → rendered: source detail (row N / page N)
//   source_url          → rendered: tappable URL in source row
//   raw_data            → annotated-not-shown: debug-only blob
//   parsed_recipe       → rendered: the edit form below this header IS the view
//   user_edits          → rendered: merged over parsed_recipe in edit form
//   error_message       → rendered: top of hierarchy when failed, collapsed to
//                         2-line preview + Show more (default closed)
//   error_code          → annotated-not-shown: internal triage code
//   retry_count         → rendered: retry row at bottom of hierarchy
//   ai_cost_cents       → annotated-not-shown: not user-facing
//   import_job_id       → annotated-not-shown: internal linkage
//   created_recipe_id   → annotated-not-shown: used post-approval for nav
//   created_at          → rendered: timestamps section
//   updated_at          → rendered: timestamps section
//
// MISSING-needs-backend (filed as bugs-act-2a-backend-fields-addendum):
//   last_successful_stage   → story AC #2 ("current stage + last successful
//                             stage"). Column exists on ImportItem model but
//                             is not exposed by GetImportItem.Response.
//   last_retry_at           → story AC #2 ("last retry timestamp"). Neither
//                             the model nor response has this; retry_count
//                             alone is rendered in the interim.
//   confidence_score        → story AC #2 (bullet 6). Not produced by the
//                             pipeline today.
//
// Update policy: when this file changes, update the audit above. When the
// backend response adds a field, add it here with its disposition. No silent
// drops.
// ─────────────────────────────────────────────────────────────────────────────

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

/// Header card rendering every user-meaningful import-item field in a
/// hierarchical order:
///   1. error message (when status is failed/errored)
///   2. stage / status
///   3. source (type + URL + reference)
///   4. created / updated timestamps
///   5. retry count
///
/// Call sites embed this at the top of the Review Import screen (both the
/// success-editable and failed branches) so the same summary lives in every
/// path into the detail view.
class ImportActivityDetail extends StatefulWidget {
  final Map<String, dynamic> item;

  const ImportActivityDetail({super.key, required this.item});

  @override
  State<ImportActivityDetail> createState() => _ImportActivityDetailState();
}

class _ImportActivityDetailState extends State<ImportActivityDetail> {
  // Default closed per story AC #3.
  bool _errorExpanded = false;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final item = widget.item;

    final errorMessage = item['error_message'] as String?;
    final status = item['status']?.toString();
    final sourceType = item['source_type']?.toString();
    final sourceUrl = item['source_url']?.toString();
    final sourceReference = item['source_reference']?.toString();
    final createdAtIso = item['created_at']?.toString();
    final updatedAtIso = item['updated_at']?.toString();
    final retryCount = (item['retry_count'] as num?)?.toInt() ?? 0;

    final rows = <Widget>[];

    // 1. Error — only when present
    if (errorMessage != null && errorMessage.isNotEmpty) {
      rows.add(_buildErrorRow(errorMessage, colorScheme, textTheme));
      rows.add(const SizedBox(height: 12));
    }

    // 2. Stage / status
    if (status != null && status.isNotEmpty) {
      rows.add(_buildStageRow(status, colorScheme, textTheme));
      rows.add(const SizedBox(height: 8));
    }

    // 3. Source
    final sourceWidget = _buildSourceRow(
      sourceType: sourceType,
      sourceUrl: sourceUrl,
      sourceReference: sourceReference,
      colorScheme: colorScheme,
      textTheme: textTheme,
    );
    if (sourceWidget != null) {
      rows.add(sourceWidget);
      rows.add(const SizedBox(height: 8));
    }

    // 4. Timestamps
    final timestampsWidget = _buildTimestamps(
      createdAtIso: createdAtIso,
      updatedAtIso: updatedAtIso,
      colorScheme: colorScheme,
      textTheme: textTheme,
    );
    if (timestampsWidget != null) {
      rows.add(timestampsWidget);
      rows.add(const SizedBox(height: 8));
    }

    // 5. Retry count (+ last retry timestamp is MISSING-needs-backend; we
    //    render retry_count only per field audit)
    if (retryCount > 0) {
      rows.add(_buildRetryRow(retryCount, colorScheme, textTheme));
    }

    if (rows.isEmpty) return const SizedBox.shrink();

    return Card(
      margin: EdgeInsets.zero,
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: rows,
        ),
      ),
    );
  }

  Widget _buildErrorRow(
      String message, ColorScheme colorScheme, TextTheme textTheme) {
    final preview = _twoLinePreview(message);
    final isTruncated = preview != message;

    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.error_outline,
                  size: 18, color: colorScheme.onErrorContainer),
              const SizedBox(width: 6),
              Text(
                'Error',
                style: textTheme.labelLarge?.copyWith(
                  color: colorScheme.onErrorContainer,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            _errorExpanded ? message : preview,
            style: textTheme.bodyMedium?.copyWith(
              color: colorScheme.onErrorContainer,
            ),
          ),
          if (isTruncated)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: () =>
                    setState(() => _errorExpanded = !_errorExpanded),
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  minimumSize: const Size(0, 32),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  foregroundColor: colorScheme.onErrorContainer,
                ),
                child: Text(_errorExpanded ? 'Show less' : 'Show more'),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildStageRow(
      String status, ColorScheme colorScheme, TextTheme textTheme) {
    final label = _statusLabel(status);
    final color = _statusColor(status, colorScheme);
    return Row(
      children: [
        Icon(Icons.timeline, size: 16, color: colorScheme.onSurfaceVariant),
        const SizedBox(width: 6),
        Text(
          'Stage',
          style: textTheme.labelSmall?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Text(
            label,
            style: textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }

  Widget? _buildSourceRow({
    required String? sourceType,
    required String? sourceUrl,
    required String? sourceReference,
    required ColorScheme colorScheme,
    required TextTheme textTheme,
  }) {
    if ((sourceType == null || sourceType.isEmpty) &&
        (sourceUrl == null || sourceUrl.isEmpty) &&
        (sourceReference == null || sourceReference.isEmpty)) {
      return null;
    }

    final icon = _iconForSourceType(sourceType);
    final detail = sourceReference != null && sourceReference.isNotEmpty
        ? '${_sourceTypeLabel(sourceType)} · $sourceReference'
        : _sourceTypeLabel(sourceType);

    final urlWidget = (sourceUrl != null && sourceUrl.isNotEmpty)
        ? GestureDetector(
            onTap: () async {
              final uri = Uri.tryParse(sourceUrl);
              if (uri == null) return;
              if (await canLaunchUrl(uri)) {
                await launchUrl(uri, mode: LaunchMode.externalApplication);
              }
            },
            child: Text(
              sourceUrl,
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.primary,
                decoration: TextDecoration.underline,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          )
        : null;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: colorScheme.onSurfaceVariant),
        const SizedBox(width: 6),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                detail,
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                ),
              ),
              if (urlWidget != null) ...[
                const SizedBox(height: 2),
                urlWidget,
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget? _buildTimestamps({
    required String? createdAtIso,
    required String? updatedAtIso,
    required ColorScheme colorScheme,
    required TextTheme textTheme,
  }) {
    final created = createdAtIso != null ? DateTime.tryParse(createdAtIso) : null;
    final updated = updatedAtIso != null ? DateTime.tryParse(updatedAtIso) : null;
    if (created == null && updated == null) return null;

    final parts = <String>[];
    if (created != null) parts.add('Created ${_formatTime(created)}');
    if (updated != null && (created == null || !updated.isAtSameMomentAs(created))) {
      parts.add('Updated ${_formatTime(updated)}');
    }
    if (parts.isEmpty) return null;

    return Row(
      children: [
        Icon(Icons.schedule, size: 16, color: colorScheme.onSurfaceVariant),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            parts.join(' · '),
            style: textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildRetryRow(
      int count, ColorScheme colorScheme, TextTheme textTheme) {
    return Row(
      children: [
        Icon(Icons.refresh, size: 16, color: colorScheme.onSurfaceVariant),
        const SizedBox(width: 6),
        Text(
          'Retries: $count',
          style: textTheme.bodySmall?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }

  String _twoLinePreview(String s) {
    // Rough two-line equivalent; the Text widget handles real wrapping.
    // We just trim aggressively for the short preview so "Show more"
    // is meaningful when the message is long.
    const previewMax = 180;
    final oneLine = s.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (oneLine.length <= previewMax) return s;
    return '${oneLine.substring(0, previewMax)}…';
  }

  String _statusLabel(String status) {
    switch (status) {
      case 'pending':
        return 'Pending';
      case 'extracting':
        return 'Extracting';
      case 'matching':
        return 'Matching';
      case 'awaiting_review':
        return 'Needs review';
      case 'approved':
        return 'Approved';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      case 'skipped':
        return 'Dismissed';
      default:
        return status;
    }
  }

  Color _statusColor(String status, ColorScheme colorScheme) {
    switch (status) {
      case 'failed':
        return colorScheme.error;
      case 'awaiting_review':
        return colorScheme.tertiary;
      case 'completed':
      case 'approved':
        return colorScheme.primary;
      case 'skipped':
        return colorScheme.outline;
      default:
        return colorScheme.secondary;
    }
  }

  IconData _iconForSourceType(String? sourceType) {
    switch (sourceType) {
      case 'url':
        return Icons.link;
      case 'url_list':
        return Icons.list;
      case 'photo':
        return Icons.camera_alt;
      case 'text':
        return Icons.description;
      case 'spreadsheet':
        return Icons.table_chart;
      case 'pdf':
        return Icons.picture_as_pdf;
      case 'audio':
        return Icons.mic;
      default:
        return Icons.import_export;
    }
  }

  String _sourceTypeLabel(String? sourceType) {
    switch (sourceType) {
      case 'url':
        return 'URL';
      case 'url_list':
        return 'URL list';
      case 'photo':
        return 'Photo';
      case 'text':
        return 'Pasted text';
      case 'spreadsheet':
        return 'Spreadsheet';
      case 'pdf':
        return 'PDF';
      case 'audio':
        return 'Audio';
      default:
        return 'Source';
    }
  }

  String _formatTime(DateTime date) {
    final local = date.toLocal();
    final now = DateTime.now();
    final diff = now.difference(local);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${local.month}/${local.day}/${local.year}';
  }
}
