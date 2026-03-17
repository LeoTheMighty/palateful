import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../core/theme/app_colors.dart';

class IngredientStrip extends StatefulWidget {
  final List<dynamic> ingredients;
  final Set<int> checkedIndices;
  final ValueChanged<int> onToggle;

  const IngredientStrip({
    super.key,
    required this.ingredients,
    required this.checkedIndices,
    required this.onToggle,
  });

  @override
  State<IngredientStrip> createState() => _IngredientStripState();
}

class _IngredientStripState extends State<IngredientStrip> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
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
                const Text(
                  'INGREDIENTS',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 1,
                    color: AppColors.textTertiary,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '${widget.checkedIndices.length}/${widget.ingredients.length}',
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppColors.textTertiary,
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
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppColors.hazelnut,
                          ),
                        ),
                        Icon(
                          _isExpanded ? Icons.expand_less : Icons.expand_more,
                          size: 18,
                          color: AppColors.hazelnut,
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
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: _IngredientChip(
              ingredient: widget.ingredients[index],
              isChecked: widget.checkedIndices.contains(index),
              onTap: () => widget.onToggle(index),
              isCompact: true,
            ),
          );
        },
      ),
    );
  }

  Widget _buildExpandedGrid() {
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
          );
        }).toList(),
      ),
    );
  }
}

class _IngredientChip extends StatelessWidget {
  final dynamic ingredient;
  final bool isChecked;
  final VoidCallback onTap;
  final bool isCompact;

  const _IngredientChip({
    required this.ingredient,
    required this.isChecked,
    required this.onTap,
    required this.isCompact,
  });

  @override
  Widget build(BuildContext context) {
    final name = ingredient['ingredient']?['canonical_name'] ?? 'Unknown';
    final quantity = ingredient['quantity_display'] ?? '';
    final unit = ingredient['unit_display'] ?? '';

    if (isCompact) {
      // Compact vertical chip for horizontal scroll
      return GestureDetector(
        onTap: () {
          HapticFeedback.selectionClick();
          onTap();
        },
        child: Container(
          width: 64,
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: isChecked ? AppColors.sage : AppColors.beige,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isChecked ? AppColors.sage : AppColors.beigeAccent,
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
                  color: isChecked ? AppColors.cream : AppColors.textPrimary,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              // Name
              Text(
                name,
                style: TextStyle(
                  fontSize: 10,
                  color: isChecked ? AppColors.cream : AppColors.textSecondary,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
              ),
              if (isChecked) ...[
                const SizedBox(height: 4),
                const Icon(Icons.check, size: 14, color: AppColors.cream),
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
          color: isChecked ? AppColors.sage : AppColors.beige,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isChecked)
              const Padding(
                padding: EdgeInsets.only(right: 6),
                child: Icon(Icons.check, size: 16, color: AppColors.cream),
              ),
            Text(
              '$quantity $unit $name'.trim(),
              style: TextStyle(
                fontSize: 13,
                color: isChecked ? AppColors.cream : AppColors.textPrimary,
                decoration: isChecked ? TextDecoration.lineThrough : null,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
