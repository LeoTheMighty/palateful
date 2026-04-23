/// cmm-3 — `RecipeSectionHeader` is the thin `<ComponentName> · N / M`
/// label that sits above the step card in meal cook mode. Hidden in
/// 1-component plans (recipe cook) because the app-bar recipe name +
/// progress bar already convey the same information.

library;

import 'package:flutter/material.dart';

import '../../../../../core/theme/theme.dart';

class RecipeSectionHeader extends StatelessWidget {
  final String componentName;
  final int localStep;
  final int componentTotal;

  const RecipeSectionHeader({
    super.key,
    required this.componentName,
    required this.localStep,
    required this.componentTotal,
  });

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    return Semantics(
      // cmm-3 AC1: announces "Step N of M in <ComponentName>".
      label: 'Step $localStep of $componentTotal in $componentName',
      container: true,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 8, 24, 0),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(
              componentName,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.4,
                color: cook.cookOnSurface.withValues(alpha: 0.7),
              ),
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(width: 8),
            Text(
              '·',
              style: TextStyle(
                fontSize: 13,
                color: cook.cookOnSurface.withValues(alpha: 0.5),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              '$localStep',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: cook.cookAccent,
              ),
            ),
            const SizedBox(width: 4),
            Text(
              '/',
              style: TextStyle(
                fontSize: 13,
                color: cook.cookOnSurface.withValues(alpha: 0.5),
              ),
            ),
            const SizedBox(width: 4),
            Text(
              '$componentTotal',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: cook.cookOnSurface.withValues(alpha: 0.7),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
