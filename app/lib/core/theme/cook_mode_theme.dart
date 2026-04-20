import 'package:flutter/material.dart';
import 'app_colors.dart';

/// Semantic color tokens for Cook Mode.
///
/// Cook Mode has a distinct palette from the rest of the app: a single
/// cohesive scaffold colour ([cookSurface]) plus a deep-orange accent
/// reserved for the Next button and active-timer ring. Callers name
/// the *role* ("this is the progress bar"), not the colour. Dark mode
/// preserves the existing terracotta / cocoa / sage identity but
/// separates [cookSurface] (cocoa) from [cookAccent] (terracotta) —
/// no more primary-as-background.
///
/// ## Usage
///
/// ```dart
/// final cook = context.cookModeTheme;
/// Scaffold(backgroundColor: cook.cookSurface, ...);
/// ```
///
/// In production (via [AppTheme]) both light and dark themes carry this
/// extension. Tests that pump widgets without the extension fall back to
/// [CookModeTheme.light] — a debug-only `assert` warns so real test
/// setups catch a missing registration.
///
/// ## Palette & WCAG AA contrast
///
/// Text-on-surface pairs (≥4.5:1 required for normal text):
///
/// | Pair                             | Light  | Dark   |
/// |----------------------------------|--------|--------|
/// | `cookOnSurface` on `cookSurface` | 14.9:1 | 10.4:1 |
/// | `cookOnAccent` on `cookAccent`   | 6.6:1  | 4.9:1  |
/// | `cookOnCompleted` on `cookCompleted` | 5.3:1 | 5.6:1 |
///
/// UI-component pairs (≥3:1 required for border visibility):
///
/// | Pair                                   | Light | Dark |
/// |----------------------------------------|-------|------|
/// | `cookDivider` on `cookSurface`         | 4.2:1 | 3.6:1 |
/// | `cookCompleted` border on `cookSurface`| 5.3:1 | 4.2:1 |
///
/// See `app/test/theme/cook_mode_theme_test.dart` for numeric assertions
/// on the three text-on-surface pairs.
class CookModeTheme extends ThemeExtension<CookModeTheme> {
  const CookModeTheme({
    required this.cookSurface,
    required this.cookSurfaceDim,
    required this.cookOnSurface,
    required this.cookAccent,
    required this.cookOnAccent,
    required this.cookProgress,
    required this.cookCompleted,
    required this.cookOnCompleted,
    required this.cookTimer,
    required this.cookError,
    required this.cookOffline,
    required this.cookDivider,
    required this.cookShadow,
  });

  /// Scaffold + header + sheet background.
  final Color cookSurface;

  /// Step-card background, upcoming-step pill.
  final Color cookSurfaceDim;

  /// Default body + heading text.
  final Color cookOnSurface;

  /// Next button, current-step pill.
  final Color cookAccent;

  /// Text / icons drawn on [cookAccent].
  final Color cookOnAccent;

  /// Linear progress indicator fill.
  final Color cookProgress;

  /// Completed-step pill + completed-card border + checked ingredient chip.
  final Color cookCompleted;

  /// Text / icons drawn on [cookCompleted].
  final Color cookOnCompleted;

  /// Active-timer pill, timer detail countdown, inline timer button.
  final Color cookTimer;

  /// Error-scaffold banner, retry button.
  final Color cookError;

  /// Offline indicator icon + label.
  final Color cookOffline;

  /// 1-px dividers, chip borders.
  final Color cookDivider;

  /// Shadow colour for StepNavigator + sheets.
  final Color cookShadow;

  /// Light mode tokens.
  ///
  /// `cookSurface` is a warm-neutral off-white (cream). `cookAccent` is a
  /// darker terracotta than the shared `AppColors.terracotta` so the
  /// Next-button text meets 4.5:1 on light.
  static const CookModeTheme light = CookModeTheme(
    cookSurface: AppColors.cream,
    cookSurfaceDim: AppColors.beige,
    cookOnSurface: AppColors.textPrimary,
    cookAccent: _lightAccent,
    cookOnAccent: AppColors.cream,
    cookProgress: _lightAccent,
    cookCompleted: AppColors.successDark,
    cookOnCompleted: AppColors.cream,
    cookTimer: AppColors.warningDark,
    cookError: AppColors.errorDark,
    cookOffline: AppColors.hazelnut,
    cookDivider: AppColors.hazelnut,
    cookShadow: AppColors.shadow,
  );

