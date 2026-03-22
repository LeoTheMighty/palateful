import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/di/injection.dart';
import '../../../core/theme/theme.dart';
import '../../recipes/add_recipe/batch_parser_service.dart';
import 'batch_job_result_sheet.dart';

class BatchImportStatusWidget extends StatefulWidget {
  const BatchImportStatusWidget({super.key});

  @override
  State<BatchImportStatusWidget> createState() =>
      _BatchImportStatusWidgetState();
}

class _BatchImportStatusWidgetState extends State<BatchImportStatusWidget> {
  final _service = getIt<BatchParserService>();
  late StreamSubscription<List<BatchParserJob>> _subscription;
  List<BatchParserJob> _jobs = [];
  bool _expanded = false;

  @override
  void initState() {
    super.initState();
    _jobs = _service.jobs;
    _subscription = _service.jobStream.listen((jobs) {
      if (mounted) setState(() => _jobs = jobs);
    });
  }

  @override
  void dispose() {
    _subscription.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_jobs.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: AnimatedSize(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeInOut,
        alignment: Alignment.topCenter,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildCollapsedBar(),
            if (_expanded) _buildJobList(),
          ],
        ),
      ),
    );
  }

  Widget _buildCollapsedBar() {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;

    final processing =
        _jobs.where((j) => j.status != BatchJobStatus.succeeded && j.status != BatchJobStatus.failed).length;
    final succeeded = _jobs.where((j) => j.status == BatchJobStatus.succeeded).length;
    final failed = _jobs.where((j) => j.status == BatchJobStatus.failed).length;

    String summary;
    if (processing > 0) {
      summary = 'Processing $processing photo${processing == 1 ? '' : 's'}...';
    } else if (succeeded > 0 && failed == 0) {
      summary = '$succeeded recipe${succeeded == 1 ? '' : 's'} ready';
    } else if (failed > 0 && succeeded == 0) {
      summary = '$failed failed';
    } else {
      summary = '$succeeded ready, $failed failed';
    }

    return GestureDetector(
      onTap: () => setState(() => _expanded = !_expanded),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            if (processing > 0)
              Padding(
                padding: const EdgeInsets.only(right: 10),
                child: SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor:
                        AlwaysStoppedAnimation<Color>(colorScheme.secondary),
                  ),
                ),
              ),
            if (processing == 0 && succeeded > 0)
              Padding(
                padding: const EdgeInsets.only(right: 10),
                child: Icon(Icons.check_circle, size: 18, color: appColors.success),
              ),
            if (processing == 0 && succeeded == 0 && failed > 0)
              Padding(
                padding: const EdgeInsets.only(right: 10),
                child: Icon(Icons.error, size: 18, color: colorScheme.error),
              ),
            Expanded(
              child: Text(
                summary,
                style: TextStyle(
                  color: colorScheme.onSurface,
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            Icon(
              _expanded ? Icons.expand_less : Icons.expand_more,
              color: appColors.textTertiary,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildJobList() {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(top: 4),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: _jobs.map((job) => _buildJobRow(job)).toList(),
      ),
    );
  }

  Widget _buildJobRow(BatchParserJob job) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;

    final isLoading = job.status == BatchJobStatus.uploading ||
        job.status == BatchJobStatus.submitting ||
        job.status == BatchJobStatus.polling;

    return InkWell(
      onTap: job.status == BatchJobStatus.succeeded
          ? () => _showResultSheet(job)
          : null,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Row(
          children: [
            // Status icon
            if (isLoading)
              SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor:
                      AlwaysStoppedAnimation<Color>(colorScheme.secondary),
                ),
              )
            else if (job.status == BatchJobStatus.succeeded)
              Icon(Icons.check_circle, size: 20, color: appColors.success)
            else
              Icon(Icons.error, size: 20, color: colorScheme.error),

            const SizedBox(width: 10),

            // Filename + status text
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    job.filename,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: colorScheme.onSurface,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (isLoading)
                    Text(
                      _statusText(job.status),
                      style: TextStyle(
                        fontSize: 11,
                        color: appColors.textTertiary,
                      ),
                    ),
                ],
              ),
            ),

            // NEW badge for succeeded
            if (job.status == BatchJobStatus.succeeded && job.isNew)
              Container(
                margin: const EdgeInsets.only(left: 6),
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: appColors.success,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  'NEW',
                  style: TextStyle(
                    color: colorScheme.surface,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),

            // Retry button for failed
            if (job.status == BatchJobStatus.failed)
              TextButton(
                onPressed: () => _service.retryJob(job.localId),
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: Text(
                  'Retry',
                  style: TextStyle(
                    fontSize: 12,
                    color: colorScheme.primary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),

            // Dismiss button
            GestureDetector(
              onTap: () => _service.dismissJob(job.localId),
              child: Padding(
                padding: const EdgeInsets.only(left: 4),
                child: Icon(Icons.close, size: 16, color: appColors.textTertiary),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _statusText(BatchJobStatus status) {
    switch (status) {
      case BatchJobStatus.uploading:
        return 'Uploading...';
      case BatchJobStatus.submitting:
        return 'Submitting...';
      case BatchJobStatus.polling:
        return 'Processing...';
      default:
        return '';
    }
  }

  void _showResultSheet(BatchParserJob job) {
    _service.markSeen(job.localId);
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => BatchJobResultSheet(job: job),
    );
  }
}
