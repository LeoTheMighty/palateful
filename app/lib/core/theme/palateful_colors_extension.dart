import 'package:flutter/material.dart';
import 'app_colors.dart';

/// Semantic color slots that adapt to light/dark mode.
///
/// Access via `context.appColors` extension method.
class PalatefulColors extends ThemeExtension<PalatefulColors> {
  const PalatefulColors({
    // Text
    required this.textPrimary,
    required this.textSecondary,
    required this.textTertiary,
    required this.textDisabled,
    // Backgrounds
    required this.cardBackground,
    required this.inputBackground,
    required this.navBackground,
    // Semantic
    required this.success,
    required this.successLight,
    required this.warning,
    required this.warningLight,
    required this.error,
    required this.errorLight,
    required this.info,
    required this.infoLight,
    // Urgency
    required this.urgentBg,
    required this.urgentText,
    // Diff
    required this.addedBg,
    required this.removedBg,
    required this.changedBg,
  });

  // Text
  final Color textPrimary;
  final Color textSecondary;
  final Color textTertiary;
  final Color textDisabled;

  // Backgrounds
  final Color cardBackground;
  final Color inputBackground;
  final Color navBackground;

  // Semantic
  final Color success;
  final Color successLight;
  final Color warning;
  final Color warningLight;
  final Color error;
  final Color errorLight;
  final Color info;
  final Color infoLight;

  // Urgency
  final Color urgentBg;
  final Color urgentText;

  // Diff
  final Color addedBg;
  final Color removedBg;
  final Color changedBg;

  /// Light mode color set
  static const light = PalatefulColors(
    textPrimary: AppColors.textPrimary,
    textSecondary: AppColors.textSecondary,
    textTertiary: AppColors.textTertiary,
    textDisabled: AppColors.textDisabled,
    cardBackground: AppColors.creamLight,
    inputBackground: AppColors.warmWhite,
    navBackground: AppColors.warmWhite,
    success: AppColors.success,
    successLight: AppColors.successLight,
    warning: AppColors.warning,
    warningLight: AppColors.warningLight,
    error: AppColors.error,
    errorLight: AppColors.errorLight,
    info: AppColors.info,
    infoLight: AppColors.infoLight,
    urgentBg: Color(0xFFFFF3E0),
    urgentText: Color(0xFFE65100),
    addedBg: Color(0xFFE8F5E9),
    removedBg: Color(0xFFFFEBEE),
    changedBg: Color(0xFFFFF8E1),
  );

  /// Dark mode color set
  static const dark = PalatefulColors(
    textPrimary: AppColors.warmIvory,
    textSecondary: AppColors.hazelnutLight,
    textTertiary: AppColors.hazelnutLighter,
    textDisabled: AppColors.hazelnutDark,
    cardBackground: AppColors.chocolateLight,
    inputBackground: AppColors.chocolateLight,
    navBackground: AppColors.chocolateDark,
    success: AppColors.sage,
    successLight: Color(0xFF3A4A35),
    warning: AppColors.warning,
    warningLight: Color(0xFF4A3D20),
    error: AppColors.coral,
    errorLight: Color(0xFF4A2828),
    info: AppColors.info,
    infoLight: Color(0xFF2A3540),
    urgentBg: Color(0xFF4A3018),
    urgentText: Color(0xFFFFB74D),
    addedBg: Color(0xFF1B3A1B),
    removedBg: Color(0xFF3A1B1B),
    changedBg: Color(0xFF3A3518),
  );

  @override
  PalatefulColors copyWith({
    Color? textPrimary,
    Color? textSecondary,
    Color? textTertiary,
    Color? textDisabled,
    Color? cardBackground,
    Color? inputBackground,
    Color? navBackground,
    Color? success,
    Color? successLight,
    Color? warning,
    Color? warningLight,
    Color? error,
    Color? errorLight,
    Color? info,
    Color? infoLight,
    Color? urgentBg,
    Color? urgentText,
    Color? addedBg,
    Color? removedBg,
    Color? changedBg,
  }) {
    return PalatefulColors(
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      textTertiary: textTertiary ?? this.textTertiary,
      textDisabled: textDisabled ?? this.textDisabled,
      cardBackground: cardBackground ?? this.cardBackground,
      inputBackground: inputBackground ?? this.inputBackground,
      navBackground: navBackground ?? this.navBackground,
      success: success ?? this.success,
      successLight: successLight ?? this.successLight,
      warning: warning ?? this.warning,
      warningLight: warningLight ?? this.warningLight,
      error: error ?? this.error,
      errorLight: errorLight ?? this.errorLight,
      info: info ?? this.info,
      infoLight: infoLight ?? this.infoLight,
      urgentBg: urgentBg ?? this.urgentBg,
      urgentText: urgentText ?? this.urgentText,
      addedBg: addedBg ?? this.addedBg,
      removedBg: removedBg ?? this.removedBg,
      changedBg: changedBg ?? this.changedBg,
    );
  }

  @override
  PalatefulColors lerp(covariant PalatefulColors? other, double t) {
    if (other == null) return this;
    return PalatefulColors(
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      textTertiary: Color.lerp(textTertiary, other.textTertiary, t)!,
      textDisabled: Color.lerp(textDisabled, other.textDisabled, t)!,
      cardBackground: Color.lerp(cardBackground, other.cardBackground, t)!,
      inputBackground: Color.lerp(inputBackground, other.inputBackground, t)!,
      navBackground: Color.lerp(navBackground, other.navBackground, t)!,
      success: Color.lerp(success, other.success, t)!,
      successLight: Color.lerp(successLight, other.successLight, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      warningLight: Color.lerp(warningLight, other.warningLight, t)!,
      error: Color.lerp(error, other.error, t)!,
      errorLight: Color.lerp(errorLight, other.errorLight, t)!,
      info: Color.lerp(info, other.info, t)!,
      infoLight: Color.lerp(infoLight, other.infoLight, t)!,
      urgentBg: Color.lerp(urgentBg, other.urgentBg, t)!,
      urgentText: Color.lerp(urgentText, other.urgentText, t)!,
      addedBg: Color.lerp(addedBg, other.addedBg, t)!,
      removedBg: Color.lerp(removedBg, other.removedBg, t)!,
      changedBg: Color.lerp(changedBg, other.changedBg, t)!,
    );
  }
}

/// Convenience extension for accessing PalatefulColors from BuildContext.
extension PalatefulColorsExtension on BuildContext {
  PalatefulColors get appColors =>
      Theme.of(this).extension<PalatefulColors>() ?? PalatefulColors.light;
}
