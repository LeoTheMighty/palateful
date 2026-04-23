/// cmm-2 — placeholder rendered inside the step card when the user
/// has navigated into the flat-step range of a `loadFailed` component.
/// Offers a Retry that re-fetches the one failing recipe; on success,
/// the parent patches the plan in place and the user can keep cooking.

library;

import 'package:flutter/material.dart';

import '../../../../../core/theme/theme.dart';

class ComponentLoadPlaceholder extends StatelessWidget {
  final String componentName;
  final bool isRetrying;
  final VoidCallback onRetry;

  const ComponentLoadPlaceholder({
    super.key,
    required this.componentName,
    required this.onRetry,
    this.isRetrying = false,
  });

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    return Container(
      padding: const EdgeInsets.all(24),
      margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
      decoration: BoxDecoration(
        color: cook.cookSurfaceDim,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: cook.cookDivider),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.cloud_off_outlined,
            size: 36,
            color: cook.cookOnSurface.withValues(alpha: 0.6),
          ),
          const SizedBox(height: 12),
          Text(
            "$componentName couldn't load",
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: cook.cookOnSurface,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 4),
          Text(
            'Some steps may be unavailable for this component.',
            style: TextStyle(
              fontSize: 13,
              color: cook.cookOnSurface.withValues(alpha: 0.7),
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            key: const Key('component_load_retry'),
            onPressed: isRetrying ? null : onRetry,
            icon: isRetrying
                ? SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      color: cook.cookOnAccent,
                      strokeWidth: 2,
                    ),
                  )
                : const Icon(Icons.refresh),
            label: Text(isRetrying ? 'Retrying…' : 'Retry'),
            style: FilledButton.styleFrom(
              backgroundColor: cook.cookAccent,
              foregroundColor: cook.cookOnAccent,
            ),
          ),
        ],
      ),
    );
  }
}
