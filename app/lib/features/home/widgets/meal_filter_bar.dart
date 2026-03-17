import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';

enum MealFilter { all, breakfast, lunch, dinner, dessert, snack }

class MealFilterBar extends StatelessWidget {
  final MealFilter selected;
  final ValueChanged<MealFilter> onChanged;

  const MealFilterBar({
    super.key,
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        children: [
          _FilterChip(
            icon: Icons.restaurant_menu,
            label: 'All',
            isSelected: selected == MealFilter.all,
            onTap: () => onChanged(MealFilter.all),
          ),
          _FilterChip(
            icon: Icons.free_breakfast,
            label: 'Breakfast',
            isSelected: selected == MealFilter.breakfast,
            onTap: () => onChanged(MealFilter.breakfast),
          ),
          _FilterChip(
            icon: Icons.lunch_dining,
            label: 'Lunch',
            isSelected: selected == MealFilter.lunch,
            onTap: () => onChanged(MealFilter.lunch),
          ),
          _FilterChip(
            icon: Icons.dinner_dining,
            label: 'Dinner',
            isSelected: selected == MealFilter.dinner,
            onTap: () => onChanged(MealFilter.dinner),
          ),
          _FilterChip(
            icon: Icons.cake,
            label: 'Dessert',
            isSelected: selected == MealFilter.dessert,
            onTap: () => onChanged(MealFilter.dessert),
          ),
          _FilterChip(
            icon: Icons.cookie,
            label: 'Snack',
            isSelected: selected == MealFilter.snack,
            onTap: () => onChanged(MealFilter.snack),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _FilterChip({
    required this.icon,
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = isSelected ? AppColors.cream : AppColors.textPrimary;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Material(
        color: isSelected ? AppColors.chocolate : AppColors.beige,
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          onTap: () {
            HapticFeedback.selectionClick();
            onTap();
          },
          borderRadius: BorderRadius.circular(20),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 16, color: color),
                const SizedBox(width: 6),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: color,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
