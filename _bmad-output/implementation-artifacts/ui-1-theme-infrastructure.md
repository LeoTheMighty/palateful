# Story UI.1: Theme Infrastructure — Dark/Light Mode Toggle & ThemeExtension

Status: complete

## Story

As a user,
I want to control my app's appearance (System / Light / Dark) from my profile,
so that the app respects my preference and looks correct in both modes.

## Acceptance Criteria

1. Profile screen has "Appearance" section with System (default) / Light / Dark options
2. Selecting a theme mode immediately applies it app-wide
3. Theme preference persists across app restarts via SharedPreferences
4. Default is System mode (follows device setting)
5. `ThemeExtension<PalatefulColors>` is available via `context.appColors` with semantic color slots
6. Both light and dark `ThemeData` include the PalatefulColors extension

## Tasks / Subtasks

- [x] Task 1: Create ThemeModeProvider (AC: #1, #2, #3, #4)
  - [x] Create `app/lib/providers/theme_mode_provider.dart`
  - [x] Implement `StateNotifierProvider<ThemeModeNotifier, ThemeMode>` with Riverpod
  - [x] Default to `ThemeMode.system`
  - [x] Persist to SharedPreferences key `theme_mode` on change
  - [x] Load saved preference on initialization

- [x] Task 2: Create PalatefulColors ThemeExtension (AC: #5, #6)
  - [x] Create `app/lib/core/theme/palateful_colors_extension.dart`
  - [x] Define semantic color slots:
    - Text: `textPrimary`, `textSecondary`, `textTertiary`, `textDisabled`
    - Backgrounds: `cardBackground`, `inputBackground`, `navBackground`
    - Semantic: `success`/`successLight`, `warning`/`warningLight`, `error`/`errorLight`, `info`/`infoLight`
    - Urgency: `urgentBg`, `urgentText`
    - Diff: `addedBg`, `removedBg`, `changedBg`
  - [x] Implement `copyWith()` and `lerp()` methods
  - [x] Create `BuildContext` extension: `context.appColors` getter

- [x] Task 3: Wire into MaterialApp (AC: #2)
  - [x] Modify `app/lib/main.dart` — make `PalatefulApp` a `ConsumerWidget` if not already
  - [x] Replace `themeMode: ThemeMode.system` with `themeMode: ref.watch(themeModeProvider)`

- [x] Task 4: Add ThemeExtension to AppTheme (AC: #6)
  - [x] Modify `app/lib/core/theme/app_theme.dart`
  - [x] Create light `PalatefulColors` instance with light-mode colors
  - [x] Create dark `PalatefulColors` instance with dark-mode colors
  - [x] Add to `ThemeData.extensions` in both `light` and `dark` getters

- [x] Task 5: Add Appearance Toggle to Profile (AC: #1)
  - [x] Modify `app/lib/features/profile/profile_screen.dart`
  - [x] Add "Appearance" section with segmented control or radio tiles
  - [x] Options: System / Light / Dark with icons
  - [x] Wire to `themeModeProvider`

## Dev Notes

- Riverpod is already available in the project — follow existing provider patterns
- SharedPreferences is already a dependency
- `PalatefulApp` likely already wraps with `ProviderScope` — verify in main.dart
- The ThemeExtension is foundational — Stories 2, 3, 4 depend on it
- Reference existing provider patterns in `app/lib/providers/`

### References

- [Investigation: 03-dark-light-mode-consistency.md]
- [Flutter ThemeExtension docs](https://api.flutter.dev/flutter/material/ThemeExtension-class.html)
