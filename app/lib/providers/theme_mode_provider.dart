import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kThemeModeKey = 'theme_mode';
const _kFontStyleKey = 'font_style';

/// Font style options for the app.
enum FontStyle {
  classic, // Libre Baskerville (headings) + Inter (body)
  modern,  // Sora (all text)
}

/// Saved preferences loaded before app starts to avoid visual flash.
class SavedAppearance {
  final ThemeMode themeMode;
  final FontStyle fontStyle;
  const SavedAppearance({required this.themeMode, required this.fontStyle});
}

/// Load saved appearance preferences before app starts.
Future<SavedAppearance> loadSavedAppearance() async {
  final prefs = await SharedPreferences.getInstance();

  final themeModeValue = prefs.getString(_kThemeModeKey);
  final themeMode = themeModeValue != null
      ? ThemeMode.values.firstWhere(
          (m) => m.name == themeModeValue,
          orElse: () => ThemeMode.system,
        )
      : ThemeMode.system;

  final fontStyleValue = prefs.getString(_kFontStyleKey);
  final fontStyle = fontStyleValue != null
      ? FontStyle.values.firstWhere(
          (f) => f.name == fontStyleValue,
          orElse: () => FontStyle.classic,
        )
      : FontStyle.classic;

  return SavedAppearance(themeMode: themeMode, fontStyle: fontStyle);
}

// ---------------------------------------------------------------------------
// Theme Mode Provider
// ---------------------------------------------------------------------------

class ThemeModeNotifier extends Notifier<ThemeMode> {
  final ThemeMode _initial;
  ThemeModeNotifier(this._initial);

  @override
  ThemeMode build() => _initial;

  Future<void> setThemeMode(ThemeMode mode) async {
    state = mode;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kThemeModeKey, mode.name);
  }
}

final themeModeProvider =
    NotifierProvider<ThemeModeNotifier, ThemeMode>(
  () => throw UnimplementedError('Must be overridden with initial value'),
);

// ---------------------------------------------------------------------------
// Font Style Provider
// ---------------------------------------------------------------------------

class FontStyleNotifier extends Notifier<FontStyle> {
  final FontStyle _initial;
  FontStyleNotifier(this._initial);

  @override
  FontStyle build() => _initial;

  Future<void> setFontStyle(FontStyle style) async {
    state = style;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kFontStyleKey, style.name);
  }
}

final fontStyleProvider =
    NotifierProvider<FontStyleNotifier, FontStyle>(
  () => throw UnimplementedError('Must be overridden with initial value'),
);
