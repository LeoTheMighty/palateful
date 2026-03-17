import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';

enum SortOption { best, newest, popular, quickest, random }

class SortChips extends StatelessWidget {
  final SortOption selected;
  final ValueChanged<SortOption> onChanged;
  final int recipeCount;

  const SortChips({
    super.key,
    required this.selected,
    required this.onChanged,
    required this.recipeCount,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
      child: Row(
        children: [
          _SortIcon(
            icon: Icons.star_rounded,
            tooltip: 'Best',
            isSelected: selected == SortOption.best,
            onTap: () => onChanged(SortOption.best),
          ),
          _SortIcon(
            icon: Icons.fiber_new_rounded,
            tooltip: 'Newest',
            isSelected: selected == SortOption.newest,
            onTap: () => onChanged(SortOption.newest),
          ),
          _SortIcon(
            icon: Icons.local_fire_department_rounded,
            tooltip: 'Popular',
            isSelected: selected == SortOption.popular,
            onTap: () => onChanged(SortOption.popular),
          ),
          _SortIcon(
            icon: Icons.schedule_rounded,
            tooltip: 'Quickest',
            isSelected: selected == SortOption.quickest,
            onTap: () => onChanged(SortOption.quickest),
          ),
          _SortIcon(
            icon: Icons.shuffle_rounded,
            tooltip: 'Random',
            isSelected: selected == SortOption.random,
            onTap: () => onChanged(SortOption.random),
          ),
          const Spacer(),
          Text(
            '$recipeCount recipes',
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }
}

class _SortIcon extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final bool isSelected;
  final VoidCallback onTap;

  const _SortIcon({
    required this.icon,
    required this.tooltip,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 4),
      child: Tooltip(
        message: tooltip,
        child: Material(
          color: isSelected
              ? AppColors.withOpacity(AppColors.chocolate, 0.12)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          child: InkWell(
            onTap: () {
              HapticFeedback.selectionClick();
              onTap();
            },
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Icon(
                icon,
                size: 20,
                color: isSelected ? AppColors.chocolate : AppColors.textTertiary,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
