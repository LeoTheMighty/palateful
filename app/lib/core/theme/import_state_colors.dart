import 'package:flutter/material.dart';
import 'app_colors.dart';

/// Semantic color tokens for the four import pipeline states.
///
/// Token names are **locked** per epic ahr-6 contract:
/// `inProgress` / `needsReview` / `failed` / `autoImported`. No
/// renames, no new variants (dismissed / archived are states, not
/// colors).
///
/// Usage:
/// ```dart
/// final states = Theme.of(context).extension<ImportStateColors>();
/// final blue = states?.inProgress ?? colorScheme.primary;
/// ```
/// or via the context helper:
/// ```dart
/// final blue = context.importStates.inProgress;
/// ```
///
/// The extension is a plain data bag: colors only, no tint. Widgets
/// that want a chip background apply `withValues(alpha: 0.15)` at the
/// call site (matching the pattern shipped in ahr-4).
class ImportStateColors extends ThemeExtension<ImportStateColors> {
  const ImportStateColors({
    required this.inProgress,
    required this.needsReview,
    required this.failed,
    required this.autoImported,
  });

  final Color inProgress;
  final Color needsReview;
  final Color failed;
  final Color autoImported;

  /// Light mode tokens — maps to the same `colorScheme` slots ahr-4
  /// hardcoded, just routed through a named extension now.
  static const light = ImportStateColors(
    inProgress: AppColors.chocolate,
    needsReview: AppColors.terracotta,
    failed: AppColors.error,
    autoImported: AppColors.hazelnut,
  );

  /// Dark mode tokens.
  static const dark = ImportStateColors(
    inProgress: AppColors.terracotta,
    needsReview: AppColors.terracotta,
    failed: AppColors.coral,
    autoImported: AppColors.hazelnutLight,
  );

  @override
  ImportStateColors copyWith({
    Color? inProgress,
    Color? needsReview,
    Color? failed,
    Color? autoImported,
  }) {
    return ImportStateColors(
      inProgress: inProgress ?? this.inProgress,
      needsReview: needsReview ?? this.needsReview,
      failed: failed ?? this.failed,
      autoImported: autoImported ?? this.autoImported,
    );
  }

  @override
  ImportStateColors lerp(covariant ImportStateColors? other, double t) {
    if (other == null) return this;
    return ImportStateColors(
      inProgress: Color.lerp(inProgress, other.inProgress, t)!,
      needsReview: Color.lerp(needsReview, other.needsReview, t)!,
      failed: Color.lerp(failed, other.failed, t)!,
      autoImported: Color.lerp(autoImported, other.autoImported, t)!,
    );
  }
}

/// Convenience context getter — falls back to [ImportStateColors.light]
/// when a widget is pumped in tests without the extension registered.
/// Production theme always carries the extension via [AppTheme].
extension ImportStateColorsContext on BuildContext {
  ImportStateColors get importStates =>
      Theme.of(this).extension<ImportStateColors>() ??
      ImportStateColors.light;
}
