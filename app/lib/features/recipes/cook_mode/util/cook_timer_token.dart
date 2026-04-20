/// cmt-4 — single-source helper for resolving the cook-mode timer
/// accent colour across the CookModeTheme extension and its
/// `colorScheme.tertiary` fallback.
///
/// The CookModeTheme extension is registered by the cook-mode-polish
/// epic; this epic runs in parallel, so we fall back gracefully if the
/// extension hasn't been wired up yet. Every timer-surface widget
/// (`step_timers_row`, `manual_timer_sheet`) calls this helper so
/// accents stay consistent.

library;

import 'package:flutter/material.dart';
import '../../../../core/theme/cook_mode_theme.dart';

Color resolveCookTimer(BuildContext context) {
  final ext = Theme.of(context).extension<CookModeTheme>();
  if (ext != null) return ext.cookTimer;
  return Theme.of(context).colorScheme.tertiary;
}
