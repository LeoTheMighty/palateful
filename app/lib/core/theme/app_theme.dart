import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';
import 'palateful_colors_extension.dart';

/// Application Theme Configuration
///
/// Provides a cohesive Material 3 theme with the Palateful
/// cream and chocolate color scheme.
class AppTheme {
  AppTheme._();

  /// Light theme (primary theme)
  static ThemeData get light {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,

      // Color scheme
      colorScheme: const ColorScheme.light(
        primary: AppColors.chocolate,
        onPrimary: Color(0xFFFFFFFF),
        primaryContainer: AppColors.chocolateLight,
        onPrimaryContainer: AppColors.cream,
        secondary: AppColors.hazelnut,
        onSecondary: Color(0xFFFFFFFF),
        secondaryContainer: AppColors.hazelnutLight,
        onSecondaryContainer: AppColors.textPrimary,
        tertiary: AppColors.terracotta,
        onTertiary: AppColors.cream,
        surface: AppColors.cream,
        onSurface: AppColors.textPrimary,
        surfaceContainerHighest: AppColors.beige,
        error: AppColors.error,
        onError: Color(0xFFFFFFFF),
        outline: AppColors.border,
        outlineVariant: AppColors.divider,
        shadow: AppColors.shadow,
      ),

      // Scaffold
      scaffoldBackgroundColor: AppColors.cream,

      // AppBar
      appBarTheme: const AppBarTheme(
        centerTitle: true,
        elevation: 0,
        scrolledUnderElevation: 1,
        backgroundColor: AppColors.appBarBackground,
        foregroundColor: AppColors.appBarForeground,
        surfaceTintColor: Colors.transparent,
        systemOverlayStyle: SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.dark,
          statusBarBrightness: Brightness.light,
        ),
        titleTextStyle: TextStyle(
          fontFamily: 'System',
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: AppColors.textPrimary,
          letterSpacing: -0.3,
        ),
        iconTheme: IconThemeData(
          color: AppColors.textPrimary,
          size: 24,
        ),
      ),

      // Cards
      cardTheme: CardThemeData(
        elevation: 0,
        color: AppColors.cardBackground,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(
            color: AppColors.cardBorder,
            width: 1,
          ),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),

