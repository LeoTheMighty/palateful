import 'package:flutter/material.dart';

import '../../../core/theme/import_state_colors.dart';

/// Inline badge rendering a recipe-extraction confidence score.
///
/// Thresholds (per irrd-5 AC4):
/// - `null` score → `—` glyph + "Unavailable" tooltip
/// - `score < 0.5` → warning glyph + "Low (N%)", rendered in the
///   needsReview color token
/// - `0.5 ≤ score ≤ 0.8` → neutral glyph + "N%", muted foreground
/// - `score > 0.8` → check glyph + "N%", autoImported color token
///
/// A `source == 'heuristic'` tag adds a subtle `*est` superscript and
/// a tooltip explaining the score is estimated client-server fallback
/// rather than model-reported.
///
/// The [dense] flag renders a tighter version used inline inside a
/// collapsed row (irrd-6).
class ConfidenceBadge extends StatelessWidget {
  final double? score;
  final String? source;
  final bool dense;

  const ConfidenceBadge({
    super.key,
    required this.score,
    required this.source,
    this.dense = false,
  });

  @override
  Widget build(BuildContext context) {
    final kind = _kindFor(score);
    final colors = context.importStates;
    final cs = Theme.of(context).colorScheme;

    final fg = switch (kind) {
      _BadgeKind.low => colors.needsReview,
      _BadgeKind.medium => cs.onSurfaceVariant,
      _BadgeKind.high => colors.autoImported,
      _BadgeKind.unknown => cs.onSurfaceVariant,
    };

    final bg = fg.withValues(alpha: 0.15);
    final label = _labelFor(score, kind);
    final glyph = _glyphFor(kind, fg);
    final isHeuristic = source == 'heuristic';

    final tooltip = _tooltipFor(kind, isHeuristic);
    final semantic = _semanticFor(kind, score, source);

    return Tooltip(
      message: tooltip,
      child: Semantics(
        container: true,
        label: semantic,
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: dense ? 6 : 8,
            vertical: dense ? 2 : 4,
          ),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(dense ? 6 : 8),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              glyph,
              const SizedBox(width: 4),
              Text(
                label,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: fg,
                      fontWeight: FontWeight.w700,
                      fontSize: dense ? 11 : null,
                    ),
              ),
              if (isHeuristic) ...[
                const SizedBox(width: 2),
                Text(
                  '*est',
                  style:
                      Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: fg.withValues(alpha: 0.7),
                            fontSize: 9,
                            fontWeight: FontWeight.w500,
                          ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  static _BadgeKind _kindFor(double? score) {
    if (score == null) return _BadgeKind.unknown;
    if (score < 0.5) return _BadgeKind.low;
    if (score <= 0.8) return _BadgeKind.medium;
    return _BadgeKind.high;
  }

  static String _labelFor(double? score, _BadgeKind kind) {
    if (score == null) return 'Unavailable';
    final pct = (score * 100).round();
    switch (kind) {
      case _BadgeKind.low:
        return 'Low ($pct%)';
      case _BadgeKind.medium:
      case _BadgeKind.high:
        return '$pct%';
      case _BadgeKind.unknown:
        return 'Unavailable';
    }
  }

  static Widget _glyphFor(_BadgeKind kind, Color color) {
    final icon = switch (kind) {
      _BadgeKind.low => Icons.warning_amber_rounded,
      _BadgeKind.medium => Icons.remove_circle_outline,
      _BadgeKind.high => Icons.check_circle,
      _BadgeKind.unknown => Icons.help_outline,
    };
    return Icon(icon, size: 14, color: color);
  }

  static String _tooltipFor(_BadgeKind kind, bool heuristic) {
    final base = switch (kind) {
      _BadgeKind.low => 'Low confidence — review recommended',
      _BadgeKind.medium => 'Medium confidence',
      _BadgeKind.high => 'High confidence',
      _BadgeKind.unknown => 'Confidence score unavailable',
    };
    if (!heuristic) return base;
    return '$base · estimated (not model-reported)';
  }

  static String _semanticFor(
    _BadgeKind kind,
    double? score,
    String? source,
  ) {
    final word = switch (kind) {
      _BadgeKind.low => 'low',
      _BadgeKind.medium => 'medium',
      _BadgeKind.high => 'high',
      _BadgeKind.unknown => 'unavailable',
    };
    if (score == null) {
      return 'Confidence unavailable';
    }
    final pct = (score * 100).round();
    final src = source == null || source.isEmpty ? 'unspecified' : source;
    return 'Confidence: $word, $pct%, source $src';
  }
}

enum _BadgeKind { low, medium, high, unknown }
