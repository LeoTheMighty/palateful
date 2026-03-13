import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

import '../../core/theme/app_colors.dart';

/// A generic shimmer block placeholder with configurable dimensions.
class ShimmerBlock extends StatelessWidget {
  final double width;
  final double height;
  final double borderRadius;

  const ShimmerBlock({
    super.key,
    this.width = double.infinity,
    required this.height,
    this.borderRadius = 12,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Shimmer.fromColors(
      baseColor: isDark ? AppColors.chocolateLight : AppColors.beige,
      highlightColor: isDark ? AppColors.hazelnutDark : AppColors.creamLight,
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: isDark ? AppColors.chocolateLight : AppColors.beige,
          borderRadius: BorderRadius.circular(borderRadius),
        ),
      ),
    );
  }
}

/// A shimmer placeholder for recipe cards.
class ShimmerCard extends StatelessWidget {
  const ShimmerCard({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Shimmer.fromColors(
      baseColor: isDark ? AppColors.chocolateLight : AppColors.beige,
      highlightColor: isDark ? AppColors.hazelnutDark : AppColors.creamLight,
      child: Container(
        decoration: BoxDecoration(
          color: isDark ? AppColors.chocolateLight : AppColors.beige,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image placeholder
            Expanded(
              flex: 3,
              child: Container(
                decoration: BoxDecoration(
                  color: isDark ? AppColors.chocolateLight : AppColors.beige,
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(16),
                  ),
                ),
              ),
            ),
            // Text placeholders
            Expanded(
              flex: 2,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: double.infinity,
                      height: 14,
                      decoration: BoxDecoration(
                        color: isDark ? AppColors.chocolateLight : AppColors.beige,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      width: 80,
                      height: 10,
                      decoration: BoxDecoration(
                        color: isDark ? AppColors.chocolateLight : AppColors.beige,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A shimmer placeholder for a list of items.
class ShimmerList extends StatelessWidget {
  final int itemCount;
  final double itemHeight;
  final double spacing;

  const ShimmerList({
    super.key,
    this.itemCount = 5,
    this.itemHeight = 72,
    this.spacing = 12,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Shimmer.fromColors(
      baseColor: isDark ? AppColors.chocolateLight : AppColors.beige,
      highlightColor: isDark ? AppColors.hazelnutDark : AppColors.creamLight,
      child: Column(
        children: List.generate(itemCount, (index) {
          return Padding(
            padding: EdgeInsets.only(bottom: index < itemCount - 1 ? spacing : 0),
            child: SizedBox(
              height: itemHeight,
              child: Row(
              children: [
                // Leading circle
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: isDark ? AppColors.chocolateLight : AppColors.beige,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 12),
                // Text lines
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: double.infinity,
                        height: 14,
                        decoration: BoxDecoration(
                          color: isDark ? AppColors.chocolateLight : AppColors.beige,
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Container(
                        width: 120,
                        height: 10,
                        decoration: BoxDecoration(
                          color: isDark ? AppColors.chocolateLight : AppColors.beige,
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            ),
          );
        }),
      ),
    );
  }
}
