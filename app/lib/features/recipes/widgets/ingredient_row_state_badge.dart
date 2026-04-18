import 'package:flutter/material.dart';

/// Small sparkle glyph rendered inline in `StructuredIngredientRow` when
/// the row's canonical ingredient was auto-created via find-or-create
/// and is still `pending_review = true` (riip-7).
///
/// Tap opens a short bottom-sheet explainer so Leo understands why the
/// badge is there and where to manage the new ingredient.
class IngredientRowStateBadge extends StatelessWidget {
  const IngredientRowStateBadge({
    super.key,
    required this.ingredientName,
  });

  /// The ingredient's display name — threaded into the bottom-sheet copy.
  final String? ingredientName;

  @override
  Widget build(BuildContext context) {
    // Epic design: `ImportStateColors.inProgress` (subtle blue). That
    // theme extension arrives with ahr-6; until then we use the color
    // scheme's primary for the same "calm information" vibe. Swap the
    // literal when the extension lands.
    final color = Theme.of(context).colorScheme.primary;
    return Semantics(
      label: 'New ingredient — tap for details',
      button: true,
      child: InkWell(
        key: const Key('ingredient_row_state_badge'),
        onTap: () => _showExplainer(context),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
          child: Icon(
            Icons.auto_awesome,
            size: 14,
            color: color,
          ),
        ),
      ),
    );
  }

  void _showExplainer(BuildContext context) {
    final name = (ingredientName?.trim().isEmpty ?? true)
        ? 'This ingredient'
        : "'${ingredientName!.trim()}'";
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.auto_awesome,
                    size: 18,
                    color: Theme.of(ctx).colorScheme.primary,
                  ),
                  const SizedBox(width: 8),
                  const Text(
                    'New ingredient',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                "$name was added to your catalog for review. You can "
                'rename or merge it later in Settings › Pantry.',
                style: const TextStyle(fontSize: 14, height: 1.35),
              ),
              const SizedBox(height: 20),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  key: const Key('ingredient_row_state_badge_dismiss'),
                  onPressed: () => Navigator.of(ctx).pop(),
                  child: const Text('Got it'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
