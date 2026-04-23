import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../../core/theme/theme.dart';
import '../../../../../core/utils/quantity_formatter.dart';

// Sentinel values for the expanded-grid group tracker. A plain `null`
// would collide with `builder(i) == null` in the comparison; these
// Object identities cannot.
const Object _kInitialSentinel = Object();
const Object _kUntaggedSentinel = Object();

class IngredientStrip extends StatefulWidget {
  final List<dynamic> ingredients;
  final Set<int> checkedIndices;
  final ValueChanged<int> onToggle;
  final double scaleFactor;

  /// Optional: when supplied, chips are emitted grouped by the value
  /// this builder returns. Recipe-cook plans pass `null`; meal-cook
  /// plans pass a builder backed by `CombinedIngredient.sourceComponentName`.
  final String? Function(int index)? sourceTagBuilder;

  const IngredientStrip({
    super.key,
    required this.ingredients,
    required this.checkedIndices,
    required this.onToggle,
    this.scaleFactor = 1.0,
    this.sourceTagBuilder,
  });

  @override
  State<IngredientStrip> createState() => _IngredientStripState();
}

class _IngredientStripState extends State<IngredientStrip> {
  @override
  Widget build(BuildContext context) {
    // cmlp-2 empty-ingredient edge case: render nothing — no padding,
    // no empty header, no "0 ingredients" label.
    if (widget.ingredients.isEmpty) return const SizedBox.shrink();
    return _buildExpandedGrid();
  }

  Widget _buildExpandedGrid() {
    final cook = context.cookModeTheme;
    final builder = widget.sourceTagBuilder;
    if (builder == null) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        child: Wrap(
          spacing: 8,
          runSpacing: 8,
          children: widget.ingredients.asMap().entries.map((entry) {
            return _IngredientChip(
              ingredient: entry.value,
              isChecked: widget.checkedIndices.contains(entry.key),
              onTap: () => widget.onToggle(entry.key),
              scaleFactor: widget.scaleFactor,
            );
          }).toList(),
        ),
      );
    }

    // Grouped view: emit "--- From <Component> ---" divider every time
    // the source tag transitions. cmlp-4 replaces the dashed text with a
    // typographic group header.
    //
    // Null contract: if the builder returns null for an index (e.g. a
    // failed-load component with no name yet), the chip is grouped
    // under "Other" so it's never silently merged into the previous
    // group's bucket. Sentinel `_kUntaggedSentinel` differentiates
    // null from a real component named "Other".
    final children = <Widget>[];
    Object? lastTag = _kInitialSentinel;
    final pendingChips = <Widget>[];
    void flushChips() {
      if (pendingChips.isEmpty) return;
      children.add(Wrap(
        spacing: 8,
        runSpacing: 8,
        children: List<Widget>.from(pendingChips),
      ));
      pendingChips.clear();
    }

    for (var i = 0; i < widget.ingredients.length; i++) {
      final rawTag = builder(i);
      final groupKey = rawTag ?? _kUntaggedSentinel;
      if (groupKey != lastTag) {
        flushChips();
        final headerText = rawTag == null
            ? '--- Other ---'
            : '--- From $rawTag ---';
        final headerKey = rawTag == null
            ? const Key('ingredient_group_untagged')
            : Key('ingredient_group_$rawTag');
        children.add(Padding(
          padding: const EdgeInsets.only(top: 12, bottom: 6),
          child: Text(
            headerText,
            key: headerKey,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.6,
              color: cook.cookOnSurface.withValues(alpha: 0.55),
            ),
          ),
        ));
        lastTag = groupKey;
      }
      pendingChips.add(_IngredientChip(
        ingredient: widget.ingredients[i],
        isChecked: widget.checkedIndices.contains(i),
        onTap: () => widget.onToggle(i),
        scaleFactor: widget.scaleFactor,
      ));
    }
    flushChips();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }
}

class _IngredientChip extends StatelessWidget {
  final dynamic ingredient;
  final bool isChecked;
  final VoidCallback onTap;
  final double scaleFactor;

  const _IngredientChip({
    required this.ingredient,
    required this.isChecked,
    required this.onTap,
    this.scaleFactor = 1.0,
  });

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    final name = ingredient['ingredient']?['canonical_name'] ?? 'Unknown';
    final quantity = scaleQuantityDisplay(
        ingredient['quantity_display'] as String?, scaleFactor);
    final unit = ingredient['unit_display'] ?? '';
    final quantityText = '$quantity $unit'.trim();

    // cmlp-3 width strategy: ConstrainedBox (not IntrinsicWidth) — the
    // chip hugs short content up to 160dp, then wraps the name to 2
    // lines. IntrinsicWidth inside a Wrap forces a layout pass per
    // child and bloats cost at 30+ ingredient meals.
    final nameColor =
        isChecked ? cook.cookOnCompleted : cook.cookOnSurface;
    final quantityColor =
        isChecked ? cook.cookOnCompleted : cook.cookAccent;

    final body = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (quantityText.isNotEmpty)
          Text(
            quantityText,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: quantityColor,
              decoration: isChecked ? TextDecoration.lineThrough : null,
            ),
          ),
        Text(
          name,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: nameColor,
            decoration: isChecked ? TextDecoration.lineThrough : null,
          ),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          softWrap: true,
        ),
      ],
    );

    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: Container(
        constraints: const BoxConstraints(minWidth: 72, maxWidth: 160),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: isChecked ? cook.cookCompleted : cook.cookSurfaceDim,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isChecked)
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: Icon(
                  Icons.check,
                  size: 16,
                  color: cook.cookOnCompleted,
                ),
              ),
            Flexible(child: body),
          ],
        ),
      ),
    );
  }
}
