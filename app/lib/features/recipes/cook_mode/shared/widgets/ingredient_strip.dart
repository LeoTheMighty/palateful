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

  /// Optional: when supplied, each chip renders a small source-tag chip
  /// underneath the name (compact view) and group dividers appear in
  /// the expanded grid view. Recipe-cook plans pass `null`; meal-cook
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
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    final labelColor = cook.cookOnSurface.withValues(alpha: 0.7);

    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
            child: Row(
              children: [
                Text(
                  'INGREDIENTS',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 1,
                    color: labelColor,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '${widget.checkedIndices.length}/${widget.ingredients.length}',
                  style: TextStyle(
                    fontSize: 11,
                    color: cook.cookAccent,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                GestureDetector(
                  onTap: () {
                    HapticFeedback.selectionClick();
                    setState(() => _isExpanded = !_isExpanded);
                  },
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 23),
                    child: Row(
                      children: [
                        Text(
                          _isExpanded ? 'Collapse' : 'Expand',
                          style: TextStyle(
                            fontSize: 12,
                            color: cook.cookOnSurface
                                .withValues(alpha: 0.7),
                          ),
                        ),
                        Icon(
                          _isExpanded ? Icons.expand_less : Icons.expand_more,
                          size: 18,
                          color: cook.cookOnSurface
                              .withValues(alpha: 0.7),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Ingredient chips
          AnimatedCrossFade(
            firstChild: _buildHorizontalStrip(),
            secondChild: _buildExpandedGrid(),
            crossFadeState: _isExpanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 300),
          ),
        ],
      ),
    );
  }

  Widget _buildHorizontalStrip() {
    return SizedBox(
      height: 80,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: widget.ingredients.length,
        itemBuilder: (context, index) {
          final tag = widget.sourceTagBuilder?.call(index);
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: _IngredientChip(
              ingredient: widget.ingredients[index],
              isChecked: widget.checkedIndices.contains(index),
              onTap: () => widget.onToggle(index),
              isCompact: true,
              scaleFactor: widget.scaleFactor,
              sourceTag: tag,
            ),
          );
        },
      ),
    );
  }

  Widget _buildExpandedGrid() {
    final cook = context.cookModeTheme;
    final builder = widget.sourceTagBuilder;
    if (builder == null) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Wrap(
          spacing: 8,
          runSpacing: 8,
          children: widget.ingredients.asMap().entries.map((entry) {
            return _IngredientChip(
              ingredient: entry.value,
              isChecked: widget.checkedIndices.contains(entry.key),
              onTap: () => widget.onToggle(entry.key),
              isCompact: false,
              scaleFactor: widget.scaleFactor,
            );
          }).toList(),
        ),
      );
    }

    // Grouped expanded view: emit "--- From <Component> ---" divider
    // every time the source tag transitions. cmm-1 AC7 + cmm-4 AC5.
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
        isCompact: false,
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
  final bool isCompact;
  final double scaleFactor;
  final String? sourceTag;

  const _IngredientChip({
    required this.ingredient,
    required this.isChecked,
    required this.onTap,
    required this.isCompact,
    this.scaleFactor = 1.0,
    this.sourceTag,
  });

  /// Truncate to 10 grapheme clusters (not code units) so emoji and
  /// accented chars don't get sliced through their surrogate pairs.
  /// Component names come from user-controlled meal data.
  String _truncatedTag(String tag) {
    final chars = tag.characters;
    if (chars.length <= 10) return tag;
    return '${chars.take(9)}…';
  }

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    final name = ingredient['ingredient']?['canonical_name'] ?? 'Unknown';
    final quantity = scaleQuantityDisplay(
        ingredient['quantity_display'] as String?, scaleFactor);
    final unit = ingredient['unit_display'] ?? '';

    if (isCompact) {
      // Compact vertical chip for horizontal scroll
      final hasTag = sourceTag != null && sourceTag!.isNotEmpty;
      return GestureDetector(
        onTap: () {
          HapticFeedback.selectionClick();
          onTap();
        },
        child: Container(
          width: hasTag ? 72 : 64,
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: isChecked ? cook.cookCompleted : cook.cookSurfaceDim,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isChecked ? cook.cookCompleted : cook.cookDivider,
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Quantity
              Text(
                '$quantity $unit'.trim(),
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: isChecked
                      ? cook.cookOnCompleted
                      : cook.cookOnSurface,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              SizedBox(height: hasTag ? 2 : 4),
              // Name — drops to 1 line when a source tag occupies the
              // third row so the chip fits in the 80dp strip.
              Text(
                name,
                style: TextStyle(
                  fontSize: 10,
                  color: isChecked
                      ? cook.cookOnCompleted
                      : cook.cookOnSurface.withValues(alpha: 0.7),
                ),
                maxLines: hasTag ? 1 : 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
              ),
              if (hasTag) ...[
                const SizedBox(height: 2),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 4, vertical: 1),
                  decoration: BoxDecoration(
                    color: cook.cookAccent.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    _truncatedTag(sourceTag!),
                    style: TextStyle(
                      fontSize: 8,
                      fontWeight: FontWeight.w600,
                      color: cook.cookAccent,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ] else if (isChecked) ...[
                const SizedBox(height: 4),
                Icon(Icons.check, size: 14, color: cook.cookOnCompleted),
              ],
            ],
          ),
        ),
      );
    }

    // Expanded horizontal chip
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: Container(
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
                child: Icon(Icons.check, size: 16, color: cook.cookOnCompleted),
              ),
            Text(
              '$quantity $unit $name'.trim(),
              style: TextStyle(
                fontSize: 13,
                color: isChecked ? cook.cookOnCompleted : cook.cookOnSurface,
                decoration: isChecked ? TextDecoration.lineThrough : null,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
