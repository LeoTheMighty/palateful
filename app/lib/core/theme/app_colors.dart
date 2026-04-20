import 'package:flutter/material.dart';

/// Palateful Color Scheme Configuration
///
/// Adjust these values to change the entire app's color scheme.
/// The design uses a warm cream/beige primary palette with
/// rich chocolate/hazelnut accents.
class AppColors {
  AppColors._();

  // ============================================
  // PRIMARY PALETTE - Cream & Beige
  // ============================================

  /// Main background - warm cream white
  static const Color cream = Color(0xFFFAF7F2);

  /// Slightly darker cream for cards/surfaces
  static const Color creamLight = Color(0xFFFFFDF9);

  /// Warm beige for subtle backgrounds
  static const Color beige = Color(0xFFF5EFE6);

  /// Darker beige for borders and dividers
  static const Color beigeAccent = Color(0xFFE8DFD0);

  /// Warm off-white for elevated surfaces
  static const Color warmWhite = Color(0xFFFEFCF9);

  /// Warm ivory for dark mode primary text
  static const Color warmIvory = Color(0xFFF5ECD7);

  // ============================================
  // SECONDARY PALETTE - Chocolate & Hazelnut
  // ============================================

  /// Primary accent - rich dark chocolate
  static const Color chocolate = Color(0xFF4A3728);

  /// Lighter chocolate for hover states
  static const Color chocolateLight = Color(0xFF5D4A3A);

  /// Darker chocolate for pressed states
  static const Color chocolateDark = Color(0xFF3A2A1E);

  /// Warm hazelnut brown - secondary accent
  static const Color hazelnut = Color(0xFF8B7355);

  /// Light hazelnut for subtle accents
  static const Color hazelnutLight = Color(0xFFA89076);

  /// Lighter hazelnut for improved contrast on dark backgrounds
  static const Color hazelnutLighter = Color(0xFFC8B89A);

  /// Dark hazelnut for text on light backgrounds
  static const Color hazelnutDark = Color(0xFF6B5642);

  // ============================================
  // ACCENT COLORS
  // ============================================

  /// Warm terracotta for highlights
  static const Color terracotta = Color(0xFFBE8A60);

  /// Darker terracotta for text on light backgrounds
  static const Color terracottaDark = Color(0xFF9A6C42);

  /// Soft sage green for success states
  static const Color sage = Color(0xFF8FA882);

  /// Muted coral for warnings
  static const Color coral = Color(0xFFCB8B73);

  /// Dusty rose for errors (softer than pure red)
  static const Color dustyRose = Color(0xFFB86B6B);

  /// Favorite/heart red
  static const Color favorite = Color(0xFFE53935);

  // ============================================
  // NEUTRAL PALETTE
  // ============================================

  /// Primary text color - warm dark brown
  static const Color textPrimary = Color(0xFF2D2420);

  /// Secondary text - medium brown
  static const Color textSecondary = Color(0xFF6B5D54);

  /// Tertiary/hint text - darker brown for AA contrast on cream
  static const Color textTertiary = Color(0xFF7A6E64);

  /// Disabled text
  static const Color textDisabled = Color(0xFFBEB5AC);

  /// Divider color
  static const Color divider = Color(0xFFE5DED5);

  /// Border color
  static const Color border = Color(0xFFD9D0C5);

  /// Shadow color
  static const Color shadow = Color(0x1A4A3728);

  // ============================================
  // SEMANTIC COLORS
  // ============================================

  /// Success - warm sage green
  static const Color success = sage;
  static const Color successLight = Color(0xFFEDF4EB);
  static const Color successDark = Color(0xFF4F6E42);

  /// Warning - warm amber
  static const Color warning = Color(0xFFD4A853);
  static const Color warningLight = Color(0xFFFDF6E7);
  static const Color warningDark = Color(0xFF8A6F2E);

  /// Error - dusty rose
  static const Color error = dustyRose;
  static const Color errorLight = Color(0xFFF9EEEE);
  static const Color errorDark = Color(0xFF944D4D);

  /// Info - muted blue-grey
  static const Color info = Color(0xFF7A8B9A);
  static const Color infoLight = Color(0xFFEEF2F5);
  static const Color infoDark = Color(0xFF4A5B6A);

  // ============================================
  // COMPONENT-SPECIFIC COLORS
  // ============================================

  /// Button primary background
  static const Color buttonPrimary = chocolate;
  static const Color buttonPrimaryHover = chocolateLight;
  static const Color buttonPrimaryPressed = chocolateDark;

  /// Button secondary (outline style)
  static const Color buttonSecondary = hazelnut;
  static const Color buttonSecondaryHover = hazelnutLight;
  static const Color buttonSecondaryPressed = hazelnutDark;

  /// Input field colors
  static const Color inputBackground = warmWhite;
  static const Color inputBorder = border;
  static const Color inputBorderFocused = hazelnut;
  static const Color inputPlaceholder = textTertiary;

  /// Card colors
  static const Color cardBackground = creamLight;
  static const Color cardBorder = beigeAccent;

  /// App bar colors
  static const Color appBarBackground = cream;
  static const Color appBarForeground = textPrimary;

  /// Bottom navigation
  static const Color navBackground = warmWhite;
  static const Color navActive = chocolate;
  static const Color navInactive = textTertiary;

  // ============================================
  // HELPER METHODS
  // ============================================

  /// Get color with opacity
  static Color withOpacity(Color color, double opacity) {
    return color.withValues(alpha: opacity);
  }

  /// Shared "muted on surface" token — `onSurface` at 0.65 alpha. Used by
  /// See-all history surfaces, "read-and-old" rows, and any muted-text
  /// element in the Activity Hub. Centralised so every consumer reads the
  /// same alpha and a single tweak updates the whole hub.
  static Color mutedOnSurface(ColorScheme scheme) =>
      scheme.onSurface.withValues(alpha: 0.65);

  /// Lighten a color by a percentage (0.0 - 1.0)
  static Color lighten(Color color, double amount) {
    final hsl = HSLColor.fromColor(color);
    return hsl
        .withLightness((hsl.lightness + amount).clamp(0.0, 1.0))
        .toColor();
  }

  /// Darken a color by a percentage (0.0 - 1.0)
  static Color darken(Color color, double amount) {
    final hsl = HSLColor.fromColor(color);
    return hsl
        .withLightness((hsl.lightness - amount).clamp(0.0, 1.0))
        .toColor();
  }
}