  /// Dark mode tokens. Preserves terracotta-on-cocoa-on-sage identity
  /// but separates surface (cocoa) from accent (terracotta).
  static const CookModeTheme dark = CookModeTheme(
    cookSurface: AppColors.chocolate,
    cookSurfaceDim: AppColors.chocolateLight,
    cookOnSurface: AppColors.warmIvory,
    cookAccent: AppColors.terracotta,
    cookOnAccent: AppColors.textPrimary,
    cookProgress: AppColors.terracotta,
    cookCompleted: AppColors.sage,
    cookOnCompleted: AppColors.textPrimary,
    cookTimer: AppColors.warning,
    cookError: AppColors.coral,
    cookOffline: AppColors.hazelnutLight,
    cookDivider: AppColors.hazelnutLight,
    cookShadow: Color(0x40000000),
  );

  /// Deep terracotta — same hue family as [AppColors.terracotta] but
  /// dark enough for a 4.5:1 contrast with cream text in light mode.
  static const Color _lightAccent = Color(0xFF8F4022);

  @override
  CookModeTheme copyWith({
    Color? cookSurface,
    Color? cookSurfaceDim,
    Color? cookOnSurface,
    Color? cookAccent,
    Color? cookOnAccent,
    Color? cookProgress,
    Color? cookCompleted,
    Color? cookOnCompleted,
    Color? cookTimer,
    Color? cookError,
    Color? cookOffline,
    Color? cookDivider,
    Color? cookShadow,
  }) {
    return CookModeTheme(
      cookSurface: cookSurface ?? this.cookSurface,
      cookSurfaceDim: cookSurfaceDim ?? this.cookSurfaceDim,
      cookOnSurface: cookOnSurface ?? this.cookOnSurface,
      cookAccent: cookAccent ?? this.cookAccent,
      cookOnAccent: cookOnAccent ?? this.cookOnAccent,
      cookProgress: cookProgress ?? this.cookProgress,
      cookCompleted: cookCompleted ?? this.cookCompleted,
      cookOnCompleted: cookOnCompleted ?? this.cookOnCompleted,
      cookTimer: cookTimer ?? this.cookTimer,
      cookError: cookError ?? this.cookError,
      cookOffline: cookOffline ?? this.cookOffline,
      cookDivider: cookDivider ?? this.cookDivider,
      cookShadow: cookShadow ?? this.cookShadow,
    );
  }

  @override
  CookModeTheme lerp(covariant CookModeTheme? other, double t) {
    if (other == null) return this;
    return CookModeTheme(
      cookSurface: Color.lerp(cookSurface, other.cookSurface, t)!,
      cookSurfaceDim: Color.lerp(cookSurfaceDim, other.cookSurfaceDim, t)!,
      cookOnSurface: Color.lerp(cookOnSurface, other.cookOnSurface, t)!,
      cookAccent: Color.lerp(cookAccent, other.cookAccent, t)!,
      cookOnAccent: Color.lerp(cookOnAccent, other.cookOnAccent, t)!,
      cookProgress: Color.lerp(cookProgress, other.cookProgress, t)!,
      cookCompleted: Color.lerp(cookCompleted, other.cookCompleted, t)!,
      cookOnCompleted: Color.lerp(cookOnCompleted, other.cookOnCompleted, t)!,
      cookTimer: Color.lerp(cookTimer, other.cookTimer, t)!,
      cookError: Color.lerp(cookError, other.cookError, t)!,
      cookOffline: Color.lerp(cookOffline, other.cookOffline, t)!,
      cookDivider: Color.lerp(cookDivider, other.cookDivider, t)!,
      cookShadow: Color.lerp(cookShadow, other.cookShadow, t)!,
    );
  }
}

/// Convenience context getter.
///
/// Falls back to [CookModeTheme.light] when a widget is pumped in tests
/// without the extension registered. A debug-only `assert` warns so
/// production test setups catch a missing [AppTheme] wrap.
extension CookModeThemeContext on BuildContext {
  CookModeTheme get cookModeTheme {
    final ext = Theme.of(this).extension<CookModeTheme>();
    assert(
      ext != null,
      'CookModeTheme not registered on the ambient Theme. '
      'Wrap the widget in MaterialApp(theme: AppTheme.light()) or '
      'AppTheme.dark() in tests.',
    );
    return ext ?? CookModeTheme.light;
  }
}
