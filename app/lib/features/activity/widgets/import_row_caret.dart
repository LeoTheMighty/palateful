import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/import_row_expansion_provider.dart';

/// Caret button that toggles an `ImportRow`'s `ImportRowExpansion`.
/// Reads the expanded-set via `select(...)` on the row's id so
/// toggling one row does NOT rebuild every sibling.
///
/// Renders a chevron that rotates 180° on expand. Accessibility:
/// semantic label flips between "Show details for X" / "Hide details
/// for X" with `toggled` state for screen readers.
///
/// When `showProgressRing` is true (blue / in-progress rows), the
/// caret sits atop a read-only `CircularProgressIndicator` via
/// `Stack(IgnorePointer(ring), IconButton(chevron))`. This reconciles
/// ahr-4's "blue is visually read-only" rule with irrd-4's "every row
/// has a caret" rule.
class ImportRowCaret extends ConsumerWidget {
  final String rowId;
  final String recipeName;
  final bool showProgressRing;
  final Color? progressColor;

  const ImportRowCaret({
    super.key,
    required this.rowId,
    required this.recipeName,
    this.showProgressRing = false,
    this.progressColor,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isExpanded = ref.watch(
      importRowExpansionProvider.select((s) => s.contains(rowId)),
    );

    final chevron = IconButton(
      padding: EdgeInsets.zero,
      constraints: const BoxConstraints(minWidth: 44, minHeight: 44),
      visualDensity: VisualDensity.compact,
      tooltip: isExpanded
          ? 'Hide details for $recipeName'
          : 'Show details for $recipeName',
      icon: AnimatedRotation(
        turns: isExpanded ? 0.5 : 0.0,
        duration: const Duration(milliseconds: 180),
        child: const Icon(Icons.expand_more, size: 24),
      ),
      onPressed: () =>
          ref.read(importRowExpansionProvider.notifier).toggle(rowId),
    );

    final caret = Semantics(
      button: true,
      toggled: isExpanded,
      label: isExpanded
          ? 'Hide details for $recipeName'
          : 'Show details for $recipeName',
      child: chevron,
    );

    if (!showProgressRing) return caret;

    // Blue-row variant: read-only ring below, interactive chevron above.
    return Stack(
      alignment: Alignment.center,
      children: [
        IgnorePointer(
          child: SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(
                progressColor ?? Theme.of(context).colorScheme.primary,
              ),
            ),
          ),
        ),
        caret,
      ],
    );
  }
}
