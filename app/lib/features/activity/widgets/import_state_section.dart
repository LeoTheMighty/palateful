import 'package:flutter/material.dart';

/// One of the four color-coded sections on the Imports tab. Renders a
/// colored header chip with the section name + count, then stacks its
/// child rows below. Renders nothing if [children] is empty — empty
/// sections stay hidden (epic AC4).
class ImportStateSection extends StatelessWidget {
  final String label;
  final int count;
  final Color color;
  final List<Widget> children;

  const ImportStateSection({
    super.key,
    required this.label,
    required this.count,
    required this.color,
    required this.children,
  });

  @override
  Widget build(BuildContext context) {
    if (children.isEmpty) return const SizedBox.shrink();
    final textTheme = Theme.of(context).textTheme;

    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '$label · $count',
                    style: textTheme.labelLarge?.copyWith(
                      color: color,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
          ),
          ...children,
        ],
      ),
    );
  }
}
