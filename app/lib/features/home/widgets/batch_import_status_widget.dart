import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../../../core/theme/theme.dart';
import '../../recipes/add_recipe/batch_parser_service.dart';

/// Compact notification badge for import status on the home screen.
///
/// Shows a single-line summary ("Processing X photos...", "X photos
/// processed — see Activity") and navigates to the Import Activity
/// screen on tap. After FR88 fan-out, one photo can produce N review
/// items, so the "processed" string counts photos (ParserJob successes)
/// and nudges the user to Activity Hub for the actual recipe count.
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

    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;

    final processing = _jobs
        .where((j) =>
            j.status != BatchJobStatus.succeeded &&
            j.status != BatchJobStatus.failed)
        .length;
    final succeeded =
        _jobs.where((j) => j.status == BatchJobStatus.succeeded).length;
    final failed =
        _jobs.where((j) => j.status == BatchJobStatus.failed).length;

    String summary;
    Widget leadingIcon;

    if (processing > 0) {
      summary = 'Processing $processing photo${processing == 1 ? '' : 's'}...';
      leadingIcon = SizedBox(
        width: 16,
        height: 16,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation<Color>(colorScheme.secondary),
        ),
      );
    } else if (succeeded > 0 && failed == 0) {
      // FR88: a processed photo can yield N recipes. Count photos here
      // and nudge the user to Activity Hub for the accurate recipe count.
      summary = '$succeeded photo${succeeded == 1 ? '' : 's'} processed — see Activity';
      leadingIcon = Icon(Icons.check_circle, size: 18, color: appColors.success);
    } else if (failed > 0 && succeeded == 0) {
      summary = '$failed import${failed == 1 ? '' : 's'} failed';
      leadingIcon = Icon(Icons.error, size: 18, color: colorScheme.error);
    } else {
      summary = '$succeeded ready, $failed failed';
      leadingIcon = Icon(Icons.info_outline, size: 18, color: colorScheme.primary);
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: GestureDetector(
        onTap: () => context.push('/activity/import-history'),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              leadingIcon,
              const SizedBox(width: 10),
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
                Icons.chevron_right,
                color: colorScheme.onSurfaceVariant,
                size: 20,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