      // Elevated Button (Primary)
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ButtonStyle(
          elevation: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.pressed)) return 0;
            if (states.contains(WidgetState.hovered)) return 2;
            return 1;
          }),
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return AppColors.textDisabled;
            }
            if (states.contains(WidgetState.pressed)) {
              return AppColors.buttonPrimaryPressed;
            }
            if (states.contains(WidgetState.hovered)) {
              return AppColors.buttonPrimaryHover;
            }
            return AppColors.buttonPrimary;
          }),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return AppColors.textDisabled;
            }
            return AppColors.cream;
          }),
          overlayColor: WidgetStateProperty.all(
            AppColors.withOpacity(AppColors.cream, 0.1),
          ),
          shadowColor: WidgetStateProperty.all(AppColors.shadow),
          surfaceTintColor: WidgetStateProperty.all(Colors.transparent),
          padding: WidgetStateProperty.all(
            const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          ),
          minimumSize: WidgetStateProperty.all(const Size(88, 48)),
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          textStyle: WidgetStateProperty.all(
            const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.2,
            ),
          ),
          animationDuration: const Duration(milliseconds: 200),
        ),
      ),

      // Outlined Button (Secondary)
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.pressed)) {
              return AppColors.withOpacity(AppColors.hazelnut, 0.1);
            }
            if (states.contains(WidgetState.hovered)) {
              return AppColors.withOpacity(AppColors.hazelnut, 0.05);
            }
            return Colors.transparent;
          }),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return AppColors.textDisabled;
            }
            return AppColors.hazelnut;
          }),
          overlayColor: WidgetStateProperty.all(
            AppColors.withOpacity(AppColors.hazelnut, 0.1),
          ),
          side: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return const BorderSide(color: AppColors.textDisabled, width: 1.5);
            }
            if (states.contains(WidgetState.pressed)) {
              return const BorderSide(
                  color: AppColors.buttonSecondaryPressed, width: 1.5);
            }
            return const BorderSide(color: AppColors.hazelnut, width: 1.5);
          }),
          padding: WidgetStateProperty.all(
            const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          ),
          minimumSize: WidgetStateProperty.all(const Size(88, 48)),
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          textStyle: WidgetStateProperty.all(
            const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.2,
            ),
          ),
          animationDuration: const Duration(milliseconds: 200),
        ),
      ),

      // Text Button (Tertiary)
      textButtonTheme: TextButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.pressed)) {
              return AppColors.withOpacity(AppColors.chocolate, 0.08);
            }
            if (states.contains(WidgetState.hovered)) {
              return AppColors.withOpacity(AppColors.chocolate, 0.04);
            }
            return Colors.transparent;
          }),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return AppColors.textDisabled;
            }
            return AppColors.chocolate;
          }),
          overlayColor: WidgetStateProperty.all(
            AppColors.withOpacity(AppColors.chocolate, 0.08),
          ),
          padding: WidgetStateProperty.all(
            const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          ),
          minimumSize: WidgetStateProperty.all(const Size(64, 44)),
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
          ),
          textStyle: WidgetStateProperty.all(
            const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.1,
            ),
          ),
          animationDuration: const Duration(milliseconds: 200),
        ),
      ),

      // Floating Action Button
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: AppColors.chocolate,
        foregroundColor: AppColors.cream,
        elevation: 3,
        focusElevation: 4,
        hoverElevation: 4,
        highlightElevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(16)),
        ),
      ),

      // Icon Button
      iconButtonTheme: IconButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.pressed)) {
              return AppColors.withOpacity(AppColors.chocolate, 0.12);
            }
            if (states.contains(WidgetState.hovered)) {
              return AppColors.withOpacity(AppColors.chocolate, 0.06);
            }
            return Colors.transparent;
          }),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return AppColors.textDisabled;
            }
            return AppColors.textPrimary;
          }),
          overlayColor: WidgetStateProperty.all(
            AppColors.withOpacity(AppColors.chocolate, 0.1),
          ),
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          animationDuration: const Duration(milliseconds: 150),
        ),
      ),

      // Input Decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.inputBackground,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.inputBorder, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.inputBorder, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:
              const BorderSide(color: AppColors.inputBorderFocused, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.error, width: 1),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.error, width: 2),
        ),
        disabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.divider, width: 1),
        ),
        hintStyle: const TextStyle(
          color: AppColors.inputPlaceholder,
          fontSize: 16,
          fontWeight: FontWeight.w400,
        ),
        labelStyle: const TextStyle(
          color: AppColors.textSecondary,
          fontSize: 16,
          fontWeight: FontWeight.w500,
        ),
        floatingLabelStyle: const TextStyle(
          color: AppColors.hazelnut,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        errorStyle: const TextStyle(
          color: AppColors.error,
          fontSize: 12,
          fontWeight: FontWeight.w400,
        ),
        prefixIconColor: AppColors.textTertiary,
        suffixIconColor: AppColors.textTertiary,
      ),

      // Chip
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.beige,
        selectedColor: AppColors.chocolate,
        disabledColor: AppColors.divider,
        labelStyle: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        secondaryLabelStyle: const TextStyle(
          color: AppColors.cream,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        side: BorderSide.none,
      ),

      // List Tile
      listTileTheme: const ListTileThemeData(
        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        titleTextStyle: TextStyle(
          color: AppColors.textPrimary,
          fontSize: 16,
          fontWeight: FontWeight.w500,
        ),
        subtitleTextStyle: TextStyle(
          color: AppColors.textSecondary,
          fontSize: 14,
          fontWeight: FontWeight.w400,
        ),
        leadingAndTrailingTextStyle: TextStyle(
          color: AppColors.textTertiary,
          fontSize: 14,
        ),
        iconColor: AppColors.hazelnut,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
        ),
      ),

      // Divider
      dividerTheme: const DividerThemeData(
        color: AppColors.divider,
        thickness: 1,
        space: 1,
      ),

      // Dialog
      dialogTheme: DialogThemeData(
        backgroundColor: AppColors.warmWhite,
        surfaceTintColor: Colors.transparent,
        elevation: 8,
        shadowColor: AppColors.shadow,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        titleTextStyle: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.3,
        ),
        contentTextStyle: const TextStyle(
          color: AppColors.textSecondary,
          fontSize: 16,
          fontWeight: FontWeight.w400,
          height: 1.5,
        ),
      ),

      // Bottom Sheet
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.warmWhite,
        surfaceTintColor: Colors.transparent,
        elevation: 8,
        shadowColor: AppColors.shadow,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        dragHandleColor: AppColors.beigeAccent,
        dragHandleSize: Size(40, 4),
        showDragHandle: true,
      ),

      // Snackbar
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.chocolate,
        contentTextStyle: const TextStyle(
          color: AppColors.cream,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        actionTextColor: AppColors.terracotta,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        elevation: 4,
      ),

      // Progress Indicator
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.chocolate,
        linearTrackColor: AppColors.beige,
        circularTrackColor: AppColors.beige,
      ),

      // Switch
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.chocolate;
          }
          return AppColors.beigeAccent;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.withOpacity(AppColors.chocolate, 0.5);
          }
          return AppColors.divider;
        }),
        trackOutlineColor: WidgetStateProperty.all(Colors.transparent),
      ),

      // Checkbox
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.chocolate;
          }
          return Colors.transparent;
        }),
        checkColor: WidgetStateProperty.all(AppColors.cream),
        side: const BorderSide(color: AppColors.border, width: 2),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
        ),
      ),

      // Radio
      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.chocolate;
          }
          return AppColors.border;
        }),
      ),

      // Navigation Bar (Bottom)
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.navBackground,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        indicatorColor: AppColors.withOpacity(AppColors.chocolate, 0.1),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(
              color: AppColors.navActive,
              size: 24,
            );
          }
          return const IconThemeData(
            color: AppColors.navInactive,
            size: 24,
          );
        }),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              color: AppColors.navActive,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            );
          }
          return const TextStyle(
            color: AppColors.navInactive,
            fontSize: 12,
            fontWeight: FontWeight.w500,
          );
        }),
      ),

      // Tab Bar
      tabBarTheme: TabBarThemeData(
        labelColor: AppColors.chocolate,
        unselectedLabelColor: AppColors.textTertiary,
        indicatorColor: AppColors.chocolate,
        indicatorSize: TabBarIndicatorSize.label,
        dividerColor: AppColors.divider,
        labelStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
      ),

      // Extensions
      extensions: const <ThemeExtension>[
        PalatefulColors.light,
      ],

      // Text Theme - Playfair Display for display/headline/title, system sans-serif for body/label
      textTheme: TextTheme(
        displayLarge: GoogleFonts.playfairDisplay(
          color: AppColors.textPrimary,
          fontSize: 36,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.25,
        ),
        displayMedium: GoogleFonts.playfairDisplay(
          color: AppColors.textPrimary,
          fontSize: 28,
          fontWeight: FontWeight.w700,
        ),
        displaySmall: GoogleFonts.playfairDisplay(
          color: AppColors.textPrimary,
          fontSize: 24,
          fontWeight: FontWeight.w600,
        ),
        headlineLarge: GoogleFonts.playfairDisplay(
          color: AppColors.textPrimary,
          fontSize: 32,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
        ),
        headlineMedium: GoogleFonts.playfairDisplay(
          color: AppColors.textPrimary,
          fontSize: 28,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.3,
        ),
        headlineSmall: GoogleFonts.playfairDisplay(
          color: AppColors.textPrimary,
          fontSize: 24,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.2,
        ),
        titleLarge: GoogleFonts.playfairDisplay(
          color: AppColors.textPrimary,
          fontSize: 22,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.1,
        ),
        titleMedium: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 16,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.15,
        ),
        titleSmall: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.1,
        ),
        bodyLarge: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 16,
          fontWeight: FontWeight.w400,
          letterSpacing: 0.15,
          height: 1.5,
        ),
        bodyMedium: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w400,
          letterSpacing: 0.25,
          height: 1.5,
        ),
        bodySmall: const TextStyle(
          color: AppColors.textSecondary,
          fontSize: 12,
          fontWeight: FontWeight.w400,
          letterSpacing: 0.4,
          height: 1.4,
        ),
        labelLarge: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.1,
        ),
        labelMedium: const TextStyle(
          color: AppColors.textSecondary,
          fontSize: 12,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.5,
        ),
        labelSmall: const TextStyle(
          color: AppColors.textTertiary,
          fontSize: 11,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  /// Dark theme (warm dark mode)
  static ThemeData get dark {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,

      // Color scheme
      colorScheme: const ColorScheme.dark(
        primary: AppColors.terracotta,
        onPrimary: AppColors.warmIvory,
        primaryContainer: AppColors.chocolateLight,
        onPrimaryContainer: AppColors.warmIvory,
        secondary: AppColors.hazelnutLight,
        onSecondary: AppColors.warmIvory,
        secondaryContainer: AppColors.hazelnut,
        onSecondaryContainer: AppColors.warmIvory,
        tertiary: AppColors.terracotta,
        onTertiary: AppColors.chocolate,
        surface: AppColors.chocolate,
        onSurface: AppColors.warmIvory,
        surfaceContainerHighest: AppColors.chocolateLight,
        error: AppColors.coral,
        onError: AppColors.chocolate,
        outline: AppColors.hazelnut,
        outlineVariant: AppColors.hazelnutDark,
        shadow: Color(0x40000000),
      ),

      // Scaffold
      scaffoldBackgroundColor: AppColors.chocolate,

      // AppBar
      appBarTheme: const AppBarTheme(
        centerTitle: true,
        elevation: 0,
        scrolledUnderElevation: 1,
        backgroundColor: AppColors.chocolate,
        foregroundColor: AppColors.warmIvory,
        surfaceTintColor: Colors.transparent,
        systemOverlayStyle: SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.light,
          statusBarBrightness: Brightness.dark,
        ),
        titleTextStyle: TextStyle(
          fontFamily: 'System',
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: AppColors.warmIvory,
          letterSpacing: -0.3,
        ),
        iconTheme: IconThemeData(
          color: AppColors.warmIvory,
          size: 24,
        ),
      ),

      // Cards
      cardTheme: CardThemeData(
        elevation: 0,
        color: AppColors.chocolateLight,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(
            color: AppColors.hazelnut,
            width: 1,
          ),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),

      // Elevated Button (Primary)
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ButtonStyle(
          elevation: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.pressed)) return 0;
            if (states.contains(WidgetState.hovered)) return 2;
            return 1;
          }),
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return AppColors.hazelnutDark;
            }
            if (states.contains(WidgetState.pressed)) {
              return AppColors.hazelnut;
            }
            return AppColors.terracotta;
          }),
          foregroundColor: WidgetStateProperty.all(AppColors.chocolate),
          overlayColor: WidgetStateProperty.all(
            AppColors.withOpacity(AppColors.chocolate, 0.1),
          ),
          shadowColor: WidgetStateProperty.all(const Color(0x40000000)),
          surfaceTintColor: WidgetStateProperty.all(Colors.transparent),
          padding: WidgetStateProperty.all(
            const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          ),
          minimumSize: WidgetStateProperty.all(const Size(88, 48)),
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          textStyle: WidgetStateProperty.all(
            const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.2,
            ),
          ),
          animationDuration: const Duration(milliseconds: 200),
        ),
      ),

      // Outlined Button (Secondary)
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.pressed)) {
              return AppColors.withOpacity(AppColors.hazelnutLight, 0.15);
            }
            if (states.contains(WidgetState.hovered)) {
              return AppColors.withOpacity(AppColors.hazelnutLight, 0.08);
            }
            return Colors.transparent;
          }),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return AppColors.hazelnutDark;
            }
            return AppColors.hazelnutLight;
          }),
          overlayColor: WidgetStateProperty.all(
            AppColors.withOpacity(AppColors.hazelnutLight, 0.1),
          ),
          side: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return const BorderSide(color: AppColors.hazelnutDark, width: 1.5);
            }
            return const BorderSide(color: AppColors.hazelnutLight, width: 1.5);
          }),
          padding: WidgetStateProperty.all(
            const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          ),
          minimumSize: WidgetStateProperty.all(const Size(88, 48)),
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          textStyle: WidgetStateProperty.all(
            const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.2,
            ),
          ),
          animationDuration: const Duration(milliseconds: 200),
        ),
      ),

      // Text Button (Tertiary)
      textButtonTheme: TextButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.pressed)) {
              return AppColors.withOpacity(AppColors.terracotta, 0.12);
            }
            return Colors.transparent;
          }),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return AppColors.hazelnutDark;
            }
            return AppColors.terracotta;
          }),
          overlayColor: WidgetStateProperty.all(
            AppColors.withOpacity(AppColors.terracotta, 0.08),
          ),
          padding: WidgetStateProperty.all(
            const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          ),
          minimumSize: WidgetStateProperty.all(const Size(64, 44)),
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
          ),
          textStyle: WidgetStateProperty.all(
            const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.1,
            ),
          ),
          animationDuration: const Duration(milliseconds: 200),
        ),
      ),

      // Floating Action Button
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: AppColors.terracotta,
        foregroundColor: AppColors.chocolate,
        elevation: 3,
        focusElevation: 4,
        hoverElevation: 4,
        highlightElevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(16)),
        ),
      ),

      // Icon Button
      iconButtonTheme: IconButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.pressed)) {
              return AppColors.withOpacity(AppColors.warmIvory, 0.12);
            }
            return Colors.transparent;
          }),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) {
              return AppColors.hazelnutDark;
            }
            return AppColors.warmIvory;
          }),
          overlayColor: WidgetStateProperty.all(
            AppColors.withOpacity(AppColors.warmIvory, 0.1),
          ),
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          animationDuration: const Duration(milliseconds: 150),
        ),
      ),

      // Input Decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.chocolateLight,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.hazelnut, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.hazelnut, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.terracotta, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.coral, width: 1),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.coral, width: 2),
        ),
        disabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.hazelnutDark, width: 1),
        ),
        hintStyle: const TextStyle(
          color: AppColors.hazelnutLight,
          fontSize: 16,
          fontWeight: FontWeight.w400,
        ),
        labelStyle: const TextStyle(
          color: AppColors.hazelnutLight,
          fontSize: 16,
          fontWeight: FontWeight.w500,
        ),
        floatingLabelStyle: const TextStyle(
          color: AppColors.terracotta,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        errorStyle: const TextStyle(
          color: AppColors.coral,
          fontSize: 12,
          fontWeight: FontWeight.w400,
        ),
        prefixIconColor: AppColors.hazelnutLight,
        suffixIconColor: AppColors.hazelnutLight,
      ),

      // Chip
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.chocolateLight,
        selectedColor: AppColors.terracotta,
        disabledColor: AppColors.hazelnutDark,
        labelStyle: const TextStyle(
          color: AppColors.warmIvory,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        secondaryLabelStyle: const TextStyle(
          color: AppColors.chocolate,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        side: BorderSide.none,
      ),

      // List Tile
      listTileTheme: const ListTileThemeData(
        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        titleTextStyle: TextStyle(
          color: AppColors.warmIvory,
          fontSize: 16,
          fontWeight: FontWeight.w500,
        ),
        subtitleTextStyle: TextStyle(
          color: AppColors.hazelnutLight,
          fontSize: 14,
          fontWeight: FontWeight.w400,
        ),
        leadingAndTrailingTextStyle: TextStyle(
          color: AppColors.hazelnutLight,
          fontSize: 14,
        ),
        iconColor: AppColors.terracotta,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
        ),
      ),

      // Divider
      dividerTheme: const DividerThemeData(
        color: AppColors.hazelnut,
        thickness: 1,
        space: 1,
      ),

      // Dialog
      dialogTheme: DialogThemeData(
        backgroundColor: AppColors.chocolateLight,
        surfaceTintColor: Colors.transparent,
        elevation: 8,
        shadowColor: const Color(0x40000000),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        titleTextStyle: const TextStyle(
          color: AppColors.warmIvory,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.3,
        ),
        contentTextStyle: const TextStyle(
          color: AppColors.warmIvory,
          fontSize: 16,
          fontWeight: FontWeight.w400,
          height: 1.5,
        ),
      ),

      // Bottom Sheet
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.chocolateLight,
        surfaceTintColor: Colors.transparent,
        elevation: 8,
        shadowColor: Color(0x40000000),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        dragHandleColor: AppColors.hazelnut,
        dragHandleSize: Size(40, 4),
        showDragHandle: true,
      ),

      // Snackbar
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.warmIvory,
        contentTextStyle: const TextStyle(
          color: AppColors.chocolate,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        actionTextColor: AppColors.terracotta,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        elevation: 4,
      ),

      // Progress Indicator
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.terracotta,
        linearTrackColor: AppColors.chocolateLight,
        circularTrackColor: AppColors.chocolateLight,
      ),

      // Switch
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.terracotta;
          }
          return AppColors.hazelnut;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.withOpacity(AppColors.terracotta, 0.5);
          }
          return AppColors.hazelnutDark;
        }),
        trackOutlineColor: WidgetStateProperty.all(Colors.transparent),
      ),

      // Checkbox
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.terracotta;
          }
          return Colors.transparent;
        }),
        checkColor: WidgetStateProperty.all(AppColors.chocolate),
        side: const BorderSide(color: AppColors.hazelnut, width: 2),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
        ),
      ),

      // Radio
      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.terracotta;
          }
          return AppColors.hazelnut;
        }),
      ),

      // Navigation Bar (Bottom)
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.chocolateDark,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        indicatorColor: AppColors.withOpacity(AppColors.terracotta, 0.15),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(
              color: AppColors.terracotta,
              size: 24,
            );
          }
          return const IconThemeData(
            color: AppColors.hazelnutLight,
            size: 24,
          );
        }),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              color: AppColors.terracotta,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            );
          }
          return const TextStyle(
            color: AppColors.hazelnutLight,
            fontSize: 12,
            fontWeight: FontWeight.w500,
          );
        }),
      ),

      // Tab Bar
      tabBarTheme: TabBarThemeData(
        labelColor: AppColors.terracotta,
        unselectedLabelColor: AppColors.hazelnutLight,
        indicatorColor: AppColors.terracotta,
        indicatorSize: TabBarIndicatorSize.label,
        dividerColor: AppColors.hazelnut,
        labelStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
      ),

      // Extensions
      extensions: const <ThemeExtension>[
        PalatefulColors.dark,
      ],

      // Text Theme - Playfair Display for display/headline/title, system sans-serif for body/label
      textTheme: TextTheme(
        displayLarge: GoogleFonts.playfairDisplay(
          color: AppColors.warmIvory,
          fontSize: 36,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.25,
        ),
        displayMedium: GoogleFonts.playfairDisplay(
          color: AppColors.warmIvory,
          fontSize: 28,
          fontWeight: FontWeight.w700,
        ),
        displaySmall: GoogleFonts.playfairDisplay(
          color: AppColors.warmIvory,
          fontSize: 24,
          fontWeight: FontWeight.w600,
        ),
        headlineLarge: GoogleFonts.playfairDisplay(
          color: AppColors.warmIvory,
          fontSize: 32,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
        ),
        headlineMedium: GoogleFonts.playfairDisplay(
          color: AppColors.warmIvory,
          fontSize: 28,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.3,
        ),
        headlineSmall: GoogleFonts.playfairDisplay(
          color: AppColors.warmIvory,
          fontSize: 24,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.2,
        ),
        titleLarge: GoogleFonts.playfairDisplay(
          color: AppColors.warmIvory,
          fontSize: 22,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.1,
        ),
        titleMedium: const TextStyle(
          color: AppColors.warmIvory,
          fontSize: 16,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.15,
        ),
        titleSmall: const TextStyle(
          color: AppColors.warmIvory,
          fontSize: 14,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.1,
        ),
        bodyLarge: const TextStyle(
          color: AppColors.warmIvory,
          fontSize: 16,
          fontWeight: FontWeight.w400,
          letterSpacing: 0.15,
          height: 1.5,
        ),
        bodyMedium: const TextStyle(
          color: AppColors.warmIvory,
          fontSize: 14,
          fontWeight: FontWeight.w400,
          letterSpacing: 0.25,
          height: 1.5,
        ),
        bodySmall: const TextStyle(
          color: AppColors.hazelnutLighter,
          fontSize: 12,
          fontWeight: FontWeight.w400,
          letterSpacing: 0.4,
          height: 1.4,
        ),
        labelLarge: const TextStyle(
          color: AppColors.warmIvory,
          fontSize: 14,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.1,
        ),
        labelMedium: const TextStyle(
          color: AppColors.hazelnutLighter,
          fontSize: 12,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.5,
        ),
        labelSmall: const TextStyle(
          color: AppColors.hazelnutLighter,
          fontSize: 11,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}
