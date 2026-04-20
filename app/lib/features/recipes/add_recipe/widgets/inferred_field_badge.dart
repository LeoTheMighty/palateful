import 'package:flutter/material.dart';

/// efi-5 — sparkle badge rendered next to an inferable field's label when
/// the extractor best-guessed the value. Tap opens an explainer sheet.
/// Visibility is derived state: parents pass a `Set&lt;String&gt;
/// _inferredFields` and render the badge only when the field name is in
/// the set. Editing the field removes the name → the badge vanishes.
class InferredFieldBadge extends StatelessWidget {
  const InferredFieldBadge({super.key, this.onTap});

  /// Override the default tap behaviour (defaults to showing the
  /// explainer bottom sheet).
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.tertiary;
    return Semantics(
      label: 'AI-inferred value, tap for details',
      button: true,
      child: InkWell(
        onTap: onTap ?? () => _showExplainer(context),
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          // 14pt icon + 13pt all-around padding = 40pt tap target.
          padding: const EdgeInsets.all(13),
          child: Icon(Icons.auto_awesome, size: 14, color: color),
        ),
      ),
    );
  }

  static void _showExplainer(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheet) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.auto_awesome,
                      size: 20,
                      color: Theme.of(sheet).colorScheme.tertiary,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'AI guess',
                      style: Theme.of(sheet).textTheme.titleMedium,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                const Text(
                  'This value was inferred from the recipe. Verify or '
                  'edit it below — your correction helps the extractor '
                  'learn.',
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
