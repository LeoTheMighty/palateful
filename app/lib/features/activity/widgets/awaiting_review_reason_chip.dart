import 'package:flutter/material.dart';

import '../../../core/theme/import_state_colors.dart';

/// 1-word chip rendered inline in collapsed yellow rows — surfaces the
/// `awaiting_review_reason` that routed the item into Needs Review
/// without requiring caret expansion.
///
/// Values map directly from the backend enum
/// (`low_confidence` / `unmatched_ingredients` / `missing_title` /
/// `manual`). Any other value renders an empty `SizedBox`.
class AwaitingReviewReasonChip extends StatelessWidget {
  final String? reason;

  const AwaitingReviewReasonChip({super.key, required this.reason});

  @override
  Widget build(BuildContext context) {
    final label = _labelFor(reason);
    if (label == null) return const SizedBox.shrink();

    final theme = Theme.of(context);
    final fg = context.importStates.needsReview;

    return Semantics(
      container: true,
      label: 'Reason: $label',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
        decoration: BoxDecoration(
          color: fg.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          label,
          style: theme.textTheme.labelSmall?.copyWith(
            color: fg,
            fontWeight: FontWeight.w600,
            fontSize: 10,
          ),
        ),
      ),
    );
  }

  static String? _labelFor(String? reason) {
    switch (reason) {
      case 'low_confidence':
        return 'low confidence';
      case 'unmatched_ingredients':
        return 'unmatched ingredients';
      case 'missing_title':
        return 'missing title';
      case 'manual':
        return 'manual review';
      default:
        return null;
    }
  }
}
