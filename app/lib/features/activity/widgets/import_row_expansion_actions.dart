import 'package:flutter/material.dart';

/// Row of action buttons rendered at the bottom of [ImportRowExpansion].
///
/// Button set varies by [state]:
/// - `needsReview` → **Review →** + **Dismiss**
/// - `failed`      → **Retry** + **Dismiss**
/// - `autoImported`→ **View Recipe** + **Dismiss**
/// - `skipped`     → **Dismiss** only (no recipe to view, no retry path)
/// - `inProgress`  → (nothing — cancel stays out-of-scope this epic)
///
/// All callbacks are nullable; a null callback disables the button. On
/// narrow screens buttons wrap to two rows via `Wrap` rather than
/// truncating so tap targets stay ≥44dp.
enum ImportRowState {
  needsReview,
  failed,
  autoImported,
  skipped,
  inProgress,
}

class ImportRowExpansionActions extends StatelessWidget {
  final ImportRowState state;
  final VoidCallback? onReview;
  final VoidCallback? onRetry;
  final VoidCallback? onViewRecipe;
  final VoidCallback? onArchive;

  const ImportRowExpansionActions({
    super.key,
    required this.state,
    this.onReview,
    this.onRetry,
    this.onViewRecipe,
    this.onArchive,
  });

  @override
  Widget build(BuildContext context) {
    final buttons = _buttonsFor(context, state);
    if (buttons.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: buttons,
      ),
    );
  }

  List<Widget> _buttonsFor(BuildContext context, ImportRowState s) {
    switch (s) {
      case ImportRowState.needsReview:
        return [
          FilledButton.icon(
            onPressed: onReview,
            icon: const Icon(Icons.rate_review_outlined, size: 18),
            label: const Text('Review'),
            style: FilledButton.styleFrom(
              minimumSize: const Size(0, 44),
            ),
          ),
          _archiveButton(),
        ];
      case ImportRowState.failed:
        return [
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 18),
            label: const Text('Retry'),
            style: FilledButton.styleFrom(
              minimumSize: const Size(0, 44),
            ),
          ),
          _archiveButton(),
        ];
      case ImportRowState.autoImported:
        return [
          FilledButton.icon(
            onPressed: onViewRecipe,
            icon: const Icon(Icons.receipt_long, size: 18),
            label: const Text('View Recipe'),
            style: FilledButton.styleFrom(
              minimumSize: const Size(0, 44),
            ),
          ),
          _archiveButton(),
        ];
      case ImportRowState.skipped:
        return [_archiveButton()];
      case ImportRowState.inProgress:
        return const [];
    }
  }

  Widget _archiveButton() {
    return OutlinedButton.icon(
      onPressed: onArchive,
      icon: const Icon(Icons.archive_outlined, size: 18),
      label: const Text('Dismiss'),
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(0, 44),
      ),
    );
  }
}
