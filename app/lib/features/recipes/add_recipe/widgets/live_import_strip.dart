import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/import_batches_provider.dart';

/// Slim ambient indicator for active imports, shown on the Add Recipe sheet.
/// When no imports are active, the strip renders nothing — no empty state.
/// Taps through to `/activity?filter=imports` so the Activity Hub owns the
/// full pipeline-state UI (bugs-act-3).
class LiveImportStrip extends ConsumerWidget {
  const LiveImportStrip({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final batches = ref.watch(importBatchesProvider);

    final activeCount = batches.when(
      data: (s) => s.active.length,
      loading: () => 0,
      error: (_, _) => 0,
    );

    if (activeCount == 0) return const SizedBox.shrink();

    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final label = activeCount == 1
        ? '1 import in progress'
        : '$activeCount imports in progress';

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () {
          // Close the Add Recipe sheet, then route to the Activity Hub's
          // imports filter. The hub owns the full list + actions.
          Navigator.of(context).maybePop();
          context.push('/activity?filter=imports');
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: colorScheme.outlineVariant.withValues(alpha: 0.5),
            ),
          ),
          child: Row(
            children: [
              SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor:
                      AlwaysStoppedAnimation<Color>(colorScheme.primary),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  label,
                  style: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurface,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              Icon(
                Icons.chevron_right,
                size: 20,
                color: colorScheme.primary,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
