import 'package:flutter/material.dart';

/// Collapsed import-row shell shared across the Imports tab and (in a
/// future epic) the rich-detail caret expansion. The row layout is:
///
/// ```
/// [source-icon] [recipe name ........................] [chip] [time] [trailing]
///               [status label — one line]
/// ```
///
/// Fixed contract:
/// - `trailing` is a `Widget?` slot so the rich-detail epic can drop in
///   a caret toggle without rewriting the signature.
/// - Tap target height ≥ 48dp via `constraints.minHeight`.
/// - The row does NOT own its tap destination — callers wire `onTap`
///   per state (blue → in-progress detail, yellow/red → review,
///   green → created recipe).
class ImportRow extends StatelessWidget {
  /// Optional unique id — used by tests and by the parent's
  /// Dismissible key. Not required for render.
  final String? id;

  /// Source-type glyph (URL / photo / PDF / etc.). Resolved by the
  /// caller from `source_type`; centralizing the mapping stays with
  /// the tab so the row widget can also render import-detail panes
  /// later without knowing anything about our source taxonomy.
  final IconData sourceIcon;

  /// Recipe name or import title. Ellipsized if it overflows.
  final String title;

  /// Optional single-line status label under the title — e.g.
  /// "Needs review", "Failed to extract", "Completed 2m ago".
  final String? statusLabel;

  /// Section color (blue / yellow / red / green) used for the chip
  /// background. Today the caller passes a raw `colorScheme.X` —
  /// ahr-6 introduces an `ImportStateColors` extension and swaps call
  /// sites. The row just uses whatever it's given.
  final Color stateColor;

  /// Short chip label printed over [stateColor]. One of "In Progress",
  /// "Needs Review", "Failed", "Auto-Imported" (or null to hide).
  final String? stateChipLabel;

  /// Formatted relative time — e.g. "2m ago", "3h ago", "4/16/2026".
  final String? timeLabel;

  /// Right-hand widget slot. For Blue rows this epic passes a small
  /// `CircularProgressIndicator`; for others a `Icons.chevron_right`.
  /// The rich-detail epic will pass a caret toggle instead.
  final Widget? trailing;

  /// Called when the row's tap area is tapped. Nullable so the row can
  /// render as non-interactive when the parent wants it (e.g. during
  /// an in-flight optimistic archive).
  final VoidCallback? onTap;

  const ImportRow({
    super.key,
    this.id,
    required this.sourceIcon,
    required this.title,
    this.statusLabel,
    required this.stateColor,
    this.stateChipLabel,
    this.timeLabel,
    this.trailing,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return InkWell(
      onTap: onTap,
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 48),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Icon(
                sourceIcon,
                size: 20,
                color: colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      title,
                      style: textTheme.bodyMedium
                          ?.copyWith(fontWeight: FontWeight.w600),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (statusLabel != null && statusLabel!.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        statusLabel!,
                        style: textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 8),
              if (stateChipLabel != null && stateChipLabel!.isNotEmpty)
                _StateChip(label: stateChipLabel!, color: stateColor),
              if (timeLabel != null && timeLabel!.isNotEmpty) ...[
                const SizedBox(width: 8),
                Text(
                  timeLabel!,
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                    fontSize: 11,
                  ),
                ),
              ],
              if (trailing != null) ...[
                const SizedBox(width: 8),
                trailing!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StateChip extends StatelessWidget {
  final String label;
  final Color color;

  const _StateChip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        label,
        style: textTheme.labelSmall?.copyWith(
          color: color,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
